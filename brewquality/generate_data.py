"""Generate a realistic, multi-table sales dataset with *controlled* defects.

The whole point of a DQ project is having defects to catch. We generate clean
data, then deliberately inject errors so every DQ dimension has work to do:

    completeness  -> null required fields (customer_id, order_amount)
    validity      -> quantity <= 0, unparseable dates, negative amount
    uniqueness    -> duplicated order_id
    consistency   -> country written inconsistently (PL / Poland / pl)
    integrity     -> order references a product_id / customer_id that doesn't exist
    accuracy      -> order_amount != quantity * unit_price

Run:  python -m brewquality.generate_data --orders 5000 --seed 42
Output: CSV/JSON under data/raw/ (gitignored — regenerate any time).
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

from faker import Faker

from brewquality.config import RAW_DIR

# A small, fixed product catalogue with a beer/SKU flavour (nod to HEINEKEN).
PRODUCTS = [
    ("P001", "Lager 330ml", "Beer", 1.20),
    ("P002", "Lager 500ml", "Beer", 1.80),
    ("P003", "IPA 330ml", "Beer", 1.60),
    ("P004", "Stout 440ml", "Beer", 2.10),
    ("P005", "Pilsner 330ml", "Beer", 1.40),
    ("P006", "Radler 330ml", "Beer", 1.30),
    ("P007", "Alc-Free 330ml", "Beer", 1.25),
    ("P008", "Cider 500ml", "Cider", 1.90),
]

# Valid ISO country codes we *intend* to use.
COUNTRIES = ["PL", "NL", "DE", "GB", "FR", "ES", "IT"]
# Inconsistent variants we inject so the consistency rule has something to flag.
COUNTRY_NOISE = {"PL": ["Poland", "pl", "POL"], "NL": ["Netherlands", "nl"], "DE": ["Germany", "de"]}


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def generate(n_orders: int, n_customers: int, seed: int, out_dir: Path) -> None:
    fake = Faker()
    Faker.seed(seed)
    random.seed(seed)

    # --- customers (clean dimension, but a few get a noisy country) ---
    customers = []
    for i in range(1, n_customers + 1):
        cust_id = f"C{i:05d}"
        country = random.choice(COUNTRIES)
        # ~8% of customers get an inconsistent country spelling.
        if random.random() < 0.08 and country in COUNTRY_NOISE:
            country = random.choice(COUNTRY_NOISE[country])
        customers.append([cust_id, fake.name(), fake.company(), country])
    _write_csv(out_dir / "customers.csv", ["customer_id", "name", "company", "country"], customers)
    valid_customer_ids = [c[0] for c in customers]

    # --- products (clean reference table, written as JSON to vary the format) ---
    products = [
        {"product_id": p, "product_name": n, "category": c, "unit_price": price}
        for (p, n, c, price) in PRODUCTS
    ]
    (out_dir / "products.json").write_text(json.dumps(products, indent=2), encoding="utf-8")
    valid_product_ids = [p[0] for p in PRODUCTS]
    price_by_product = {p[0]: p[3] for p in PRODUCTS}

    # --- orders (the fact table — this is where we inject most defects) ---
    rows: list[list] = []
    order_seq = 0
    for _ in range(n_orders):
        order_seq += 1
        order_id = f"O{order_seq:07d}"
        cust_id = random.choice(valid_customer_ids)
        product_id = random.choice(valid_product_ids)
        qty = random.randint(1, 24)
        unit_price = price_by_product[product_id]
        amount = round(qty * unit_price, 2)
        order_date = fake.date_between(start_date="-90d", end_date="today").isoformat()

        # ---- inject controlled defects ----
        r = random.random()
        if r < 0.04:  # completeness: missing customer_id
            cust_id = ""
        elif r < 0.08:  # completeness: missing amount
            amount = ""
        elif r < 0.11:  # validity: negative / zero quantity
            qty = -qty if qty else -1
            amount = round(qty * unit_price, 2)
        elif r < 0.14:  # validity: unparseable date
            order_date = "2025-13-40"
        elif r < 0.17:  # integrity: product that isn't in the catalogue
            product_id = "P999"
        elif r < 0.19:  # integrity: customer that doesn't exist
            cust_id = "C99999"
        elif r < 0.22:  # accuracy: amount doesn't match qty * unit_price
            amount = round(amount * 1.5, 2)

        rows.append([order_id, cust_id, product_id, qty, unit_price, amount, order_date])

        # uniqueness: ~1.5% chance to emit the *same* order_id twice.
        if random.random() < 0.015:
            rows.append([order_id, cust_id, product_id, qty, unit_price, amount, order_date])

    _write_csv(
        out_dir / "orders.csv",
        ["order_id", "customer_id", "product_id", "quantity", "unit_price", "order_amount", "order_date"],
        rows,
    )

    print(f"Wrote {len(customers)} customers, {len(products)} products, {len(rows)} order rows to {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate dirty sales data for BrewQuality.")
    parser.add_argument("--orders", type=int, default=5000, help="approx number of orders")
    parser.add_argument("--customers", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=RAW_DIR)
    args = parser.parse_args()
    generate(args.orders, args.customers, args.seed, args.out)


if __name__ == "__main__":
    main()
