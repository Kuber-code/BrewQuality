"""Apply a rule set to a DataFrame: evaluate -> split (clean/quarantine) -> metrics.

This is the reusable DQ gate. It's deliberately tool-agnostic (plain PySpark) so
the same rules unit-test locally and run on Databricks. It mirrors what
Databricks **DQX** / Great Expectations give you out of the box — quarantine of
failing rows with a reason, plus per-rule metrics — but stays in the repo and in
CI. See ADR-0002 for why we hand-rolled this instead of adopting a framework.
"""

from __future__ import annotations

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F

from brewquality.dq.rules import Rule

PASS_PREFIX = "_pass__"


def _fail_array(rules: list[Rule], hard: bool) -> Column:
    """Array of rule names that failed, for the given severity class."""
    parts = [
        F.when(~F.col(PASS_PREFIX + r.name), F.lit(r.name))
        for r in rules
        if r.is_hard == hard
    ]
    if not parts:
        return F.array().cast("array<string>")
    return F.array_compact(F.array(*parts))


def evaluate(df: DataFrame, rules: list[Rule]) -> DataFrame:
    """Add per-rule pass columns + ``_dq_failed_rules`` / ``_dq_warnings`` / ``_dq_passed``.

    A null rule expression (e.g. a comparison against an unparseable value) counts
    as a **failure**, never a silent pass — that's the whole reason the row is bad.
    """
    pass_cols = {PASS_PREFIX + r.name: F.coalesce(r.passes(), F.lit(False)) for r in rules}
    df = df.withColumns(pass_cols)
    df = df.withColumn("_dq_failed_rules", _fail_array(rules, hard=True))
    df = df.withColumn("_dq_warnings", _fail_array(rules, hard=False))
    df = df.withColumn("_dq_passed", F.size("_dq_failed_rules") == 0)
    return df


def split(evaluated: DataFrame) -> tuple[DataFrame, DataFrame]:
    """Return (clean, quarantine). Quarantine rows carry a human-readable reason."""
    clean = evaluated.filter(F.col("_dq_passed"))
    quarantine = evaluated.filter(~F.col("_dq_passed")).withColumn(
        "_dq_reason", F.concat_ws("; ", F.col("_dq_failed_rules"))
    )
    return clean, quarantine


def strip_internal_cols(df: DataFrame) -> DataFrame:
    """Drop engine scratch columns so downstream layers stay clean."""
    drop = [c for c in df.columns if c.startswith(PASS_PREFIX)]
    drop += ["_dq_failed_rules", "_dq_warnings", "_dq_passed"]
    return df.drop(*[c for c in drop if c in df.columns])


def compute_metrics(
    evaluated: DataFrame, rules: list[Rule], *, run_id: str, dataset: str
) -> DataFrame:
    """One metric row per rule for this run: rows evaluated/passed/failed + pass_rate.

    These rows are appended to the ``ops.dq_metrics`` Delta table and drive the KPI
    dashboard + alerting (Phase 5). Built entirely with DataFrame ops (one
    aggregation + ``stack`` to go wide->long), so it never round-trips Python
    objects through a Spark worker — fast and portable.
    """
    # Single pass: total rows + passed count per rule, as one wide row.
    wide = evaluated.agg(
        F.count(F.lit(1)).alias("_total"),
        *[F.sum(F.col(PASS_PREFIX + r.name).cast("long")).alias(r.name) for r in rules],
    )

    # Pivot that one wide row into one row per rule: (rule_name, rows_passed).
    pairs = ", ".join(f"'{r.name}', `{r.name}`" for r in rules)
    long = wide.selectExpr(
        "_total", f"stack({len(rules)}, {pairs}) as (rule_name, rows_passed)"
    )

    # Attach each rule's dimension/severity via when-chains (no Python needed).
    def _lookup(attr: str) -> Column:
        col = F.lit(None).cast("string")
        for r in rules:
            col = F.when(F.col("rule_name") == r.name, F.lit(getattr(r, attr))).otherwise(col)
        return col

    return long.select(
        F.lit(run_id).alias("run_id"),
        F.lit(dataset).alias("dataset"),
        F.col("rule_name"),
        _lookup("dimension").alias("dimension"),
        _lookup("severity").alias("severity"),
        F.col("_total").alias("rows_evaluated"),
        F.col("rows_passed"),
        (F.col("_total") - F.col("rows_passed")).alias("rows_failed"),
        F.when(F.col("_total") > 0, F.round(F.col("rows_passed") / F.col("_total"), 6))
        .otherwise(F.lit(1.0))
        .alias("pass_rate"),
        F.current_timestamp().alias("measured_at"),
    )
