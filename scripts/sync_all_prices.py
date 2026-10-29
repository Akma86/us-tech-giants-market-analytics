"""
Script: sync_all_prices.py
Description: Master price synchronization pipeline that:
  1. Backfills full IPO-to-present daily price history into `us_equities.db` for any
     AI Universe, Safe-Haven Universe, Contagion Supply-Chain, or Knowledge Graph
     tickers that were missing from the local SQLite database.
  2. Incrementally updates all 2,200+ active equities in `us_equities.db` to the
     latest trading session via Yahoo Finance batch downloads.
  3. Updates `tickers` metadata (`first_date`, `last_date`, `total_records`, `sector`, `industry`).
  4. Refreshes raw CSV files (`data/raw/*.csv`) and rebuilds `data/us/prices.parquet`
     and `data/us/stocklens.duckdb` for the StockLens Quantitative & Graph Engines.
"""

from __future__ import annotations

import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import yfinance as yf

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from scripts.db_manager import USStockDatabase
from src.bubble_valuation import AI_UNIVERSE
from src.dotcom_comparison import SAFE_HAVEN_UNIVERSE
from src.bubble_contagion import SUPPLY_CHAIN_SENSITIVITIES

# Metadata mapping for important tickers that may not have been in the initial bulk universe
MISSING_TICKER_METADATA: Dict[str, Tuple[str, str, str]] = {
    "BRK-B": ("Berkshire Hathaway Inc.", "Financials", "Multi-Sector Holdings"),
    "DLR": ("Digital Realty Trust, Inc.", "Real Estate", "Data Center REITs"),
    "GLD": ("SPDR Gold Shares ETF", "Materials", "Gold & Precious Metals"),
    "INTC": ("Intel Corporation", "Information Technology", "Semiconductors"),
    "KR": ("The Kroger Co.", "Consumer Staples", "Food Retail"),
    "LMT": ("Lockheed Martin Corporation", "Industrials", "Aerospace & Defense"),
    "LRCX": ("Lam Research Corporation", "Information Technology", "Semiconductor Equipment"),
    "MDT": ("Medtronic plc", "Health Care", "Health Care Equipment"),
    "MO": ("Altria Group, Inc.", "Consumer Staples", "Tobacco"),
    "MU": ("Micron Technology, Inc.", "Information Technology", "Semiconductors"),
    "NEM": ("Newmont Corporation", "Materials", "Gold"),
    "NOW": ("ServiceNow, Inc.", "Information Technology", "Systems Software"),
    "ORCL": ("Oracle Corporation", "Information Technology", "Systems Software"),
    "PEP": ("PepsiCo, Inc.", "Consumer Staples", "Soft Drinks & Non-alcoholic Beverages"),
    "PGR": ("The Progressive Corporation", "Financials", "Property & Casualty Insurance"),
    "PLTR": ("Palantir Technologies Inc.", "Information Technology", "Application Software"),
    "RTX": ("RTX Corporation", "Industrials", "Aerospace & Defense"),
    "SMCI": ("Super Micro Computer, Inc.", "Information Technology", "Technology Hardware, Storage & Peripherals"),
    "SNOW": ("Snowflake Inc.", "Information Technology", "Internet Services & Infrastructure"),
    "SO": ("The Southern Company", "Utilities", "Electric Utilities"),
    "TSM": ("Taiwan Semiconductor Manufacturing Co.", "Information Technology", "Semiconductors"),
    "VRT": ("Vertiv Holdings Co", "Industrials", "Electrical Components & Equipment"),
    "WM": ("Waste Management, Inc.", "Industrials", "Environmental & Facilities Services"),
}


def chunk_list(lst: List[str], chunk_size: int):
    for i in range(0, len(lst), chunk_size):
        yield lst[i : i + chunk_size]


