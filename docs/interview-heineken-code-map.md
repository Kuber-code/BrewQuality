# Heineken DQ Engineer — code → interview-question map

How to use: for each likely question you get *where in this repo it lives* and a
*1–2 sentence answer you can say out loud*. Open the file on a second screen
during the call. Questions follow the prep Q&A numbering.

---

## 1. Lakehouse & Delta (Q1, Q4–Q6)

**Q1 — What is the lakehouse / why Delta for data quality?**
→ [`brewquality/bronze.py`](../brewquality/bronze.py), [`docs/adr/0005-delta-lake-storage.md`](adr/0005-delta-lake-storage.md)
*Say:* "Every layer is a Delta table, so I get ACID, schema enforcement and time
travel on cheap object storage — I can validate, version and roll back data
instead of a data swamp. Delta constraints are a write-time backstop behind my
application DQ rules."

**Q4 — Delta over plain Parquet?**
→ ADR-0005, `write.format("delta")` in bronze/silver/gold.
*Say:* "Delta is Parquet plus a transaction log → ACID, schema evolution, time
travel, and MERGE. For DQ that means an auditable history and the ability to diff
a bad load against the last good version."

**Q5 — MERGE / OPTIMIZE / VACUUM?**
→ [`docs/runbook-data-incident.md`](runbook-data-incident.md) (time-travel diff), ADR-0005.
*Say:* "MERGE for upserts/dedup; OPTIMIZE+ZORDER for the small-file problem and
data skipping; VACUUM reclaims old files but destroys time travel past its
retention, so I weigh it against audit needs."

**Q6 — How does Delta contain bad data?**
→ ADR-0005 (constraints as backstop), [`brewquality/silver.py`](../brewquality/silver.py) (quarantine).
*Say:* "Schema enforcement stops malformed writes; NOT NULL/CHECK constraints
reject rule-violating rows at write time; and my gate quarantines bad rows before
they reach silver."

## 2. Medallion & quarantine (Q7, Q8) — the heart

**Q7 — Describe Medallion and where DQ lives.**
→ [`brewquality/bronze.py`](../brewquality/bronze.py) · [`silver.py`](../brewquality/silver.py) · [`gold.py`](../brewquality/gold.py)
*Say:* "Bronze is raw append-only full fidelity; silver is validated, conformed,
deduplicated; gold is a dimensional star schema. The **DQ gate lives at
bronze→silver** — that's the `silver.build` function."

**Q8 — Quarantine pattern, why not drop?**
→ [`brewquality/dq/engine.py`](../brewquality/dq/engine.py) `split()`, [`silver.py`](../brewquality/silver.py) quarantine write, [`docs/adr/0003-quarantine-not-drop.md`](adr/0003-quarantine-not-drop.md)
*Say:* "Failing rows go to a `quarantine.orders` table tagged with the failed rule
and reason, not dropped — so it's auditable, remediable (fix → reprocess), and
feeds DQ metrics. Dropping silently destroys the evidence."

## 3. Data quality core (Q9, Q10, Q11, Q18) — most likely questions

**Q9 — The DQ dimensions and how you measure each.**
→ [`brewquality/dq/rules.py`](../brewquality/dq/rules.py) (every `Rule` is tagged with its dimension)
*Say:* "Completeness, accuracy, consistency, uniqueness, validity/integrity, plus
timeliness. In the code each rule is a `Rule` object carrying its dimension,
severity and a boolean expression — completeness = non-null key, integrity =
referential join exists, uniqueness = no duplicate business key, etc."

**Q10 — Design a DQ rule; hard vs soft.**
→ [`brewquality/dq/rules.py`](../brewquality/dq/rules.py) (`Rule` dataclass, `accuracy_amount_matches` is soft), [`docs/adr/0004-hard-vs-soft-rules.md`](adr/0004-hard-vs-soft-rules.md)
*Say:* "A rule = assertion + dimension + severity + action. Hard rules (severity
`error`) quarantine; soft rules (`warn`) let the row through but flag and count
it so I alert on spikes — e.g. amount ≠ qty×price is soft because manual discounts
are legitimate."

