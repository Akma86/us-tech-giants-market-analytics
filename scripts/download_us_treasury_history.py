"""Download primary US Treasury yield history (1919-Present) from FRED and align with S&P 500 (^GSPC).

Sources:
- M1333AUSM156NNBR : NBER Yields on Long-Term United States Bonds (1919-01 to 1944-02)
- LTGOVTBD         : Federal Reserve Long-Term U.S. Government Securities (1925-01 to 2000-06)
- GS10             : 10-Year Treasury Constant Maturity Yield, Monthly (1953-04 to Present)
- DGS10            : 10-Year Treasury Constant Maturity Yield, Daily (1962-01-02 to Present)
- TB3MS            : 3-Month Treasury Bill Secondary Market Rate, Monthly (1934-01 to Present)
- GS1 / GS2 / GS5 / GS20 / GS30, DGS2 / DGS30, DFF, FEDFUNDS, CPIAUCSL
- ^GSPC & ^TNX     : Local SQLite/raw equity database (+ optional yfinance tail sync)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_MACRO_DIR = ROOT_DIR / "data" / "raw" / "macro"
RAW_EQUITY_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
PORTFOLIO_DATA_DIR = ROOT_DIR / "portfolio" / "data"
DB_PATH = ROOT_DIR / "data" / "database" / "us_equities.db"

FRED_SERIES: dict[str, dict[str, str]] = {
    "M1333AUSM156NNBR": {
        "name": "NBER Long-Term US Government Bond Yield",
        "freq": "M",
        "units": "%",
    },
    "LTGOVTBD": {
        "name": "Federal Reserve Long-Term US Government Securities Yield",
        "freq": "M",
        "units": "%",
    },
    "TB3MS": {
        "name": "3-Month Treasury Bill Secondary Market Rate",
        "freq": "M",
        "units": "%",
    },
    "DTB3": {
        "name": "3-Month Treasury Bill Secondary Market Rate (Daily)",
        "freq": "D",
        "units": "%",
    },
    "GS1": {
        "name": "1-Year Treasury Constant Maturity Yield (Monthly)",
        "freq": "M",
        "units": "%",
    },
    "GS2": {
        "name": "2-Year Treasury Constant Maturity Yield (Monthly)",
        "freq": "M",
        "units": "%",
    },
    "GS5": {
        "name": "5-Year Treasury Constant Maturity Yield (Monthly)",
        "freq": "M",
        "units": "%",
    },
    "GS10": {
        "name": "10-Year Treasury Constant Maturity Yield (Monthly)",
        "freq": "M",
        "units": "%",
    },
    "GS20": {
        "name": "20-Year Treasury Constant Maturity Yield (Monthly)",
        "freq": "M",
        "units": "%",
    },
    "GS30": {
        "name": "30-Year Treasury Constant Maturity Yield (Monthly)",
        "freq": "M",
        "units": "%",
    },
    "DGS10": {
        "name": "10-Year Treasury Constant Maturity Yield (Daily)",
        "freq": "D",
        "units": "%",
    },
    "DGS2": {
        "name": "2-Year Treasury Constant Maturity Yield (Daily)",
        "freq": "D",
        "units": "%",
    },
    "DGS30": {
        "name": "30-Year Treasury Constant Maturity Yield (Daily)",
        "freq": "D",
        "units": "%",
    },
    "DFF": {
        "name": "Federal Funds Effective Rate (Daily)",
        "freq": "D",
        "units": "%",
    },
    "FEDFUNDS": {
        "name": "Federal Funds Effective Rate (Monthly)",
        "freq": "M",
        "units": "%",
    },
    "CPIAUCSL": {
        "name": "CPI All Urban Consumers (Index 1982-84=100)",
        "freq": "M",
        "units": "Index",
    },
}


@dataclass(frozen=True)
class SecularEra:
    label: str
    start: str
    end: str | None
    rate_regime: str


SECULAR_ERAS: list[SecularEra] = [
    SecularEra("1928-1945 · Depression & WWII Peg", "1928-01-01", "1945-12-01", "2.0%–3.9% Capped / Crisis"),
    SecularEra("1946-1964 · Post-War Expansion", "1946-01-01", "1964-12-01", "Gradual Normalization (<4.3%)"),
    SecularEra("1965-1981 · Great Inflation Surge", "1965-01-01", "1981-09-01", "Secular Bear Bonds (Yields -> 15.3%)"),
    SecularEra("1982-2021 · Great Disinflation Bull", "1981-10-01", "2021-12-01", "Secular Yield Compression (15% -> 0.6%)"),
    SecularEra("2022-Present · Tightening & Higher Neutral", "2022-01-01", None, "Rapid Fed Hike & Elevated Term Premia"),
]


def download_fred_csv(series_id: str, force: bool = True) -> pd.DataFrame:
    """Download a FRED CSV via curl.exe with urllib fallback and cache to data/raw/macro/."""
    RAW_MACRO_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_MACRO_DIR / f"{series_id.lower()}.csv"
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

    if force or not raw_path.exists():
        content = ""
        try:
            proc = subprocess.run(
                ["curl.exe", "-sS", "-L", "--max-time", "25", url],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                content = proc.stdout
        except FileNotFoundError:
            content = ""

        if not content:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as resp:
                content = resp.read().decode("utf-8", errors="replace")

        lines = content.strip().splitlines()
        if not lines or "," not in lines[0]:
            raise RuntimeError(f"Invalid FRED response for {series_id}: {content[:120]}")
        raw_path.write_text(content, encoding="utf-8")

    df = pd.read_csv(raw_path)
    date_col = df.columns[0]
    val_col = df.columns[1]
    df = df.rename(columns={date_col: "date", val_col: series_id.lower()})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df[series_id.lower()] = pd.to_numeric(df[series_id.lower()], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").drop_duplicates(subset=["date"], keep="last")
    return df


def load_equity_symbol(symbol: str, sync_yf: bool = False) -> pd.DataFrame:
    """Load daily OHLCV for ^GSPC or ^TNX from SQLite/raw CSV, optionally syncing latest yfinance bars."""
    df = pd.DataFrame()
    if DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql_query(
                "SELECT date, open, high, low, close, adj_close, volume FROM daily_prices WHERE symbol = ? ORDER BY date ASC",
                conn,
                params=(symbol,),
            )

    raw_csv_name = f"{symbol.lstrip('^')}.csv"
    raw_csv_path = RAW_EQUITY_DIR / raw_csv_name
    if df.empty and raw_csv_path.exists():
        raw_df = pd.read_csv(raw_csv_path)
        cols = [c for c in ["date", "open", "high", "low", "close", "adj_close", "volume"] if c in raw_df.columns]
        df = raw_df[cols].copy()

    if df.empty:
        raise FileNotFoundError(f"No historical price data found for {symbol} in DB or {raw_csv_path}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in ["open", "high", "low", "close", "adj_close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["date", "close"]).sort_values("date").drop_duplicates("date", keep="last")

    if sync_yf:
        try:
            import yfinance as yf  # noqa: PLC0415

            last_date = df["date"].max()
            start_str = (last_date - pd.Timedelta(days=5)).strftime("%Y-%m-%d")
            tail = yf.download(symbol, start=start_str, progress=False, auto_adjust=False)
            if isinstance(tail, pd.DataFrame) and not tail.empty:
                if isinstance(tail.columns, pd.MultiIndex):
                    tail.columns = [str(c[0]).lower().replace(" ", "_") for c in tail.columns]
                else:
                    tail.columns = [str(c).lower().replace(" ", "_") for c in tail.columns]
                tail = tail.reset_index()
                dt_col = "Date" if "Date" in tail.columns else ("date" if "date" in tail.columns else tail.columns[0])
                tail["date"] = pd.to_datetime(tail[dt_col]).dt.tz_localize(None)
                keep = [c for c in ["date", "open", "high", "low", "close", "adj_close", "volume"] if c in tail.columns]
                tail = tail[keep].dropna(subset=["date", "close"])
                if not tail.empty:
                    df = (
                        pd.concat([df, tail], ignore_index=True)
                        .sort_values("date")
                        .drop_duplicates("date", keep="last")
                        .reset_index(drop=True)
                    )
        except Exception as exc:  # noqa: BLE001
            print(f"[!] yfinance sync warning for {symbol}: {exc}")

    return df.reset_index(drop=True)


def build_monthly_treasury_history(fred_frames: dict[str, pd.DataFrame], tnx_daily: pd.DataFrame) -> pd.DataFrame:
    """Stitch primary monthly US Long-Term / 10Y Treasury yields cleanly from 1919-01 to latest."""
    monthly_ids = ["M1333AUSM156NNBR", "LTGOVTBD", "GS10", "TB3MS", "GS1", "GS2", "GS5", "GS20", "GS30", "FEDFUNDS", "CPIAUCSL"]
    merged = fred_frames["M1333AUSM156NNBR"][["date", "m1333ausm156nnbr"]].copy()
    for sid in monthly_ids[1:]:
        col = sid.lower()
        merged = merged.merge(fred_frames[sid][["date", col]], on="date", how="outer")

    # Add month-to-date average from daily DGS10 (or ^TNX) & DTB3 / DFF if current month is ahead of monthly FRED release
    dgs10 = fred_frames["DGS10"].dropna(subset=["dgs10"]).copy()
    dgs10["month"] = dgs10["date"].dt.to_period("M").dt.to_timestamp()
    dgs10_mtd = dgs10.groupby("month", as_index=False)["dgs10"].mean().rename(columns={"month": "date", "dgs10": "dgs10_mtd"})

    dtb3 = fred_frames["DTB3"].dropna(subset=["dtb3"]).copy()
    dtb3["month"] = dtb3["date"].dt.to_period("M").dt.to_timestamp()
    dtb3_mtd = dtb3.groupby("month", as_index=False)["dtb3"].mean().rename(columns={"month": "date", "dtb3": "dtb3_mtd"})

    tnx = tnx_daily[["date", "close"]].dropna(subset=["close"]).copy()
    tnx["month"] = tnx["date"].dt.to_period("M").dt.to_timestamp()
    tnx_mtd = tnx.groupby("month", as_index=False)["close"].mean().rename(columns={"month": "date", "close": "tnx_mtd"})

    merged = merged.merge(dgs10_mtd, on="date", how="outer").merge(dtb3_mtd, on="date", how="outer").merge(tnx_mtd, on="date", how="outer")
    merged = merged.sort_values("date").reset_index(drop=True)

    dff = fred_frames["DFF"].dropna(subset=["dff"]).copy()
    dff["month"] = dff["date"].dt.to_period("M").dt.to_timestamp()
    dff_mtd = dff.groupby("month", as_index=False)["dff"].mean().rename(columns={"month": "date", "dff": "dff_mtd"})
    merged = merged.merge(dff_mtd, on="date", how="left")
    merged["fedfunds_rate"] = merged["fedfunds"].where(merged["fedfunds"].notna(), merged["dff_mtd"])
    merged["tb3ms"] = merged["tb3ms"].where(merged["tb3ms"].notna(), merged["dtb3_mtd"])

    # Stitch authoritative US 10Y / Long-Term Treasury Yield benchmark:
    # 1. GS10 (10Y Constant Maturity, 1953-04+) -> highest precedence
    # 2. LTGOVTBD (Fed Long-Term US Govt Bonds, 1925-01..1953-03) -> official pre-CMT Federal Reserve benchmark
    # 3. M1333AUSM156NNBR (NBER US Long-Term Govt Bonds, 1919-01..1924-12) -> pre-Fed series start
    # 4. DGS10_MTD / TNX_MTD -> current in-flight month before GS10 monthly release
    sources = np.full(len(merged), "", dtype=object)
    yield_10y = np.full(len(merged), np.nan, dtype=float)

    for idx, row in merged.iterrows():
        if pd.notna(row.get("gs10")):
            yield_10y[idx] = float(row["gs10"])
            sources[idx] = "GS10 (Fed 10Y CMT)"
        elif pd.notna(row.get("dgs10_mtd")) and row["date"] >= pd.Timestamp("1962-01-01"):
            yield_10y[idx] = float(row["dgs10_mtd"])
            sources[idx] = "DGS10 (Month-to-Date Avg)"
        elif pd.notna(row.get("tnx_mtd")) and row["date"] >= pd.Timestamp("1962-01-01"):
            yield_10y[idx] = float(row["tnx_mtd"])
            sources[idx] = "^TNX (Month-to-Date Avg)"
        elif pd.notna(row.get("ltgovtbd")):
            yield_10y[idx] = float(row["ltgovtbd"])
            sources[idx] = "LTGOVTBD (Fed LT Govt Bond)"
        elif pd.notna(row.get("m1333ausm156nnbr")):
            yield_10y[idx] = float(row["m1333ausm156nnbr"])
            sources[idx] = "M1333AUSM156NNBR (NBER LT US Bond)"

    merged["treasury_10y_yield"] = yield_10y
    merged["source_series"] = sources
    merged = merged.dropna(subset=["treasury_10y_yield"]).sort_values("date").reset_index(drop=True)

    # Derived curve spreads and inflation-adjusted yield
    merged = merged.rename(
        columns={
            "m1333ausm156nnbr": "nber_lt_bond_yield",
            "ltgovtbd": "ltgovtbd_yield",
            "gs10": "gs10_yield",
            "tb3ms": "tbill_3m_yield",
            "gs1": "yield_1y",
            "gs2": "yield_2y",
            "gs5": "yield_5y",
            "gs20": "yield_20y",
            "gs30": "yield_30y",
            "cpiaucsl": "cpi_index",
        }
    )
    merged["spread_10y_3m"] = (merged["treasury_10y_yield"] - merged["tbill_3m_yield"]).round(4)
    merged["spread_10y_2y"] = (merged["treasury_10y_yield"] - merged["yield_2y"]).round(4)
    merged["cpi_yoy_pct"] = (merged["cpi_index"].pct_change(12, fill_method=None) * 100.0).round(3)
    merged["real_10y_yield"] = (merged["treasury_10y_yield"] - merged["cpi_yoy_pct"]).round(3)
    merged["treasury_10y_yoy_bps"] = ((merged["treasury_10y_yield"] - merged["treasury_10y_yield"].shift(12)) * 100.0).round(1)

    ordered_cols = [
        "date",
        "treasury_10y_yield",
        "source_series",
        "treasury_10y_yoy_bps",
        "tbill_3m_yield",
        "yield_1y",
        "yield_2y",
        "yield_5y",
        "yield_20y",
        "yield_30y",
        "spread_10y_3m",
        "spread_10y_2y",
        "fedfunds_rate",
        "cpi_index",
        "cpi_yoy_pct",
        "real_10y_yield",
        "nber_lt_bond_yield",
        "ltgovtbd_yield",
        "gs10_yield",
    ]
    return merged[ordered_cols]


def assign_secular_era(date_val: pd.Timestamp) -> str:
    for era in SECULAR_ERAS:
        start_ts = pd.Timestamp(era.start)
        end_ts = pd.Timestamp(era.end) if era.end else pd.Timestamp("2099-12-31")
        if start_ts <= date_val <= end_ts:
            return era.label
    return "1919-1927 · Post-WWI Reconstruction"


def attach_treasury_prices_and_total_return(
    panel: pd.DataFrame, fred_frames: dict[str, pd.DataFrame], tnx_daily: pd.DataFrame
) -> pd.DataFrame:
    """Attach Swinkels (2019) 10Y UST Total Return / Clean Price Indices (1919=100) and real market prices."""
    # EOM 10Y yield for accurate bond return alignment (DGS10 1962+, ^TNX latest month, stitched monthly pre-1962)
    dgs10 = fred_frames["DGS10"].dropna(subset=["dgs10"]).copy()
    dgs10["month"] = dgs10["date"].dt.to_period("M").dt.to_timestamp()
    dgs10_eom = dgs10.groupby("month", as_index=False)["dgs10"].last().rename(columns={"month": "date", "dgs10": "dgs10_eom"})

    tnx = tnx_daily[["date", "close"]].dropna(subset=["close"]).copy()
    tnx["month"] = tnx["date"].dt.to_period("M").dt.to_timestamp()
    tnx_eom = tnx.groupby("month", as_index=False)["close"].last().rename(columns={"month": "date", "close": "tnx_eom"})

    out = panel.merge(dgs10_eom, on="date", how="left").merge(tnx_eom, on="date", how="left").sort_values("date").reset_index(drop=True)
    # Prefer EOM DGS10 from 1962-01 onward; fall back to ^TNX EOM for latest in-flight month; else primary stitched yield
    pricing_y = out["treasury_10y_yield"].copy()
    mask_1962 = out["date"] >= pd.Timestamp("1962-01-01")
    pricing_y = pricing_y.where(~mask_1962 | out["dgs10_eom"].isna(), out["dgs10_eom"])
    mask_tnx_fill = mask_1962 & out["dgs10_eom"].isna() & out["tnx_eom"].notna()
    pricing_y = pricing_y.where(~mask_tnx_fill, out["tnx_eom"])
    # For incomplete latest month where DGS10 stops a couple days before ^TNX, use latest ^TNX EOM on last row
    if pd.notna(out["tnx_eom"].iloc[-1]):
        pricing_y.iloc[-1] = float(out["tnx_eom"].iloc[-1])

    m_rem = 10.0 - (1.0 / 12.0)
    tr_idx = np.full(len(out), np.nan, dtype=float)
    clean_idx = np.full(len(out), np.nan, dtype=float)
    tr_mult = 100.0
    clean_mult = 100.0
    prev_y: float | None = None

    for idx, y_val in enumerate(pricing_y):
        if pd.isna(y_val):
            continue
        y1 = float(y_val) / 100.0
        if prev_y is None:
            tr_idx[idx] = tr_mult
            clean_idx[idx] = clean_mult
            prev_y = y1
            continue
        y0 = prev_y
        dfac = (1.0 + y1 / 2.0) ** (-2.0 * m_rem)
        p_end = (y0 / y1) * (1.0 - dfac) + dfac if y1 > 1e-6 else 1.0 + y0 * m_rem
        cap_ret = p_end - 1.0
        carry = y0 / 12.0
        clean_mult *= 1.0 + cap_ret
        tr_mult *= 1.0 + cap_ret + carry
        clean_idx[idx] = clean_mult
        tr_idx[idx] = tr_mult
        prev_y = y1

    out["ust10y_tr_index"] = pd.Series(tr_idx, index=out.index).round(2)
    out["ust10y_clean_index"] = pd.Series(clean_idx, index=out.index).round(2)
    out["ust10y_tr_monthly_ret_pct"] = (out["ust10y_tr_index"].pct_change(1, fill_method=None) * 100.0).round(3)
    out["ust10y_tr_yoy_pct"] = (out["ust10y_tr_index"].pct_change(12, fill_method=None) * 100.0).round(3)
    out["ust10y_tr_drawdown_pct"] = (((out["ust10y_tr_index"] / out["ust10y_tr_index"].cummax()) - 1.0) * 100.0).round(3)

    # Merge monthly market prices from us_treasury_prices_daily.csv if generated
    prices_daily_csv = PROCESSED_DIR / "us_treasury_prices_daily.csv"
    mkt_cols = [
        "ief_close",
        "ief_adj_close",
        "tlt_close",
        "tlt_adj_close",
        "shy_close",
        "shy_adj_close",
        "zn_futures_close",
        "zb_futures_close",
        "vustx_adj_close",
        "vfitx_adj_close",
    ]
    if prices_daily_csv.exists():
        p_df = pd.read_csv(prices_daily_csv)
        p_df["date"] = pd.to_datetime(p_df["date"])
        p_df["month"] = p_df["date"].dt.to_period("M").dt.to_timestamp()
        keep_cols = [c for c in mkt_cols if c in p_df.columns]
        agg_map = {c: "last" for c in keep_cols}
        p_monthly = p_df.sort_values("date").groupby("month", as_index=False).agg(agg_map).rename(columns={"month": "date"})
        out = out.merge(p_monthly, on="date", how="left")
    for c in mkt_cols:
        if c not in out.columns:
            out[c] = np.nan
        else:
            out[c] = out[c].round(2)

    out = out.drop(columns=["dgs10_eom", "tnx_eom"], errors="ignore")
    return out


def build_monthly_sp500_comparison(
    treasury_monthly: pd.DataFrame, gspc_daily: pd.DataFrame, fred_frames: dict[str, pd.DataFrame], tnx_daily: pd.DataFrame
) -> pd.DataFrame:
    """Merge stitched 1919-Present US Treasury yields & prices with monthly S&P 500 metrics."""
    sp = gspc_daily[["date", "close"]].copy()
    sp["month"] = sp["date"].dt.to_period("M").dt.to_timestamp()
    sp_monthly = (
        sp.groupby("month", as_index=False)
        .agg(
            sp500_close=("close", "last"),
            sp500_month_high=("close", "max"),
            sp500_month_low=("close", "min"),
            sp500_last_trade_date=("date", "max"),
        )
        .rename(columns={"month": "date"})
        .sort_values("date")
        .reset_index(drop=True)
    )

    sp_monthly["sp500_monthly_ret_pct"] = (sp_monthly["sp500_close"].pct_change(1, fill_method=None) * 100.0).round(3)
    sp_monthly["sp500_yoy_pct"] = (sp_monthly["sp500_close"].pct_change(12, fill_method=None) * 100.0).round(3)
    sp_monthly["sp500_5y_cagr_pct"] = (((sp_monthly["sp500_close"] / sp_monthly["sp500_close"].shift(60)) ** (1.0 / 5.0) - 1.0) * 100.0).round(3)
    sp_monthly["sp500_10y_cagr_pct"] = (((sp_monthly["sp500_close"] / sp_monthly["sp500_close"].shift(120)) ** (1.0 / 10.0) - 1.0) * 100.0).round(3)
    running_peak = sp_monthly["sp500_close"].cummax()
    sp_monthly["sp500_drawdown_pct"] = (((sp_monthly["sp500_close"] / running_peak) - 1.0) * 100.0).round(3)

    panel = treasury_monthly.merge(sp_monthly, on="date", how="outer").sort_values("date").reset_index(drop=True)
    panel = attach_treasury_prices_and_total_return(panel, fred_frames, tnx_daily)
    panel["secular_era"] = panel["date"].apply(assign_secular_era)
    panel["treasury_10y_yield"] = panel["treasury_10y_yield"].round(4)
    panel["sp500_close"] = panel["sp500_close"].round(2)

    cols = [
        "date",
        "treasury_10y_yield",
        "source_series",
        "treasury_10y_yoy_bps",
        "tbill_3m_yield",
        "yield_2y",
        "yield_30y",
        "spread_10y_3m",
        "spread_10y_2y",
        "fedfunds_rate",
        "cpi_yoy_pct",
        "real_10y_yield",
        "ust10y_tr_index",
        "ust10y_clean_index",
        "ust10y_tr_monthly_ret_pct",
        "ust10y_tr_yoy_pct",
        "ust10y_tr_drawdown_pct",
        "ief_close",
        "ief_adj_close",
        "tlt_close",
        "tlt_adj_close",
        "shy_close",
        "shy_adj_close",
        "zn_futures_close",
        "zb_futures_close",
        "vustx_adj_close",
        "vfitx_adj_close",
        "sp500_close",
        "sp500_monthly_ret_pct",
        "sp500_yoy_pct",
        "sp500_5y_cagr_pct",
        "sp500_10y_cagr_pct",
        "sp500_drawdown_pct",
        "sp500_last_trade_date",
        "secular_era",
    ]
    return panel[cols]


def build_daily_sp500_comparison(fred_frames: dict[str, pd.DataFrame], gspc_daily: pd.DataFrame, tnx_daily: pd.DataFrame) -> pd.DataFrame:
    """Build daily aligned 1962-Present dataset using DGS10 (^TNX fallback on latest day) & ^GSPC."""
    dgs10 = fred_frames["DGS10"][["date", "dgs10"]].copy()
    dgs2 = fred_frames["DGS2"][["date", "dgs2"]].copy()
    dgs30 = fred_frames["DGS30"][["date", "dgs30"]].copy()
    dff = fred_frames["DFF"][["date", "dff"]].copy()

    sp = gspc_daily[gspc_daily["date"] >= pd.Timestamp("1962-01-02")][["date", "close"]].rename(columns={"close": "sp500_close"}).copy()
    tnx = tnx_daily[["date", "close"]].rename(columns={"close": "tnx_close"}).copy()

    daily = (
        sp.merge(dgs10, on="date", how="left")
        .merge(tnx, on="date", how="left")
        .merge(dgs2, on="date", how="left")
        .merge(dgs30, on="date", how="left")
        .merge(dff, on="date", how="left")
        .sort_values("date")
        .reset_index(drop=True)
    )

    daily["treasury_10y_yield"] = daily["dgs10"].where(daily["dgs10"].notna(), daily["tnx_close"])
    daily["yield_source"] = np.where(daily["dgs10"].notna(), "DGS10", np.where(daily["tnx_close"].notna(), "^TNX", ""))
    daily["treasury_10y_yield"] = daily["treasury_10y_yield"].ffill()
    daily["spread_10y_2y"] = (daily["treasury_10y_yield"] - daily["dgs2"]).round(4)

    daily["sp500_ret_1d_pct"] = (daily["sp500_close"].pct_change(1) * 100.0).round(4)
    daily["treasury_10y_chg_bps"] = (daily["treasury_10y_yield"].diff(1) * 100.0).round(2)
    daily["sp500_252d_ret_pct"] = (daily["sp500_close"].pct_change(252) * 100.0).round(3)
    daily["sp500_drawdown_pct"] = (((daily["sp500_close"] / daily["sp500_close"].cummax()) - 1.0) * 100.0).round(3)
    daily["rolling_60d_corr_sp_vs_10y_chg"] = (
        daily["sp500_ret_1d_pct"].rolling(60, min_periods=45).corr(daily["treasury_10y_chg_bps"]).round(4)
    )
    daily["rolling_252d_corr_sp_vs_10y_chg"] = (
        daily["sp500_ret_1d_pct"].rolling(252, min_periods=180).corr(daily["treasury_10y_chg_bps"]).round(4)
    )

    cols = [
        "date",
        "sp500_close",
        "treasury_10y_yield",
        "yield_source",
        "dgs2",
        "dgs30",
        "spread_10y_2y",
        "dff",
        "sp500_ret_1d_pct",
        "treasury_10y_chg_bps",
        "sp500_252d_ret_pct",
        "sp500_drawdown_pct",
        "rolling_60d_corr_sp_vs_10y_chg",
        "rolling_252d_corr_sp_vs_10y_chg",
    ]
    return daily[cols]


def compute_summary(monthly_cmp: pd.DataFrame, daily_cmp: pd.DataFrame) -> dict[str, Any]:
    """Compute rigorous historical summary metrics & secular era comparison table."""
    valid_yield = monthly_cmp.dropna(subset=["treasury_10y_yield"])
    overlap = monthly_cmp.dropna(subset=["treasury_10y_yield", "sp500_close"])

    peak_yield_row = valid_yield.loc[valid_yield["treasury_10y_yield"].idxmax()]
    trough_yield_row = valid_yield.loc[valid_yield["treasury_10y_yield"].idxmin()]
    latest_row = overlap.iloc[-1]

    # Regime summary over overlapping 1928-Present window
    regimes: list[dict[str, Any]] = []
    for era in SECULAR_ERAS:
        start_ts = pd.Timestamp(era.start)
        end_ts = pd.Timestamp(era.end) if era.end else overlap["date"].max()
        sub = overlap[(overlap["date"] >= start_ts) & (overlap["date"] <= end_ts)].dropna(subset=["sp500_close"])
        if len(sub) < 6:
            continue
        years = max((sub["date"].iloc[-1] - sub["date"].iloc[0]).days / 365.25, 1.0 / 12.0)
        sp_cagr = ((sub["sp500_close"].iloc[-1] / sub["sp500_close"].iloc[0]) ** (1.0 / years) - 1.0) * 100.0
        # Max drawdown within this regime window
        reg_dd = ((sub["sp500_close"] / sub["sp500_close"].cummax()) - 1.0).min() * 100.0
        corr_sub = sub.dropna(subset=["sp500_yoy_pct", "treasury_10y_yoy_bps"])
        corr_yoy = float(corr_sub["sp500_yoy_pct"].corr(corr_sub["treasury_10y_yoy_bps"])) if len(corr_sub) >= 12 else None

        regimes.append(
            {
                "era": era.label,
                "rate_regime": era.rate_regime,
                "start_date": sub["date"].iloc[0].strftime("%Y-%m-%d"),
                "end_date": sub["date"].iloc[-1].strftime("%Y-%m-%d"),
                "months": int(len(sub)),
                "avg_10y_yield_pct": round(float(sub["treasury_10y_yield"].mean()), 2),
                "min_10y_yield_pct": round(float(sub["treasury_10y_yield"].min()), 2),
                "max_10y_yield_pct": round(float(sub["treasury_10y_yield"].max()), 2),
                "sp500_cagr_pct": round(float(sp_cagr), 2),
                "sp500_max_drawdown_pct": round(float(reg_dd), 2),
                "corr_sp500_yoy_vs_10y_chg": round(corr_yoy, 3) if corr_yoy is not None else None,
            }
        )

    # Boundary continuity checks at splice transitions
    lt_at_1925 = monthly_cmp[monthly_cmp["date"] == pd.Timestamp("1925-01-01")]["treasury_10y_yield"].iloc[0]
    gs10_at_1953_04 = monthly_cmp[monthly_cmp["date"] == pd.Timestamp("1953-04-01")]["treasury_10y_yield"].iloc[0]

    # Yield curve inversion count (10Y - 3M < 0)
    inv_df = monthly_cmp.dropna(subset=["spread_10y_3m"])
    inv_months = int((inv_df["spread_10y_3m"] < 0).sum())

    # Daily high/low check
    daily_peak = daily_cmp.loc[daily_cmp["treasury_10y_yield"].idxmax()]
    daily_trough = daily_cmp.loc[daily_cmp["treasury_10y_yield"].idxmin()]
    valid_spread_rows = overlap.dropna(subset=["spread_10y_3m"])
    latest_spread_row = valid_spread_rows.iloc[-1] if not valid_spread_rows.empty else None
    valid_real_rows = overlap.dropna(subset=["real_10y_yield"])
    latest_real_row = valid_real_rows.iloc[-1] if not valid_real_rows.empty else None

    # Treasury bond price & total return benchmarks
    tr_overlap = overlap.dropna(subset=["ust10y_tr_index"])
    tr_years = max((tr_overlap["date"].iloc[-1] - tr_overlap["date"].iloc[0]).days / 365.25, 1.0)
    tr_cagr = ((tr_overlap["ust10y_tr_index"].iloc[-1] / tr_overlap["ust10y_tr_index"].iloc[0]) ** (1.0 / tr_years) - 1.0) * 100.0
    sp_cagr_full = ((tr_overlap["sp500_close"].iloc[-1] / tr_overlap["sp500_close"].iloc[0]) ** (1.0 / tr_years) - 1.0) * 100.0
    ust_max_dd = float(overlap["ust10y_tr_drawdown_pct"].min())

    ief_sub = monthly_cmp.dropna(subset=["ief_adj_close", "ust10y_tr_monthly_ret_pct"]).copy()
    ief_sub["ief_mret"] = ief_sub["ief_adj_close"].pct_change(1, fill_method=None) * 100.0
    ief_corr = float(ief_sub["ust10y_tr_monthly_ret_pct"].corr(ief_sub["ief_mret"])) if len(ief_sub) > 12 else None

    tlt_sub = monthly_cmp.dropna(subset=["tlt_adj_close"])
    tlt_dd = float(((tlt_sub["tlt_adj_close"] / tlt_sub["tlt_adj_close"].cummax()) - 1.0).min() * 100.0) if not tlt_sub.empty else None

    cat_path = PROCESSED_DIR / "us_treasury_price_catalog.json"
    price_catalog = json.loads(cat_path.read_text(encoding="utf-8")) if cat_path.exists() else []

    price_benchmarks = {
        "ust10y_tr_start_1919": 100.0,
        "ust10y_tr_latest": round(float(latest_row["ust10y_tr_index"]), 2),
        "ust10y_clean_latest": round(float(latest_row["ust10y_clean_index"]), 2),
        "ust10y_tr_cagr_1927_present_pct": round(float(tr_cagr), 2),
        "sp500_price_cagr_1927_present_pct": round(float(sp_cagr_full), 2),
        "ust10y_tr_max_drawdown_pct": round(ust_max_dd, 2),
        "ief_validation_corr": round(ief_corr, 4) if ief_corr is not None else None,
        "tlt_max_drawdown_pct": round(tlt_dd, 2) if tlt_dd is not None else None,
        "latest_ief_close": round(float(monthly_cmp["ief_close"].dropna().iloc[-1]), 2) if monthly_cmp["ief_close"].notna().any() else None,
        "latest_tlt_close": round(float(monthly_cmp["tlt_close"].dropna().iloc[-1]), 2) if monthly_cmp["tlt_close"].notna().any() else None,
        "latest_shy_close": round(float(monthly_cmp["shy_close"].dropna().iloc[-1]), 2) if monthly_cmp["shy_close"].notna().any() else None,
        "latest_zn_futures_close": round(float(monthly_cmp["zn_futures_close"].dropna().iloc[-1]), 2) if monthly_cmp["zn_futures_close"].notna().any() else None,
        "latest_zb_futures_close": round(float(monthly_cmp["zb_futures_close"].dropna().iloc[-1]), 2) if monthly_cmp["zb_futures_close"].notna().any() else None,
        "latest_vustx_adj_close": round(float(monthly_cmp["vustx_adj_close"].dropna().iloc[-1]), 2) if monthly_cmp["vustx_adj_close"].notna().any() else None,
    }

    return {
        "generated_at": pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "coverage": {
            "treasury_start": valid_yield["date"].iloc[0].strftime("%Y-%m-%d"),
            "treasury_end": valid_yield["date"].iloc[-1].strftime("%Y-%m-%d"),
            "treasury_months": int(len(valid_yield)),
            "sp500_overlap_start": overlap["date"].iloc[0].strftime("%Y-%m-%d"),
            "sp500_overlap_end": overlap["date"].iloc[-1].strftime("%Y-%m-%d"),
            "sp500_overlap_months": int(len(overlap)),
            "daily_start": daily_cmp["date"].iloc[0].strftime("%Y-%m-%d"),
            "daily_end": daily_cmp["date"].iloc[-1].strftime("%Y-%m-%d"),
            "daily_observations": int(len(daily_cmp)),
            "tbill_3m_start": monthly_cmp.dropna(subset=["tbill_3m_yield"])["date"].iloc[0].strftime("%Y-%m-%d"),
            "cpi_real_yield_start": monthly_cmp.dropna(subset=["real_10y_yield"])["date"].iloc[0].strftime("%Y-%m-%d"),
        },
        "benchmarks": {
            "monthly_peak_yield_pct": round(float(peak_yield_row["treasury_10y_yield"]), 2),
            "monthly_peak_yield_date": peak_yield_row["date"].strftime("%Y-%m"),
            "monthly_trough_yield_pct": round(float(trough_yield_row["treasury_10y_yield"]), 2),
            "monthly_trough_yield_date": trough_yield_row["date"].strftime("%Y-%m"),
            "daily_peak_yield_pct": round(float(daily_peak["treasury_10y_yield"]), 2),
            "daily_peak_yield_date": daily_peak["date"].strftime("%Y-%m-%d"),
            "daily_trough_yield_pct": round(float(daily_trough["treasury_10y_yield"]), 2),
            "daily_trough_yield_date": daily_trough["date"].strftime("%Y-%m-%d"),
            "latest_month": latest_row["date"].strftime("%Y-%m"),
            "latest_10y_yield_pct": round(float(latest_row["treasury_10y_yield"]), 2),
            "latest_sp500_close": round(float(latest_row["sp500_close"]), 2),
            "latest_spread_10y_3m_pct": round(float(latest_spread_row["spread_10y_3m"]), 2) if latest_spread_row is not None else None,
            "latest_spread_date": latest_spread_row["date"].strftime("%Y-%m") if latest_spread_row is not None else None,
            "latest_real_10y_yield_pct": round(float(latest_real_row["real_10y_yield"]), 2) if latest_real_row is not None else None,
            "latest_real_10y_date": latest_real_row["date"].strftime("%Y-%m") if latest_real_row is not None else None,
            "latest_daily_date": daily_cmp["date"].iloc[-1].strftime("%Y-%m-%d"),
            "latest_daily_10y_yield_pct": round(float(daily_cmp["treasury_10y_yield"].iloc[-1]), 3),
            "latest_daily_sp500_close": round(float(daily_cmp["sp500_close"].iloc[-1]), 2),
            "latest_60d_corr_sp_vs_10y_bps": (
                round(float(daily_cmp["rolling_60d_corr_sp_vs_10y_chg"].iloc[-1]), 3)
                if pd.notna(daily_cmp["rolling_60d_corr_sp_vs_10y_chg"].iloc[-1])
                else None
            ),
            "inversion_months_10y_3m": inv_months,
            "inversion_share_pct": round((inv_months / len(inv_df)) * 100.0, 2) if len(inv_df) else 0.0,
            "splice_check_1925_01": round(float(lt_at_1925), 2),
            "splice_check_1953_04": round(float(gs10_at_1953_04), 2),
        },
        "price_benchmarks": price_benchmarks,
        "price_catalog": price_catalog,
        "secular_regimes": regimes,
        "methodology": (
            "Continuous US Long-Term / 10-Year Treasury Yield benchmark constructed from official Federal Reserve & NBER records "
            "published via FRED: M1333AUSM156NNBR (1919-01..1924-12), LTGOVTBD (1925-01..1953-03), GS10 (1953-04..Latest Monthly), "
            "and DGS10 / ^TNX month-to-date average for any incomplete current month; paired with month-end S&P 500 (^GSPC, 1927-12..Present) "
            "and daily DGS10 vs ^GSPC (1962-01-02..Present)."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch primary US Treasury Yield history & compare with S&P 500")
    parser.add_argument("--no-fetch", action="store_true", help="Reuse existing CSVs in data/raw/macro/")
    parser.add_argument("--sync-yf", action="store_true", help="Check yfinance for newer ^GSPC / ^TNX trading days")
    args = parser.parse_args()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    PORTFOLIO_DATA_DIR.mkdir(parents=True, exist_ok=True)

    fred_frames: dict[str, pd.DataFrame] = {}
    for sid in FRED_SERIES:
        df = download_fred_csv(sid, force=not args.no_fetch)
        fred_frames[sid] = df
        valid = df.dropna(subset=[sid.lower()])
        print(
            f"[FRED] {sid:18s} | rows={len(valid):5d} | {valid['date'].min():%Y-%m-%d} -> {valid['date'].max():%Y-%m-%d} | latest={valid[sid.lower()].iloc[-1]:.3f}"
        )

    gspc_daily = load_equity_symbol("^GSPC", sync_yf=args.sync_yf)
    tnx_daily = load_equity_symbol("^TNX", sync_yf=args.sync_yf)
    print(f"[EQ  ] ^GSPC              | rows={len(gspc_daily):5d} | {gspc_daily['date'].min():%Y-%m-%d} -> {gspc_daily['date'].max():%Y-%m-%d} | latest={gspc_daily['close'].iloc[-1]:.2f}")
    print(f"[EQ  ] ^TNX               | rows={len(tnx_daily):5d} | {tnx_daily['date'].min():%Y-%m-%d} -> {tnx_daily['date'].max():%Y-%m-%d} | latest={tnx_daily['close'].iloc[-1]:.3f}")

    treasury_monthly = build_monthly_treasury_history(fred_frames, tnx_daily)
    monthly_cmp = build_monthly_sp500_comparison(treasury_monthly, gspc_daily, fred_frames, tnx_daily)
    daily_cmp = build_daily_sp500_comparison(fred_frames, gspc_daily, tnx_daily)
    summary = compute_summary(monthly_cmp, daily_cmp)

    out_treasury = PROCESSED_DIR / "us_treasury_yield_history_monthly.csv"
    out_monthly_cmp = PROCESSED_DIR / "us_treasury_sp500_comparison_monthly.csv"
    out_daily_cmp = PROCESSED_DIR / "us_treasury_sp500_daily_1962_present.csv"
    out_summary = PROCESSED_DIR / "us_treasury_sp500_summary.json"

    treasury_monthly.to_csv(out_treasury, index=False, date_format="%Y-%m-%d")
    monthly_cmp.to_csv(out_monthly_cmp, index=False, date_format="%Y-%m-%d")
    daily_cmp.to_csv(out_daily_cmp, index=False, date_format="%Y-%m-%d")
    out_summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Mirror download CSVs to portfolio/data/
    monthly_cmp.to_csv(PORTFOLIO_DATA_DIR / "us_treasury_sp500_comparison_monthly.csv", index=False, date_format="%Y-%m-%d")
    treasury_monthly.to_csv(PORTFOLIO_DATA_DIR / "us_treasury_yield_history_monthly.csv", index=False, date_format="%Y-%m-%d")

    print("\n=== SUMMARY ===")
    print(json.dumps(summary["coverage"], indent=2))
    print(json.dumps(summary["benchmarks"], indent=2))


if __name__ == "__main__":
    main()

