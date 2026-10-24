"""
Script: fetch_data.py
Description: Fetches complete historical daily market data for Apple (AAPL),
             Microsoft (MSFT), NVIDIA (NVDA), Alphabet (GOOGL), and Amazon (AMZN)
             from their respective initial public offerings (IPO) to the current date.
Author: Akmal Yaasir Fauzaan
Project: Risk-Return Analysis of US Tech Giants
"""

import os
from pathlib import Path
from datetime import datetime
import pandas as pd
import yfinance as yf

# Target stock tickers and metadata
TARGET_STOCKS = {
    "AAPL": {
        "company_name": "Apple Inc.",
        "sector": "Information Technology",
        "industry": "Consumer Electronics"
    },
    "MSFT": {
        "company_name": "Microsoft Corporation",
        "sector": "Information Technology",
        "industry": "Software - Infrastructure"
    },
    "NVDA": {
        "company_name": "NVIDIA Corporation",
        "sector": "Information Technology",
        "industry": "Semiconductors"
    },
    "GOOGL": {
        "company_name": "Alphabet Inc. (Google)",
        "sector": "Communication Services",
        "industry": "Internet Content & Information"
    },
    "AMZN": {
        "company_name": "Amazon.com, Inc.",
        "sector": "Consumer Discretionary",
        "industry": "Internet Retail"
    }
}


def get_project_root() -> Path:
    """Returns the project root directory."""
    return Path(__file__).resolve().parent.parent


def fetch_and_save_stock_data(output_dir: Path | None = None) -> pd.DataFrame:
    """
    Downloads full historical data for all target tickers from Yahoo Finance
    and saves both individual CSV files and a combined dataset.
    
    Parameters:
    -----------
    output_dir : Path, optional
        Target directory to save raw CSV files. Defaults to '<root>/data/raw'.
        
    Returns:
    --------
    pd.DataFrame
        Summary statistics table of the downloaded dataset.
    """
    if output_dir is None:
        output_dir = get_project_root() / "data" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)

    combined_frames = []
    summary_records = []

    print("=" * 75)
    print("STARTING HISTORICAL DATA EXTRACTION (FROM IPO TO PRESENT)")
    print("=" * 75)

    for ticker, info in TARGET_STOCKS.items():
        print(f"\n[+] Fetching {ticker} ({info['company_name']})...")
        try:
            stock = yf.Ticker(ticker)
            # Fetch maximum available history (from IPO date)
            # auto_adjust=False preserves both raw 'Close' and 'Adj Close'
            df = stock.history(period="max", auto_adjust=False)

            if df.empty:
                print(f"    [!] Warning: Received empty dataset for {ticker}.")
                continue

            # Standardize index to YYYY-MM-DD Date
            df = df.reset_index()
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None).dt.date
            
            # Format and arrange columns
            ordered_cols = ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume", "Dividends", "Stock Splits"]
            existing_cols = [c for c in ordered_cols if c in df.columns]
            df = df[existing_cols]

            # Save individual stock CSV
            individual_file = output_dir / f"{ticker}.csv"
            df.to_csv(individual_file, index=False)
            print(f"    -> Saved individual file: {individual_file.name}")
            print(f"       Records: {len(df):,} trading days")
            print(f"       Date Range: {df['Date'].min()} to {df['Date'].max()}")

            # Prepare for combined master dataset
            df_combined = df.copy()
            df_combined.insert(1, "Ticker", ticker)
            df_combined.insert(2, "Company", info["company_name"])
            df_combined.insert(3, "Sector", info["sector"])
            combined_frames.append(df_combined)

            summary_records.append({
                "Ticker": ticker,
                "Company": info["company_name"],
                "Sector": info["sector"],
                "First Trading Day (IPO)": str(df["Date"].min()),
                "Latest Trading Day": str(df["Date"].max()),
                "Total Trading Days": len(df),
                "Latest Close ($)": round(float(df["Close"].iloc[-1]), 2),
                "Latest Adj Close ($)": round(float(df["Adj Close"].iloc[-1]), 2),
            })

        except Exception as e:
            print(f"    [X] Error downloading {ticker}: {str(e)}")

    if combined_frames:
        combined_df = pd.concat(combined_frames, ignore_index=True)
        # Sort by Date ascending then Ticker
        combined_df = combined_df.sort_values(by=["Date", "Ticker"]).reset_index(drop=True)
        
        combined_file = output_dir / "us_tech_giants_daily_history.csv"
        combined_df.to_csv(combined_file, index=False)
        print("\n" + "=" * 75)
        print(f"[SUCCESS] Consolidated dataset saved to: {combined_file.name}")
        print(f"Total Combined Observations: {len(combined_df):,} rows")
        print("=" * 75)

    summary_df = pd.DataFrame(summary_records)
    print("\n--- DATASET INVENTORY SUMMARY ---")
    print(summary_df.to_string(index=False))
    print("=" * 75)

    return summary_df


if __name__ == "__main__":
    fetch_and_save_stock_data()