**Q11 — Data profiling.**
→ [`brewquality/generate_data.py`](../brewquality/generate_data.py) (known defect rates), roadmap item.
*Say:* "Profiling is the stats step before writing rules — null rate, distinct
counts, distributions — to discover what rules should exist. Here I injected
controlled defects so I know the expected rates; a profiling pass (GX/PyDeequ) is
my next extension to auto-suggest rules."

**Q18 — Find DQ problems with SQL / window functions.**
→ [`brewquality/dq/prepare.py`](../brewquality/dq/prepare.py) (`row_number` dedup, broadcast left-join for referential integrity, safe casts)
*Say:* "Duplicates via `ROW_NUMBER() OVER (PARTITION BY order_id)` keeping the
first; referential integrity via a left join and checking the right side is null;
completeness via null checks; validity via safe casts that become null on bad
input. That's exactly what `prepare_orders` computes."

## 4. PySpark (Q3, Q16, Q17)

**Q16 — Lazy eval, transformations vs actions, narrow vs wide.**
→ [`brewquality/dq/engine.py`](../brewquality/dq/engine.py) (`compute_metrics` is one agg + `stack`, no Python round-trip)
*Say:* "Transformations build a lazy DAG; an action triggers it. Wide ops (join,
groupBy) shuffle — the cost. I keep the metrics computation to a single
aggregation and a `stack` instead of pulling rows to Python."

**Q17 / Q3 — UDFs and optimizing a slow job.**
→ [`brewquality/dq/prepare.py`](../brewquality/dq/prepare.py) (`F.broadcast` on dimensions), [`brewquality/session.py`](../brewquality/session.py) (shuffle partitions, Arrow).
*Say:* "I avoid Python UDFs — all rules are native Spark expressions, so they stay
in the JVM and Catalyst-optimize. I broadcast the small product/customer
dimensions instead of shuffling, and let AQE handle skew."

## 5. Unity Catalog & governance (Q20, Q21)

**Q20 — What is Unity Catalog and why it matters.**
→ [`databricks/notebooks/00_setup_unity_catalog.sql`](../databricks/notebooks/00_setup_unity_catalog.sql), [`databricks/README.md`](../databricks/README.md)
*Say:* "Three-level namespace `catalog.schema.table`, central grants, automatic
table/column lineage, and managed vs external tables. I use one catalog per
environment and grant analysts only `gold`+`ops` — least privilege, and lineage
is my root-cause tool."

**Q21 — Managed vs external; where storage/secrets fit.**
→ [`scripts/azure_provision.ps1`](../scripts/azure_provision.ps1), [`docs/azure-setup.md`](azure-setup.md), [`docs/azure-databricks-senior-guide.md`](azure-databricks-senior-guide.md)
*Say:* "Managed = UC owns metadata and files; external = files live at an ADLS
path I control via an external location + storage credential. **I actually built
this**: a storage credential backed by an Access Connector managed identity, so
UC reaches ADLS with zero account keys."

## 6. Azure security (Q22, Q23) — they stressed this

**Q22 — Service Principals, Managed Identities, Key Vault together.**
→ [`scripts/azure_provision.ps1`](../scripts/azure_provision.ps1), [`docs/azure-setup.md`](azure-setup.md)
*Say:* "I provisioned a **Service Principal** as the CI/CD deploy identity with its
secret only in **Key Vault**, and a **Managed Identity** (Access Connector) for
UC→ADLS where there's no secret to rotate. Notebooks read secrets from a
Key-Vault-backed secret scope — no plaintext credentials anywhere."

**Q23 — ADLS Gen2 / hierarchical namespace.**
→ `azure_provision.ps1` (`--hns true`), azure-setup.md.
*Say:* "ADLS Gen2 is Blob plus a hierarchical namespace — real directories, atomic
dir ops, POSIX ACLs — the storage under the Delta files. I created it with HNS and
bound it to UC via an external location."

## 7. CI/CD & DAB (Q24, Q25, Q26) — your DevOps edge

