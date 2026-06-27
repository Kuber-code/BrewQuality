"""Compute the derived columns the order rules evaluate against.

Some DQ checks aren't row-local:
  * uniqueness needs to know if an order_id repeats  -> window count
  * referential integrity needs the dimensions       -> left joins

We compute these once, as plain boolean/typed columns, so every rule in
``rules.py`` stays a trivial expression. Type casts use Spark's safe cast: an
unparseable value becomes NULL (which the rules treat as a failure).
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window


def prepare_orders(
    orders: DataFrame, products: DataFrame, customers: DataFrame
) -> DataFrame:
    """Add typed + relational columns used by ORDER_RULES."""
    # Safe casts: bad strings -> NULL, surfaced by the validity/completeness rules.
    df = (
        orders.withColumn("quantity_int", F.col("quantity").cast("int"))
        .withColumn("order_amount_dbl", F.col("order_amount").cast("double"))
        .withColumn("unit_price_dbl", F.col("unit_price").cast("double"))
        # to_date returns NULL for "2025-13-40" — exactly what validity_order_date wants.
        .withColumn("order_date_parsed", F.to_date(F.col("order_date"), "yyyy-MM-dd"))
    )

    # uniqueness: keep the first occurrence of each order_id, flag the rest as
    # duplicates. ROW_NUMBER over the key is the classic dedup pattern — here we
    # don't silently drop the extras, we route them to quarantine for audit.
    dup_window = Window.partitionBy("order_id").orderBy(F.col("_ingested_at").asc())
    df = df.withColumn("_dup_rank", F.row_number().over(dup_window))
    df = df.withColumn("_is_duplicate", F.col("_dup_rank") > 1)

    # referential integrity: does the product / customer key exist in its dimension?
    product_keys = products.select("product_id").distinct().withColumn("_product_exists", F.lit(True))
    customer_keys = (
        customers.select("customer_id").distinct().withColumn("_customer_exists", F.lit(True))
    )
    df = (
        df.join(F.broadcast(product_keys), on="product_id", how="left")
        .join(F.broadcast(customer_keys), on="customer_id", how="left")
        .withColumn("_product_exists", F.coalesce(F.col("_product_exists"), F.lit(False)))
        .withColumn("_customer_exists", F.coalesce(F.col("_customer_exists"), F.lit(False)))
    )
    return df
