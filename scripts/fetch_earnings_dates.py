"""
Script: fetch_earnings_dates.py
Description: Fetches historical earnings announcement dates, EPS estimates,
             reported EPS, and surprise percentages for AAPL, MSFT, NVDA, GOOGL, and AMZN.
Author: Akmal Yaasir Fauzaan
Project: US Tech Giants Market Analytics
"""

from pathlib import Path
import pandas as pd
import yfinance as yf

TICKERS = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
    "GOOGL": "Alphabet Inc. (Google)",
    "AMZN": "Amazon.com, Inc."
}


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def fetch_all_earnings_dates():
    root = get_project_root()
    output_dir = root / "data" / "raw" / "earnings"
    output_dir.mkdir(parents=True, exist_ok=True)

    all_frames = []
    summary = []

    print("=" * 75)
    print("FETCHING HISTORICAL EARNINGS ANNOUNCEMENT DATES")
    print("=" * 75)

    for ticker, name in TICKERS.items():
        print(f"\n[+] Fetching earnings calendar for {ticker} ({name})...")
        try:
            stock = yf.Ticker(ticker)
            df = stock.get_earnings_dates(limit=100)

            if df is None or df.empty:
                print(f"    [!] No earnings data returned for {ticker}.")
                continue

            # Reset index and clean column names
            df = df.reset_index()
            # Standardize date column
            date_col = [c for c in df.columns if "Date" in c or "date" in c][0]
            
            # Extract clean date and announcement time
            df["Earnings_Timestamp"] = pd.to_datetime(df[date_col])
            df["Earnings_Date"] = df["Earnings_Timestamp"].dt.date
            df["Announcement_Time_EST"] = df["Earnings_Timestamp"].dt.strftime("%H:%M:%S")
            
            # Classify announcement timing (Before Market Open / After Market Close)
            def classify_timing(hour):
                if hour < 10:
                    return "Before Market Open (BMO)"
                elif hour >= 16:
                    return "After Market Close (AMC)"
                else:
                    return "Intraday / Unspecified"

            df["Session_Timing"] = df["Earnings_Timestamp"].dt.hour.apply(classify_timing)

            # Insert metadata
            df.insert(0, "Ticker", ticker)
            df.insert(1, "Company", name)

            # Reorder columns
            desired_cols = [
                "Earnings_Date", "Ticker", "Company", "Session_Timing",
                "Announcement_Time_EST", "EPS Estimate", "Reported EPS", "Surprise(%)"
            ]
            cols = [c for c in desired_cols if c in df.columns]
            df_clean = df[cols].drop_duplicates(subset=["Earnings_Date", "Ticker"]).sort_values(by="Earnings_Date", ascending=False).reset_index(drop=True)

            # Save individual CSV
            individual_file = output_dir / f"{ticker}_earnings_history.csv"
            df_clean.to_csv(individual_file, index=False)
            print(f"    -> Saved: {individual_file.name} ({len(df_clean)} quarters)")
            print(f"       Coverage: {df_clean['Earnings_Date'].min()} to {df_clean['Earnings_Date'].max()}")

            all_frames.append(df_clean)
            summary.append({
                "Ticker": ticker,
                "Company": name,
                "Total Quarters": len(df_clean),
                "Earliest Available Date": str(df_clean["Earnings_Date"].min()),
                "Latest / Upcoming Date": str(df_clean["Earnings_Date"].max()),
                "Avg Surprise (%)": f"{df_clean['Surprise(%)'].dropna().mean():.2f}%"
            })

        except Exception as e:
            print(f"    [X] Error fetching {ticker}: {str(e)}")

    if all_frames:
        combined_df = pd.concat(all_frames, ignore_index=True)
        combined_df = combined_df.sort_values(by=["Earnings_Date", "Ticker"], ascending=[False, True]).reset_index(drop=True)
        master_file = root / "data" / "raw" / "us_tech_giants_earnings_history.csv"
        combined_df.to_csv(master_file, index=False)
        print("\n" + "=" * 75)
        print(f"[SUCCESS] Master earnings file saved: {master_file.name}")
        print(f"Total Quarterly Earnings Records: {len(combined_df):,} quarters")
        print("=" * 75)

    summary_df = pd.DataFrame(summary)
    print("\n--- EARNINGS DATASET SUMMARY ---")
    print(summary_df.to_string(index=False))
    print("=" * 75)

    return summary_df


if __name__ == "__main__":
    fetch_all_earnings_dates()
