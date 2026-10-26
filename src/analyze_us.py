"""
Module: analyze_us.py
Description: Quantitative analytics engine for StockLens US.
             Implements Market Model OLS regressions, Event Study (AR/CAR) analysis,
             and Macro/Commodity Lead-Lag transmission cross-correlations.
Author: Akmal Yaasir Fauzaan
Project: StockLens US - Financial Knowledge Graph & Market Intelligence
"""

from pathlib import Path
from typing import Optional, Union
import numpy as np
import pandas as pd
import duckdb
from scipy import stats

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_US_DIR = PROJECT_ROOT / "data" / "us"
PARQUET_PATH = DATA_US_DIR / "prices.parquet"
DUCKDB_PATH = DATA_US_DIR / "stocklens.duckdb"


class FinancialAnalyticsEngine:
    """Quantitative engine powered by DuckDB, NumPy, and SciPy."""

    def __init__(self, duckdb_path: Optional[Path] = None, parquet_path: Optional[Path] = None):
        self.duckdb_path = duckdb_path or DUCKDB_PATH
        self.parquet_path = parquet_path or PARQUET_PATH
        self._con = None

    def get_connection(self):
        """Returns or creates a DuckDB connection in read-only mode."""
        if self._con is None:
            self._con = duckdb.connect(str(self.duckdb_path), read_only=True)
        return self._con

    def close(self):
        """Closes DuckDB connection if open."""
        if self._con is not None:
            self._con.close()
            self._con = None

    def get_price_history(
        self,
        tickers: list[str],
        start_date: str = "2020-01-01",
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Fast retrieval of historical daily prices and calculates daily percentage returns.
        """
        end_date_filter = f"AND date <= '{end_date}'" if end_date else ""
        placeholders = ", ".join([f"'{t}'" for t in tickers])

        con = self.get_connection()
        query = f"""
        SELECT ticker, date, close, adj_close, volume, series_type, unit
        FROM market_prices
        WHERE ticker IN ({placeholders}) AND date >= '{start_date}' {end_date_filter}
        ORDER BY ticker, date ASC;
        """
        df = con.cursor().execute(query).df()
        if df.empty:
            return pd.DataFrame()

        df["date"] = pd.to_datetime(df["date"])
        # Compute daily return per ticker
        df["daily_return"] = df.groupby("ticker")["adj_close"].pct_change()
        return df

    def get_returns_matrix(
        self,
        tickers: list[str],
        start_date: str = "2020-01-01",
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """Returns a pivot table of daily returns (index=Date, columns=Ticker)."""
        df = self.get_price_history(tickers, start_date=start_date, end_date=end_date)
        if df.empty:
            return pd.DataFrame()
        pivot = df.pivot(index="date", columns="ticker", values="daily_return")
        return pivot

    def run_market_model(
        self,
        ticker: str,
        benchmark: str = "^GSPC",
        start_date: str = "2020-01-01",
        end_date: Optional[str] = None
    ) -> dict:
        """
        Fits Market Model OLS regression:
            R_{i,t} = alpha_i + beta_i * R_{m,t} + epsilon_{i,t}
        Returns:
            alpha (annualized & daily), beta, r_squared, idiosyncratic_vol,
            total_vol, sharpe_ratio, sample_size.
        """
        returns_df = self.get_returns_matrix([ticker, benchmark], start_date=start_date, end_date=end_date).dropna()
        if len(returns_df) < 30:
            raise ValueError(f"Insufficient overlapping return observations ({len(returns_df)}) for {ticker} vs {benchmark}")

        y = returns_df[ticker].values
        x = returns_df[benchmark].values

        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        residuals = y - (intercept + slope * x)

        # Annualized metrics (assuming 252 trading days)
        ann_factor = np.sqrt(252)
        daily_total_vol = np.std(y, ddof=1)
        annualized_total_vol = daily_total_vol * ann_factor
        daily_residual_vol = np.std(residuals, ddof=1)
        annualized_residual_vol = daily_residual_vol * ann_factor
        annualized_alpha = intercept * 252
        annualized_return = np.mean(y) * 252
        sharpe_ratio = annualized_return / annualized_total_vol if annualized_total_vol > 0 else 0.0

        return {
            "ticker": ticker,
            "benchmark": benchmark,
            "sample_size": int(len(returns_df)),
            "start_date": str(returns_df.index.min().date()),
            "end_date": str(returns_df.index.max().date()),
            "alpha_daily": float(intercept),
            "alpha_annualized": float(annualized_alpha),
            "alpha_pvalue": float(p_value),
            "beta": float(slope),
            "beta_std_err": float(std_err),
            "r_squared": float(r_value ** 2),
            "correlation": float(r_value),
            "total_volatility_annualized": float(annualized_total_vol),
            "idiosyncratic_volatility_annualized": float(annualized_residual_vol),
            "sharpe_ratio": float(sharpe_ratio)
        }

    def run_event_study(
        self,
        ticker: str,
        event_date: str,
        benchmark: str = "^GSPC",
        pre_event_window: int = 5,
        post_event_window: int = 10,
        estimation_length: int = 120,
        estimation_gap: int = 15
    ) -> dict:
        """
        Institutional Event Study methodology:
        - Estimation window: [T0 - (estimation_length + estimation_gap), T0 - estimation_gap]
        - Event window: [T0 - pre_event_window, T0 + post_event_window]
        Computes Abnormal Return (AR) and Cumulative Abnormal Return (CAR) with t-statistics.
        """
        t0 = pd.to_datetime(event_date)
        # Fetch wide window of prices
        fetch_start = (t0 - pd.Timedelta(days=estimation_length * 2 + 60)).strftime("%Y-%m-%d")
        fetch_end = (t0 + pd.Timedelta(days=post_event_window * 3 + 30)).strftime("%Y-%m-%d")

        returns_df = self.get_returns_matrix([ticker, benchmark], start_date=fetch_start, end_date=fetch_end).dropna()
        if returns_df.empty or t0 not in returns_df.index:
            # Find nearest trading day if event_date was a weekend/holiday
            sub = returns_df[returns_df.index >= t0]
            if sub.empty:
                raise ValueError(f"No trading data found on or after event date {event_date}")
            t0 = sub.index[0]

        t0_idx = returns_df.index.get_loc(t0)

        # Bounds
        est_end_idx = t0_idx - estimation_gap
        est_start_idx = est_end_idx - estimation_length
        ev_start_idx = t0_idx - pre_event_window
        ev_end_idx = min(t0_idx + post_event_window, len(returns_df) - 1)

        if est_start_idx < 0:
            raise ValueError(f"Insufficient history prior to event {event_date} for {ticker}")

        # Estimation Window OLS
        est_df = returns_df.iloc[est_start_idx:est_end_idx]
        y_est = est_df[ticker].values
        x_est = est_df[benchmark].values

        slope, intercept, r_value, _, _ = stats.linregress(x_est, y_est)
        resids = y_est - (intercept + slope * x_est)
        sigma_eps = np.std(resids, ddof=2)

        # Event Window Abnormal Returns
        ev_df = returns_df.iloc[ev_start_idx:ev_end_idx + 1].copy()
        ev_df["expected_return"] = intercept + slope * ev_df[benchmark]
        ev_df["abnormal_return"] = ev_df[ticker] - ev_df["expected_return"]
        ev_df["car"] = ev_df["abnormal_return"].cumsum()
        ev_df["rel_day"] = [i - pre_event_window for i in range(len(ev_df))]

        # Event stats
        car_final = float(ev_df["car"].iloc[-1])
        n_event = len(ev_df)
        car_std_err = sigma_eps * np.sqrt(n_event)
        t_stat = car_final / car_std_err if car_std_err > 0 else 0.0
        p_val = 2 * (1 - stats.t.cdf(abs(t_stat), df=len(est_df) - 2))

        records = []
        for _, row in ev_df.reset_index().iterrows():
            records.append({
                "date": str(row["date"].date()),
                "rel_day": int(row["rel_day"]),
                "stock_return": float(row[ticker]),
                "market_return": float(row[benchmark]),
                "abnormal_return": float(row["abnormal_return"]),
                "car": float(row["car"])
            })

        return {
            "ticker": ticker,
            "benchmark": benchmark,
            "event_date": str(t0.date()),
            "estimation_window": [str(est_df.index.min().date()), str(est_df.index.max().date())],
            "event_window": [str(ev_df.index.min().date()), str(ev_df.index.max().date())],
            "alpha": float(intercept),
            "beta": float(slope),
            "car": car_final,
            "t_statistic": float(t_stat),
            "p_value": float(p_val),
            "statistically_significant": bool(p_val < 0.05),
            "event_series": records
        }

    def run_lead_lag_correlation(
        self,
        equity_ticker: str,
        macro_ticker: str,
        lags: list[int] = [-20, -10, -5, -2, -1, 0, 1, 2, 5, 10, 20],
        start_date: str = "2020-01-01",
        end_date: Optional[str] = None
    ) -> dict:
        """
        Computes cross-correlation across different lags between an economic factor/commodity
        and equity daily returns:
            lag > 0 means the macro/commodity LEADS equity returns by k trading days.
            lag < 0 means the equity LEADS the macro factor.
        """
        returns_df = self.get_returns_matrix([equity_ticker, macro_ticker], start_date=start_date, end_date=end_date).dropna()
        if len(returns_df) < 50:
            raise ValueError(f"Insufficient overlapping records for {equity_ticker} and {macro_ticker}")

        eq_series = returns_df[equity_ticker]
        macro_series = returns_df[macro_ticker]

        lag_results = []
        best_lag = 0
        max_abs_corr = -1.0

        for k in sorted(lags):
            if k == 0:
                corr, pval = stats.pearsonr(eq_series, macro_series)
            elif k > 0:
                # Macro leads equity: equity at t vs macro at t - k
                shifted_macro = macro_series.shift(k)
                valid = pd.concat([eq_series, shifted_macro], axis=1).dropna()
                corr, pval = stats.pearsonr(valid.iloc[:, 0], valid.iloc[:, 1])
            else:
                # Equity leads macro: macro at t vs equity at t - abs(k)
                shifted_eq = eq_series.shift(abs(k))
                valid = pd.concat([shifted_eq, macro_series], axis=1).dropna()
                corr, pval = stats.pearsonr(valid.iloc[:, 0], valid.iloc[:, 1])

            lag_results.append({
                "lag_days": k,
                "correlation": float(corr),
                "p_value": float(pval),
                "interpretation": (
                    f"{macro_ticker} leads {equity_ticker} by {k}d" if k > 0
                    else f"Coincident (0d lag)" if k == 0
                    else f"{equity_ticker} leads {macro_ticker} by {abs(k)}d"
                )
            })

            if abs(corr) > max_abs_corr:
                max_abs_corr = abs(corr)
                best_lag = k

        return {
            "equity_ticker": equity_ticker,
            "macro_ticker": macro_ticker,
            "sample_size": len(returns_df),
            "optimal_lag_days": best_lag,
            "max_abs_correlation": float(max_abs_corr),
            "lag_matrix": lag_results
        }


if __name__ == "__main__":
    engine = FinancialAnalyticsEngine()
    print("=" * 75)
    print("FINANCIAL ANALYTICS ENGINE — TESTING MODULE")
    print("=" * 75)

    # 1. Market Model
    print("\n[+] 1. Market Model: NVDA vs ^GSPC")
    mm = engine.run_market_model("NVDA", "^GSPC", start_date="2022-01-01")
    print(f"    Beta: {mm['beta']:.2f} | Alpha (Ann): {mm['alpha_annualized']:.2%} | R^2: {mm['r_squared']:.2%}")
    print(f"    Total Vol: {mm['total_volatility_annualized']:.1%} | Idio Vol: {mm['idiosyncratic_volatility_annualized']:.1%}")

    # 2. Event Study
    print("\n[+] 2. Event Study: NVDA around Blackwell GTC Keynote (2024-03-18)")
    ev = engine.run_event_study("NVDA", "2024-03-18", pre_event_window=3, post_event_window=5)
    print(f"    Cumulative Abnormal Return (CAR): {ev['car']:.2%}")
    print(f"    t-stat: {ev['t_statistic']:.2f} | p-value: {ev['p_value']:.4f} | Sig: {ev['statistically_significant']}")

    # 3. Lead-Lag: DAL vs WTI Crude (CL=F)
    print("\n[+] 3. Lead-Lag Cross-Correlation: DAL (Delta Air Lines) vs CL=F (Crude Oil)")
    ll = engine.run_lead_lag_correlation("DAL", "CL=F")
    print(f"    Optimal Lag: {ll['optimal_lag_days']} days | Max Abs Corr: {ll['max_abs_correlation']:.3f}")
    for r in ll["lag_matrix"]:
        if r["lag_days"] in [-5, 0, 1, 5]:
            print(f"      Lag {r['lag_days']:>2}d: Corr = {r['correlation']:+.3f} (p={r['p_value']:.3f}) -> {r['interpretation']}")
    print("=" * 75)
