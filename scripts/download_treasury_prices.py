"""Download real traded US Treasury market prices (ETFs, Futures, Historical Mutual Funds) and curve yield indices.

Stores:
- Raw OHLCV CSVs in data/raw/ matching existing schema (Date,Ticker,Open,High,Low,Close,Adj Close,Volume,Stock Splits,Dividends)
- Upserts metadata & daily bars into data/database/us_equities.db (via USStockDatabase)
- Exports data/processed/us_treasury_prices_daily.csv (+ portfolio/data/ mirror)
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

from db_manager import USStockDatabase

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
PORTFOLIO_DATA_DIR = ROOT_DIR / "portfolio" / "data"


@dataclass(frozen=True)
class TreasuryInstrument:
    symbol: str
    raw_filename: str
    security_name: str
    exchange: str
    etf_flag: str
    sector: str
    category: str
    unit: str


TREASURY_UNIVERSE: list[TreasuryInstrument] = [
    # US Treasury Bond & Note ETFs (Actual traded share prices + Adj Close total return)
    TreasuryInstrument("IEF", "IEF.csv", "iShares 7-10 Year Treasury Bond ETF", "NASDAQ", "Y", "Macro", "Treasury ETF Price", "USD"),
    TreasuryInstrument("TLT", "TLT.csv", "iShares 20+ Year Treasury Bond ETF", "NASDAQ", "Y", "Macro", "Treasury ETF Price", "USD"),
    TreasuryInstrument("IEI", "IEI.csv", "iShares 3-7 Year Treasury Bond ETF", "NASDAQ", "Y", "Macro", "Treasury ETF Price", "USD"),
    TreasuryInstrument("SHY", "SHY.csv", "iShares 1-3 Year Treasury Bond ETF", "NASDAQ", "Y", "Macro", "Treasury ETF Price", "USD"),
    TreasuryInstrument("BIL", "BIL.csv", "SPDR Bloomberg 1-3 Month T-Bill ETF", "NYSE ARCA", "Y", "Macro", "Treasury ETF Price", "USD"),
    TreasuryInstrument("GOVT", "GOVT.csv", "iShares U.S. Treasury Bond ETF", "CBOE", "Y", "Macro", "Treasury ETF Price", "USD"),
    TreasuryInstrument("SGOV", "SGOV.csv", "iShares 0-3 Month Treasury Bond ETF", "NYSE ARCA", "Y", "Macro", "Treasury ETF Price", "USD"),
    # CME Continuous Front-Month US Treasury Futures Prices
    TreasuryInstrument("ZN=F", "ZN_F.csv", "10-Year US Treasury Note Futures (CBOT)", "CBOT", "N", "Macro", "Treasury Futures Price", "Points (100=Par)"),
    TreasuryInstrument("ZB=F", "ZB_F.csv", "30-Year US Treasury Bond Futures (CBOT)", "CBOT", "N", "Macro", "Treasury Futures Price", "Points (100=Par)"),
    TreasuryInstrument("ZF=F", "ZF_F.csv", "5-Year US Treasury Note Futures (CBOT)", "CBOT", "N", "Macro", "Treasury Futures Price", "Points (100=Par)"),
    TreasuryInstrument("ZT=F", "ZT_F.csv", "2-Year US Treasury Note Futures (CBOT)", "CBOT", "N", "Macro", "Treasury Futures Price", "Points (100=Par)"),
    # Long-History Vanguard US Treasury Mutual Funds (1986 & 1991+)
    TreasuryInstrument("VUSTX", "VUSTX.csv", "Vanguard Long-Term Treasury Fund Investor", "NASDAQ", "N", "Macro", "Treasury Mutual Fund", "USD"),
    TreasuryInstrument("VFITX", "VFITX.csv", "Vanguard Intermediate-Term Treasury Fund Investor", "NASDAQ", "N", "Macro", "Treasury Mutual Fund", "USD"),
    TreasuryInstrument("VFISX", "VFISX.csv", "Vanguard Short-Term Treasury Fund Investor", "NASDAQ", "N", "Macro", "Treasury Mutual Fund", "USD"),
    # Full Curve Daily Yield Benchmarks & S&P 500 Sync
    TreasuryInstrument("^TNX", "TNX.csv", "10-Year Treasury Yield Index", "INDEX", "N", "Macro", "Treasury Yield Index", "%"),
    TreasuryInstrument("^TYX", "TYX.csv", "30-Year Treasury Yield Index", "INDEX", "N", "Macro", "Treasury Yield Index", "%"),
    TreasuryInstrument("^FVX", "FVX.csv", "5-Year Treasury Yield Index", "INDEX", "N", "Macro", "Treasury Yield Index", "%"),
    TreasuryInstrument("^IRX", "IRX.csv", "13-Week Treasury Bill Yield Index", "INDEX", "N", "Macro", "Treasury Yield Index", "%"),
    TreasuryInstrument("^GSPC", "GSPC.csv", "S&P 500 Index", "INDEX", "N", "Index", "Equity Benchmark", "Index"),
]


def fetch_symbol_full(inst: TreasuryInstrument) -> pd.DataFrame:
    """Download maximum history for a Yahoo Finance symbol and standardize OHLCV columns."""
    tk = yf.Ticker(inst.symbol)
    hist = tk.history(period="max", interval="1d", auto_adjust=False, actions=True)
    if hist.empty:
        raw = yf.download(inst.symbol, period="max", interval="1d", progress=False, auto_adjust=False)
        if raw.empty:
            return pd.DataFrame()
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = [c[0] for c in raw.columns]
        hist = raw

    hist = hist.reset_index()
    date_col = "Date" if "Date" in hist.columns else hist.columns[0]
    hist["Date"] = pd.to_datetime(hist[date_col]).dt.tz_localize(None).dt.strftime("%Y-%m-%d")

    out = pd.DataFrame()
    out["Date"] = hist["Date"]
    out["Ticker"] = inst.symbol
    for col in ["Open", "High", "Low", "Close", "Adj Close"]:
        if col in hist.columns:
            out[col] = pd.to_numeric(hist[col], errors="coerce")
        elif col == "Adj Close" and "Close" in hist.columns:
            out[col] = pd.to_numeric(hist["Close"], errors="coerce")
        else:
            out[col] = pd.to_numeric(hist.get("Close", pd.NA), errors="coerce")

    out["Volume"] = pd.to_numeric(hist.get("Volume", 0), errors="coerce").fillna(0).astype("int64")
    out["Stock Splits"] = pd.to_numeric(hist.get("Stock Splits", 0.0), errors="coerce").fillna(0.0)
    out["Dividends"] = pd.to_numeric(hist.get("Dividends", 0.0), errors="coerce").fillna(0.0)
    out = out.dropna(subset=["Date", "Close"]).drop_duplicates(subset=["Date"], keep="last").sort_values("Date").reset_index(drop=True)
    return out


def upsert_sqlite_instruments(db: USStockDatabase, frames: dict[str, pd.DataFrame]) -> None:
    """Upsert Treasury tickers and daily price bars into SQLite safely."""
    meta_rows = pd.DataFrame(
        [
            {
                "symbol": inst.symbol,
                "security_name": inst.security_name,
                "exchange": inst.exchange,
                "etf_flag": inst.etf_flag,
            }
            for inst in TREASURY_UNIVERSE
            if inst.symbol in frames and not frames[inst.symbol].empty
        ]
    )
    if not meta_rows.empty:
        db.insert_tickers(meta_rows)

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with db.get_connection() as conn:
        for inst in TREASURY_UNIVERSE:
            if inst.symbol in frames and not frames[inst.symbol].empty:
                conn.execute(
                    "UPDATE tickers SET sector = ?, industry = ?, sector_source = ?, sector_updated_at = ? WHERE symbol = ?",
                    (inst.sector, inst.category, "yfinance", now_iso, inst.symbol),
                )

    total_rows = 0
    for inst in TREASURY_UNIVERSE:
        df = frames.get(inst.symbol)
        if df is None or df.empty:
            continue
        db_df = pd.DataFrame(
            {
                "symbol": df["Ticker"],
                "date": df["Date"],
                "open": df["Open"],
                "high": df["High"],
                "low": df["Low"],
                "close": df["Close"],
                "adj_close": df["Adj Close"],
                "volume": df["Volume"],
                "dividends": df["Dividends"],
                "stock_splits": df["Stock Splits"],
            }
        )
        total_rows += db.insert_daily_prices(db_df)

    db.update_ticker_metadata()
    print(f"[SQLite] Upserted {total_rows:,} daily rows across {len(frames)} Treasury & Benchmark instruments.")


def build_daily_treasury_prices_csv(frames: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    """Combine traded Treasury ETFs, futures, mutual funds & yields into an aligned daily CSV."""
    price_cols = {
        "^GSPC": ("sp500_close", "Close"),
        "IEF": ("ief_close", "Close"),
        "TLT": ("tlt_close", "Close"),
        "SHY": ("shy_close", "Close"),
        "IEI": ("iei_close", "Close"),
        "BIL": ("bil_close", "Close"),
        "GOVT": ("govt_close", "Close"),
        "SGOV": ("sgov_close", "Close"),
        "ZN=F": ("zn_futures_close", "Close"),
        "ZB=F": ("zb_futures_close", "Close"),
        "ZF=F": ("zf_futures_close", "Close"),
        "ZT=F": ("zt_futures_close", "Close"),
        "VUSTX": ("vustx_close", "Close"),
        "VFITX": ("vfitx_close", "Close"),
        "VFISX": ("vfisx_close", "Close"),
        "^TNX": ("yield_10y_tnx", "Close"),
        "^TYX": ("yield_30y_tyx", "Close"),
        "^FVX": ("yield_5y_fvx", "Close"),
        "^IRX": ("yield_13w_irx", "Close"),
    }
    adj_cols = {
        "IEF": "ief_adj_close",
        "TLT": "tlt_adj_close",
        "SHY": "shy_adj_close",
        "GOVT": "govt_adj_close",
        "VUSTX": "vustx_adj_close",
        "VFITX": "vfitx_adj_close",
    }

    merged: pd.DataFrame | None = None
    catalog: list[dict[str, Any]] = []
    for inst in TREASURY_UNIVERSE:
        df = frames.get(inst.symbol)
        if df is None or df.empty:
            continue
        col_name, src_col = price_cols[inst.symbol]
        part = df[["Date", src_col]].rename(columns={"Date": "date", src_col: col_name}).copy()
        part[col_name] = part[col_name].round(4)
        if inst.symbol in adj_cols:
            adj_name = adj_cols[inst.symbol]
            part[adj_name] = df["Adj Close"].round(4)

        merged = part if merged is None else merged.merge(part, on="date", how="outer")
        catalog.append(
            {
                "symbol": inst.symbol,
                "name": inst.security_name,
                "category": inst.category,
                "unit": inst.unit,
                "start_date": df["Date"].iloc[0],
                "end_date": df["Date"].iloc[-1],
                "rows": int(len(df)),
                "latest_close": round(float(df["Close"].iloc[-1]), 3),
                "latest_adj_close": round(float(df["Adj Close"].iloc[-1]), 3),
            }
        )

    if merged is None:
        return catalog

    merged = merged.sort_values("date").reset_index(drop=True)
    # Limit aligned market-price export to start from earliest non-S&P Treasury price/yield bar (1960-01-04) or keep all?
    # Keeping 1960-01-04+ keeps file compact while covering all ^IRX/^FVX/^TNX/^TYX + 1986+ VUSTX + 2000+ futures + 2002+ ETFs!
    treasury_only = merged[merged["date"] >= "1960-01-04"].reset_index(drop=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    PORTFOLIO_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = PROCESSED_DIR / "us_treasury_prices_daily.csv"
    treasury_only.to_csv(out_csv, index=False)
    treasury_only.to_csv(PORTFOLIO_DATA_DIR / "us_treasury_prices_daily.csv", index=False)

    cat_json = PROCESSED_DIR / "us_treasury_price_catalog.json"
    cat_json.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"[CSV   ] Exported {len(treasury_only):,} daily rows -> {out_csv}")
    return catalog


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch real US Treasury market prices (ETFs, Futures, Mutual Funds)")
    parser.add_argument("--no-fetch", action="store_true", help="Read cached CSVs from data/raw/ if present")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    frames: dict[str, pd.DataFrame] = {}

    for inst in TREASURY_UNIVERSE:
        raw_path = RAW_DIR / inst.raw_filename
        if args.no_fetch and raw_path.exists():
            df = pd.read_csv(raw_path)
        else:
            df = fetch_symbol_full(inst)
            if not df.empty:
                df.to_csv(raw_path, index=False)
        if not df.empty:
            frames[inst.symbol] = df
            print(
                f"[PRICE ] {inst.symbol:7s} ({inst.category:22s}) | rows={len(df):6d} | "
                f"{df['Date'].iloc[0]} -> {df['Date'].iloc[-1]} | last={float(df['Close'].iloc[-1]):.3f} {inst.unit}"
            )

    db = USStockDatabase()
    upsert_sqlite_instruments(db, frames)
    build_daily_treasury_prices_csv(frames)


if __name__ == "__main__":
    main()

