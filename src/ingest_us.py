"""
Module: ingest_us.py
Description: Ingests market price series, commodity benchmarks, and macro indicators
             into Parquet and DuckDB for the StockLens US Financial Knowledge Graph.
Author: Akmal Yaasir Fauzaan
Project: StockLens US - Financial Knowledge Graph & Market Intelligence
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import yfinance as yf
import duckdb

# Path configuration
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_US_DIR = PROJECT_ROOT / "data" / "us"
SQLITE_DB_PATH = PROJECT_ROOT / "data" / "database" / "us_equities.db"
PARQUET_PATH = DATA_US_DIR / "prices.parquet"
DUCKDB_PATH = DATA_US_DIR / "stocklens.duckdb"

COMMODITY_TICKERS = {
    "CL=F": ("commodity_wti", "Crude Oil WTI", "USD/bbl"),
    "BZ=F": ("commodity_brent", "Crude Oil Brent", "USD/bbl"),
    "NG=F": ("commodity_gas", "Natural Gas Henry Hub", "USD/MMBtu"),
    "HG=F": ("commodity_copper", "Copper COMEX", "USD/lb"),
    "^TNX": ("macro_us10y", "10-Year Treasury Yield", "Percent"),
    "^VIX": ("macro_vix", "CBOE Volatility Index", "Index"),
    "^GSPC": ("macro_sp500", "S&P 500 Benchmark", "Index"),
    "GC=F": ("commodity_gold", "Gold COMEX", "USD/oz")
}


def load_seed_tickers() -> list[str]:
    """Reads distinct stock tickers from entities.csv."""
    entities_path = DATA_US_DIR / "entities.csv"
    if not entities_path.exists():
        raise FileNotFoundError(f"Missing entities file: {entities_path}")
    df_ent = pd.read_csv(entities_path)
    tickers = df_ent[df_ent["entity_type"] == "Company"]["ticker"].dropna().unique().tolist()
    return sorted(tickers)


def extract_equities_from_sqlite(tickers: list[str], start_date: str = "2020-01-01") -> pd.DataFrame:
    """Queries local SQLite database for company price histories."""
    import sqlite3
    if not SQLITE_DB_PATH.exists():
        print(f"[!] Warning: SQLite database {SQLITE_DB_PATH} not found.")
        return pd.DataFrame()

    conn = sqlite3.connect(f"{SQLITE_DB_PATH.as_uri()}?mode=ro", uri=True)
    placeholders = ",".join(["?"] * len(tickers))
    query = f"""
    SELECT symbol as ticker, date, open, high, low, close, adj_close, volume
    FROM daily_prices
    WHERE symbol IN ({placeholders}) AND date >= ?
    ORDER BY symbol, date ASC;
    """
    df = pd.read_sql_query(query, conn, params=[*tickers, start_date])
    conn.close()
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df["series_type"] = "Equity"
        df["unit"] = "USD"
    return df


def fetch_commodities_and_macro(start_date: str = "2020-01-01") -> pd.DataFrame:
    """Downloads commodity and macro benchmark series from Yahoo Finance."""
    print(f"[+] Downloading {len(COMMODITY_TICKERS)} commodity and macro benchmark series...")
    syms = list(COMMODITY_TICKERS.keys())
    data = yf.download(syms, start=start_date, group_by="ticker", threads=True, progress=False)

    records = []
    for sym in syms:
        ent_id, name, unit = COMMODITY_TICKERS[sym]
        if sym in data.columns.levels[0]:
            df_sub = data[sym].dropna(subset=["Close"]).reset_index()
            for _, r in df_sub.iterrows():
                d_str = str(r.get("Date", ""))[:10]
                records.append({
                    "ticker": sym,
                    "date": pd.to_datetime(d_str),
                    "open": float(r.get("Open")) if pd.notna(r.get("Open")) else None,
                    "high": float(r.get("High")) if pd.notna(r.get("High")) else None,
                    "low": float(r.get("Low")) if pd.notna(r.get("Low")) else None,
                    "close": float(r.get("Close")) if pd.notna(r.get("Close")) else None,
                    "adj_close": float(r.get("Adj Close", r.get("Close"))) if pd.notna(r.get("Close")) else None,
                    "volume": int(r.get("Volume", 0)) if pd.notna(r.get("Volume")) else 0,
                    "series_type": "MacroCommodity",
                    "unit": unit
                })
    return pd.DataFrame(records)


def build_stocklens_dataset():
    """Main pipeline execution for time series ingestion."""
    print("=" * 75)
    print("STOCKLENS US — INGESTION PIPELINE (TIME SERIES & COLUMNAR DATABASE)")
    print("=" * 75)

    DATA_US_DIR.mkdir(parents=True, exist_ok=True)
    seed_tickers = load_seed_tickers()
    print(f"[+] Loaded {len(seed_tickers)} seed equities from entities.csv: {', '.join(seed_tickers[:8])}...")

    # 1. Equities
    df_equities = extract_equities_from_sqlite(seed_tickers)
    print(f"[+] Extracted {len(df_equities):,} equity daily bars from local SQLite database.")

    # 2. Commodities & Macro
    df_macro = fetch_commodities_and_macro()
    print(f"[+] Extracted {len(df_macro):,} commodity/macro daily observations.")

    # 3. Concatenate and save to Parquet
    df_combined = pd.concat([df_equities, df_macro], ignore_index=True).sort_values(["ticker", "date"])
    df_combined.to_parquet(PARQUET_PATH, index=False, engine="pyarrow", compression="snappy")
    print(f"[OK] Successfully exported consolidated Parquet: {PARQUET_PATH} ({PARQUET_PATH.stat().st_size / 1024:.1f} KB)")

    # 4. Ingest into DuckDB
    print(f"[+] Registering relational tables in DuckDB: {DUCKDB_PATH}...")
    con = duckdb.connect(str(DUCKDB_PATH))
    con.execute("CREATE OR REPLACE TABLE market_prices AS SELECT * FROM df_combined;")
    entities_posix = (DATA_US_DIR / "entities.csv").as_posix()
    rel_posix = (DATA_US_DIR / "relationships.csv").as_posix()
    ev_posix = (DATA_US_DIR / "evidence.csv").as_posix()
    con.execute(f"CREATE OR REPLACE TABLE entities AS SELECT * FROM read_csv_auto('{entities_posix}');")
    con.execute(f"CREATE OR REPLACE TABLE relationships AS SELECT * FROM read_csv_auto('{rel_posix}');")
    con.execute(f"CREATE OR REPLACE TABLE evidence AS SELECT * FROM read_csv_auto('{ev_posix}');")

    stats = con.execute("""
    SELECT 
        (SELECT count(*) FROM entities) as total_entities,
        (SELECT count(*) FROM relationships) as total_relationships,
        (SELECT count(*) FROM evidence) as total_evidence,
        (SELECT count(*) FROM market_prices) as total_prices,
        (SELECT min(date) FROM market_prices) as min_date,
        (SELECT max(date) FROM market_prices) as max_date
    """).df().to_dict(orient="records")[0]

    con.close()
    print("\n--- DUCKDB CATALOG STATUS ---")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print("=" * 75)
    return stats


if __name__ == "__main__":
    build_stocklens_dataset()
