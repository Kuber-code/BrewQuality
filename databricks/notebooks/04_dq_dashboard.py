# Databricks notebook source
# MAGIC %md
# MAGIC # BrewQuality — DQ KPI dashboard (notebook)
# MAGIC A code-first dashboard over `ops.dq_metrics` + `quarantine.orders`. Runs on
# MAGIC **serverless** (no SQL warehouse needed). Charts are rendered with matplotlib
# MAGIC so they show up the same for anyone who runs the notebook. Run it after the
# MAGIC pipeline; screenshot for the portfolio.

# COMMAND ----------
dbutils.widgets.text("catalog", "brewquality_dev")
catalog = dbutils.widgets.get("catalog")

import matplotlib.pyplot as plt
from pyspark.sql import functions as F

# COMMAND ----------
# Latest run's per-rule metrics, into a small pandas frame for plotting.
metrics = spark.read.table(f"{catalog}.ops.dq_metrics")
latest_run = metrics.orderBy(F.col("measured_at").desc()).first()["run_id"]
m = (
    metrics.filter(F.col("run_id") == latest_run)
    .orderBy("pass_rate")
    .toPandas()
)
quar = (
    spark.read.table(f"{catalog}.quarantine.orders")
    .select(F.explode("failed_rules").alias("rule"))
    .groupBy("rule").count().orderBy(F.col("count").desc())
    .toPandas()
)
clean_n = spark.read.table(f"{catalog}.silver.orders").count()
quar_n = spark.read.table(f"{catalog}.quarantine.orders").count()

# COMMAND ----------
# MAGIC %md ## Pass rate per rule (hard rules vs the 0.80 SLA)

# COMMAND ----------
fig, ax = plt.subplots(figsize=(9, 4))
colors = ["#c0392b" if s == "error" else "#7f8c8d" for s in m["severity"]]
ax.barh(m["rule_name"], m["pass_rate"], color=colors)
ax.axvline(0.80, color="black", linestyle="--", linewidth=1, label="SLA 0.80")
ax.set_xlim(0, 1.0); ax.set_xlabel("pass rate"); ax.set_title(f"DQ pass rate — run {latest_run}")
for i, v in enumerate(m["pass_rate"]):
    ax.text(v + 0.005, i, f"{v:.3f}", va="center", fontsize=8)
ax.legend(loc="lower right")
plt.tight_layout()
display(fig)

# COMMAND ----------
# MAGIC %md ## Where bad rows go — quarantine reasons & clean/quarantine split

# COMMAND ----------
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
axes[0].barh(quar["rule"], quar["count"], color="#e67e22")
axes[0].set_title("Quarantined rows by failed rule"); axes[0].invert_yaxis()
for i, v in enumerate(quar["count"]):
    axes[0].text(v, i, f" {v}", va="center", fontsize=8)
axes[1].pie([clean_n, quar_n], labels=[f"clean\n{clean_n}", f"quarantine\n{quar_n}"],
            colors=["#27ae60", "#e74c3c"], autopct="%1.1f%%", startangle=90)
axes[1].set_title("Clean vs quarantined")
plt.tight_layout()
display(fig)

# COMMAND ----------
# MAGIC %md ## KPI table (interactive — switch to a chart with the viz button)

# COMMAND ----------
display(
    metrics.filter(F.col("run_id") == latest_run)
    .select("rule_name", "dimension", "severity", "rows_evaluated", "rows_failed", "pass_rate")
    .orderBy("dimension", "rule_name")
)

# COMMAND ----------
# MAGIC %md ## Pass-rate trend across runs (if the pipeline has run more than once)

# COMMAND ----------
trend = (
    metrics.filter(F.col("severity") == "error")
    .groupBy("measured_at").agg(F.min("pass_rate").alias("worst_hard_rule_pass_rate"))
    .orderBy("measured_at").toPandas()
)
if len(trend) > 1:
    fig, ax = plt.subplots(figsize=(9, 3))
    ax.plot(trend["measured_at"], trend["worst_hard_rule_pass_rate"], marker="o")
    ax.axhline(0.80, color="red", linestyle="--", linewidth=1)
    ax.set_title("Worst hard-rule pass rate per run"); ax.set_ylim(0, 1.0)
    plt.tight_layout(); display(fig)
else:
    print("Only one run so far — trend appears once the pipeline has run multiple times.")
