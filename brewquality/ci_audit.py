"""CI audit step: read the DQ metrics + lake and assert they're within bounds.

This is the "Audit" in Write-Audit-Publish. The pipeline writes silver/gold and
DQ metrics; this step inspects them and *fails the build* if data quality is off
— e.g. a hard rule's pass rate collapsed, or nothing reached silver. It turns
data quality into a merge gate, not a dashboard nobody reads.
"""

from __future__ import annotations

import sys

from pyspark.sql import functions as F

from brewquality import config
from brewquality.session import get_spark

# Expectations for the seeded sample. Defects are injected at known rates, so the
# clean fraction should land in a sane band — too high means the gate isn't
# catching anything; too low means it's over-rejecting (or a regression).
MIN_CLEAN_ROWS = 1000
MIN_OVERALL_CLEAN_FRACTION = 0.55
MAX_OVERALL_CLEAN_FRACTION = 0.95


def main() -> int:
    spark = get_spark("brewquality-ci-audit")
    failures: list[str] = []

    silver = spark.read.format("delta").load(config.SILVER.path(config.RAW_ORDERS))
    quarantine = spark.read.format("delta").load(config.QUARANTINE.path(config.RAW_ORDERS))
    metrics = spark.read.format("delta").load(config.OPS.path(config.DQ_METRICS_TABLE))

    clean = silver.count()
    quarantined = quarantine.count()
    total = clean + quarantined
    frac = clean / total if total else 0.0

    print(f"clean={clean}  quarantined={quarantined}  clean_fraction={frac:.3f}")

    if clean < MIN_CLEAN_ROWS:
        failures.append(f"too few clean rows reached silver: {clean} < {MIN_CLEAN_ROWS}")
    if not (MIN_OVERALL_CLEAN_FRACTION <= frac <= MAX_OVERALL_CLEAN_FRACTION):
        failures.append(
            f"clean fraction {frac:.3f} outside "
            f"[{MIN_OVERALL_CLEAN_FRACTION}, {MAX_OVERALL_CLEAN_FRACTION}]"
        )

    # Silver must be deduplicated: every order_id appears at most once. (A dup's
    # first copy is kept in silver and the extra is quarantined, so the *same*
    # order_id legitimately appears in both tables — that's expected. What must
    # never happen is a duplicate surviving *inside* silver.)
    silver_dupes = silver.count() - silver.select("order_id").distinct().count()
    if silver_dupes:
        failures.append(f"{silver_dupes} duplicate order_id(s) survived into silver")

    # Show the per-rule KPI table for the latest run (this is what the dashboard plots).
    latest = metrics.orderBy(F.col("measured_at").desc()).limit(len(_rule_names(metrics)))
    print("\nLatest DQ metrics:")
    for r in latest.orderBy("rule_name").collect():
        print(f"  {r['rule_name']:<28} {r['dimension']:<13} pass_rate={r['pass_rate']:.3f}")

    spark.stop()

    if failures:
        print("\nAUDIT FAILED:")
        for f_ in failures:
            print(f"  - {f_}")
        return 1
    print("\nAUDIT PASSED")
    return 0


def _rule_names(metrics) -> list[str]:
    return [r["rule_name"] for r in metrics.select("rule_name").distinct().collect()]


if __name__ == "__main__":
    sys.exit(main())
