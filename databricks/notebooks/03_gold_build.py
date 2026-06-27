# Databricks notebook source
# MAGIC %md
# MAGIC # Gold — dimensional model (Unity Catalog)
# MAGIC Star schema + aggregates built only from trusted silver. Writes
# MAGIC `{catalog}.gold.*`. These tables are what `data-analysts` are granted
# MAGIC SELECT on (see `00_setup_unity_catalog.sql`).

# COMMAND ----------
dbutils.widgets.text("catalog", "brewquality_dev")
catalog = dbutils.widgets.get("catalog")

from pyspark.sql import functions as F

orders = spark.read.table(f"{catalog}.silver.orders")
customers = spark.read.table(f"{catalog}.silver.customers")
products = spark.read.table(f"{catalog}.silver.products")

# COMMAND ----------
dim_customer = customers.select("customer_id", "name", "company", "country")
dim_product = products.select("product_id", "product_name", "category", "unit_price")
dim_date = (
    orders.select("order_date").distinct().where(F.col("order_date").isNotNull()).select(
        F.date_format("order_date", "yyyyMMdd").cast("int").alias("date_key"),
        F.col("order_date").alias("date"),
        F.year("order_date").alias("year"),
        F.month("order_date").alias("month"),
    )
)
fact_sales = orders.select(
    "order_id", "customer_id", "product_id",
    F.date_format("order_date", "yyyyMMdd").cast("int").alias("date_key"),
    "quantity", "unit_price", "order_amount",
)

# COMMAND ----------
for name, df in {
    "dim_customer": dim_customer, "dim_product": dim_product,
    "dim_date": dim_date, "fact_sales": fact_sales,
}.items():
    df.write.format("delta").mode("overwrite").saveAsTable(f"{catalog}.gold.{name}")

print("gold build complete")
