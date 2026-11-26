"""Configuration definitions for the Macro-Aware RL Portfolio Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass(frozen=True)
class RLConfig:
    """Hyperparameters, asset universe, and walk-forward boundaries for RL allocation."""

    assets: Tuple[str, ...] = (
        "AAPL",
        "MSFT",
        "NVDA",
        "GOOGL",
        "AMZN",
        "^GSPC",
        "IEF",
        "TLT",
        "SHY",
    )
    single_equities: Tuple[str, ...] = ("AAPL", "MSFT", "NVDA", "GOOGL", "AMZN")
    defensive_assets: Tuple[str, ...] = ("^GSPC", "IEF", "TLT", "SHY")
    cash_proxy_ticker: str = "SHY"
    benchmark_equity_ticker: str = "^GSPC"
    benchmark_bond_ticker: str = "IEF"

    rebalance_freq_days: int = 5
    cost_bps: float = 10.0
    max_single_stock_weight: float = 0.25

    train_start: str = "2005-01-01"
    train_end: str = "2017-12-31"
    val_start: str = "2018-01-01"
    val_end: str = "2021-12-31"
    test_start: str = "2022-01-01"
    test_end: str = "2026-12-31"

    macro_publication_lag_days: int = 35
    zscore_window_days: int = 252
    zscore_min_periods: int = 60
    zscore_clip: float = 4.0

    downside_penalty: float = 14.0
    drawdown_penalty: float = 0.20
    drawdown_threshold: float = 0.08
    turnover_penalty: float = 0.025
    relative_bench_weight: float = 0.35

    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_eps: float = 0.20
    lr: float = 3e-4
    entropy_coef: float = 0.012
    value_coef: float = 0.50
    max_grad_norm: float = 0.50
    ppo_epochs: int = 6
    training_episodes: int = 90
    hidden_dim: int = 128
    seeds: Tuple[int, ...] = (42, 101, 2024)

    db_path: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "database" / "us_equities.db")
    treasury_daily_csv: Path = field(
        default_factory=lambda: PROJECT_ROOT / "data" / "processed" / "us_treasury_prices_daily.csv"
    )
    inflation_monthly_csv: Path = field(
        default_factory=lambda: PROJECT_ROOT / "data" / "processed" / "us_inflation_macro_monthly.csv"
    )
    treasury_monthly_csv: Path = field(
        default_factory=lambda: PROJECT_ROOT / "data" / "processed" / "us_treasury_sp500_comparison_monthly.csv"
    )
    output_json_path: Path = field(
        default_factory=lambda: PROJECT_ROOT / "data" / "processed" / "rl_portfolio_backtest.json"
    )
    portfolio_json_path: Path = field(
        default_factory=lambda: PROJECT_ROOT / "portfolio" / "data" / "rl_portfolio_backtest.json"
    )
    output_csv_path: Path = field(
        default_factory=lambda: PROJECT_ROOT / "data" / "processed" / "rl_portfolio_oos_daily.csv"
    )
    portfolio_csv_path: Path = field(
        default_factory=lambda: PROJECT_ROOT / "portfolio" / "data" / "rl_portfolio_oos_daily.csv"
    )
    model_dir: Path = field(
        default_factory=lambda: PROJECT_ROOT / "data" / "processed" / "rl_models"
    )

    @property
    def num_assets(self) -> int:
        return len(self.assets)

    @property
    def max_weights_vector(self) -> List[float]:
        return [
            self.max_single_stock_weight if sym in self.single_equities else 1.0
            for sym in self.assets
        ]
