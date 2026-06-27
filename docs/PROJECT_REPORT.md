# BrewQuality — project report

What's in the repo, what works, and how the pieces fit. Snapshot for review.

## What this is
A production-style **Medallion lakehouse with automated data-quality gates** on
**PySpark + Delta**, built to cover the Heineken Data Quality Engineer stack
end to end. Deliberately dirty sales data → bronze → a DQ gate that validates
across the five DQ dimensions and **quarantines** bad rows → trusted silver → a
gold star schema. Orchestrated, tested in CI, deployed to **Azure Databricks**
via Asset Bundles, and monitored with DQ KPIs.

## Status at a glance
| Area | State |
|---|---|
| Local pipeline (bronze→silver→gold) | ✅ runs |
| DQ engine + quarantine + metrics | ✅ |
| Unit tests (every rule) | ✅ green in CI |
| GitHub Actions CI + DQ audit gate | ✅ green |
| Azure Databricks (workspace, Unity Catalog, ADLS, secrets) | ✅ provisioned + deployed |
| Workflow run on Azure (serverless) | ✅ end-to-end |
| Databricks Asset Bundle deploy | ✅ |

## Repository map
```
brewquality/
  config.py          lakehouse layout (paths local; UC names on Databricks)
  session.py         Delta-enabled SparkSession (Arrow on; Py3.12/Win notes)
  generate_data.py   Faker data with controlled defects per DQ dimension
  bronze.py          raw -> bronze (append-only, full fidelity, audit cols)
  dq/
    rules.py         declarative Rule objects, tagged by dimension + severity
    prepare.py       casts + window dedup + referential-integrity joins
    engine.py        evaluate -> split(clean/quarantine) -> compute_metrics (JVM)
  silver.py          the DQ gate: validate, quarantine, conform, dedup
  gold.py            dimensional star schema + reporting aggregates
  pipeline.py        local orchestrator (raw->bronze->silver->gold)
  dq_report.py       KPI trends, top failing rules, quarantine reasons, alerting
  ci_audit.py        Write-Audit-Publish gate: fail build if DQ drifts
databricks/
  databricks.yml     Asset Bundle: serverless Workflow, dev/staging/prod targets
  notebooks/         00 UC setup (SQL), 01 bronze, 02 silver gate, 03 gold (UC I/O)
  README.md          local<->UC mapping + deploy story
docs/
  adr/                       5 architecture decision records
  runbook-data-incident.md   SRE detect→contain→root-cause→fix→prevent
  azure-setup.md             Key Vault / SP / Managed Identity / ADLS
  azure-databricks-senior-guide.md   senior cheat-sheet (+ smaczki)
  azure-operations.md        cost control, stop, and rebuild runbook
  tech-alternatives.md       alternative techs per component + trade-offs
  interview-heineken-code-map.md     code → interview-question map
  PROJECT_REPORT.md · ROADMAP.md
scripts/
  azure_provision.ps1   Azure resources (RG, ADLS, workspace, MI, KV, SP)
  azure_bootstrap.ps1   UC objects, secret scope, data upload (inside Databricks)
  azure_deploy.ps1      build wheel + deploy bundle + run Workflow
  azure_teardown.ps1    delete everything (cost -> 0)
  setup_hadoop_win.ps1  local Windows Spark helper
tests/                unit tests for transforms + every DQ rule
.github/workflows/ci.yml   tests + pipeline + DQ audit gate (Linux)
```

## The data-quality model (the core)
Rules are declarative `Rule(name, dimension, severity, passes)` objects, so they
read as documentation and unit-test trivially. Eight rules cover:
- **completeness** (customer_id, order_amount present)
- **validity** (quantity > 0, parseable date)
- **uniqueness** (no duplicate order_id — keep first, quarantine the rest)
- **integrity** (product_id / customer_id exist in their dimension)
- **accuracy** (amount = qty × price) — the one **soft** rule (warn, not block)

Hard rules quarantine the row with the failed-rule name + reason; soft rules pass
but are flagged and counted. Per-rule pass rates persist to `ops.dq_metrics`.

## How it runs in three places (same core code)
1. **Local**: `python -m brewquality.pipeline` over Delta files in `data/lake`.
2. **CI (Linux)**: pytest + the full pipeline + `ci_audit` as a merge gate.
3. **Azure Databricks**: the three notebooks reuse `brewquality.dq` (installed as
   the wheel), reading/writing **Unity Catalog** tables, orchestrated as a
   **serverless Workflow** deployed by the Asset Bundle.

## Azure footprint actually stood up
- Resource group `rg-brewquality` (West Europe).
- **ADLS Gen2** storage (hierarchical namespace) + `lake` container.
- **Azure Databricks** premium workspace.
- **Unity Catalog**: catalog `brewquality_dev`, schemas bronze/silver/gold/
  quarantine/ops, a landing volume + a libs volume.
- **Access Connector (Managed Identity)** → UC **storage credential** + **external
  location** on the lake → keyless ADLS access.
- **Key Vault** + **Key-Vault-backed secret scope** (secrets never in code).
- **Service Principal** as the CI/CD deploy identity (secret in Key Vault).
- Compute: **serverless** (the trial's classic VM SKUs were stock-restricted).

## Known limitations / caveats
- Local **Windows** Delta reads need a matching `hadoop.dll` + MSVC++; CI/Databricks
  (Linux) are the validated surfaces.
- Phases scaffolded vs deeply exercised: staging/prod targets and the Azure DevOps
  pipeline are illustrative; the GitHub Actions CI is the live one.
- No live external data source — data is generated; profiling is manual.
- Single dataset (orders/customers/products); rules are hand-authored, not
  profile-suggested yet.

See [`ROADMAP.md`](ROADMAP.md) for what I'd build next.
