"""
Script: init_universe.py
Description: Builds the US stock universe of >2,000 common equities using the official
             NASDAQ traded directory and populates the SQLite database.
             Also migrates existing Big 5 historical prices into the database.
Author: Akmal Yaasir Fauzaan
Project: US Tech Giants Market Analytics
"""

import re
import urllib.request
from pathlib import Path
import pandas as pd
from db_manager import USStockDatabase, get_project_root

NASDAQ_TRADED_URL = "http://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"


def build_and_populate_universe(target_count: int = 2500) -> pd.DataFrame:
    print("=" * 75)
    print("INITIALIZING US EQUITY UNIVERSE (>2,000 STOCKS)")
    print("=" * 75)

    print(f"[+] Fetching live US securities directory from {NASDAQ_TRADED_URL}...")
    req = urllib.request.Request(NASDAQ_TRADED_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        df_raw = pd.read_csv(resp, sep="|")

    print(f"    Raw records received: {len(df_raw):,} listings")

    # Filter out footer rows (e.g. File Creation Time)
    df_raw = df_raw.dropna(subset=["Symbol", "Security Name"])

    # Filter out test issues and ETFs
    is_not_test = df_raw["Test Issue"] == "N"
    is_not_etf = df_raw.get("ETF", "N") == "N"
    
    # Filter for standard common stock ticker symbols (letters only, length 1-5)
    # Exclude warrants (W), units (U), rights (R), preferreds
    valid_symbol = df_raw["Symbol"].apply(lambda s: bool(re.match(r"^[A-Z]{1,5}$", str(s))))
    not_warrant_unit = ~df_raw["Symbol"].str.endswith(("W", "WS", "U", "R", "P", "Q", "Z"), na=False)

    df_clean = df_raw[is_not_test & is_not_etf & valid_symbol & not_warrant_unit].copy()

    # Prioritize well-known benchmark equities and sort
    df_clean["symbol"] = df_clean["Symbol"].str.upper()
    df_clean["security_name"] = df_clean["Security Name"]
    df_clean["exchange"] = df_clean.get("Listing Exchange", "US")
    df_clean["etf_flag"] = "N"

    # Deduplicate symbols
    df_clean = df_clean.drop_duplicates(subset=["symbol"]).reset_index(drop=True)

    print(f"    Filtered pure common equities: {len(df_clean):,} symbols")

    # If target_count specified, ensure Big 5 and top liquid symbols are included first
    priority_tickers = [
        "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "BRK-B", "JPM", "V",
        "JNJ", "WMT", "PG", "UNH", "HD", "MA", "BAC", "XOM", "LLY", "DIS", "COST", "CVX",
        "ABBV", "MRK", "KO", "PEP", "AVGO", "CSCO", "TMO", "ADBE", "CRM", "NFLX", "AMD"
    ]
    
    priority_rows = df_clean[df_clean["symbol"].isin(priority_tickers)]
    remaining_rows = df_clean[~df_clean["symbol"].isin(priority_tickers)]
    
    combined_universe = pd.concat([priority_rows, remaining_rows], ignore_index=True)
    if target_count and len(combined_universe) > target_count:
        final_universe = combined_universe.iloc[:target_count].copy()
    else:
        final_universe = combined_universe.copy()

    print(f"[+] Finalizing universe selection: {len(final_universe):,} target equities.")

    # Initialize SQLite and store universe
    db = USStockDatabase()
    db.insert_tickers(final_universe)
    print(f"[SUCCESS] {len(final_universe):,} tickers registered in SQLite database: {db.db_path.name}")

    # Seed existing Big 5 stock prices into database
    root = get_project_root()
    master_price_file = root / "data" / "raw" / "us_tech_giants_daily_history.csv"
    if master_price_file.exists():
        print(f"\n[+] Migrating existing historical price dataset ({master_price_file.name}) into database...")
        df_seed = pd.read_csv(master_price_file)
        df_seed = df_seed.rename(columns={
            "Ticker": "symbol",
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
            "Dividends": "dividends",
            "Stock Splits": "stock_splits"
        })
        rows_inserted = db.insert_daily_prices(df_seed)
        db.update_ticker_metadata()
        print(f"    -> Successfully inserted {rows_inserted:,} historical rows for Big 5 tech equities.")

    db.log_pipeline_event("INIT_UNIVERSE", len(final_universe), len(final_universe), "SUCCESS", "Initialized 2,000+ US stock universe")
    
    stats = db.get_database_stats()
    print("\n--- DATABASE CURRENT STATUS ---")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print("=" * 75)

    return final_universe


if __name__ == "__main__":
    build_and_populate_universe(target_count=2200)
