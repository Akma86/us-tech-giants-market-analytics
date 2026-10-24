"""
Module: db_manager.py
Description: High-performance SQLite database layer for US stock market analytics.
             Supports batch inserts, WAL mode, indexing, incremental daily updates,
             and fast SQL/Pandas querying for 2,000+ equities.
Author: Akmal Yaasir Fauzaan
Project: US Tech Giants Market Analytics
"""

import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_default_db_path() -> Path:
    root = get_project_root()
    db_dir = root / "data" / "database"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "us_equities.db"


class USStockDatabase:
    """Manages the local SQLite database for US equity market historical data."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else get_default_db_path()
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Returns a connection configured with WAL mode and high-speed pragmas."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA cache_size = -64000;")  # 64 MB cache
        conn.execute("PRAGMA temp_store = MEMORY;")
        return conn

    def init_db(self):
        """Initializes tables and high-performance indices if they do not exist."""
        with self.get_connection() as conn:
            # 1. Tickers metadata table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS tickers (
                symbol TEXT PRIMARY KEY,
                security_name TEXT,
                exchange TEXT,
                etf_flag TEXT DEFAULT 'N',
                is_active INTEGER DEFAULT 1,
                first_date TEXT,
                last_date TEXT,
                total_records INTEGER DEFAULT 0,
                last_updated TEXT
            );
            """)

            # 2. Daily price table (OHLCV + Adj Close)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_prices (
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                adj_close REAL,
                volume INTEGER,
                dividends REAL DEFAULT 0.0,
                stock_splits REAL DEFAULT 0.0,
                PRIMARY KEY (symbol, date)
            );
            """)

            # 3. Dedicated fast search indices
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prices_symbol ON daily_prices (symbol);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prices_date ON daily_prices (date);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prices_symbol_date ON daily_prices (symbol, date);")

            # 4. Pipeline execution logs table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                job_type TEXT NOT NULL,
                symbols_processed INTEGER DEFAULT 0,
                rows_affected INTEGER DEFAULT 0,
                status TEXT NOT NULL,
                message TEXT
            );
            """)

    def insert_tickers(self, df_tickers: pd.DataFrame):
        """Inserts or updates ticker definitions in the tickers table."""
        records = []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for _, row in df_tickers.iterrows():
            records.append((
                str(row["symbol"]).strip().upper(),
                str(row.get("security_name", "")),
                str(row.get("exchange", "")),
                str(row.get("etf_flag", "N")),
                1,
                now_str
            ))

        with self.get_connection() as conn:
            conn.executemany("""
            INSERT INTO tickers (symbol, security_name, exchange, etf_flag, is_active, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                security_name = excluded.security_name,
                exchange = excluded.exchange,
                last_updated = excluded.last_updated;
            """, records)

    def insert_daily_prices(self, df_prices: pd.DataFrame) -> int:
        """Batch inserts or replaces daily price records into SQLite."""
        if df_prices.empty:
            return 0

        # Standardize required columns
        req_cols = ["symbol", "date", "open", "high", "low", "close", "adj_close", "volume"]
        for col in req_cols:
            if col not in df_prices.columns:
                raise ValueError(f"Missing required column '{col}' in price dataframe.")

        if "dividends" not in df_prices.columns:
            df_prices["dividends"] = 0.0
        if "stock_splits" not in df_prices.columns:
            df_prices["stock_splits"] = 0.0

        records = []
        for _, r in df_prices.iterrows():
            records.append((
                str(r["symbol"]).strip().upper(),
                str(r["date"])[:10],
                float(r["open"]) if pd.notna(r["open"]) else None,
                float(r["high"]) if pd.notna(r["high"]) else None,
                float(r["low"]) if pd.notna(r["low"]) else None,
                float(r["close"]) if pd.notna(r["close"]) else None,
                float(r["adj_close"]) if pd.notna(r["adj_close"]) else None,
                int(r["volume"]) if pd.notna(r["volume"]) else 0,
                float(r["dividends"]) if pd.notna(r["dividends"]) else 0.0,
                float(r["stock_splits"]) if pd.notna(r["stock_splits"]) else 0.0,
            ))

        with self.get_connection() as conn:
            conn.executemany("""
            INSERT OR REPLACE INTO daily_prices
            (symbol, date, open, high, low, close, adj_close, volume, dividends, stock_splits)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, records)

        return len(records)

    def update_ticker_metadata(self):
        """Refreshes first_date, last_date, and total_records in tickers table."""
        with self.get_connection() as conn:
            conn.execute("""
            UPDATE tickers
            SET
                first_date = (SELECT MIN(date) FROM daily_prices WHERE daily_prices.symbol = tickers.symbol),
                last_date = (SELECT MAX(date) FROM daily_prices WHERE daily_prices.symbol = tickers.symbol),
                total_records = (SELECT COUNT(*) FROM daily_prices WHERE daily_prices.symbol = tickers.symbol)
            WHERE symbol IN (SELECT DISTINCT symbol FROM daily_prices);
            """)

    def get_latest_dates_all(self) -> Dict[str, str]:
        """Returns a mapping of symbol -> MAX(date) in the database."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT symbol, MAX(date) FROM daily_prices GROUP BY symbol;")
            return {row[0]: row[1] for row in cursor.fetchall()}

    def get_universe(self, active_only: bool = True, limit: Optional[int] = None) -> List[str]:
        """Returns list of ticker symbols in the universe."""
        sql = "SELECT symbol FROM tickers"
        conditions = []
        if active_only:
            conditions.append("is_active = 1")
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY symbol ASC"
        if limit:
            sql += f" LIMIT {int(limit)}"

        with self.get_connection() as conn:
            cursor = conn.execute(sql)
            return [row[0] for row in cursor.fetchall()]

    def get_price_history(
        self,
        symbols: List[str] | str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """Queries historical prices into a clean Pandas DataFrame."""
        if isinstance(symbols, str):
            symbols = [symbols]

        placeholders = ",".join(["?"] * len(symbols))
        sql = f"SELECT symbol, date, open, high, low, close, adj_close, volume FROM daily_prices WHERE symbol IN ({placeholders})"
        params = list(symbols)

        if start_date:
            sql += " AND date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date <= ?"
            params.append(end_date)

        sql += " ORDER BY symbol ASC, date ASC"

        with self.get_connection() as conn:
            df = pd.read_sql_query(sql, conn, params=params)

        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
        return df

    def get_database_stats(self) -> Dict[str, Any]:
        """Returns summary statistics about the database."""
        with self.get_connection() as conn:
            total_tickers = conn.execute("SELECT COUNT(*) FROM tickers;").fetchone()[0]
            tickers_with_data = conn.execute("SELECT COUNT(DISTINCT symbol) FROM daily_prices;").fetchone()[0]
            total_rows = conn.execute("SELECT COUNT(*) FROM daily_prices;").fetchone()[0]
            dates = conn.execute("SELECT MIN(date), MAX(date) FROM daily_prices;").fetchone()

        file_size_mb = self.db_path.stat().st_size / (1024 * 1024) if self.db_path.exists() else 0.0

        return {
            "db_path": str(self.db_path),
            "file_size_mb": round(file_size_mb, 2),
            "total_registered_tickers": total_tickers,
            "tickers_with_price_data": tickers_with_data,
            "total_price_records": total_rows,
            "earliest_date": dates[0] if dates else None,
            "latest_date": dates[1] if dates else None,
        }

    def log_pipeline_event(self, job_type: str, symbols: int, rows: int, status: str, message: str = ""):
        """Writes execution telemetry into the pipeline_logs table."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            conn.execute("""
            INSERT INTO pipeline_logs (timestamp, job_type, symbols_processed, rows_affected, status, message)
            VALUES (?, ?, ?, ?, ?, ?);
            """, (now_str, job_type, symbols, rows, status, message))


if __name__ == "__main__":
    db = USStockDatabase()
    print("Database initialized successfully.")
    print("Stats:", db.get_database_stats())