def backfill_missing_core_tickers(db: USStockDatabase) -> int:
    """Finds any core AI, Safe-Haven, Contagion, or Graph tickers missing from SQLite and backfills full history."""
    entities_csv = PROJECT_ROOT / "data" / "us" / "entities.csv"
    ent_tickers = set()
    if entities_csv.exists():
        df_ent = pd.read_csv(entities_csv)
        ent_tickers = set(
            df_ent[df_ent["entity_type"] == "Company"]["ticker"].dropna().astype(str).str.strip().str.upper()
        )

    required_tickers = (
        set(AI_UNIVERSE.keys())
        | set(SAFE_HAVEN_UNIVERSE.keys())
        | set(SUPPLY_CHAIN_SENSITIVITIES.keys())
        | ent_tickers
    )

    with db.get_connection() as conn:
        existing = {
            r[0] for r in conn.execute("SELECT symbol FROM tickers WHERE total_records > 100").fetchall()
        }

    missing = sorted(required_tickers - existing)
    if not missing:
        print("[+] All core AI, Safe-Haven, and Knowledge Graph tickers already have full history in SQLite.")
        return 0

    print(f"[+] Backfilling full historical daily prices (period='max') for {len(missing)} missing core tickers:")
    print(f"    {', '.join(missing)}")

    data = yf.download(
        tickers=missing,
        period="max",
        group_by="ticker",
        threads=True,
        auto_adjust=False,
        progress=False,
    )

    total_inserted = 0
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    ticker_meta_rows = []

    for sym in missing:
        records = []
        if len(missing) == 1:
            df_sub = data.dropna(subset=["Close"]).reset_index()
        else:
            if sym not in data.columns.levels[0]:
                continue
            df_sub = data[sym].dropna(subset=["Close"]).reset_index()

        if df_sub.empty:
            continue

        for _, r in df_sub.iterrows():
            d_str = str(r.get("Date", ""))[:10]
            if not d_str or pd.isna(r.get("Close")):
                continue
            records.append({
                "symbol": sym,
                "date": d_str,
                "open": r.get("Open"),
                "high": r.get("High"),
                "low": r.get("Low"),
                "close": r.get("Close"),
                "adj_close": r.get("Adj Close", r.get("Close")),
                "volume": int(r.get("Volume", 0)) if pd.notna(r.get("Volume")) else 0,
                "dividends": float(r.get("Dividends", 0.0)) if pd.notna(r.get("Dividends")) else 0.0,
                "stock_splits": float(r.get("Stock Splits", 0.0)) if pd.notna(r.get("Stock Splits")) else 0.0,
            })

        if records:
            df_ins = pd.DataFrame(records)
            inserted = db.insert_daily_prices(df_ins)
            total_inserted += inserted

            default_name = (
                AI_UNIVERSE.get(sym, {}).get("name")
                or SAFE_HAVEN_UNIVERSE.get(sym, {}).get("name")
                or sym
            )
            name, sector, industry = MISSING_TICKER_METADATA.get(
                sym, (default_name, "Information Technology", "Technology")
            )
            etf_flag = "Y" if sym == "GLD" else "N"
            ticker_meta_rows.append((sym, name, "NYSE/NASDAQ", etf_flag, 1, now_iso, sector, industry, "Curated/GICS", now_iso))
            print(f"    -> {sym}: {inserted:,} daily bars inserted ({records[0]['date']} to {records[-1]['date']})")

    if ticker_meta_rows:
        with db.get_connection() as conn:
            conn.executemany(
                """
                INSERT INTO tickers (
                    symbol, security_name, exchange, etf_flag, is_active, last_updated,
                    sector, industry, sector_source, sector_updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    security_name = excluded.security_name,
                    sector = COALESCE(NULLIF(tickers.sector, 'Unclassified'), excluded.sector),
                    industry = COALESCE(NULLIF(tickers.industry, ''), excluded.industry),
                    is_active = 1,
                    last_updated = excluded.last_updated;
                """,
                ticker_meta_rows,
            )

    db.update_ticker_metadata()
    return total_inserted


