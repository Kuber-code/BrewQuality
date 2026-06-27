# Databricks deployment (Phases 3, 4, 6)

How the local lakehouse maps onto **Azure Databricks + Unity Catalog**, deployed
via **Databricks Asset Bundles** and **CI/CD**. The DQ core (`brewquality/dq`) is
unchanged — only the I/O moves from `data/lake/<layer>` paths to UC tables.

## Local ↔ Unity Catalog mapping

| Local (Delta path)            | Unity Catalog (`catalog.schema.table`) |
|-------------------------------|----------------------------------------|
| `data/lake/bronze/orders`     | `brewquality_<env>.bronze.orders`      |
| `data/lake/silver/orders`     | `brewquality_<env>.silver.orders`      |
| `data/lake/quarantine/orders` | `brewquality_<env>.quarantine.orders`  |
| `data/lake/gold/*`            | `brewquality_<env>.gold.*`             |
| `data/lake/ops/dq_metrics`    | `brewquality_<env>.ops.dq_metrics`     |

One **catalog per environment** (`dev` / `staging` / `prod`) gives clean
isolation. Three-level namespace, centralized `GRANT`s, and automatic
table/column **lineage** are what make this *governed* — see
`notebooks/00_setup_unity_catalog.sql`.

## Phase 3 — run on Databricks (Free Edition works)

1. Create the catalog + schemas: run `notebooks/00_setup_unity_catalog.sql`.
2. Upload the sample data to the UC volume `/<catalog>/bronze/landing`.
3. Run the three notebooks in order (or the Workflow below). They reuse the
   pip-installed `brewquality` wheel, so the rules are identical to CI.
4. Inspect **lineage** in the UC UI (bronze → silver → gold) and the
   **Workflow** run graph.

## Phase 4 — CI/CD with Asset Bundles

`databricks.yml` declares the job (a Workflow: ingest → DQ gate → gold), the
wheel artifact, and `dev`/`staging`/`prod` targets.

```bash
databricks bundle validate                 # CI: syntax + schema check
databricks bundle deploy  -t staging       # deploy to staging
databricks bundle run brewquality_pipeline -t staging   # integration run
databricks bundle deploy  -t prod          # promote (with approval gate)
```

In **Azure DevOps** (`azure-pipelines.yml`, equivalent to the GitHub Actions CI
here): lint → `pytest` → `bundle validate` → deploy staging → integration test
(assert DQ metrics) → manual-approval promote to prod. The deploy identity is a
**Service Principal**, not a person. This is the JD's "end-to-end CI/CD for
Databricks using Azure DevOps".

> **This bundle was actually deployed and run** on the `dev` target against a real
> Azure Databricks workspace. Two serverless-specific notes worth knowing:
> - the job runs on **serverless** (no VM SKU), so the silver notebook installs
>   the wheel in-notebook: `%pip install --no-deps <volume>/…whl` — `--no-deps`
>   because the runtime already provides pyspark/delta and the wheel's pinned
>   pyspark would otherwise conflict;
> - **`.cache()`/`.persist()` are unsupported on serverless** (Spark Connect) — the
>   notebook recomputes the plan instead.

## Phase 6 — Azure security

See [`../docs/azure-setup.md`](../docs/azure-setup.md): Key Vault-backed secret
scopes, Service Principal / Managed Identity auth to ADLS Gen2 over OAuth, and
external locations — **no plaintext credentials in notebooks or Git**.
