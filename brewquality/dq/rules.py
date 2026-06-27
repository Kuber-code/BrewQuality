"""Declarative data-quality rules, organised by DQ dimension.

A rule is a *testable assertion + a dimension + a severity*:

    severity = "error"  -> hard rule: failing rows are quarantined (blocked).
    severity = "warn"   -> soft rule: row passes but is flagged + counted (alert
                           if the failure rate spikes). We don't halt a pipeline
                           on benign anomalies.

``passes`` returns a Spark Column that is **True when the row satisfies the
rule**. Row-level rules read source columns directly; relational rules
(uniqueness, referential integrity) read *derived* boolean columns that
``prepare.py`` computes first (via window / join) — keeping every rule a simple,
unit-testable boolean expression.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pyspark.sql import Column
from pyspark.sql import functions as F

# The five (+timeliness) DQ dimensions the JD cares about.
COMPLETENESS = "completeness"
VALIDITY = "validity"
UNIQUENESS = "uniqueness"
CONSISTENCY = "consistency"
INTEGRITY = "integrity"
ACCURACY = "accuracy"


@dataclass(frozen=True)
class Rule:
    name: str
    dimension: str
    severity: str  # "error" | "warn"
    description: str
    passes: Callable[[], Column]

    @property
    def is_hard(self) -> bool:
        return self.severity == "error"


def _non_blank(col: str) -> Column:
    c = F.col(col)
    return c.isNotNull() & (F.trim(c) != F.lit(""))


# Rules for the orders fact table. Derived columns used here
# (quantity_int, order_amount_dbl, order_date_parsed, _is_duplicate,
#  _product_exists, _customer_exists) are produced by prepare.prepare_orders().
ORDER_RULES: list[Rule] = [
    Rule(
        "completeness_customer_id",
        COMPLETENESS,
        "error",
        "customer_id must be present (non-null, non-blank).",
        lambda: _non_blank("customer_id"),
    ),
    Rule(
        "completeness_order_amount",
        COMPLETENESS,
        "error",
        "order_amount must be present and parse to a number.",
        lambda: F.col("order_amount_dbl").isNotNull(),
    ),
    Rule(
        "validity_quantity_positive",
        VALIDITY,
        "error",
        "quantity must parse to an integer > 0.",
        lambda: F.col("quantity_int") > 0,
    ),
    Rule(
        "validity_order_date",
        VALIDITY,
        "error",
        "order_date must be a parseable calendar date.",
        lambda: F.col("order_date_parsed").isNotNull(),
    ),
    Rule(
        "uniqueness_order_id",
        UNIQUENESS,
        "error",
        "order_id must be unique across the batch.",
        lambda: ~F.col("_is_duplicate"),
    ),
    Rule(
        "integrity_product_id",
        INTEGRITY,
        "error",
        "product_id must exist in the product dimension.",
        lambda: F.col("_product_exists"),
    ),
    Rule(
        "integrity_customer_id",
        INTEGRITY,
        "error",
        "customer_id must exist in the customer dimension.",
        lambda: F.col("_customer_exists"),
    ),
    Rule(
        "accuracy_amount_matches",
        ACCURACY,
        "warn",  # soft: known to drift with manual discounts/fees — flag, don't block.
        "order_amount should equal quantity * unit_price (±0.01).",
        lambda: F.abs(
            F.col("order_amount_dbl") - (F.col("quantity_int") * F.col("unit_price_dbl"))
        )
        <= F.lit(0.01),
    ),
]
