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


def run_daily_update(
    chunk_size: int = 100,
    lookback_days: int = 7,
    sync_mongo: bool = False,
    mongo_db=None,
    symbols: list = None,
    limit: int = None
):
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
    cutoff_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    
    # Identify tickers to update
    if symbols:
        tickers_to_update = [s.strip().upper() for s in symbols if s.strip().upper() in all_tickers or s.strip().upper() in latest_dates]
    else:
        tickers_to_update = [t for t in all_tickers if t in latest_dates]

    if limit:
        tickers_to_update = tickers_to_update[:limit]

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
                
                # Dual sync to MongoDB if enabled
                if sync_mongo and mongo_db:
                    try:
                        mongo_db.insert_prices_bulk(df_to_insert)
                    except Exception:
                        pass

        except Exception as e:
            print(f"    [!] Error updating batch {chunk_idx}: {str(e)}")

        time.sleep(0.5)

    # Refresh metadata in database
    db.update_ticker_metadata(symbols=tickers_to_update if len(tickers_to_update) <= 100 else None)
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
    
    if sync_mongo and mongo_db:
        print("\n--- MONGODB STATUS ---")
        m_stats = mongo_db.get_stats()
        for k, v in m_stats.items():
            print(f"  {k}: {v}")
    print("=" * 75)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run daily market price update for SQLite database and MongoDB")
    parser.add_argument("--chunk-size", type=int, default=100, help="Batch size for downloads")
    parser.add_argument("--lookback", type=int, default=7, help="Lookback days to synchronize")
    parser.add_argument("--mongo", action="store_true", default=False, help="Also synchronize to local MongoDB")
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated ticker list to update (e.g. AAPL,MSFT,NVDA)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of tickers to update")
    args = parser.parse_args()

    mongo_inst = None
    if args.mongo:
        try:
            from mongo_manager import MongoStockDatabase
            mongo_inst = MongoStockDatabase()
            print("[+] MongoDB integration enabled: mongodb://localhost:27018")
        except Exception as e:
            print(f"[!] Warning: Could not connect to MongoDB: {e}")

    symbols_list = [s.strip().upper() for s in args.symbols.split(",")] if args.symbols else None
    run_daily_update(
        chunk_size=args.chunk_size,
        lookback_days=args.lookback,
        sync_mongo=args.mongo,
        mongo_db=mongo_inst,
        symbols=symbols_list,
        limit=args.limit
    )