**Q24 — Databricks Asset Bundles, why.**
→ [`databricks/databricks.yml`](../databricks/databricks.yml)
*Say:* "DAB is IaC for Databricks — jobs, clusters and libraries declared in
`databricks.yml`, deployed per target (dev/staging/prod) with the CLI. Same
mindset as Terraform; I actually deployed this bundle to my Azure workspace."

**Q25 — Design a CI/CD pipeline.**
→ [`.github/workflows/ci.yml`](../.github/workflows/ci.yml), [`brewquality/ci_audit.py`](../brewquality/ci_audit.py)
*Say:* "PR → lint + pytest + `bundle validate`; merge → deploy staging, integration
run asserting DQ metrics, then approval-gated promote to prod as the Service
Principal. My CI already runs the pipeline and **fails the build if data quality
drifts** — Write-Audit-Publish."

**Q26 — Test pipelines and DQ rules.**
→ [`tests/test_dq_rules.py`](../tests/test_dq_rules.py), [`brewquality/ci_audit.py`](../brewquality/ci_audit.py)
*Say:* "I unit-test every rule on tiny DataFrames including edge cases (nulls,
dupes, bad dates), and treat the rules as testable artifacts. Integration is the
full pipeline plus an audit step — Write-Audit-Publish: only publish if checks
pass."

## 8. Orchestration & monitoring (Q27, Q28)

**Q27 — Orchestrate/schedule validation.**
→ [`databricks/databricks.yml`](../databricks/databricks.yml) (job DAG: ingest → gate → build, retries, alerts)
*Say:* "A Databricks Workflow as a task DAG: bronze_ingest → silver_dq_gate →
gold_build, with a retry on the gate and email-on-failure, declared in the bundle."

**Q28 — Monitor DQ KPIs and alert.**
→ [`brewquality/dq_report.py`](../brewquality/dq_report.py), [`brewquality/dq/engine.py`](../brewquality/dq/engine.py) `compute_metrics`
*Say:* "Per-rule pass rates land in `ops.dq_metrics` (Delta); `dq_report` trends
them, shows top failing rules and quarantine reasons, and exits non-zero on an SLA
breach — the hook an email/Teams alert calls. It's observability applied to data."

## 9. Incident root-cause (Q12) — your strongest, SRE angle

**Q12 — Revenue dropped 40% overnight; investigate.**
→ [`docs/runbook-data-incident.md`](runbook-data-incident.md)
*Say:* "My SRE loop applied to data: confirm it's a data issue, check freshness
and volume of the load, check DQ metrics and the quarantine table for that run,
time-travel diff vs the last good version, use UC lineage to trace the upstream
change, check recent deploys — then contain, fix, reprocess, and add a rule so
it's caught automatically. That whole runbook is in the repo."

## 10. System design (Q29)

**Q29 — Design a DQ framework for a Medallion lakehouse on Azure Databricks.**
→ The whole repo; narrate [`README.md`](../README.md) architecture diagram.
*Say:* "This is literally what I built: ADLS+Delta bronze/silver/gold under Unity
Catalog, a DQ engine at bronze→silver with quarantine and per-dimension rules,
orchestrated as a Workflow via Asset Bundles, secrets via Managed
Identity/SP/Key Vault, CI/CD with a DQ gate, and KPI metrics + a runbook for
root-cause. One architecture covering the whole JD — and it runs."

## 11. Ataccama bridge (Q13–Q15)

→ [`docs/adr/0002-dq-engine-vs-framework.md`](adr/0002-dq-engine-vs-framework.md)
*Say:* "I haven't used Ataccama in production, but I built the same concepts —
profiling, rules per DQ dimension, quarantine, KPI monitoring — as a small PySpark
engine, and ADR-0002 maps the clean migration path to DQX/Great Expectations or a
platform like Ataccama. The platform centralizes governance; I'd ramp fast
because I've implemented the primitives."

---

### The one-liner if they ask "did you really run it?"
"Yes — on Azure Databricks I provisioned myself: premium workspace, Unity Catalog
over ADLS Gen2 via a managed-identity Access Connector (no keys), Key-Vault-backed
secrets, deployed as an Asset Bundle, and ran the Workflow end-to-end on a
single-node jobs cluster. Teardown is one script so it doesn't burn credit."
