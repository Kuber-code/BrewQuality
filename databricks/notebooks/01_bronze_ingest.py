# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze ingest (Unity Catalog)
# MAGIC Raw, append-only landing. On Databricks the sources live in a UC **volume**
# MAGIC (or ADLS Gen2 external location); we write to `{catalog}.bronze.*` tables.
# MAGIC Same intent as `brewquality.bronze`, just UC table I/O instead of paths.

# COMMAND ----------
dbutils.widgets.text("catalog", "brewquality_dev")
catalog = dbutils.widgets.get("catalog")

from pyspark.sql import functions as F

VOLUME = f"/Volumes/{catalog}/bronze/landing"  # raw drop zone (UC volume)

# COMMAND ----------
def with_audit(df, source):
    return df.withColumn("_ingested_at", F.current_timestamp()).withColumn("_source_file", F.lit(source))

orders = with_audit(spark.read.option("header", True).csv(f"{VOLUME}/orders.csv"), "orders.csv")
customers = with_audit(spark.read.option("header", True).csv(f"{VOLUME}/customers.csv"), "customers.csv")
products = with_audit(spark.read.option("multiLine", True).json(f"{VOLUME}/products.json"), "products.json")

# COMMAND ----------
# Idempotent re-ingest of the current landing snapshot: overwrite, so re-running
# the job doesn't stack duplicate copies of every order (which would make the
# uniqueness rule fail en masse). In production bronze is append-only with a
# MERGE on a load key; for a repeatable demo, overwrite the snapshot.
orders.write.format("delta").mode("overwrite").option("overwriteSchema", True).saveAsTable(f"{catalog}.bronze.orders")
customers.write.format("delta").mode("overwrite").option("overwriteSchema", True).saveAsTable(f"{catalog}.bronze.customers")
products.write.format("delta").mode("overwrite").option("overwriteSchema", True).saveAsTable(f"{catalog}.bronze.products")

print("bronze ingest complete")
