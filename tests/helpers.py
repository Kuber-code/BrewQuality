"""Test helper: build a Spark DataFrame via the Arrow (pandas) path.

We go through pandas so the JVM does the conversion (Arrow). This keeps tests
working on every platform — including Windows + Python 3.12, where the plain
``createDataFrame([...])`` Python-worker path can crash. Inputs are dicts, so
column order and (string) types match the bronze shape exactly.
"""

from __future__ import annotations

import pandas as pd
from pyspark.sql import DataFrame, SparkSession


def make_df(spark: SparkSession, rows: list[dict]) -> DataFrame:
    return spark.createDataFrame(pd.DataFrame(rows))
