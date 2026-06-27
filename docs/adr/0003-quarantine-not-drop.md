# ADR-0003: Quarantine failing rows instead of dropping them

**Status:** Accepted

## Context
Rows that fail a hard rule must not reach silver. The simplest option is to drop
them — but a silent drop destroys evidence and makes "where did my row go?"
unanswerable.

## Decision
Route failing rows to a separate **`quarantine.orders`** Delta table, tagged with
the **failed rule names**, a human-readable **reason**, and the **run_id** —
instead of discarding them.

## Consequences
- **Auditable**: we can always answer *what* failed and *why*, per run.
- **Remediable**: fix the source or the rule, then reprocess — quarantine is the
  work queue for issue remediation (directly the JD's "issue remediation").
- **Measurable**: quarantine counts per rule feed the DQ KPIs.
- Costs a little storage and one extra write; negligible versus the audit value.
- Duplicates use the same path: the first occurrence stays clean, extra copies
  are quarantined (not dropped), so dedup is auditable too.