def update_all_database_prices(db: USStockDatabase, chunk_size: int = 150, lookback_days: int = 10) -> Tuple[int, int]:
    """Incrementally updates all active tickers in `us_equities.db` to the latest trading session."""
    all_tickers = db.get_universe(active_only=True)
    cutoff_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    print(f"\n[+] Synchronizing incremental daily prices for {len(all_tickers):,} tickers since {cutoff_date}...")
    total_chunks = (len(all_tickers) + chunk_size - 1) // chunk_size
    total_rows = 0
    updated_tickers = 0

    for idx, chunk in enumerate(chunk_list(all_tickers, chunk_size), 1):
        try:
            data = yf.download(
                tickers=chunk,
                start=cutoff_date,
                group_by="ticker",
                threads=True,
                auto_adjust=False,
                progress=False,
            )
            if data.empty:
                continue

            records = []
            if len(chunk) == 1:
                sym = chunk[0]
                df_sub = data.dropna(subset=["Close"]).reset_index()
                if not df_sub.empty:
                    updated_tickers += 1
                    for _, r in df_sub.iterrows():
                        d_str = str(r.get("Date", ""))[:10]
                        records.append({
                            "symbol": sym,
                            "date": d_str,
                            "open": r.get("Open"),
                            "high": r.get("High"),
                            "low": r.get("Low"),
                            "close": r.get("Close"),
                            "adj_close": r.get("Adj Close", r.get("Close")),
                            "volume": int(r.get("Volume", 0)) if pd.notna(r.get("Volume")) else 0,
                            "dividends": float(r.get("Dividends", 0.0)) if pd.notna(r.get("Dividends")) else 0.0,
                            "stock_splits": float(r.get("Stock Splits", 0.0)) if pd.notna(r.get("Stock Splits")) else 0.0,
                        })
            else:
                lvl0 = set(data.columns.levels[0])
                for sym in chunk:
                    if sym not in lvl0:
                        continue
                    df_sub = data[sym].dropna(subset=["Close"]).reset_index()
                    if df_sub.empty:
                        continue
                    updated_tickers += 1
                    for _, r in df_sub.iterrows():
                        d_str = str(r.get("Date", ""))[:10]
                        if not d_str:
                            continue
                        records.append({
                            "symbol": sym,
                            "date": d_str,
                            "open": r.get("Open"),
                            "high": r.get("High"),
                            "low": r.get("Low"),
                            "close": r.get("Close"),
                            "adj_close": r.get("Adj Close", r.get("Close")),
                            "volume": int(r.get("Volume", 0)) if pd.notna(r.get("Volume")) else 0,
                            "dividends": float(r.get("Dividends", 0.0)) if pd.notna(r.get("Dividends")) else 0.0,
                            "stock_splits": float(r.get("Stock Splits", 0.0)) if pd.notna(r.get("Stock Splits")) else 0.0,
                        })

            if records:
                inserted = db.insert_daily_prices(pd.DataFrame(records))
                total_rows += inserted
            print(f"    Batch [{idx}/{total_chunks}] processed -> {len(records):,} bars synced (cumulative: {total_rows:,})")
        except Exception as e:
            print(f"    [!] Batch {idx} warning: {e}")

    print("[+] Updating SQLite `tickers` table summary metadata (first_date, last_date, total_records)...")
    db.update_ticker_metadata()
    db.log_pipeline_event("FULL_SYNC_UPDATE", updated_tickers, total_rows, "SUCCESS", "Master sync pipeline")
    return updated_tickers, total_rows


def main():
    t0 = time.time()
    print("=" * 78)
    print("MASTER US EQUITY & STOCKLENS DATABASE SYNCHRONIZATION PIPELINE")
    print("=" * 78)

    db = USStockDatabase()

    # Step 1: Backfill full history for any missing core AI / Safe-Haven / Graph tickers
    backfilled_rows = backfill_missing_core_tickers(db)

    # Step 2: Incrementally update all 2,200+ tickers in SQLite
    updated_tickers, synced_rows = update_all_database_prices(db, chunk_size=150, lookback_days=10)

    # Step 3: Refresh StockLens Parquet & DuckDB (Equities + Commodities + Macro)
    print("\n[+] Rebuilding StockLens Parquet (`data/us/prices.parquet`) & DuckDB (`data/us/stocklens.duckdb`)...")
    from src.ingest_us import build_stocklens_dataset
    build_stocklens_dataset()

    # Step 4: Refresh raw Big-5 Tech CSVs (`data/raw/*.csv`)
    print("\n[+] Refreshing Big-5 Tech raw CSV files (`data/raw/*.csv`)...")
    from scripts.fetch_data import fetch_and_save_stock_data
    fetch_and_save_stock_data()

    elapsed = time.time() - t0
    stats = db.get_database_stats()
    print("\n" + "=" * 78)
    print(f"ALL DATABASES & FILES UPDATED SUCCESSFULLY IN {elapsed:.1f}s")
    print(f"  - Core Missing Tickers Backfilled Bars : {backfilled_rows:,}")
    print(f"  - Active Tickers Refreshed             : {updated_tickers:,}")
    print(f"  - Incremental Bars Synchronized        : {synced_rows:,}")
    print(f"  - Total Registered Tickers in SQLite   : {stats['total_registered_tickers']:,}")
    print(f"  - Total Price Records in SQLite        : {stats['total_price_records']:,}")
    print(f"  - Date Coverage                        : {stats['earliest_date']} -> {stats['latest_date']}")
    print("=" * 78)


if __name__ == "__main__":
    main()

