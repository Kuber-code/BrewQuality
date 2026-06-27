# Technology alternatives & trade-offs

For each building block of BrewQuality: **what we chose**, the **alternatives**,
and **how each would help or hurt**. This is the "why this and not that" you want
ready for the interview — picking a tool is a trade-off, not a default.

---

## 1. Orchestration — *chosen: Databricks Workflows (Jobs)*
- **Apache Airflow** — *helps:* richer DAGs, huge operator ecosystem, cross-system
  orchestration, mature backfills. *hurts:* another service to run/patch, Python
  DAG sprawl, and it sits *outside* Databricks so you lose native task/cluster
  integration and pay for an extra control plane.
- **Azure Data Factory** — *helps:* native Azure, low-code, great for ingest/copy
  and hybrid sources; integrates with Databricks notebooks. *hurts:* weaker for
  code-first logic and testing; UI-driven pipelines are harder to review in Git.
- **dbt + a scheduler** — *helps:* SQL-first transformations with built-in tests
  and lineage. *hurts:* SQL-only (no PySpark), and you still need an orchestrator;
  better as a *complement* than a replacement.
- **Why Workflows here:** native to the platform, declared as code in the Asset
  Bundle, jobs clusters/serverless, retries+alerts built in — least moving parts.

## 2. Data-quality engine — *chosen: small in-repo PySpark engine*
- **Databricks DQX** — *helps:* Databricks-native, quarantine + metrics out of the
  box, PySpark. *hurts:* younger project, one more dependency; less transparent in
  an interview than ~100 lines you can read.
- **Great Expectations** — *helps:* big expectation library, profiling, "data docs"
  HTML reports, CI-friendly. *hurts:* heavier, its own config/store to manage, and
  Spark integration is clunkier than native expressions.
- **Soda / SodaCL** — *helps:* lightweight YAML checks, Soda Cloud monitoring.
  *hurts:* less expressive for complex/relational rules; another runtime.
- **dbt tests** — *helps:* trivial if you're already SQL/dbt. *hurts:* SQL-only,
  weaker for row-level quarantine with reasons.
- **Ataccama ONE / Informatica / Collibra DQ** — *helps:* enterprise governance,
  business-user rule authoring, lineage-aware monitoring, remediation workflows.
  *hurts:* licence cost, less flexible for bespoke logic, slower to iterate.
- **Why a small engine here:** transparent, zero deps, trivially unit-tested, and
  the dimension/severity model maps 1:1 to a framework later (see ADR-0002).

## 3. Storage / table format — *chosen: Delta Lake*
- **Apache Iceberg** — *helps:* engine-neutral (Spark/Trino/Flink/Snowflake),
  hidden partitioning, strong schema evolution; the emerging open standard. *hurts:*
  less turn-key on Databricks (Delta is first-class there), fewer Databricks-native
  optimizations (Photon/predictive optimization).
- **Apache Hudi** — *helps:* great for streaming upserts/CDC, record-level indexes.
  *hurts:* more tuning knobs, smaller ecosystem on Azure/Databricks.
- **Plain Parquet** — *helps:* simplest, universally readable. *hurts:* no ACID, no
  schema enforcement, no time travel — i.e. no foundation for a DQ gate. The "data
  swamp" we explicitly avoid.
- **Why Delta:** ACID + schema enforcement + time travel + MERGE, and it's native to
  Databricks/Unity Catalog. (UniForm even exposes Delta as Iceberg if needed.)

## 4. Governance / catalog — *chosen: Unity Catalog*
- **Microsoft Purview** — *helps:* org-wide catalog across Azure (not just
  Databricks), classification/sensitivity. *hurts:* not the runtime access layer;
  you'd still govern Databricks tables in UC — they're complementary.
- **Collibra / Alation** — *helps:* business glossary, stewardship workflows,
  enterprise data governance. *hurts:* licence cost, integration effort; sit above
  the platform, not replacing UC's access control/lineage.
- **Hive metastore (legacy)** — *helps:* simple, ubiquitous. *hurts:* no unified
  governance, no built-in lineage/column-level security — the things this role is
  about.
- **Why UC:** three-level namespace, central grants, automatic table/column lineage
  (root-cause!), and the managed-identity storage model — all native.

## 5. Compute — *chosen: serverless jobs compute*
- **Classic clusters** — *helps:* full control of VNet/instance type/Spark conf,
  needed for some libraries. *hurts:* you size/manage them, slower start, and (here)
  trial VM SKUs were capacity-restricted.
- **Delta Live Tables (DLT / Lakeflow Declarative Pipelines)** — *helps:* declarative
  pipelines with **built-in expectations** (DQ as a first-class feature), auto
  orchestration and data quality metrics. *hurts:* more opinionated/Databricks-
  locked, less control over the exact transform; a strong alternative specifically
  for the DQ-gate pattern.
