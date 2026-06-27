"""Unit tests for the DQ gate: each rule fires on the defect it targets.

Treating DQ rules as testable artifacts is the point — these tests prove every
dimension's rule catches its defect and that clean rows pass untouched. They run
on tiny hand-built DataFrames, so they're fast and CI-friendly.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from brewquality.dq import engine
from brewquality.dq.prepare import prepare_orders
from brewquality.dq.rules import ORDER_RULES
from tests.helpers import make_df

TS = datetime(2025, 1, 1, 0, 0, 0)


def _orders(spark, rows):
    """Build a bronze-shaped orders DF (all strings + audit cols)."""
    cols = ["order_id", "customer_id", "product_id", "quantity", "unit_price",
            "order_amount", "order_date"]
    data = [{**dict(zip(cols, r)), "_ingested_at": TS, "_source_file": "t.csv"} for r in rows]
    return make_df(spark, data)


def _dims(spark):
    products = make_df(
        spark,
        [{"product_id": "P001", "product_name": "Lager", "category": "Beer", "unit_price": 1.2}],
    )
    customers = make_df(
        spark,
        [{"customer_id": "C00001", "name": "A", "company": "X", "country": "PL"}],
    )
    return products, customers


def _evaluate(spark, rows):
    products, customers = _dims(spark)
    prepared = prepare_orders(_orders(spark, rows), products, customers)
    return engine.evaluate(prepared, ORDER_RULES)


def _failed_rules(evaluated, order_id):
    row = evaluated.filter(f"order_id = '{order_id}'").select("_dq_failed_rules").first()
    return set(row["_dq_failed_rules"])


# A clean, fully-valid order — the control case.
GOOD = ("O1", "C00001", "P001", "2", "1.2", "2.4", "2025-01-15")


def test_clean_row_passes(spark):
    evaluated = _evaluate(spark, [GOOD])
    assert _failed_rules(evaluated, "O1") == set()


@pytest.mark.parametrize(
    "row, expected_rule",
    [
        (("O2", "", "P001", "2", "1.2", "2.4", "2025-01-15"), "completeness_customer_id"),
        (("O3", "C00001", "P001", "2", "1.2", "", "2025-01-15"), "completeness_order_amount"),
        (("O4", "C00001", "P001", "-2", "1.2", "-2.4", "2025-01-15"), "validity_quantity_positive"),
        (("O5", "C00001", "P001", "2", "1.2", "2.4", "2025-13-40"), "validity_order_date"),
        (("O6", "C00001", "P999", "2", "1.2", "2.4", "2025-01-15"), "integrity_product_id"),
        (("O7", "C99999", "P001", "2", "1.2", "2.4", "2025-01-15"), "integrity_customer_id"),
    ],
)
def test_each_dimension_rule_fires(spark, row, expected_rule):
    evaluated = _evaluate(spark, [row])
    assert expected_rule in _failed_rules(evaluated, row[0])


def test_uniqueness_keeps_one_quarantines_extra(spark):
    # Same order_id twice: first kept clean, the duplicate flagged.
    dup = ("O8", "C00001", "P001", "2", "1.2", "2.4", "2025-01-15")
    evaluated = _evaluate(spark, [dup, dup])
    ranks = {
        r["_dup_rank"]: set(r["_dq_failed_rules"])
        for r in evaluated.filter("order_id = 'O8'").select("_dup_rank", "_dq_failed_rules").collect()
    }
    assert ranks[1] == set()  # first survives
    assert "uniqueness_order_id" in ranks[2]  # extra quarantined


def test_accuracy_is_soft_warns_but_passes(spark):
    # amount != qty*price -> warning, but row is NOT quarantined (soft rule).
    bad_amount = ("O9", "C00001", "P001", "2", "1.2", "9.99", "2025-01-15")
    evaluated = _evaluate(spark, [bad_amount])
    assert _failed_rules(evaluated, "O9") == set()  # no hard failure
    warnings = set(evaluated.filter("order_id = 'O9'").select("_dq_warnings").first()["_dq_warnings"])
    assert "accuracy_amount_matches" in warnings


def test_split_routes_clean_and_quarantine(spark):
    bad = ("O10", "", "P001", "2", "1.2", "2.4", "2025-01-15")
    evaluated = _evaluate(spark, [GOOD, bad])
    clean, quarantine = engine.split(evaluated)
    assert {r["order_id"] for r in clean.select("order_id").collect()} == {"O1"}
    q = quarantine.select("order_id", "_dq_reason").first()
    assert q["order_id"] == "O10"
    assert "completeness_customer_id" in q["_dq_reason"]


def test_metrics_one_row_per_rule(spark):
    evaluated = _evaluate(spark, [GOOD])
    metrics = engine.compute_metrics(evaluated, ORDER_RULES, run_id="r1", dataset="orders")
    assert metrics.count() == len(ORDER_RULES)
    assert metrics.filter("rule_name = 'completeness_customer_id'").first()["pass_rate"] == 1.0
