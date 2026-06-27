"""DQ KPI report: the observability view over ops.dq_metrics + quarantine.

Locally this prints the same numbers a Databricks SQL / Grafana dashboard would
show: per-rule pass-rate trend, the rules failing most, and a breakdown of *why*
rows were quarantined. ``--alert`` exits non-zero if any hard-rule pass rate is
below its SLA — the hook an alerting job (email/Teams) would call.

    python -m brewquality.dq_report
    python -m brewquality.dq_report --alert --sla 0.8
"""

from __future__ import annotations

import argparse
import sys

from pyspark.sql import functions as F
from pyspark.sql.window import Window

from brewquality import config
from brewquality.session import get_spark


def _print_pass_rate_trend(metrics) -> None:
    print("\n# Pass-rate trend (per rule, per run, newest first)")
    w = Window.partitionBy("rule_name").orderBy(F.col("measured_at").desc())
    ranked = metrics.withColumn("_rk", F.row_number().over(w)).filter("_rk <= 3")
    for r in ranked.orderBy("rule_name", F.col("measured_at").desc()).collect():
        flag = "" if r["severity"] == "warn" else ("  <-- LOW" if r["pass_rate"] < 0.8 else "")
        print(
            f"  {r['rule_name']:<28} {r['dimension']:<13} "
            f"{r['severity']:<5} pass_rate={r['pass_rate']:.3f}  "
            f"(failed {r['rows_failed']}/{r['rows_evaluated']}){flag}"
        )


def _print_top_failing(metrics) -> None:
    print("\n# Top rules by failed rows (latest run)")
    latest_run = metrics.orderBy(F.col("measured_at").desc()).first()["run_id"]
    top = (
        metrics.filter(F.col("run_id") == latest_run)
        .orderBy(F.col("rows_failed").desc())
        .limit(5)
    )
    for r in top.collect():
        print(f"  {r['rule_name']:<28} failed={r['rows_failed']}  ({r['dimension']})")


def _print_quarantine_reasons(spark) -> None:
    print("\n# Quarantine breakdown (by failed rule)")
    q = spark.read.format("delta").load(config.QUARANTINE.path(config.RAW_ORDERS))
    exploded = q.select(F.explode("failed_rules").alias("rule"))
    for r in exploded.groupBy("rule").count().orderBy(F.col("count").desc()).collect():
        print(f"  {r['rule']:<28} {r['count']}")


def _check_alerts(metrics, sla: float) -> list[str]:
    """Return alert messages for any hard rule whose latest pass rate < SLA."""
    w = Window.partitionBy("rule_name").orderBy(F.col("measured_at").desc())
    latest = metrics.withColumn("_rk", F.row_number().over(w)).filter("_rk = 1")
    breaches = latest.filter((F.col("severity") == "error") & (F.col("pass_rate") < sla))
    return [
        f"SLA BREACH: {r['rule_name']} pass_rate={r['pass_rate']:.3f} < {sla} ({r['dimension']})"
        for r in breaches.collect()
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="DQ KPI report / alerting.")
    parser.add_argument("--alert", action="store_true", help="exit non-zero on SLA breach")
    parser.add_argument("--sla", type=float, default=0.8, help="hard-rule pass-rate SLA")
    args = parser.parse_args()

    spark = get_spark("brewquality-dq-report")
    metrics = spark.read.format("delta").load(config.OPS.path(config.DQ_METRICS_TABLE))

    _print_pass_rate_trend(metrics)
    _print_top_failing(metrics)
    _print_quarantine_reasons(spark)

    alerts = _check_alerts(metrics, args.sla)
    if alerts:
        print("\n# ALERTS")
        for a in alerts:
            print(f"  {a}")

    spark.stop()
    if args.alert and alerts:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
