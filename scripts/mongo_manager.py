"""
Module: mongo_manager.py
Description: Production MongoDB client for US stock market analytics.
             Connects to local MongoDB instance (mongodb://localhost:27017),
             manages collections (daily_prices, tickers, earnings), and supports
             high-throughput bulk_write operations and Pandas query interfaces.
Author: Akmal Yaasir Fauzaan
Project: US Tech Giants Market Analytics
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
from pymongo import MongoClient, UpdateOne, ASCENDING, DESCENDING


DEFAULT_MONGO_URI = "mongodb://localhost:27018/"
DEFAULT_DB_NAME = "us_equities_db"


class MongoStockDatabase:
    """Manages MongoDB collections and high-performance bulk operations for equity datasets."""

    def __init__(self, uri: str = DEFAULT_MONGO_URI, db_name: str = DEFAULT_DB_NAME):
        self.client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        self.db = self.client[db_name]
        self.init_indices()

    def init_indices(self):
        """Creates high-performance compound indices across collections."""
        # 1. daily_prices: Fast time-series lookup per stock
        self.db.daily_prices.create_index([("symbol", ASCENDING), ("date", DESCENDING)])
        self.db.daily_prices.create_index([("date", DESCENDING)])
        
        # 2. tickers: Unique symbol directory
        self.db.tickers.create_index([("symbol", ASCENDING)], unique=True)
        
        # 3. earnings: Fast quarterly earnings lookup
        self.db.earnings.create_index([("symbol", ASCENDING), ("earnings_date", DESCENDING)])

    def insert_prices_bulk(self, df_prices: pd.DataFrame, batch_size: int = 5000) -> int:
        """High-throughput bulk upsert of daily price records into MongoDB."""
        if df_prices.empty:
            return 0

        total_inserted = 0
        operations = []

        for _, r in df_prices.iterrows():
            sym = str(r["symbol"]).strip().upper()
            d_str = str(r["date"])[:10]
            doc_id = f"{sym}_{d_str}"
            
            # Convert date to standard datetime
            try:
                date_obj = datetime.strptime(d_str, "%Y-%m-%d")
            except Exception:
                date_obj = d_str

            doc = {
                "_id": doc_id,
                "symbol": sym,
                "date": date_obj,
                "date_str": d_str,
                "open": float(r["open"]) if pd.notna(r["open"]) else None,
                "high": float(r["high"]) if pd.notna(r["high"]) else None,
                "low": float(r["low"]) if pd.notna(r["low"]) else None,
                "close": float(r["close"]) if pd.notna(r["close"]) else None,
                "adj_close": float(r["adj_close"]) if pd.notna(r["adj_close"]) else None,
                "volume": int(r["volume"]) if pd.notna(r["volume"]) else 0,
                "dividends": float(r.get("dividends", 0.0)) if pd.notna(r.get("dividends")) else 0.0,
                "stock_splits": float(r.get("stock_splits", 0.0)) if pd.notna(r.get("stock_splits")) else 0.0,
                "updated_at": datetime.now()
            }

            operations.append(UpdateOne({"_id": doc_id}, {"$set": doc}, upsert=True))

            if len(operations) >= batch_size:
                res = self.db.daily_prices.bulk_write(operations, ordered=False)
                total_inserted += (res.upserted_count + res.modified_count)
                operations = []

        if operations:
            res = self.db.daily_prices.bulk_write(operations, ordered=False)
            total_inserted += (res.upserted_count + res.modified_count)

        return total_inserted

    def insert_tickers_bulk(self, df_tickers: pd.DataFrame) -> int:
        """Upserts ticker definitions into tickers collection."""
        if df_tickers.empty:
            return 0

        operations = []
        for _, r in df_tickers.iterrows():
            sym = str(r["symbol"]).strip().upper()
            doc = {
                "_id": sym,
                "symbol": sym,
                "security_name": str(r.get("security_name", "")),
                "exchange": str(r.get("exchange", "")),
                "etf_flag": str(r.get("etf_flag", "N")),
                "updated_at": datetime.now()
            }
            operations.append(UpdateOne({"_id": sym}, {"$set": doc}, upsert=True))

        res = self.db.tickers.bulk_write(operations, ordered=False)
        return res.upserted_count + res.modified_count

    def insert_earnings_bulk(self, df_earnings: pd.DataFrame) -> int:
        """Upserts earnings announcement records into earnings collection."""
        if df_earnings.empty:
            return 0

        operations = []
        for _, r in df_earnings.iterrows():
            sym = str(r["Ticker"]).strip().upper()
            d_str = str(r["Earnings_Date"])[:10]
            doc_id = f"{sym}_{d_str}"
            
            doc = {
                "_id": doc_id,
                "symbol": sym,
                "company": str(r.get("Company", "")),
                "earnings_date": d_str,
                "session_timing": str(r.get("Session_Timing", "")),
                "announcement_time_est": str(r.get("Announcement_Time_EST", "")),
                "eps_estimate": float(r["EPS Estimate"]) if pd.notna(r.get("EPS Estimate")) else None,
                "reported_eps": float(r["Reported EPS"]) if pd.notna(r.get("Reported EPS")) else None,
                "surprise_pct": float(r["Surprise(%)"]) if pd.notna(r.get("Surprise(%)")) else None,
                "updated_at": datetime.now()
            }
            operations.append(UpdateOne({"_id": doc_id}, {"$set": doc}, upsert=True))

        res = self.db.earnings.bulk_write(operations, ordered=False)
        return res.upserted_count + res.modified_count

    def get_price_history(
        self,
        symbols: List[str] | str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """Queries price history from MongoDB into a Pandas DataFrame."""
        if isinstance(symbols, str):
            symbols = [symbols]

        query: Dict[str, Any] = {"symbol": {"$in": [s.upper() for s in symbols]}}
        
        date_cond = {}
        if start_date:
            date_cond["$gte"] = datetime.strptime(start_date[:10], "%Y-%m-%d")
        if end_date:
            date_cond["$lte"] = datetime.strptime(end_date[:10], "%Y-%m-%d")
        if date_cond:
            query["date"] = date_cond

        cursor = self.db.daily_prices.find(
            query,
            projection={"_id": 0, "symbol": 1, "date_str": 1, "open": 1, "high": 1, "low": 1, "close": 1, "adj_close": 1, "volume": 1}
        ).sort([("symbol", ASCENDING), ("date", ASCENDING)])

        df = pd.DataFrame(list(cursor))
        if not df.empty:
            df = df.rename(columns={"date_str": "date"})
            df["date"] = pd.to_datetime(df["date"])
        return df

    def get_stats(self) -> Dict[str, Any]:
        """Returns collection counts and statistics fast."""
        return {
            "database_name": self.db.name,
            "tickers_count": self.db.tickers.estimated_document_count(),
            "daily_prices_count": self.db.daily_prices.estimated_document_count(),
            "earnings_count": self.db.earnings.estimated_document_count(),
        }


if __name__ == "__main__":
    mongo = MongoStockDatabase()
    print("Connected to MongoDB successfully.")
    print("Stats:", mongo.get_stats())
