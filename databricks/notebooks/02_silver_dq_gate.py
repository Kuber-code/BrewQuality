# Databricks notebook source
# MAGIC %md
# MAGIC # Silver — the DQ gate (Unity Catalog)
# MAGIC Reuses the **exact same tested DQ core** as local + CI
# MAGIC (`brewquality.dq`), proving the rules are portable. Only the I/O changes:
# MAGIC read/write UC tables instead of `data/lake` paths. Failing rows are
# MAGIC quarantined with reasons; clean rows build silver; metrics land in `ops`.

# COMMAND ----------
dbutils.widgets.text("catalog", "brewquality_dev")
catalog = dbutils.widgets.get("catalog")

import uuid
from pyspark.sql import functions as F

# Installed as a wheel by the Asset Bundle — same code unit-tested in CI.
from brewquality.dq import engine
from brewquality.dq.prepare import prepare_orders
from brewquality.dq.rules import ORDER_RULES
from brewquality.silver import conform_customers, _silver_order_columns

run_id = uuid.uuid4().hex[:12]

# COMMAND ----------
orders = spark.read.table(f"{catalog}.bronze.orders")
products = spark.read.table(f"{catalog}.bronze.products")
customers = spark.read.table(f"{catalog}.bronze.customers")

silver_customers = conform_customers(customers)
silver_customers.write.format("delta").mode("overwrite").saveAsTable(f"{catalog}.silver.customers")
products.select("product_id", "product_name", "category", "unit_price").write.format("delta").mode(
    "overwrite"
).saveAsTable(f"{catalog}.silver.products")

# COMMAND ----------
prepared = prepare_orders(orders, products, silver_customers)
evaluated = engine.evaluate(prepared, ORDER_RULES).cache()
clean, quarantine = engine.split(evaluated)

_silver_order_columns(clean).write.format("delta").mode("overwrite").saveAsTable(f"{catalog}.silver.orders")

quarantine.select(
    "order_id", "customer_id", "product_id",
    F.col("_dq_failed_rules").alias("failed_rules"),
    F.col("_dq_reason").alias("reason"),
    F.lit(run_id).alias("run_id"),
).write.format("delta").mode("append").saveAsTable(f"{catalog}.quarantine.orders")

engine.compute_metrics(evaluated, ORDER_RULES, run_id=run_id, dataset="orders").write.format(
    "delta"
).mode("append").saveAsTable(f"{catalog}.ops.dq_metrics")

# COMMAND ----------
# Fail the task if any HARD rule fell below SLA — turns the gate into a real stop.
SLA = 0.80
breaches = (
    spark.read.table(f"{catalog}.ops.dq_metrics")
    .filter((F.col("run_id") == run_id) & (F.col("severity") == "error") & (F.col("pass_rate") < SLA))
    .collect()
)
if breaches:
    raise Exception(f"DQ SLA breach: {[ (b['rule_name'], b['pass_rate']) for b in breaches ]}")
print(f"silver gate complete: clean={clean.count()} quarantined={quarantine.count()}")
