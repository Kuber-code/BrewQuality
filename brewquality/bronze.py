"""Bronze layer: raw ingest, append-only, full fidelity.

Bronze is the immutable landing zone. We read the source files *as text where it
matters* (no eager casting) so that even malformed rows survive — bronze must be
a faithful, replayable copy of what arrived. Validation happens later, at the
bronze -> silver gate. We only add lineage/audit columns here.
"""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from brewquality import config


def _with_audit(df: DataFrame, source: str) -> DataFrame:
    """Add ingestion metadata so every bronze row is traceable to its load."""
    return df.withColumn("_ingested_at", F.current_timestamp()).withColumn(
        "_source_file", F.lit(source)
    )


def ingest_orders(spark: SparkSession) -> DataFrame:
    # everything read as string: bronze keeps raw values, even "2025-13-40".
    df = (
        spark.read.option("header", "true")
        .option("mode", "PERMISSIVE")
        .csv(str(config.RAW_DIR / "orders.csv"))
    )
    return _with_audit(df, "orders.csv")


def ingest_customers(spark: SparkSession) -> DataFrame:
    df = spark.read.option("header", "true").csv(str(config.RAW_DIR / "customers.csv"))
    return _with_audit(df, "customers.csv")


def ingest_products(spark: SparkSession) -> DataFrame:
    df = spark.read.option("multiLine", "true").json(str(config.RAW_DIR / "products.json"))
    return _with_audit(df, "products.json")


def write_bronze(df: DataFrame, table: str) -> None:
    """Append into the bronze Delta table (bronze is append-only by design)."""
    (
        df.write.format("delta")
        .mode("append")
        .option("mergeSchema", "true")
        .save(config.BRONZE.path(table))
    )


def run(spark: SparkSession) -> None:
    """Ingest all three sources into bronze Delta tables."""
    write_bronze(ingest_orders(spark), config.RAW_ORDERS)
    write_bronze(ingest_customers(spark), config.RAW_CUSTOMERS)
    write_bronze(ingest_products(spark), config.RAW_PRODUCTS)
