# ADR-0002: A small in-repo DQ engine instead of adopting a framework

**Status:** Accepted

## Context
The DQ gate could be built on Databricks **DQX**, **Great Expectations**, **Soda**,
or **PyDeequ** — all of which do rules + quarantine/metrics. We need something
that (a) is easy to unit-test in CI, (b) maps cleanly onto the five DQ
dimensions, and (c) is transparent for an interview/portfolio.

## Decision
Hand-roll a ~100-line PySpark engine (`brewquality/dq/`): rules are declarative
`Rule` objects (name, dimension, severity, boolean expression); the engine
evaluates them, splits clean/quarantine, and emits per-rule metrics.

## Consequences
- **Pro:** zero extra dependencies, trivially unit-testable, the dimension model
  is explicit, and the code reads as documentation of *what* DQ means here.
- **Pro:** the pattern is identical to DQX/GX, so migrating to one later is
  mechanical — rules already carry dimension + severity.
- **Con:** we don't get a framework's profiling, data-docs UI, or expectation
  library for free. For this scope that's fine; at enterprise scale you'd adopt
  a platform (e.g. **Ataccama ONE**) for governed, business-authored rules and
  keep code-based checks shifted-left in CI alongside it.

See also: [0003](0003-quarantine-not-drop.md), [0004](0004-hard-vs-soft-rules.md).
