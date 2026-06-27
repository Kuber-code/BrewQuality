"""Gold layer: dimensional (star schema) model + business aggregates for BI.

Built only from *trusted* silver data, so the numbers can be relied on. We expose
a classic star — ``fact_sales`` referencing ``dim_customer`` / ``dim_product`` /
``dim_date`` — plus a couple of pre-aggregated reporting tables.
"""

from __future__ import annotations

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from brewquality import config


def build(spark: SparkSession) -> None:
    orders = spark.read.format("delta").load(config.SILVER.path(config.RAW_ORDERS))
    customers = spark.read.format("delta").load(config.SILVER.path(config.RAW_CUSTOMERS))
    products = spark.read.format("delta").load(config.SILVER.path(config.RAW_PRODUCTS))

    # --- dimensions ---
    dim_customer = customers.select(
        "customer_id", "name", "company", "country"
    )
    dim_product = products.select("product_id", "product_name", "category", "unit_price")
    dim_date = (
        orders.select("order_date")
        .distinct()
        .where(F.col("order_date").isNotNull())
        .select(
            F.date_format("order_date", "yyyyMMdd").cast("int").alias("date_key"),
            F.col("order_date").alias("date"),
            F.year("order_date").alias("year"),
            F.month("order_date").alias("month"),
            F.dayofmonth("order_date").alias("day"),
        )
    )

    # --- fact ---
    fact_sales = orders.select(
        "order_id",
        "customer_id",
        "product_id",
        F.date_format("order_date", "yyyyMMdd").cast("int").alias("date_key"),
        "quantity",
        "unit_price",
        "order_amount",
    )

    for name, df in {
        "dim_customer": dim_customer,
        "dim_product": dim_product,
        "dim_date": dim_date,
        "fact_sales": fact_sales,
    }.items():
        df.write.format("delta").mode("overwrite").save(config.GOLD.path(name))

    # --- reporting aggregates (the "report" the business actually opens) ---
    revenue_by_country = (
        fact_sales.join(dim_customer, "customer_id")
        .groupBy("country")
        .agg(
            F.round(F.sum("order_amount"), 2).alias("revenue"),
            F.countDistinct("order_id").alias("orders"),
        )
        .orderBy(F.desc("revenue"))
    )
    revenue_by_category = (
        fact_sales.join(dim_product, "product_id")
        .groupBy("category")
        .agg(
            F.round(F.sum("order_amount"), 2).alias("revenue"),
            F.sum("quantity").alias("units"),
        )
        .orderBy(F.desc("revenue"))
    )
    revenue_by_country.write.format("delta").mode("overwrite").save(
        config.GOLD.path("revenue_by_country")
    )
    revenue_by_category.write.format("delta").mode("overwrite").save(
        config.GOLD.path("revenue_by_category")
    )
