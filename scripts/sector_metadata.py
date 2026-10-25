"""Sector metadata utilities for the local US equity universe.

Nasdaq's public stock screener exposes a current sector and industry for US
listings.  The screener's labels are normalized to the eleven GICS-style
sectors used in this project before being stored in SQLite.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


NASDAQ_SCREENER_URL = (
    "https://api.nasdaq.com/api/screener/stocks?"
    "tableonly=true&limit=10000&offset=0&download=true"
)
SOURCE_NAME = "Nasdaq public stock screener"

# The display names are intentionally kept in English to match the source data
# and the common GICS convention.  The UI adds the Indonesian labels.
SECTOR_DEFINITIONS = (
    ("Information Technology", "Teknologi Informasi"),
    ("Health Care", "Kesehatan"),
    ("Financials", "Keuangan"),
    ("Consumer Discretionary", "Konsumer Siklikal"),
    ("Consumer Staples", "Konsumer Barang Pokok"),
    ("Energy", "Energi"),
    ("Industrials", "Industri"),
    ("Utilities", "Utilitas"),
    ("Real Estate", "Real Estat"),
    ("Materials", "Material"),
    ("Communication Services", "Layanan Komunikasi"),
)

NASDAQ_TO_PROJECT_SECTOR = {
    "Technology": "Information Technology",
    "Information Technology": "Information Technology",
    "Health Care": "Health Care",
    "Finance": "Financials",
    "Financials": "Financials",
    "Consumer Discretionary": "Consumer Discretionary",
    "Consumer Staples": "Consumer Staples",
    "Energy": "Energy",
    "Industrials": "Industrials",
    "Utilities": "Utilities",
    "Real Estate": "Real Estate",
    "Basic Materials": "Materials",
    "Materials": "Materials",
    "Telecommunications": "Communication Services",
    "Communication Services": "Communication Services",
    "Miscellaneous": "Unclassified",
    "": "Unclassified",
}


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_db_path() -> Path:
    return project_root() / "data" / "database" / "us_equities.db"


def normalize_sector(raw_sector: object) -> str:
    """Convert a Nasdaq sector label to the project's sector taxonomy."""
    return NASDAQ_TO_PROJECT_SECTOR.get(str(raw_sector or "").strip(), "Unclassified")


def download_nasdaq_classifications() -> dict[str, tuple[str, str]]:
    """Return {SYMBOL: (normalized_sector, industry)} from Nasdaq's screener."""
    request = Request(
        NASDAQ_SCREENER_URL,
        headers={
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (compatible; US-Equity-Explorer/1.0)",
        },
    )
    with urlopen(request, timeout=60) as response:
        payload = json.load(response)

    rows = payload.get("data", {}).get("rows", [])
    if not rows:
        raise RuntimeError("Nasdaq screener returned no classification rows.")

    classifications: dict[str, tuple[str, str]] = {}
    for row in rows:
        symbol = str(row.get("symbol", "")).strip().upper()
        if not symbol:
            continue
        classifications[symbol] = (
            normalize_sector(row.get("sector")),
            str(row.get("industry", "")).strip(),
        )
    return classifications


def ensure_sector_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(tickers)")}
    additions = {
        "sector": "TEXT",
        "industry": "TEXT",
        "sector_source": "TEXT",
        "sector_updated_at": "TEXT",
    }
    for name, sql_type in additions.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE tickers ADD COLUMN {name} {sql_type}")


def enrich_database(db_path: Path) -> dict[str, object]:
    """Fetch classifications and write them transactionally into the ticker table."""
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database was not found: {db_path}")

    classifications = download_nasdaq_classifications()
    updated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    with sqlite3.connect(db_path, timeout=60) as conn:
        ensure_sector_columns(conn)
        local_symbols = [row[0] for row in conn.execute("SELECT symbol FROM tickers")]
        updates = []
        for symbol in local_symbols:
            sector, industry = classifications.get(symbol, ("Unclassified", ""))
            updates.append((sector, industry, SOURCE_NAME, updated_at, symbol))
        conn.executemany(
            """
            UPDATE tickers
            SET sector = ?, industry = ?, sector_source = ?, sector_updated_at = ?
            WHERE symbol = ?
            """,
            updates,
        )

    sector_counts = Counter(sector for sector, _, _, _, _ in updates)
    return {
        "database_tickers": len(local_symbols),
        "source_rows": len(classifications),
        "matched_tickers": sum(symbol in classifications for symbol in local_symbols),
        "unclassified_tickers": sector_counts["Unclassified"],
        "sectors": dict(sorted(sector_counts.items())),
        "updated_at": updated_at,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add normalized sector and industry metadata to the local SQLite stock database."
    )
    parser.add_argument("--db", type=Path, default=default_db_path(), help="Path to us_equities.db")
    args = parser.parse_args()

    result = enrich_database(args.db)
    print("Sector metadata update complete")
    print(f"  Database tickers : {result['database_tickers']:,}")
    print(f"  Nasdaq matches   : {result['matched_tickers']:,}")
    print(f"  Unclassified     : {result['unclassified_tickers']:,}")
    print(f"  Updated at (UTC) : {result['updated_at']}")
    for sector, count in result["sectors"].items():
        print(f"  {sector:<26} {count:,}")


if __name__ == "__main__":
    main()
