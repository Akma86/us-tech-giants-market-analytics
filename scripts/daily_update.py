"""
Script: daily_update.py
Description: Automated incremental daily updater for the 2,000+ US stock database.
             Queries the database for the latest recorded trading day per ticker,
             fetches only missing recent bars from Yahoo Finance, and appends them to SQLite.
Author: Akmal Yaasir Fauzaan
Project: US Tech Giants Market Analytics
"""

import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
from db_manager import USStockDatabase


def chunk_list(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]


def run_daily_update(chunk_size: int = 100, lookback_days: int = 7):
    print("=" * 75)
    print("RUNNING INCREMENTAL DAILY MARKET UPDATE PIPELINE")
    print("=" * 75)

    start_time = time.time()
    db = USStockDatabase()
    latest_dates = db.get_latest_dates_all()
    all_tickers = db.get_universe(active_only=True)

    if not latest_dates:
        print("[!] Database is empty. Please run init_universe.py and download_bulk_universe.py first.")
        return

    # Find the earliest required start date across tickers
    # To be safe against weekend adjustments, fetch from lookback_days ago
    cutoff_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    
    # Identify tickers to update (all active tickers in universe)
    tickers_to_update = [t for t in all_tickers if t in latest_dates]
    print(f"[+] Total active tickers to update: {len(tickers_to_update):,}")
    print(f"[+] Fetching incremental bars since: {cutoff_date}...")

    total_chunks = (len(tickers_to_update) + chunk_size - 1) // chunk_size
    total_new_rows = 0
    updated_tickers_count = 0

    for chunk_idx, chunk in enumerate(chunk_list(tickers_to_update, chunk_size), 1):
        try:
            # Download recent bars for chunk
            data = yf.download(
                tickers=chunk,
                start=cutoff_date,
                group_by="ticker",
                threads=True,
                auto_adjust=False,
                progress=False
            )

            if data.empty:
                continue

            records = []
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
                    updated_tickers_count += 1
            else:
                for sym in chunk:
                    if sym not in data.columns.levels[0]:
                        continue
                    df_sub = data[sym].dropna(subset=["Close"]).reset_index()
                    if df_sub.empty:
                        continue
                    updated_tickers_count += 1
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
                total_new_rows += inserted

        except Exception as e:
            print(f"    [!] Error updating batch {chunk_idx}: {str(e)}")

        time.sleep(0.5)

    # Refresh metadata in database
    db.update_ticker_metadata()
    elapsed = time.time() - start_time
    db.log_pipeline_event("DAILY_UPDATE", updated_tickers_count, total_new_rows, "SUCCESS", f"Elapsed: {elapsed:.1f}s")

    print("\n" + "=" * 75)
    print("DAILY UPDATE COMPLETE")
    print(f"Tickers Refreshed: {updated_tickers_count:,}")
    print(f"Bars Synchronized: {total_new_rows:,}")
    print(f"Total Execution Time: {elapsed:.1f} seconds")

    stats = db.get_database_stats()
    print("\n--- DATABASE CURRENT STATUS ---")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print("=" * 75)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run daily market price update for SQLite database")
    parser.add_argument("--chunk-size", type=int, default=100, help="Batch size for downloads")
    parser.add_argument("--lookback", type=int, default=7, help="Lookback days to synchronize")
    args = parser.parse_args()

    run_daily_update(chunk_size=args.chunk_size, lookback_days=args.lookback)
