#!/usr/bin/env python3
"""Master Data Pipeline: Fetch Full IPO Prices, Financial Statements & Earnings.

Scope:
1. 10 US Flagship Leaders + Benchmarks:
   AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, AVGO, AMD, ORCL, ^GSPC, ^TNX, ^VIX
2. Historical Daily Prices from IPO Day to Present (Nov 2026).
3. Complete Financial Statements:
   - Annual & Quarterly Income Statements
   - Annual & Quarterly Balance Sheets
   - Annual & Quarterly Cash Flow Statements
4. Valuation Multiples & Fundamental Ratios (P/E, EV/EBITDA, Margins, ROE, FCF).
5. Historical Earnings Announcement Dates & EPS Surprises.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import yfinance as yf

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
FINANCIALS_DIR = RAW_DIR / "financials"
EARNINGS_DIR = RAW_DIR / "earnings"
PORTFOLIO_DATA_DIR = PROJECT_ROOT / "portfolio" / "data"

RAW_DIR.mkdir(parents=True, exist_ok=True)
FINANCIALS_DIR.mkdir(parents=True, exist_ok=True)
EARNINGS_DIR.mkdir(parents=True, exist_ok=True)
PORTFOLIO_DATA_DIR.mkdir(parents=True, exist_ok=True)

TARGET_STOCKS = {
    "AAPL": {"name": "Apple Inc.", "sector": "Consumer Electronics", "ipo": "1980-12-12"},
    "MSFT": {"name": "Microsoft Corporation", "sector": "Software - Infrastructure", "ipo": "1986-03-13"},
    "NVDA": {"name": "NVIDIA Corporation", "sector": "Semiconductors", "ipo": "1999-01-22"},
    "GOOGL": {"name": "Alphabet Inc.", "sector": "Internet Content & Information", "ipo": "2004-08-19"},
    "AMZN": {"name": "Amazon.com, Inc.", "sector": "Internet Retail", "ipo": "1997-05-15"},
    "META": {"name": "Meta Platforms, Inc.", "sector": "Internet Content & Information", "ipo": "2012-05-18"},
    "TSLA": {"name": "Tesla, Inc.", "sector": "Auto Manufacturers", "ipo": "2010-06-29"},
    "AVGO": {"name": "Broadcom Inc.", "sector": "Semiconductors", "ipo": "2009-08-06"},
    "AMD": {"name": "Advanced Micro Devices, Inc.", "sector": "Semiconductors", "ipo": "1979-03-15"},
    "ORCL": {"name": "Oracle Corporation", "sector": "Software - Infrastructure", "ipo": "1986-03-12"},
}

BENCHMARKS = {
    "^GSPC": {"name": "S&P 500 Index", "sector": "US Broad Equity Market Benchmark"},
    "^TNX": {"name": "CBOE 10-Year Treasury Note Yield", "sector": "US Macro Risk-Free Rate"},
    "^VIX": {"name": "CBOE Volatility Index", "sector": "US Macro Volatility & Fear Gauge"},
}


def fetch_historical_prices(ticker: str, is_benchmark: bool = False) -> pd.DataFrame:
    """Download maximum historical daily prices from IPO to today."""
    print(f"  [>] Fetching full daily history (period='max') for {ticker}...", end=" ", flush=True)
    t = yf.Ticker(ticker)
    df = t.history(period="max", auto_adjust=False)
    if df is None or df.empty:
        raise ValueError(f"No price data returned for {ticker}")

    df = df.reset_index()
    # Normalize Date column
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None).dt.strftime("%Y-%m-%d")

    df["Ticker"] = ticker
    # Reorder columns
    cols = ["Date", "Ticker", "Open", "High", "Low", "Close", "Adj Close", "Volume"]
    if "Stock Splits" in df.columns:
        cols.append("Stock Splits")
    if "Dividends" in df.columns:
        cols.append("Dividends")

    existing_cols = [c for c in cols if c in df.columns]
    df = df[existing_cols].sort_values("Date").reset_index(drop=True)
    
    first_dt = df["Date"].min()
    last_dt = df["Date"].max()
    print(f"✓ {len(df):>5} days ({first_dt} -> {last_dt})")
    return df


def fetch_financial_statements(ticker: str, t: yf.Ticker) -> Dict[str, Any]:
    """Fetch complete balance sheet, income statement, cash flow, and valuation ratios."""
    print(f"  [>] Fetching financial statements & ratios for {ticker}...", end=" ", flush=True)
    
    # 1. Income Statement
    inc_annual = t.income_stmt
    inc_quarterly = t.quarterly_income_stmt
    if inc_annual is not None and not inc_annual.empty:
        inc_annual.to_csv(FINANCIALS_DIR / f"{ticker}_income_statement_annual.csv")
    if inc_quarterly is not None and not inc_quarterly.empty:
        inc_quarterly.to_csv(FINANCIALS_DIR / f"{ticker}_income_statement_quarterly.csv")

    # 2. Balance Sheet
    bal_annual = t.balance_sheet
    bal_quarterly = t.quarterly_balance_sheet
    if bal_annual is not None and not bal_annual.empty:
        bal_annual.to_csv(FINANCIALS_DIR / f"{ticker}_balance_sheet_annual.csv")
    if bal_quarterly is not None and not bal_quarterly.empty:
        bal_quarterly.to_csv(FINANCIALS_DIR / f"{ticker}_balance_sheet_quarterly.csv")

    # 3. Cash Flow
    cf_annual = t.cashflow
    cf_quarterly = t.quarterly_cashflow
    if cf_annual is not None and not cf_annual.empty:
        cf_annual.to_csv(FINANCIALS_DIR / f"{ticker}_cash_flow_annual.csv")
    if cf_quarterly is not None and not cf_quarterly.empty:
        cf_quarterly.to_csv(FINANCIALS_DIR / f"{ticker}_cash_flow_quarterly.csv")

    # 4. Fundamental Ratios & Valuation Info
    info = t.info or {}
    key_metrics = {
        "ticker": ticker,
        "company_name": TARGET_STOCKS[ticker]["name"],
        "sector": TARGET_STOCKS[ticker]["sector"],
        "market_cap": info.get("marketCap"),
        "enterprise_value": info.get("enterpriseValue"),
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "peg_ratio": info.get("pegRatio"),
        "price_to_sales": info.get("priceToSalesTrailing12Months"),
        "price_to_book": info.get("priceToBook"),
        "enterprise_to_revenue": info.get("enterpriseToRevenue"),
        "enterprise_to_ebitda": info.get("enterpriseToEbitda"),
        "profit_margins": info.get("profitMargins"),
        "operating_margins": info.get("operatingMargins"),
        "gross_margins": info.get("grossMargins"),
        "return_on_equity": info.get("returnOnEquity"),
        "return_on_assets": info.get("returnOnAssets"),
        "trailing_eps": info.get("trailingEps"),
        "forward_eps": info.get("forwardEps"),
        "total_revenue": info.get("totalRevenue"),
        "revenue_growth": info.get("revenueGrowth"),
        "gross_profits": info.get("grossProfits"),
        "ebitda": info.get("ebitda"),
        "net_income": info.get("netIncomeToCommon"),
        "operating_cash_flow": info.get("operatingCashflow"),
        "free_cash_flow": info.get("freeCashflow"),
        "total_cash": info.get("totalCash"),
        "total_debt": info.get("totalDebt"),
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
        "dividend_yield": info.get("dividendYield"),
        "beta": info.get("beta"),
        "52_week_high": info.get("fiftyTwoWeekHigh"),
        "52_week_low": info.get("fiftyTwoWeekLow"),
    }
    
    with open(FINANCIALS_DIR / f"{ticker}_key_ratios.json", "w", encoding="utf-8") as f:
        json.dump(key_metrics, f, indent=2)

    # 5. Earnings dates & surprise history
    try:
        ed = t.get_earnings_dates(limit=40)
        if ed is not None and not ed.empty:
            ed = ed.reset_index()
            date_col = "Earnings Date" if "Earnings Date" in ed.columns else ed.columns[0]
            ed = ed.rename(columns={date_col: "Earnings_Date"})
            ed["Ticker"] = ticker
            ed.to_csv(EARNINGS_DIR / f"{ticker}_earnings_history.csv", index=False)
    except Exception as e:
        print(f"(earnings note: {e})", end=" ")

    print("✓ Statements, ratios & earnings saved")
    return key_metrics


def main():
    print("==========================================================================")
    print("US TECH GIANTS & MARKET LEADERS: MASTER DATA INGESTION")
    print("1. Daily Historical Prices from IPO to Present")
    print("2. Financial Statements (Income Statement, Balance Sheet, Cash Flow)")
    print("3. Valuation Ratios, Multiples & Earnings Surprises")
    print("==========================================================================\n")

    all_price_frames = []
    ratio_summaries = []
    all_earnings_frames = []

    # 1. Fetch 10 US Leaders
    for ticker in TARGET_STOCKS:
        print(f"\nProcessing {ticker} ({TARGET_STOCKS[ticker]['name']}):")
        t = yf.Ticker(ticker)
        
        # Prices
        p_df = fetch_historical_prices(ticker)
        p_df.to_csv(RAW_DIR / f"{ticker}.csv", index=False)
        all_price_frames.append(p_df)
        
        # Financials
        try:
            ratios = fetch_financial_statements(ticker, t)
            ratio_summaries.append(ratios)
        except Exception as e:
            print(f"  [!] Financials error for {ticker}: {e}")

        # Earnings frame check
        efile = EARNINGS_DIR / f"{ticker}_earnings_history.csv"
        if efile.exists():
            try:
                edf = pd.read_csv(efile)
                all_earnings_frames.append(edf)
            except Exception:
                pass

        time.sleep(0.5)

    # 2. Fetch Benchmarks
    print("\nProcessing Macro Benchmarks:")
    for ticker in BENCHMARKS:
        try:
            b_df = fetch_historical_prices(ticker, is_benchmark=True)
            clean_name = ticker.replace("^", "")
            b_df.to_csv(RAW_DIR / f"{clean_name}.csv", index=False)
            all_price_frames.append(b_df)
        except Exception as e:
            print(f"  [!] Benchmark error for {ticker}: {e}")
        time.sleep(0.5)

    # 3. Save Consolidated Master Prices from IPO
    print("\nConsolidating Master Price Dataset...")
    master_df = pd.concat(all_price_frames, ignore_index=True)
    master_df = master_df.sort_values(["Ticker", "Date"]).reset_index(drop=True)
    master_csv = RAW_DIR / "us_tech_giants_daily_history.csv"
    master_df.to_csv(master_csv, index=False)
    print(f"✓ Consolidated master daily dataset saved: {master_csv}")
    print(f"  Total records: {len(master_df):,} daily bars across {master_df['Ticker'].nunique()} tickers")
    print(f"  Earliest observation: {master_df['Date'].min()} | Latest: {master_df['Date'].max()}")

    # 4. Save Consolidated Fundamental Financial Ratios Table
    if ratio_summaries:
        print("\nConsolidating Fundamental Ratios & Valuation Multiples...")
        ratio_df = pd.DataFrame(ratio_summaries)
        ratio_csv = FINANCIALS_DIR / "us_tech_giants_financial_summary.csv"
        ratio_df.to_csv(ratio_csv, index=False)
        print(f"✓ Master Financials Summary saved: {ratio_csv}")

    # 5. Save Consolidated Earnings History
    if all_earnings_frames:
        print("\nConsolidating Master Earnings History...")
        master_earnings = pd.concat(all_earnings_frames, ignore_index=True)
        earnings_csv = EARNINGS_DIR / "us_tech_giants_earnings_history.csv"
        master_earnings.to_csv(earnings_csv, index=False)
        print(f"✓ Master Earnings History saved: {earnings_csv} ({len(master_earnings)} events)")

    print("\n==========================================================================")
    print("PIPELINE COMPLETED SUCCESSFULLY!")
    print("==========================================================================")


if __name__ == "__main__":
    main()

