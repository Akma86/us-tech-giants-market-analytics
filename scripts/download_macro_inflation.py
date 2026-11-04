#!/usr/bin/env python3
"""Automated US Inflation & Macroeconomic Data Ingestion Pipeline.

Fetches official primary macroeconomic time series:
1. Headline CPI (BLS · CPIAUCSL)
2. Core CPI (BLS · CPILFESL)
3. Headline PCE (BEA · PCEPI)
4. Core PCE (BEA · PCEPILFE - Fed Primary Inflation Target Gauge)
5. Effective Federal Funds Rate (Federal Reserve · FEDFUNDS)
6. 10-Year Breakeven Inflation Rate (St. Louis Fed · T10YIE)
7. 10Y-2Y Treasury Yield Spread (St. Louis Fed · T10Y2Y)

Computes Year-over-Year (YoY), Month-over-Month (MoM), 3M Annualized rates,
Real Policy Rates, and the CPI-PCE Wedge.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Workspace directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_MACRO_DIR = PROJECT_ROOT / "data" / "raw" / "macro"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

SERIES_SPECS = {
    "CPIAUCSL": {
        "name": "Headline CPI",
        "agency": "Bureau of Labor Statistics (BLS)",
        "freq": "Monthly",
        "units": "Index 1982-1984=100, Seasonally Adjusted",
        "description": "Consumer Price Index for All Urban Consumers: All Items",
    },
    "CPILFESL": {
        "name": "Core CPI",
        "agency": "Bureau of Labor Statistics (BLS)",
        "freq": "Monthly",
        "units": "Index 1982-1984=100, Seasonally Adjusted",
        "description": "Consumer Price Index for All Urban Consumers: All Items Less Food and Energy",
    },
    "PCEPI": {
        "name": "Headline PCE",
        "agency": "Bureau of Economic Analysis (BEA)",
        "freq": "Monthly",
        "units": "Index 2017=100, Seasonally Adjusted",
        "description": "Personal Consumption Expenditures: Chain-type Price Index",
    },
    "PCEPILFE": {
        "name": "Core PCE",
        "agency": "Bureau of Economic Analysis (BEA)",
        "freq": "Monthly",
        "units": "Index 2017=100, Seasonally Adjusted",
        "description": "Personal Consumption Expenditures Excluding Food and Energy (Federal Reserve Preferred Gauge)",
    },
    "FEDFUNDS": {
        "name": "Effective Federal Funds Rate",
        "agency": "Federal Reserve Board of Governors",
        "freq": "Monthly",
        "units": "Percent",
        "description": "Volume-weighted median of overnight federal funds transactions",
    },
    "T10YIE": {
        "name": "10-Year Breakeven Inflation",
        "agency": "Federal Reserve Bank of St. Louis",
        "freq": "Daily (Aggregated to Monthly)",
        "units": "Percent",
        "description": "Expected 10-year inflation implied by 10Y Nominal vs TIPS yield spread",
    },
    "T10Y2Y": {
        "name": "10Y-2Y Treasury Yield Spread",
        "agency": "Federal Reserve Bank of St. Louis",
        "freq": "Daily (Aggregated to Monthly)",
        "units": "Percent",
        "description": "Yield curve slope indicator (10-Year Constant Maturity minus 2-Year)",
    },
}


def fetch_fred_series(series_id: str) -> pd.DataFrame:
    """Fetch series from FRED using curl for robust bot-protection handling, with retry & cache fallback."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    cache_path = RAW_MACRO_DIR / f"{series_id.lower()}.csv"
    
    last_err = None
    for attempt in range(1, 4):
        cmd = ["curl.exe", "-s", url, "--max-time", "20"]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if res.returncode == 0 and res.stdout.strip():
            try:
                df = pd.read_csv(io.StringIO(res.stdout))
                date_col = "observation_date" if "observation_date" in df.columns else "DATE"
                if date_col in df.columns and series_id in df.columns:
                    df = df.rename(columns={date_col: "Date", series_id: "Value"})
                    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
                    df["Value"] = pd.to_numeric(df["Value"].replace(".", pd.NA), errors="coerce")
                    df = df.dropna().sort_values("Date").reset_index(drop=True)
                    return df
            except Exception as e:
                last_err = e
        else:
            last_err = RuntimeError(f"curl exit code {res.returncode}")
        time.sleep(2 * attempt)

    # Fallback to existing cache if available
    if cache_path.exists():
        print(f"(using local cache for {series_id})", end=" ", flush=True)
        df = pd.read_csv(cache_path)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
        return df.dropna().sort_values("Date").reset_index(drop=True)

    raise RuntimeError(f"Failed to fetch {series_id} after 3 attempts: {last_err}")


