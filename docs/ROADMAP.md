# BrewQuality — roadmap (fixes & extensions)

Prioritised by ratio of *interview/portfolio signal* to *effort*. Each item notes
which JD theme it deepens.

## Quick fixes / hardening (hours)
- **Delta constraints as a backstop** — add `NOT NULL` / `CHECK` constraints on
  silver tables so a code bug can't write data that violates a hard invariant
  (complements the app-level gate). *Theme: Delta, defence in depth.*
- **Idempotent bronze ingest** — switch bronze from blind `append` to a `MERGE`
  on a natural/load key so re-runs don't duplicate. *Theme: Delta MERGE.*
- **Freshness & volume checks** — add a rule class that flags a load that's late
  or abnormally small (row-count vs trailing average). *Theme: timeliness.*
- **Parameterise the wheel path** in the silver notebook (read from a job
  parameter instead of a hard-coded volume path). *Theme: clean DAB.*
- **Pin a Delta `RESTORE` demo** in the runbook with real version numbers from a
  seeded bad load. *Theme: time travel / incident.*

## Medium extensions (a day each)
- **Profiling pass** — add a `profile.py` (or PyDeequ/Great Expectations) that
  computes column stats and **suggests** candidate rules, instead of hand-authoring
  them. Directly answers the profiling question. *Theme: DQ profiling.*
- **Adopt a DQ framework alongside** — wire **Databricks DQX** or **Great
  Expectations** for one table and show the same quarantine + metrics, proving the
  migration path in ADR-0002 is real. *Theme: Ataccama proxy.*
- **DQ dashboard** — a Databricks SQL dashboard (or Grafana over `ops.dq_metrics`)
  with pass-rate trends, top failing rules, freshness. Screenshot for the README.
  *Theme: KPI/alerting.*
- **Real alerting** — Databricks SQL alert or a job that calls
  `dq_report --alert` and posts to Teams/email on SLA breach. *Theme: observability.*
- **SCD2 dimension** — make `dim_customer` slowly-changing (track country changes
  over time) with `MERGE`. *Theme: data modeling depth.*

## Larger / platform (multi-day)
- **Streaming ingest** — a Structured Streaming / Auto Loader path into bronze with
  the same gate, to show batch+streaming unification. *Theme: Spark, Delta.*
- **Staging→prod promotion live** — actually deploy the `staging` and `prod`
  bundle targets to separate UC catalogs and demonstrate approval-gated promotion.
  *Theme: CI/CD, DAB.*
- **Azure DevOps pipeline** — mirror the GitHub Actions CI in `azure-pipelines.yml`
  with a Service Principal service connection, since the JD names Azure DevOps.
  *Theme: CI/CD on their tooling.*
- **Lineage-driven impact analysis** — a small script that reads Unity Catalog
  lineage to answer "if this source breaks, which gold tables/dashboards are
  affected?" *Theme: governance, root-cause.*
- **Data contracts** — express the source schema as a versioned contract and fail
  ingest on an incompatible change (schema drift), feeding the quarantine story.
  *Theme: contracts, shift-left.*

## Testing / quality engineering
- **Property-based tests** (Hypothesis) for the rule engine — generate random
  rows and assert invariants (a row in silver passes every hard rule).
- **Integration test on Databricks** in CI — a scheduled GitHub Action that runs
  `bundle validate` + a tiny serverless run against a `ci` catalog.
- **Mutation testing** on the DQ rules to prove the tests actually catch breakage.

## If I had one afternoon before the interview
1. Delta `CHECK`/`NOT NULL` constraints on silver (fast, strong "defence in depth").
2. A Databricks SQL dashboard over `ops.dq_metrics` + one screenshot in the README.
3. The freshness/volume check + a matching line in the runbook.
These three most visibly close the "DQ KPIs / monitoring / timeliness" gaps.
