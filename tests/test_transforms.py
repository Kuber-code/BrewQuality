"""Unit tests for transformation logic (no I/O): customer conform + prepare casts."""

from __future__ import annotations

from datetime import datetime

from brewquality.dq.prepare import prepare_orders
from brewquality.silver import conform_customers
from tests.helpers import make_df

TS = datetime(2025, 1, 1)


def test_conform_customers_standardises_country(spark):
    df = make_df(
        spark,
        [
            {"customer_id": "C1", "name": "A", "company": "X", "country": "Poland"},
            {"customer_id": "C2", "name": "B", "company": "Y", "country": "pl"},
            {"customer_id": "C3", "name": "C", "company": "Z", "country": "NL"},
            {"customer_id": "C4", "name": "D", "company": "W", "country": "Germany"},
        ],
    )
    out = {r["customer_id"]: r["country"] for r in conform_customers(df).collect()}
    assert out == {"C1": "PL", "C2": "PL", "C3": "NL", "C4": "DE"}


def test_prepare_casts_bad_values_to_null(spark):
    orders = make_df(
        spark,
        [
            {"order_id": "O1", "customer_id": "C1", "product_id": "P1",
             "quantity": "abc", "unit_price": "1.2", "order_amount": "x",
             "order_date": "2025-13-40", "_ingested_at": TS, "_source_file": "t"},
        ],
    )
    products = make_df(spark, [{"product_id": "P1"}])
    customers = make_df(spark, [{"customer_id": "C1"}])
    row = prepare_orders(orders, products, customers).first()
    assert row["quantity_int"] is None
    assert row["order_amount_dbl"] is None
    assert row["order_date_parsed"] is None
    assert row["_product_exists"] is True
    assert row["_customer_exists"] is True