- **Why serverless:** zero infra, scales to zero, sidesteps SKU limits — cheapest
  path for bursty validation jobs.

> **Worth saying in the interview:** "If I leaned further into the platform I'd
> evaluate **DLT/Lakeflow** — its `EXPECT` constraints do quarantine + DQ metrics
> declaratively, which overlaps with my hand-rolled gate."

## 6. Ingestion — *chosen: batch read of files in a volume*
- **Auto Loader (`cloudFiles`)** — *helps:* incremental, schema-evolution-aware file
  ingestion at scale, exactly-once. *hurts:* streaming mindset/checkpoints; overkill
  for a fixed demo batch.
- **Azure Data Factory / Event Hubs / Kafka** — *helps:* real source connectivity,
  CDC, streaming. *hurts:* more infra; only needed when sources are live.
- **Why batch:** the dataset is generated; batch keeps the demo deterministic.

## 7. Secrets & storage auth — *chosen: Managed Identity (+ SP for CI/CD)*
- **Account keys / SAS tokens** — *helps:* dead simple. *hurts:* long-lived,
  over-privileged, leak-prone, manual rotation — the anti-pattern.
- **Service Principal everywhere** — *helps:* works for automation. *hurts:* a secret
  to store and rotate; prefer Managed Identity where the workload runs in Azure.
- **Why MI + SP:** MI for UC→ADLS (no secret to rotate), SP only as the CI/CD deploy
  identity, secret in Key Vault. Least privilege, no keys in code.

## 8. CI/CD — *chosen: GitHub Actions*
- **Azure DevOps Pipelines** — *helps:* the JD names it; native Azure service
  connections, environments/approvals, Boards integration. *hurts:* mostly mirrors
  the GitHub Actions flow here; another platform to host.
- **GitLab CI / Jenkins** — *helps:* fits existing org tooling. *hurts:* no special
  advantage for Databricks vs Actions/DevOps.
- **Why Actions:** free, already validating tests + pipeline + DQ audit on Linux.
  (An `azure-pipelines.yml` mirror is a cheap add to literally match the JD.)

## 9. Infrastructure as code — *chosen: Databricks Asset Bundles*
- **Terraform (databricks provider)** — *helps:* manages the *whole* footprint
  (workspace, UC, storage, identities) in one tool; great for platform teams.
  *hurts:* more verbose; for *app* resources (jobs/notebooks) DAB is purpose-built.
- **ARM / Bicep** — *helps:* native Azure resource provisioning. *hurts:* doesn't
  manage in-workspace objects (jobs, UC grants) well.
- **Why DAB + a bit of az CLI:** DAB for the job/notebooks/libraries (the app), az
  CLI/Terraform for the cloud resources. Right tool per layer.

## 10. Serving / dashboards — *chosen: `ops.dq_metrics` Delta table (+ optional dashboard)*
- **Databricks SQL / Lakeview dashboards** — *helps:* native, queries the metrics
  table directly, shareable. *hurts:* needs a SQL warehouse (small cost).
- **Power BI** — *helps:* enterprise BI standard, rich sharing. *hurts:* another tool
  + gateway/refresh setup.
- **Grafana** — *helps:* you already know it; great for time-series KPIs/alerting.
  *hurts:* needs a data source connector; less native to the lakehouse.
- **Why a Delta table first:** the KPI *data* is the durable asset; any of the above
  can render it.

## 11. Data modeling (gold) — *chosen: star schema (Kimball)*
- **Data Vault 2.0** — *helps:* auditable, agile to source changes, great for highly
  integrated EDWs. *hurts:* more tables/joins, steeper learning, overkill for a focused
  mart.
- **One Big Table (wide denormalized)** — *helps:* simplest for BI read performance.
  *hurts:* duplication, harder to maintain conformed dimensions.
- **Why star schema:** the clearest BI-facing model and the expected answer for a
  reporting mart.

## 12. Data observability (beyond rule pass-rates)
- **Databricks Lakehouse Monitoring** — *helps:* native drift/quality/profile
  monitoring on tables with auto dashboards. *hurts:* Databricks-specific, extra cost.
- **Monte Carlo / Soda Cloud / Bigeye** — *helps:* automated anomaly detection,
  freshness/volume monitors, incident workflows ("data observability"). *hurts:*
  SaaS cost; overlaps with what we hand-build (metrics + runbook).
- **Why our approach:** explicit rules + KPIs + a runbook show you *understand* the
  mechanics; a platform automates them once scale demands it.

---

### The meta-point for the interview
"Every choice here is a trade-off I can defend. I picked the **native, transparent,
testable** option for each layer, and I know exactly which managed platform
(Ataccama, DLT, Lakehouse Monitoring, Monte Carlo, Terraform, Azure DevOps) I'd
reach for as scale and team size grow — and what it costs me in flexibility."
