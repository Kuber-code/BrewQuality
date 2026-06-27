# DQ dashboards — two approaches, compared

BrewQuality ships **both** ways to visualize `ops.dq_metrics`, so you can compare
them. Both read the same Delta table populated by the pipeline.

| | Notebook dashboard | Lakeview SQL dashboard |
|---|---|---|
| File | [`databricks/notebooks/04_dq_dashboard.py`](../databricks/notebooks/04_dq_dashboard.py) | [`databricks/dashboards/dq_kpis.lvdash.json`](../databricks/dashboards/dq_kpis.lvdash.json) |
| Renders with | matplotlib in notebook cells | native Databricks BI widgets |
| Compute | **serverless** (no SQL warehouse) | needs a **SQL warehouse** (serverless, auto-stops) |
| Cost when idle | €0 | €0 (warehouse auto-stops; starts on view) |
| Best for | engineers, repeatable, in-context with the run | stakeholders, sharing, a polished BI artifact |
| Refresh | re-run the notebook | auto-queries on open / scheduled |
| IaC / versionable | yes (it's code) | yes (the `.lvdash.json` is the definition) |
| Interactivity | static charts + one `display()` table | filters, drill-down, native viz |
| Setup friction | none | needs a warehouse to view |

## How to view each

### Notebook dashboard (no warehouse)
Open `notebooks/04_dq_dashboard.py` in the workspace (deployed by `bundle deploy`)
and **Run all** on serverless. You get: pass-rate-per-rule bar (vs the 0.80 SLA
line), quarantine-by-rule bar, a clean/quarantine pie, the KPI table, and a
pass-rate trend across runs. Screenshot for the portfolio.

### Lakeview SQL dashboard (live)
Already created **and published** on the workspace (dashboard id
`01f1725b8ff3118fbf20a9cb5df8ca1b`):
- Published: `https://adb-7405608746580780.0.azuredatabricks.net/dashboardsv3/01f1725b8ff3118fbf20a9cb5df8ca1b/published`
- Draft (edit): `https://adb-7405608746580780.0.azuredatabricks.net/dashboardsv3/01f1725b8ff3118fbf20a9cb5df8ca1b`

Opening it starts the small serverless SQL warehouse (`bq-dash`, auto-stops after
5 min idle). It shows the same KPIs as native BI widgets.

> Both verified: notebook 04 ran green on serverless; the Lakeview dashboard
> created + published via the API from the `.lvdash.json`.

## How each was built (reproducible)
- **Notebook** — just a notebook synced by the Asset Bundle; nothing else.
- **Lakeview** — the `.lvdash.json` *is* the dashboard (datasets = SQL queries,
  pages = widgets). It was deployed via the `lakeview` API against a serverless
  SQL warehouse. It can also be managed by the **Asset Bundle** as a
  `resources.dashboards` entry (commented in `databricks.yml`; pass
  `--var warehouse_id=<id>` to enable) — that's the fully-IaC path.

## Which to lead with in the interview
Show the **Lakeview dashboard** as the headline visual (it looks like the BI
artifact a DQ team actually ships), and mention the **notebook** as the
zero-infrastructure, code-first alternative engineers run inline. Saying *"I built
the KPI layer as a Delta table so it's tool-agnostic — here it is rendered both as
a native Lakeview dashboard and as a serverless notebook"* shows you think about
the data product, not just one tool.

## Teardown note
The `bq-dash` warehouse is tiny and auto-stops (≈€0 idle). It's removed anyway by
`scripts/azure_teardown.ps1` (which deletes the whole resource group). To remove
just the warehouse: `databricks warehouses delete <id>`.