def main() -> None:
    RAW_MACRO_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("=================================================================")
    print("US INFLATION & MACROECONOMIC DATA INGESTION ENGINE")
    print("Primary Sources: BLS, BEA, Federal Reserve Board, St. Louis Fed")
    print("=================================================================\n")

    dfs = {}
    for sid, meta in SERIES_SPECS.items():
        print(f"Fetching {sid:<10} | {meta['name']:<28} ({meta['agency']})...", end=" ", flush=True)
        try:
            df = fetch_fred_series(sid)
            # Save raw series
            raw_path = RAW_MACRO_DIR / f"{sid.lower()}.csv"
            df.to_csv(raw_path, index=False)
            dfs[sid] = df
            latest_row = df.iloc[-1]
            print(f"✓ {len(df):>5} obs | Latest: {latest_row['Date'].strftime('%Y-%m-%d')} = {latest_row['Value']:>8.3f}")
        except Exception as e:
            print(f"✗ FAILED: {e}")

    # Build Monthly Consolidated Matrix
    print("\nEngineering Monthly Macroeconomic & Inflation Matrix...")
    
    # Standardize to Monthly (End of Month)
    monthly_series = {}
    for sid, df in dfs.items():
        m_df = df.copy()
        # For monthly series (1st of month), convert to YYYY-MM
        m_df["YearMonth"] = m_df["Date"].dt.to_period("M")
        # For daily series, take monthly mean
        if SERIES_SPECS[sid]["freq"].startswith("Daily"):
            m_agg = m_df.groupby("YearMonth")["Value"].mean().reset_index()
        else:
            m_agg = m_df.groupby("YearMonth")["Value"].last().reset_index()
        m_agg = m_agg.rename(columns={"Value": sid})
        monthly_series[sid] = m_agg

    # Merge all on YearMonth
    merged = None
    for sid, m_df in monthly_series.items():
        if merged is None:
            merged = m_df
        else:
            merged = pd.merge(merged, m_df, on="YearMonth", how="outer")

    merged = merged.sort_values("YearMonth").reset_index(drop=True)
    merged["Date"] = merged["YearMonth"].dt.to_timestamp(how="end").dt.strftime("%Y-%m-%d")

    # Reorder columns with Date first
    cols = ["Date", "YearMonth"] + list(SERIES_SPECS.keys())
    merged = merged[[c for c in cols if c in merged.columns]]

    # Compute Inflation Rates (% YoY and % MoM)
    # 1. Headline CPI YoY & MoM
    if "CPIAUCSL" in merged.columns:
        merged["CPI_Headline_Index"] = merged["CPIAUCSL"]
        merged["CPI_Headline_YoY_Pct"] = ((merged["CPIAUCSL"] / merged["CPIAUCSL"].shift(12)) - 1.0) * 100.0
        merged["CPI_Headline_MoM_Pct"] = ((merged["CPIAUCSL"] / merged["CPIAUCSL"].shift(1)) - 1.0) * 100.0
        merged["CPI_Headline_3M_Ann_Pct"] = (((merged["CPIAUCSL"] / merged["CPIAUCSL"].shift(3)) ** 4) - 1.0) * 100.0

    # 2. Core CPI YoY & MoM
    if "CPILFESL" in merged.columns:
        merged["CPI_Core_Index"] = merged["CPILFESL"]
        merged["CPI_Core_YoY_Pct"] = ((merged["CPILFESL"] / merged["CPILFESL"].shift(12)) - 1.0) * 100.0
        merged["CPI_Core_MoM_Pct"] = ((merged["CPILFESL"] / merged["CPILFESL"].shift(1)) - 1.0) * 100.0
        merged["CPI_Core_3M_Ann_Pct"] = (((merged["CPILFESL"] / merged["CPILFESL"].shift(3)) ** 4) - 1.0) * 100.0

    # 3. Headline PCE YoY & MoM
    if "PCEPI" in merged.columns:
        merged["PCE_Headline_Index"] = merged["PCEPI"]
        merged["PCE_Headline_YoY_Pct"] = ((merged["PCEPI"] / merged["PCEPI"].shift(12)) - 1.0) * 100.0
        merged["PCE_Headline_MoM_Pct"] = ((merged["PCEPI"] / merged["PCEPI"].shift(1)) - 1.0) * 100.0
        merged["PCE_Headline_3M_Ann_Pct"] = (((merged["PCEPI"] / merged["PCEPI"].shift(3)) ** 4) - 1.0) * 100.0

    # 4. Core PCE YoY & MoM (Fed Preferred)
    if "PCEPILFE" in merged.columns:
        merged["PCE_Core_Index"] = merged["PCEPILFE"]
        merged["PCE_Core_YoY_Pct"] = ((merged["PCEPILFE"] / merged["PCEPILFE"].shift(12)) - 1.0) * 100.0
        merged["PCE_Core_MoM_Pct"] = ((merged["PCEPILFE"] / merged["PCEPILFE"].shift(1)) - 1.0) * 100.0
        merged["PCE_Core_3M_Ann_Pct"] = (((merged["PCEPILFE"] / merged["PCEPILFE"].shift(3)) ** 4) - 1.0) * 100.0

    # 5. Real Fed Funds Rate (Fed Funds - Core PCE YoY)
    if "FEDFUNDS" in merged.columns and "PCE_Core_YoY_Pct" in merged.columns:
        merged["Real_Fed_Funds_Rate_Pct"] = merged["FEDFUNDS"] - merged["PCE_Core_YoY_Pct"]

    # 6. CPI vs PCE Wedge (Core CPI YoY minus Core PCE YoY)
    if "CPI_Core_YoY_Pct" in merged.columns and "PCE_Core_YoY_Pct" in merged.columns:
        merged["CPI_PCE_Core_Wedge_Pct"] = merged["CPI_Core_YoY_Pct"] - merged["PCE_Core_YoY_Pct"]

    # Save consolidated dataset
    merged["YearMonth"] = merged["YearMonth"].astype(str)
    out_csv = PROCESSED_DIR / "us_inflation_macro_monthly.csv"
    merged.to_csv(out_csv, index=False)
    print(f"✓ Consolidated matrix saved to {out_csv} ({len(merged)} rows)")

    # Filter to recent 25 years (2000 - Present) for focused research dataset
    recent_df = merged[merged["Date"] >= "2000-01-01"].copy()
    recent_csv = PROCESSED_DIR / "us_inflation_macro_2000_present.csv"
    recent_df.to_csv(recent_csv, index=False)
    print(f"✓ 2000–Present research matrix saved to {recent_csv} ({len(recent_df)} rows)")

    # Generate Summary Metadata JSON
    latest_valid = merged.dropna(subset=["CPI_Headline_YoY_Pct", "PCE_Core_YoY_Pct"]).iloc[-1]
    summary = {
        "pipeline_run_utc": datetime.utcnow().isoformat() + "Z",
        "sample_start_date": str(merged["Date"].min()),
        "sample_end_date": str(merged["Date"].max()),
        "total_monthly_observations": len(merged),
        "latest_macro_reading": {
            "date": latest_valid["Date"],
            "year_month": latest_valid["YearMonth"],
            "cpi_headline_yoy_pct": round(float(latest_valid["CPI_Headline_YoY_Pct"]), 2),
            "cpi_core_yoy_pct": round(float(latest_valid["CPI_Core_YoY_Pct"]), 2),
            "pce_headline_yoy_pct": round(float(latest_valid["PCE_Headline_YoY_Pct"]), 2),
            "pce_core_yoy_pct": round(float(latest_valid["PCE_Core_YoY_Pct"]), 2),
            "fed_funds_rate_pct": round(float(latest_valid.get("FEDFUNDS", 0)), 2),
            "real_policy_rate_pct": round(float(latest_valid.get("Real_Fed_Funds_Rate_Pct", 0)), 2),
            "cpi_pce_wedge_pct": round(float(latest_valid.get("CPI_PCE_Core_Wedge_Pct", 0)), 2),
            "breakeven_10y_inflation_pct": round(float(latest_valid.get("T10YIE", 0)), 2),
            "yield_curve_10y_2y_pct": round(float(latest_valid.get("T10Y2Y", 0)), 2),
        },
        "primary_sources": {
            "cpi": "Bureau of Labor Statistics (BLS) Consumer Price Index",
            "pce": "Bureau of Economic Analysis (BEA) Personal Consumption Expenditures",
            "rates_and_yields": "Federal Reserve Board & Federal Reserve Bank of St. Louis (FRED)",
        },
    }

    out_json = PROCESSED_DIR / "us_inflation_macro_summary.json"
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"✓ Summary JSON saved to {out_json}")

    print("\n-------------------------------------------------------------")
    print("LATEST US INFLATION & MACROECONOMIC SNAPSHOT:")
    for k, v in summary["latest_macro_reading"].items():
        print(f"  {k:<30}: {v}")
    print("-------------------------------------------------------------\n")


if __name__ == "__main__":
    main()
