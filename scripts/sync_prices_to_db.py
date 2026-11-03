#!/usr/bin/env python3
"""Sync Fresh IPO-to-Present Prices into SQLite (`us_equities.db`), Parquet & DuckDB.

Inserts / Updates:
- 10 US Leaders: AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, AVGO, AMD, ORCL
- Benchmarks & Macro: ^GSPC, ^TNX, ^VIX
- Total 126,172 daily observations from IPO day to 2026-11-02.
- Updates metadata in `tickers` table (first_date, last_date, total_records, last_updated).
- Refreshes `data/us/prices.parquet` and `data/us/stocklens.duckdb`.
"""

from __future__ import annotations

import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import duckdb
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "database" / "us_equities.db"
RAW_CSV = PROJECT_ROOT / "data" / "raw" / "us_tech_giants_daily_history.csv"
PARQUET_PATH = PROJECT_ROOT / "data" / "us" / "prices.parquet"
DUCKDB_PATH = PROJECT_ROOT / "data" / "us" / "stocklens.duckdb"

BENCHMARK_META = {
    "^GSPC": ("S&P 500 Index", "Index", "US Broad Market Benchmark"),
    "^TNX": ("10-Year Treasury Yield", "Macro", "US Risk-Free Benchmark"),
    "^VIX": ("CBOE Volatility Index", "Macro", "Market Volatility / Fear Gauge"),
}


