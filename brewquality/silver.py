"""Silver layer: cleaned, conformed, validated, deduplicated.

This is where the DQ gate lives (bronze -> silver). Orders are typed, checked
against the rule set, deduplicated, and split: clean rows build
``silver.orders``; rows that fail a hard rule land in ``quarantine.orders`` with
the reason and rule name. Customers are conformed (country standardised) so the
consistency dimension is fixed at the source of truth.
"""

from __future__ import annotations

import uuid

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from brewquality import config
from brewquality.dq import engine
from brewquality.dq.prepare import prepare_orders
from brewquality.dq.rules import ORDER_RULES

# Map the inconsistent country spellings back to ISO-2 (consistency dimension).
COUNTRY_STANDARDISATION = {
    "poland": "PL", "pl": "PL", "pol": "PL",
    "netherlands": "NL", "nl": "NL",
    "germany": "DE", "de": "DE",
}


def conform_customers(customers: DataFrame) -> DataFrame:
    """Standardise the country code so the same customer/country is consistent."""
    mapping = F.create_map([F.lit(x) for kv in COUNTRY_STANDARDISATION.items() for x in kv])
    lowered = F.lower(F.trim(F.col("country")))
    return customers.select(
        "customer_id",
        "name",
        "company",
        F.coalesce(mapping[lowered], F.upper(F.col("country"))).alias("country"),
    )


def _silver_order_columns(df: DataFrame) -> DataFrame:
    """Project the clean, typed business columns for the silver fact table."""
    return df.select(
        "order_id",
        "customer_id",
        "product_id",
        F.col("quantity_int").alias("quantity"),
        F.col("unit_price_dbl").alias("unit_price"),
        F.col("order_amount_dbl").alias("order_amount"),
        F.col("order_date_parsed").alias("order_date"),
        F.col("_dq_warnings").alias("dq_warnings"),  # soft-rule flags ride along
    )


def build(spark: SparkSession, run_id: str | None = None) -> dict[str, int]:
    """Run the bronze -> silver DQ gate. Returns a small summary for logging/tests."""
    run_id = run_id or uuid.uuid4().hex

    orders = spark.read.format("delta").load(config.BRONZE.path(config.RAW_ORDERS))
    products = spark.read.format("delta").load(config.BRONZE.path(config.RAW_PRODUCTS))
    customers = spark.read.format("delta").load(config.BRONZE.path(config.RAW_CUSTOMERS))

    silver_customers = conform_customers(customers)
    silver_customers.write.format("delta").mode("overwrite").save(
        config.SILVER.path(config.RAW_CUSTOMERS)
    )
    products.select("product_id", "product_name", "category", "unit_price").write.format(
        "delta"
    ).mode("overwrite").save(config.SILVER.path(config.RAW_PRODUCTS))

    # --- the DQ gate on orders ---
    prepared = prepare_orders(orders, products, silver_customers)
    evaluated = engine.evaluate(prepared, ORDER_RULES)
    evaluated.cache()  # reused by split + metrics

    clean, quarantine = engine.split(evaluated)

    _silver_order_columns(clean).write.format("delta").mode("overwrite").save(
        config.SILVER.path(config.RAW_ORDERS)
    )

    quarantine.select(
        "order_id", "customer_id", "product_id", "quantity", "unit_price",
        "order_amount", "order_date", "_source_file", "_ingested_at",
        F.col("_dq_failed_rules").alias("failed_rules"),
        F.col("_dq_reason").alias("reason"),
        F.lit(run_id).alias("run_id"),
    ).write.format("delta").mode("append").save(config.QUARANTINE.path(config.RAW_ORDERS))

    metrics = engine.compute_metrics(
        evaluated, ORDER_RULES, run_id=run_id, dataset="orders"
    )
    metrics.write.format("delta").mode("append").save(config.OPS.path(config.DQ_METRICS_TABLE))

    summary = {
        "run_id_len": len(run_id),
        "clean": clean.count(),
        "quarantined": quarantine.count(),
    }
    evaluated.unpersist()
    return summary
