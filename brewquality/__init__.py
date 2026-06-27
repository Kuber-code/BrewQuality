"""BrewQuality — a Medallion lakehouse with automated data-quality gates.

A production-style PySpark + Delta Lake pipeline: deliberately "dirty" sales /
logistics data lands in bronze, a data-quality gate validates it across the five
DQ dimensions and quarantines bad records, and clean data builds silver and a
gold dimensional model — orchestrated, tested, and monitored.
"""

__version__ = "0.1.0"
