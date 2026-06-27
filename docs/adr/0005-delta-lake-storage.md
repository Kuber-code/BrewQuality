# ADR-0005: Delta Lake as the storage format, with constraints as a backstop

**Status:** Accepted

## Context
We need ACID guarantees, schema enforcement, an audit trail, and the ability to
roll back a bad load on cheap object storage — not a "data swamp" of raw Parquet.

## Decision
Use **Delta Lake** for every layer. Rely on its transaction log for ACID, schema
enforcement, **time travel** (diff/restore during incidents), and `MERGE`. Use
the application-level DQ engine for business rules, and add Delta **`NOT NULL` /
`CHECK` constraints** on silver as a **backstop** so a code bug can't write data
that violates a hard invariant.

## Consequences
- Two layers of defence: the DQ gate catches and *quarantines with reasons*
  (rich, auditable); Delta constraints are a last-line guard that *fails the
  write* if something slips past.
- Time travel + lineage make the incident runbook (root-cause, restore) possible.
- `VACUUM` retention must be balanced against how far back time-travel/audit needs
  to reach — we keep the default 7-day floor in mind before shortening it.
