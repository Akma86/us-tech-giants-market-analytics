"""Reference benchmark strategies evaluated under identical drift and transaction cost rules."""

from __future__ import annotations

from typing import Any, Callable, Dict, List

import numpy as np

from src.rl.config import RLConfig
from src.rl.env import MacroPortfolioEnv
from src.rl.features import MacroPortfolioDataset


def run_weight_policy(
    dataset: MacroPortfolioDataset,
    config: RLConfig,
    weight_fn: Callable[[int, MacroPortfolioDataset, np.ndarray], np.ndarray],
) -> List[Dict[str, Any]]:
    """Executes a deterministic weight policy inside MacroPortfolioEnv and returns the ledger."""
    env = MacroPortfolioEnv(dataset=dataset, config=config)
    env.reset(seed=0)
    terminated = False
    while not terminated:
        idx = env.step_idx
        w = weight_fn(idx, dataset, env.current_weights)
        _, _, terminated, _, _ = env.step(w, is_direct_weights=True)
    return env.ledger


def equal_weight_policy(idx: int, dataset: MacroPortfolioDataset, prev_w: np.ndarray) -> np.ndarray:
    n = len(dataset.assets)
    return np.ones(n, dtype=np.float64) / n


def sixty_forty_policy(idx: int, dataset: MacroPortfolioDataset, prev_w: np.ndarray) -> np.ndarray:
    w = np.zeros(len(dataset.assets), dtype=np.float64)
    assets = list(dataset.assets)
    w[assets.index("^GSPC")] = 0.60
    w[assets.index("IEF")] = 0.40
    return w


def sp500_buy_hold_policy(idx: int, dataset: MacroPortfolioDataset, prev_w: np.ndarray) -> np.ndarray:
    w = np.zeros(len(dataset.assets), dtype=np.float64)
    assets = list(dataset.assets)
    w[assets.index("^GSPC")] = 1.0
    return w


def inverse_vol_risk_parity_policy(
    idx: int, dataset: MacroPortfolioDataset, prev_w: np.ndarray
) -> np.ndarray:
    """Allocates inversely proportional to trailing 21-day realized volatility."""
    assets = list(dataset.assets)
    feat_names = dataset.feature_names
    inv_vols = np.ones(len(assets), dtype=np.float64)
    for i, sym in enumerate(assets):
        col = f"{sym}_vol_21d"
        if col in feat_names:
            z_vol = float(dataset.features[idx, feat_names.index(col)])
            # Map standardized volatility z-score to positive scale factor
            inv_vols[i] = np.exp(-0.55 * np.clip(z_vol, -2.5, 2.5))
    return inv_vols / np.sum(inv_vols)


def evaluate_all_baselines(
    dataset: MacroPortfolioDataset, config: RLConfig
) -> Dict[str, List[Dict[str, Any]]]:
    """Runs all four standard non-ML baselines on the supplied dataset slice."""
    return {
        "60/40 Benchmark (^GSPC/IEF)": run_weight_policy(dataset, config, sixty_forty_policy),
        "Equal-Weight (1/N)": run_weight_policy(dataset, config, equal_weight_policy),
        "Inverse-Vol Risk Parity": run_weight_policy(dataset, config, inverse_vol_risk_parity_policy),
        "S&P 500 Buy & Hold (^GSPC)": run_weight_policy(dataset, config, sp500_buy_hold_policy),
    }
