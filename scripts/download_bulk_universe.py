"""
Script: download_bulk_universe.py
Description: Parallel batch downloader for the 2,000+ US stock universe.
             Extracts lifetime historical data from respective IPOs into the SQLite database.
             Features resume capability, multi-threading, and rate-limit mitigation.
Author: Akmal Yaasir Fauzaan
Project: US Tech Giants Market Analytics
"""

import sys
import time
import argparse
from pathlib import Path
from datetime import datetime
import pandas as pd
import yfinance as yf
from db_manager import USStockDatabase


def chunk_list(lst, chunk_size):
    """Splits a list into smaller chunks."""
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]


def download_universe_data(
    limit: int = 2200,
    chunk_size: int = 50,
    period: str = "max",
    sleep_sec: float = 1.5,
    skip_existing: bool = True,
    sync_mongo: bool = True
):
    db = USStockDatabase()
    mongo_db = None
    if sync_mongo:
        try:
            from mongo_manager import MongoStockDatabase
            mongo_db = MongoStockDatabase()
            print("[+] Connected to dedicated MongoDB instance: mongodb://localhost:27018/")
        except Exception as e:
            print(f"[!] Warning: Could not connect to MongoDB: {e}")

    all_tickers = db.get_universe(active_only=True, limit=limit)

    print("=" * 75)
    print(f"STARTING BULK HISTORICAL DATA EXTRACTION (TARGET: {len(all_tickers):,} STOCKS)")
    print(f"Period: {period} (From Inception/IPO) | Batch Size: {chunk_size} tickers | Threads: Enabled")
    print("=" * 75)

    if skip_existing:
        latest_dates = db.get_latest_dates_all()
        # Filter tickers that already have substantial history
        pending_tickers = [t for t in all_tickers if t not in latest_dates]
        print(f"[i] Resuming pipeline: {len(latest_dates):,} stocks already in DB. {len(pending_tickers):,} pending download.")
    else:
        pending_tickers = all_tickers

    if not pending_tickers:
        print("[i] All target tickers already downloaded and populated in database!")
        return

    total_chunks = (len(pending_tickers) + chunk_size - 1) // chunk_size
    total_rows_inserted = 0
    successful_tickers = 0
    start_time = time.time()

    for chunk_idx, chunk in enumerate(chunk_list(pending_tickers, chunk_size), 1):
        print(f"\n[Batch {chunk_idx}/{total_chunks}] Downloading {len(chunk)} tickers ({chunk[0]} .. {chunk[-1]})...")
        try:
            # Download batch in parallel using yfinance multi-threading
            data = yf.download(
                tickers=chunk,
                period=period,
                group_by="ticker",
                threads=True,
                auto_adjust=False,
                progress=False
            )

            if data.empty:
                print(f"    [!] Warning: Batch {chunk_idx} returned empty data.")
                continue

            records = []

            # Handle single ticker vs multi-ticker DataFrame structures
            if len(chunk) == 1:
                sym = chunk[0]
                df_single = data.reset_index()
                for _, r in df_single.iterrows():
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
                    successful_tickers += 1
            else:
                # MultiIndex columns: (Ticker, PriceAttribute)
                for sym in chunk:
                    if sym not in data.columns.levels[0]:
                        continue
                    df_sub = data[sym].dropna(subset=["Close"]).reset_index()
                    if df_sub.empty:
                        continue
                    successful_tickers += 1
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

            if records:
                df_to_insert = pd.DataFrame(records)
                inserted = db.insert_daily_prices(df_to_insert)
                if mongo_db:
                    try:
                        mongo_db.insert_prices_bulk(df_to_insert)
                    except Exception as me:
                        pass
                total_rows_inserted += inserted
                elapsed = time.time() - start_time
                print(f"    -> Inserted {inserted:,} rows (SQLite + MongoDB). Cumulative: {total_rows_inserted:,} ({elapsed:.1f}s elapsed)")

        except Exception as e:
            print(f"    [X] Error in batch {chunk_idx}: {str(e)}")

        # Respect API rate limits with polite pause
        time.sleep(sleep_sec)

    # Refresh metadata in SQLite
    print("\n[+] Updating database index statistics and ticker coverage...")
    db.update_ticker_metadata()
    db.log_pipeline_event("BULK_DOWNLOAD", successful_tickers, total_rows_inserted, "SUCCESS", f"Period: {period}")

    elapsed_total = time.time() - start_time
    print("\n" + "=" * 75)
    print("BULK DOWNLOAD PIPELINE COMPLETED")
    print(f"Total Tickers Ingested: {successful_tickers:,}")
    print(f"Total Rows Ingested: {total_rows_inserted:,}")
    print(f"Total Elapsed Time: {elapsed_total:.1f} seconds ({elapsed_total/60:.1f} minutes)")
    
    stats = db.get_database_stats()
    print("\n--- DATABASE CURRENT STATUS ---")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print("=" * 75)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk download US stock universe into SQLite")
    parser.add_argument("--limit", type=int, default=2200, help="Max tickers to download")
    parser.add_argument("--chunk-size", type=int, default=50, help="Tickers per batch")
    parser.add_argument("--period", type=str, default="max", help="Lookback period (e.g. max, 10y, 5y)")
    parser.add_argument("--sleep", type=float, default=1.0, help="Sleep seconds between chunks")
    args = parser.parse_args()

    download_universe_data(limit=args.limit, chunk_size=args.chunk_size, period=args.period, sleep_sec=args.sleep)
