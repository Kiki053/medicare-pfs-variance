"""Export the dbt marts as Parquet files for Power BI Desktop.

Power BI reads these with Get Data > Parquet. The star schema keeps its
shape: dimensions and facts load as separate tables, and the relationships
are rebuilt in the model view (see powerbi/BUILD_GUIDE.md).

Usage:
    python analysis/export_powerbi.py
"""

from __future__ import annotations

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
OUT = ROOT / "powerbi" / "data"

TABLES = [
    "dim_release",
    "dim_code",
    "dim_locality",
    "fct_rvu",
    "fct_payment",
    "mart_payment_variance",
    "mart_volume_weighted_change",
    "mart_efficiency_adjustment",
    "mart_local_comparison",
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    for table in TABLES:
        target = OUT / f"{table}.parquet"
        con.execute(f"copy (select * from {table}) to '{target}' (format parquet, compression zstd)")
        count = con.execute(f"select count(*) from {table}").fetchone()[0]
        print(f"{table}: {count:,} rows -> {target.relative_to(ROOT)} ({target.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
