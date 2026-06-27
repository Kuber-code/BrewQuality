"""Central configuration: lakehouse layout and layer paths.

Locally the "lakehouse" is just a folder of Delta tables under ``data/lake``.
On Databricks the same logical names map to Unity Catalog
(``catalog.schema.table``) — see ``databricks/`` and the README. Keeping paths in
one place means the transformation code never hard-codes a location.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Repo root = two levels up from this file (brewquality/config.py -> repo root).
REPO_ROOT = Path(__file__).resolve().parents[1]

# Allow overriding the data root (e.g. /dbfs or an ADLS mount) via env var.
DATA_ROOT = Path(os.environ.get("BREWQUALITY_DATA_ROOT", REPO_ROOT / "data"))

RAW_DIR = DATA_ROOT / "raw"
LAKE_DIR = DATA_ROOT / "lake"


@dataclass(frozen=True)
class Layer:
    """A Medallion layer + the Delta tables that live in it."""

    name: str

    def path(self, table: str) -> str:
        return str(LAKE_DIR / self.name / table)


BRONZE = Layer("bronze")
SILVER = Layer("silver")
GOLD = Layer("gold")
# Quarantine sits beside silver: failing rows routed here instead of dropped.
QUARANTINE = Layer("quarantine")
# Operational metrics (DQ KPIs per rule, per run) — the observability layer.
OPS = Layer("ops")

# Logical table names (kept stable across local + Databricks).
RAW_ORDERS = "orders"
RAW_CUSTOMERS = "customers"
RAW_PRODUCTS = "products"

DQ_METRICS_TABLE = "dq_metrics"
