# ADR-0001: Medallion (bronze / silver / gold) architecture

**Status:** Accepted

## Context
We ingest deliberately messy sales/logistics data and need consumers (BI/ML) to
trust the result. We need a clear place for data quality to live and an auditable
path from raw to report.

## Decision
Adopt the **Medallion** layout on Delta Lake:
- **bronze** — raw, append-only, full fidelity (read as strings; nothing rejected).
- **silver** — typed, validated, conformed, deduplicated. The **DQ gate lives at
  bronze→silver**.
- **gold** — dimensional star schema + aggregates for reporting.

## Consequences
- Clear ownership of quality: silver is the trust boundary; gold is always built
  from trusted data.
- Bronze stays replayable, so we can reprocess after fixing a rule or a bug.
- Slightly more storage (data is materialised three times) — acceptable for the
  auditability and reprocessing it buys. Delta `OPTIMIZE`/`VACUUM` manage cost.
