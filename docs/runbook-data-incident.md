# Runbook — Data Incident Response

> Applying SRE incident practice to data. The loop is the same one I use for
> production systems: **detect → contain → root-cause → fix → prevent**, with a
> blameless postmortem at the end.

Use this when a downstream consumer reports a data problem ("yesterday's revenue
dropped 40% overnight", "this dashboard looks wrong", a DQ alert fired).

## 0. Triage — is this a *data* issue or a real business change?

Before anything else, decide whether the number is wrong or the world changed.

- Compare the metric against the same period last week / last month.
- Check whether *one* segment moved (a country, a product) or everything.
- Ask the reporter what they expected and why.

If it's a genuine business change, document and close. Otherwise → contain.

## 1. Detect / scope

- Which table(s) and column(s)? Which `date_key` / load?
- Who/what consumes it (BI, ML, finance close)? What's the blast radius?
- Is it still ongoing (next load will also be bad) or a one-off?

## 2. Contain (stop the bleeding)

- If a bad load is propagating, **pause the downstream job** (don't let gold
  rebuild from bad silver).
- Bad rows should already be in **`quarantine.orders`** — confirm they're being
  caught, not leaking into silver.
- If silver/gold is already corrupted, **`RESTORE`** the Delta table to the last
  known-good version (see step 3) rather than hand-patching.

## 3. Root-cause (follow the data, newest signal first)

Work the layers in this order — cheapest, most-likely signals first:

1. **Freshness** — did the source arrive on time? `MAX(_ingested_at)` per source.
   A late/missing load is the most common cause.
2. **Volume** — is the row count roughly normal? A load that's half-size or 10×
   is a quality signal even before any rule fires.
   ```sql
   SELECT _source_file, COUNT(*) FROM bronze.orders
   GROUP BY _source_file ORDER BY _source_file DESC;
   ```
3. **DQ metrics** — did a rule's pass rate drop? `python -m brewquality.dq_report`
   or query `ops.dq_metrics` for the run. A spike in one rule points straight at
   the dimension that broke (schema change? new bad source?).
4. **Quarantine** — read the reasons for this run:
   ```sql
   SELECT reason, COUNT(*) FROM quarantine.orders
   WHERE run_id = '<run>' GROUP BY reason ORDER BY 2 DESC;
   ```
5. **Time travel diff** — compare the suspect version to the prior good one:
   ```sql
   SELECT * FROM silver.orders VERSION AS OF <bad>
   MINUS
   SELECT * FROM silver.orders VERSION AS OF <good>;
   ```
6. **Lineage (Unity Catalog)** — trace upstream: which source/table feeding this
   one changed? Column-level lineage tells you exactly which field moved.
7. **Recent changes** — last pipeline deploy / bundle release / source-schema
   change. Correlate the incident start with the deploy timeline.

## 4. Fix & reprocess

- Fix the root cause (source contract, a rule, a transform bug).
- **Remediate quarantined rows**: correct upstream or adjust the rule, then
  re-run the gate so they flow into silver — don't hand-edit silver.
- Reprocess the affected `date_key`(s); verify counts and DQ metrics recover.

## 5. Prevent (so it can't happen silently again)

- Add or tighten a **DQ rule** for the failure mode (a new hard/soft rule).
- Add an **alert / SLA** if a KPI would have caught it earlier
  (`dq_report --alert`).
- Add a **freshness/volume check** if that was the gap.
- Write a short **blameless postmortem**: timeline, root cause, what we changed.

## Quick reference — first 5 minutes

| Question | Where to look |
|---|---|
| Did data arrive? | `MAX(_ingested_at)` in bronze |
| Right amount of data? | row counts per `_source_file` |
| Did quality drop? | `ops.dq_metrics` / `dq_report` |
| What exactly failed? | `quarantine.orders.reason` |
| What changed in the data? | Delta time-travel diff |
| What changed upstream? | Unity Catalog lineage |
| What did we deploy? | bundle / pipeline deploy history |