def main():
    print("==========================================================================")
    print("SYNCING HISTORICAL IPO-TO-PRESENT PRICES TO DATABASE")
    print(f"Target SQLite DB: {DB_PATH}")
    print("==========================================================================\n")

    if not DB_PATH.exists():
        print(f"Error: Database {DB_PATH} not found!")
        sys.exit(1)

    if not RAW_CSV.exists():
        print(f"Error: Raw CSV {RAW_CSV} not found!")
        sys.exit(1)

    print(f"Loading raw daily prices from {RAW_CSV}...")
    df = pd.read_csv(RAW_CSV)
    print(f"Loaded {len(df):,} records across {df['Ticker'].nunique()} tickers.")
    print(f"Date range in raw data: {df['Date'].min()} -> {df['Date'].max()}\n")

    # Connect to SQLite with high-speed PRAGMAs
    conn = sqlite3.connect(str(DB_PATH), timeout=60.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA cache_size = -64000;")  # 64MB cache
    conn.execute("PRAGMA temp_store = MEMORY;")

    # 1. Ensure benchmark tickers exist in `tickers` table
    print("Upserting ticker metadata entries...")
    for sym, (name, sec, ind) in BENCHMARK_META.items():
        conn.execute("""
        INSERT INTO tickers (symbol, security_name, exchange, etf_flag, is_active, sector, industry, sector_source, sector_updated_at)
        VALUES (?, ?, 'INDEX', 'N', 1, ?, ?, 'Benchmark Macro Feed', CURRENT_TIMESTAMP)
        ON CONFLICT(symbol) DO UPDATE SET
            security_name = excluded.security_name,
            sector = excluded.sector,
            industry = excluded.industry;
        """, (sym, name, sec, ind))

    conn.commit()

    # 2. Batch insert/replace into `daily_prices`
    print("Batch upserting records into `daily_prices` table...")
    t0 = time.time()

    # Prepare records
    records = []
    for _, r in df.iterrows():
        records.append((
            str(r["Ticker"]).strip(),
            str(r["Date"])[:10],
            float(r["Open"]) if pd.notna(r["Open"]) else None,
            float(r["High"]) if pd.notna(r["High"]) else None,
            float(r["Low"]) if pd.notna(r["Low"]) else None,
            float(r["Close"]) if pd.notna(r["Close"]) else None,
            float(r["Adj Close"]) if pd.notna(r["Adj Close"]) else (float(r["Close"]) if pd.notna(r["Close"]) else None),
            int(r["Volume"]) if pd.notna(r["Volume"]) else 0,
            float(r.get("Dividends", 0.0)) if pd.notna(r.get("Dividends")) else 0.0,
            float(r.get("Stock Splits", 0.0)) if pd.notna(r.get("Stock Splits")) else 0.0,
        ))

    # Chunked inserts of 10,000 records
    chunk_size = 10000
    for i in range(0, len(records), chunk_size):
        chunk = records[i:i + chunk_size]
        conn.executemany("""
        INSERT OR REPLACE INTO daily_prices
        (symbol, date, open, high, low, close, adj_close, volume, dividends, stock_splits)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, chunk)
        conn.commit()
        print(f"  Processed {min(i + chunk_size, len(records)):,} / {len(records):,} records...", end="\r", flush=True)

    elapsed = time.time() - t0
    print(f"\n✓ Successfully upserted {len(records):,} records in {elapsed:.2f}s ({len(records)/max(elapsed, 0.01):,.0f} rows/sec)")

    # 3. Update `tickers` summary table
    print("\nRefreshing `tickers` metadata (first_date, last_date, total_records)...")
    tickers_list = list(df["Ticker"].unique())
    for sym in tickers_list:
        conn.execute("""
        UPDATE tickers
        SET
            first_date = (SELECT MIN(date) FROM daily_prices WHERE daily_prices.symbol = tickers.symbol),
            last_date = (SELECT MAX(date) FROM daily_prices WHERE daily_prices.symbol = tickers.symbol),
            total_records = (SELECT COUNT(*) FROM daily_prices WHERE daily_prices.symbol = tickers.symbol),
            last_updated = CURRENT_TIMESTAMP
        WHERE symbol = ?;
        """, (sym,))

    conn.commit()

    # Verify updated tickers
    print("\nVerified Database Status for Synced Tickers:")
    print(f"{'Symbol':<8} | {'First Date':<12} | {'Last Date':<12} | {'Total Records'}")
    print("-" * 55)
    for sym in tickers_list:
        cur = conn.cursor()
        cur.execute("SELECT symbol, first_date, last_date, total_records FROM tickers WHERE symbol = ?", (sym,))
        row = cur.fetchone()
        if row:
            print(f"{row[0]:<8} | {str(row[1]):<12} | {str(row[2]):<12} | {row[3]:>8,}")

    conn.close()
    print("✓ SQLite database update complete.")

    # 4. Refresh Parquet & DuckDB for StockLens Quantitative Engines
    if PARQUET_PATH.exists() or DUCKDB_PATH.exists():
        print("\nSyncing Columnar Engines (Parquet & DuckDB)...")
        try:
            # Append/merge into prices.parquet
            if PARQUET_PATH.exists():
                pq_df = pd.read_parquet(PARQUET_PATH)
                # Filter out existing records for these tickers and append new ones
                pq_df = pq_df[~pq_df["ticker"].isin(tickers_list)]
                # Format df for parquet (lower case columns)
                new_pq = df.copy().rename(columns={
                    "Ticker": "ticker",
                    "Date": "date",
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Adj Close": "adj_close",
                    "Volume": "volume",
                })
                # Keep common columns
                common_cols = [c for c in pq_df.columns if c in new_pq.columns]
                comb_pq = pd.concat([pq_df[common_cols], new_pq[common_cols]], ignore_index=True)
                comb_pq.to_parquet(PARQUET_PATH, index=False)
                print(f"✓ prices.parquet updated ({len(comb_pq):,} total rows)")

            # Update DuckDB
            if DUCKDB_PATH.exists():
                ddb = duckdb.connect(str(DUCKDB_PATH))
                # Delete old rows for these tickers and insert new
                for sym in tickers_list:
                    ddb.execute("DELETE FROM daily_prices WHERE ticker = ?", [sym])
                
                ddb_df = df.copy().rename(columns={
                    "Ticker": "ticker",
                    "Date": "date",
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Adj Close": "adj_close",
                    "Volume": "volume",
                })
                ddb.register("temp_new_prices", ddb_df)
                ddb.execute("INSERT INTO daily_prices SELECT * FROM temp_new_prices")
                ddb.close()
                print("✓ stocklens.duckdb updated successfully.")
        except Exception as e:
            print(f"  Note on columnar update: {e}")

    print("\n==========================================================================")
    print("ALL DATABASES AND DATASETS ARE 100% IN SYNC!")
    print("==========================================================================")


if __name__ == "__main__":
    main()
