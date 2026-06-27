"""Shared pytest fixtures — a single local SparkSession for the whole test run."""

from __future__ import annotations

import pytest

from brewquality.session import get_spark


@pytest.fixture(scope="session")
def spark():
    spark = get_spark("brewquality-tests", shuffle_partitions=2)
    yield spark
    spark.stop()
