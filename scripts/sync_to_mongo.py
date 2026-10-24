"""
Script: sync_to_mongo.py
Description: Synchronizes all market datasets (tickers, historical prices, and earnings announcements)
             from local SQLite / CSV storage directly into MongoDB (mongodb://localhost:27017).
Author: Akmal Yaasir Fauzaan
Project: US Tech Giants Market Analytics
"""

import sqlite3
import time
from pathlib import Path
import pandas as pd
from mongo_manager import MongoStockDatabase
from db_manager import get_default_db_path, get_project_root


def sync_all_data_to_mongodb():
    print("=" * 75)
    print("SYNCHRONIZING US EQUITIES DATASET TO MONGODB")
    print("Target Instance: mongodb://localhost:27018 | Database: us_equities_db")
    print("=" * 75)

    start_time = time.time()
    mongo = MongoStockDatabase()
    sqlite_path = get_default_db_path()
    root = get_project_root()

    # 1. Sync Tickers
    print("\n[1/3] Syncing Tickers Metadata to MongoDB...")
    if sqlite_path.exists():
        with sqlite3.connect(sqlite_path) as conn:
            df_tickers = pd.read_sql_query("SELECT symbol, security_name, exchange, etf_flag FROM tickers;", conn)
        
        if not df_tickers.empty:
            count_t = mongo.insert_tickers_bulk(df_tickers)
            print(f"      -> Successfully upserted {count_t:,} tickers into MongoDB.")
    
    # 2. Sync Earnings History
    print("\n[2/3] Syncing Historical Earnings Calendar to MongoDB...")
    earnings_file = root / "data" / "raw" / "us_tech_giants_earnings_history.csv"
    if earnings_file.exists():
        df_earnings = pd.read_csv(earnings_file)
        count_e = mongo.insert_earnings_bulk(df_earnings)
        print(f"      -> Successfully upserted {count_e:,} earnings reports into MongoDB.")

    # 3. Sync Daily Prices
    print("\n[3/3] Syncing Daily Price History to MongoDB...")
    if sqlite_path.exists():
        with sqlite3.connect(sqlite_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM daily_prices;")
            total_rows = cursor.fetchone()[0]
            print(f"      Reading {total_rows:,} daily price records from SQLite...")
            
            # Read and stream in chunks of 50,000 rows
            chunk_size = 50000
            offset = 0
            total_synced = 0
            while offset < total_rows:
                df_chunk = pd.read_sql_query(
                    f"SELECT symbol, date, open, high, low, close, adj_close, volume, dividends, stock_splits FROM daily_prices LIMIT {chunk_size} OFFSET {offset};",
                    conn
                )
                if df_chunk.empty:
                    break
                synced = mongo.insert_prices_bulk(df_chunk, batch_size=5000)
                total_synced += synced
                offset += chunk_size
                print(f"      -> Synced {total_synced:,} / {total_rows:,} rows to MongoDB...")

    elapsed = time.time() - start_time
    stats = mongo.get_stats()
    print("\n" + "=" * 75)
    print("MONGODB SYNCHRONIZATION COMPLETED")
    print(f"Elapsed Time: {elapsed:.1f} seconds")
    print("\n--- MONGODB COLLECTION INVENTORY ---")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print("=" * 75)


if __name__ == "__main__":
    sync_all_data_to_mongodb()
