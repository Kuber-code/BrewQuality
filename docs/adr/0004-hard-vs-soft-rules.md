# ADR-0004: Distinguish hard (blocking) from soft (alerting) rules

**Status:** Accepted

## Context
Not every anomaly should stop a pipeline. A missing `customer_id` makes a row
unusable; an `order_amount` that differs from `quantity * unit_price` by a few
cents might be a legitimate manual discount or fee. Treating both the same either
halts pipelines on benign noise or lets real corruption through.

## Decision
Every rule carries a **severity**:
- **`error` (hard)** — row is quarantined (e.g. completeness, validity,
  uniqueness, referential integrity).
- **`warn` (soft)** — row passes to silver but is flagged in `dq_warnings` and
  counted; alert if the failure *rate* spikes (e.g. accuracy/amount-mismatch).

## Consequences
- Pipelines don't break on benign anomalies, but those anomalies are still
  visible and trended.
- Severity is data, not code branching — re-classifying a rule is a one-line
  change, and metrics distinguish the two classes automatically.
- Alerting (`dq_report --alert`) keys off hard-rule SLAs; soft rules drive
  trend-based alerts instead of hard gates.
