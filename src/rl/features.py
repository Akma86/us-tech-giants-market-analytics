"""Point-in-time feature builder with strict publication lags for macroeconomic series."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.rl.config import PROJECT_ROOT, RLConfig


@dataclass
class MacroPortfolioDataset:
    """Aligned rebalance-step dataset with causal features, forward asset returns, and dates."""

    dates: pd.DatetimeIndex
    daily_dates: pd.DatetimeIndex
    daily_returns: pd.DataFrame
    step_returns: np.ndarray
    features: np.ndarray
    raw_macro_table: pd.DataFrame
    feature_names: List[str]
    assets: Tuple[str, ...]
    raw_asset_signals: Optional[np.ndarray] = None

    def slice_window(self, start_date: str, end_date: str) -> "MacroPortfolioDataset":
        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date)
        mask = (self.dates >= start_ts) & (self.dates <= end_ts)
        indices = np.where(mask)[0]
        if len(indices) == 0:
            raise ValueError(f"No rebalance dates found between {start_date} and {end_date}")

        daily_mask = (self.daily_dates >= start_ts) & (self.daily_dates <= end_ts)
        return MacroPortfolioDataset(
            dates=self.dates[indices],
            daily_dates=self.daily_dates[daily_mask],
            daily_returns=self.daily_returns.loc[daily_mask].copy(),
            step_returns=self.step_returns[indices].copy(),
            features=self.features[indices].copy(),
            raw_macro_table=self.raw_macro_table.iloc[indices].copy(),
            feature_names=list(self.feature_names),
            assets=self.assets,
            raw_asset_signals=self.raw_asset_signals[indices].copy()
            if self.raw_asset_signals is not None
            else None,
        )


class MacroPortfolioFeatureBuilder:
    """Builds point-in-time multi-asset and macroeconomic state representations."""

    def __init__(self, config: Optional[RLConfig] = None):
        self.config = config or RLConfig()

    def load_daily_asset_prices(self) -> pd.DataFrame:
        """Loads adjusted close prices for all universe assets plus ^VIX and ^TNX."""
        needed = list(self.config.assets) + ["^VIX", "^TNX"]
        needed_unique = sorted(set(needed))

        frames: List[pd.DataFrame] = []
        if self.config.db_path.exists():
            placeholders = ",".join(["?"] * len(needed_unique))
            query = f"""
                SELECT symbol, date, COALESCE(adj_close, close) AS px
                FROM daily_prices
                WHERE symbol IN ({placeholders})
                  AND date >= '2002-01-01'
                ORDER BY date ASC
            """
            with sqlite3.connect(str(self.config.db_path)) as conn:
                df_db = pd.read_sql_query(query, conn, params=needed_unique)
            if not df_db.empty:
                frames.append(df_db)

        raw_dir = PROJECT_ROOT / "data" / "raw"
        fallback_files = {
            "^VIX": raw_dir / "VIX.csv",
            "^TNX": raw_dir / "TNX.csv",
            "^GSPC": raw_dir / "GSPC.csv",
            "IEF": raw_dir / "IEF.csv",
            "TLT": raw_dir / "TLT.csv",
            "SHY": raw_dir / "SHY.csv",
            "AAPL": raw_dir / "AAPL.csv",
            "MSFT": raw_dir / "MSFT.csv",
            "NVDA": raw_dir / "NVDA.csv",
            "GOOGL": raw_dir / "GOOGL.csv",
            "AMZN": raw_dir / "AMZN.csv",
        }

        present_symbols = set(frames[0]["symbol"].unique()) if frames else set()
        for sym in needed_unique:
            if sym not in present_symbols and sym in fallback_files and fallback_files[sym].exists():
                raw_df = pd.read_csv(fallback_files[sym])
                val_col = "Adj Close" if "Adj Close" in raw_df.columns else "Close"
                sub = pd.DataFrame(
                    {
                        "symbol": sym,
                        "date": raw_df["Date"].astype(str).str[:10],
                        "px": pd.to_numeric(raw_df[val_col], errors="coerce"),
                    }
                )
                frames.append(sub)

        if not frames:
            raise FileNotFoundError("Could not load daily asset prices from SQLite or data/raw CSVs.")

        combined = pd.concat(frames, ignore_index=True)
        combined["date"] = pd.to_datetime(combined["date"])
        combined = combined.drop_duplicates(subset=["symbol", "date"], keep="last")
        pivot = combined.pivot(index="date", columns="symbol", values="px").sort_index()

        # Filter to calendar days where S&P 500 and core assets trade
        if "^GSPC" in pivot.columns:
            pivot = pivot[pivot["^GSPC"].notna()]
        pivot = pivot.ffill()
        missing_assets = [a for a in self.config.assets if a not in pivot.columns]
        if missing_assets:
            raise ValueError(f"Missing required universe columns in price matrix: {missing_assets}")

        # Keep dates where all configured portfolio assets have valid historical data
        valid_mask = pivot[list(self.config.assets)].notna().all(axis=1)
        pivot = pivot.loc[valid_mask].copy()
        return pivot

    def load_lagged_macro_series(self, daily_index: pd.DatetimeIndex) -> pd.DataFrame:
        """Loads monthly macro series shifted forward by publication lag to prevent look-ahead bias."""
        macro_daily = pd.DataFrame(index=daily_index)

        if self.config.inflation_monthly_csv.exists():
            inf = pd.read_csv(self.config.inflation_monthly_csv)
            dt_col = "date" if "date" in inf.columns else ("Date" if "Date" in inf.columns else inf.columns[0])
            inf["obs_date"] = pd.to_datetime(inf[dt_col])
            rename_map = {
                "CPI_Headline_YoY_Pct": "cpi_headline_yoy_pct",
                "CPI_Core_YoY_Pct": "cpi_core_yoy_pct",
                "PCE_Core_YoY_Pct": "pce_core_yoy_pct",
                "FEDFUNDS": "fed_funds_rate_pct",
                "Real_Fed_Funds_Rate_Pct": "real_policy_rate_pct",
                "T10YIE": "breakeven_10y_inflation_pct",
                "T10Y2Y": "yield_curve_10y_2y_pct",
            }
            inf = inf.rename(columns=rename_map)
            # Official BLS/BEA monthly releases become known ~35 calendar days after month start
            inf["effective_date"] = inf["obs_date"] + pd.Timedelta(days=self.config.macro_publication_lag_days)
            inf = inf.sort_values("effective_date")

            cols = [
                "cpi_headline_yoy_pct",
                "cpi_core_yoy_pct",
                "pce_core_yoy_pct",
                "fed_funds_rate_pct",
                "real_policy_rate_pct",
                "breakeven_10y_inflation_pct",
                "yield_curve_10y_2y_pct",
            ]
            avail_cols = [c for c in cols if c in inf.columns]
            inf_sub = inf[["effective_date"] + avail_cols].copy()
            for c in avail_cols:
                inf_sub[c] = pd.to_numeric(inf_sub[c], errors="coerce")
            inf_sub = inf_sub.ffill()

            left_df = pd.DataFrame({"effective_date": daily_index})
            merged_inf = pd.merge_asof(
                left_df.sort_values("effective_date"),
                inf_sub.sort_values("effective_date"),
                on="effective_date",
                direction="backward",
            )
            merged_inf.index = daily_index
            for c in avail_cols:
                macro_daily[c] = merged_inf[c]

        if self.config.treasury_monthly_csv.exists():
            ty = pd.read_csv(self.config.treasury_monthly_csv)
            ty_dt_col = "date" if "date" in ty.columns else ("Date" if "Date" in ty.columns else ty.columns[0])
            ty["obs_date"] = pd.to_datetime(ty[ty_dt_col])
            ty["effective_date"] = ty["obs_date"] + pd.Timedelta(days=self.config.macro_publication_lag_days)
            ty = ty.sort_values("effective_date")
            ty_cols = ["spread_10y_3m", "real_10y_yield", "tbill_3m_yield"]
            avail_ty = [c for c in ty_cols if c in ty.columns]
            ty_sub = ty[["effective_date"] + avail_ty].copy()
            for c in avail_ty:
                ty_sub[c] = pd.to_numeric(ty_sub[c], errors="coerce")
            ty_sub = ty_sub.ffill()

            left_df = pd.DataFrame({"effective_date": daily_index})
            merged_ty = pd.merge_asof(
                left_df.sort_values("effective_date"),
                ty_sub.sort_values("effective_date"),
                on="effective_date",
                direction="backward",
            )
            merged_ty.index = daily_index
            for c in avail_ty:
                macro_daily[c] = merged_ty[c]

        macro_daily = macro_daily.ffill().bfill()
        return macro_daily

    def build_dataset(self, price_matrix: Optional[pd.DataFrame] = None) -> MacroPortfolioDataset:
        """Constructs the causal feature matrix and step-forward return array."""
        prices = price_matrix.copy() if price_matrix is not None else self.load_daily_asset_prices()
        assets = list(self.config.assets)
        asset_px = prices[assets].copy()
        daily_rets = asset_px.pct_change().fillna(0.0)

        macro_df = self.load_lagged_macro_series(prices.index)
        vix_series = prices["^VIX"] if "^VIX" in prices.columns else pd.Series(18.0, index=prices.index)
        tnx_series = prices["^TNX"] if "^TNX" in prices.columns else pd.Series(4.0, index=prices.index)

        raw_feats: Dict[str, pd.Series] = {}

        # Per-asset causal technical & risk indicators
        for sym in assets:
            px = asset_px[sym]
            ret1 = daily_rets[sym]
            raw_feats[f"{sym}_ret_5d"] = np.log(px / px.shift(5))
            raw_feats[f"{sym}_ret_21d"] = np.log(px / px.shift(21))
            raw_feats[f"{sym}_ret_63d"] = np.log(px / px.shift(63))
            raw_feats[f"{sym}_ret_126d"] = np.log(px / px.shift(126))
            raw_feats[f"{sym}_vol_21d"] = ret1.rolling(21, min_periods=10).std() * np.sqrt(252.0)
            sma126 = px.rolling(126, min_periods=25).mean()
            raw_feats[f"{sym}_sma126_gap"] = (px / sma126) - 1.0
            roll_max = px.rolling(126, min_periods=20).max()
            raw_feats[f"{sym}_dd_126d"] = (px / roll_max) - 1.0

        # Cross-asset & macroeconomic regime features
        raw_feats["macro_vix_level"] = vix_series
        raw_feats["macro_vix_chg_21d"] = vix_series - vix_series.shift(21)
        raw_feats["macro_tnx_level"] = tnx_series
        raw_feats["macro_tnx_chg_21d"] = tnx_series - tnx_series.shift(21)
        raw_feats["macro_tnx_chg_63d"] = tnx_series - tnx_series.shift(63)

        for col in [
            "cpi_headline_yoy_pct",
            "pce_core_yoy_pct",
            "fed_funds_rate_pct",
            "real_policy_rate_pct",
            "yield_curve_10y_2y_pct",
            "spread_10y_3m",
            "real_10y_yield",
        ]:
            if col in macro_df.columns:
                raw_feats[f"macro_{col}"] = macro_df[col]
            else:
                raw_feats[f"macro_{col}"] = pd.Series(0.0, index=prices.index)

        # Rolling 60-day stock-bond return correlation (^GSPC vs IEF)
        sp_ret = daily_rets[self.config.benchmark_equity_ticker]
        bond_ret = daily_rets[self.config.benchmark_bond_ticker]
        raw_feats["macro_sp_bond_corr_60d"] = (
            sp_ret.rolling(60, min_periods=20).corr(bond_ret).fillna(0.0)
        )

        feat_df = pd.DataFrame(raw_feats, index=prices.index).ffill().fillna(0.0)

        # Causal rolling z-score standardization (strictly <= t)
        win = self.config.zscore_window_days
        min_p = self.config.zscore_min_periods
        roll_mean = feat_df.rolling(win, min_periods=min_p).mean()
        roll_std = feat_df.rolling(win, min_periods=min_p).std().replace(0.0, 1.0).fillna(1.0)
        norm_df = ((feat_df - roll_mean) / (roll_std + 1e-8)).fillna(0.0)
        norm_df = norm_df.clip(-self.config.zscore_clip, self.config.zscore_clip)

        # Trim initial warmup before sampling rebalance steps
        warmup = 140
        valid_dates = prices.index[warmup:]
        k = self.config.rebalance_freq_days

        step_indices = list(range(warmup, len(prices.index) - k, k))
        rebalance_dates = prices.index[step_indices]

        step_returns_list: List[np.ndarray] = []
        step_features_list: List[np.ndarray] = []
        raw_signals_list: List[np.ndarray] = []
        macro_rows: List[Dict[str, float]] = []

        for idx in step_indices:
            # Forward K-day holding period cumulative return per asset: (P_{t+K} / P_t) - 1
            p_now = asset_px.iloc[idx].to_numpy(dtype=np.float64)
            p_next = asset_px.iloc[idx + k].to_numpy(dtype=np.float64)
            period_ret = (p_next / np.maximum(p_now, 1e-12)) - 1.0
            step_returns_list.append(period_ret)
            step_features_list.append(norm_df.iloc[idx].to_numpy(dtype=np.float32))

            # True cross-sectional unnormalized asset signals at decision date t: (N, 5)
            sig_mat = np.zeros((len(assets), 5), dtype=np.float64)
            for i_sym, sym in enumerate(assets):
                sig_mat[i_sym, 0] = float(feat_df[f"{sym}_ret_21d"].iloc[idx])
                sig_mat[i_sym, 1] = float(feat_df[f"{sym}_ret_63d"].iloc[idx])
                sig_mat[i_sym, 2] = float(feat_df[f"{sym}_ret_126d"].iloc[idx])
                sig_mat[i_sym, 3] = float(feat_df[f"{sym}_vol_21d"].iloc[idx])
                sig_mat[i_sym, 4] = float(feat_df[f"{sym}_sma126_gap"].iloc[idx])
            raw_signals_list.append(sig_mat)

            # Unnormalized macro snapshot at decision date t for regime attribution & prior
            macro_rows.append(
                {
                    "vix": float(vix_series.iloc[idx]),
                    "tnx_10y": float(tnx_series.iloc[idx]),
                    "tnx_chg_63d": float(feat_df["macro_tnx_chg_63d"].iloc[idx]),
                    "cpi_yoy": float(feat_df["macro_cpi_headline_yoy_pct"].iloc[idx]),
                    "core_pce_yoy": float(feat_df["macro_pce_core_yoy_pct"].iloc[idx]),
                    "spread_10y_3m": float(feat_df["macro_spread_10y_3m"].iloc[idx]),
                    "spread_10y_2y": float(feat_df["macro_yield_curve_10y_2y_pct"].iloc[idx]),
                    "sp_bond_corr_60d": float(feat_df["macro_sp_bond_corr_60d"].iloc[idx]),
                    "sp_sma126_gap": float(feat_df[f"{self.config.benchmark_equity_ticker}_sma126_gap"].iloc[idx]),
                    "ief_sma126_gap": float(feat_df[f"{self.config.benchmark_bond_ticker}_sma126_gap"].iloc[idx]),
                    "tlt_sma126_gap": float(feat_df["TLT_sma126_gap"].iloc[idx]),
                }
            )

        return MacroPortfolioDataset(
            dates=rebalance_dates,
            daily_dates=valid_dates,
            daily_returns=daily_rets.loc[valid_dates].copy(),
            step_returns=np.vstack(step_returns_list).astype(np.float64),
            features=np.vstack(step_features_list).astype(np.float32),
            raw_macro_table=pd.DataFrame(macro_rows, index=rebalance_dates),
            feature_names=list(norm_df.columns),
            assets=self.config.assets,
            raw_asset_signals=np.stack(raw_signals_list, axis=0),
        )
