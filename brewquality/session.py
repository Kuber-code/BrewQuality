"""Spark session factory wired for Delta Lake.

On Databricks the session already exists and Delta is built in, so this is only
used for local development and tests. ``delta-spark``'s ``configure_spark_with_delta_pip``
injects the right Delta JARs and SQL extensions.
"""

from __future__ import annotations

import os
import sys

from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession

# Pin the driver *and* worker to the exact interpreter running this process.
# On Windows the Spark Python worker otherwise picks whatever ``python`` is on
# PATH, and a mismatch makes the worker "exit unexpectedly (crashed)".
os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)


def get_spark(app_name: str = "brewquality", shuffle_partitions: int = 4) -> SparkSession:
    """Return a local Delta-enabled SparkSession.

    ``shuffle_partitions`` is set low (4) because local/test datasets are tiny —
    the Spark default of 200 just creates hundreds of empty partitions and slow
    jobs. On a real cluster you'd leave this to Adaptive Query Execution.
    """
    builder = (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.sql.shuffle.partitions", str(shuffle_partitions))
        # Arrow makes createDataFrame(pandas)/toPandas convert in the JVM. It also
        # sidesteps a Python-worker crash seen on Windows + Python 3.12 for the
        # plain-RDD createDataFrame path; harmless and recommended everywhere.
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        .config("spark.sql.execution.arrow.pyspark.fallback.enabled", "true")
        # Quieter, faster local runs.
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.session.timeZone", "UTC")
    )
    spark = configure_spark_with_delta_pip(builder).getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark
