"""End-to-end local orchestration: raw -> bronze -> (DQ gate) -> silver -> gold.

This is the local stand-in for a Databricks Workflow (Phase 3). Each step is
idempotent enough for a demo: bronze appends, silver/gold overwrite, quarantine
and dq_metrics append (so KPI history accumulates across runs).

    python -m brewquality.pipeline            # run the whole thing
    python -m brewquality.pipeline --reset     # wipe the lake first
"""

from __future__ import annotations

import argparse
import shutil
import uuid

from brewquality import bronze, config, gold, silver
from brewquality.session import get_spark


def reset_lake() -> None:
    if config.LAKE_DIR.exists():
        shutil.rmtree(config.LAKE_DIR)
        print(f"Wiped {config.LAKE_DIR}")


def run(reset: bool = False) -> dict:
    if reset:
        reset_lake()

    spark = get_spark("brewquality-pipeline")
    run_id = uuid.uuid4().hex[:12]
    print(f"== BrewQuality pipeline run {run_id} ==")

    print("-> bronze: ingesting raw sources")
    bronze.run(spark)

    print("-> silver: DQ gate (validate + quarantine + metrics)")
    summary = silver.build(spark, run_id=run_id)
    print(f"   clean={summary['clean']}  quarantined={summary['quarantined']}")

    print("-> gold: dimensional model + aggregates")
    gold.build(spark)

    print("== done ==")
    spark.stop()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the BrewQuality lakehouse pipeline.")
    parser.add_argument("--reset", action="store_true", help="wipe the local lake first")
    args = parser.parse_args()
    run(reset=args.reset)


if __name__ == "__main__":
    main()
