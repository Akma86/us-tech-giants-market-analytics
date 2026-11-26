"""Gymnasium-compatible portfolio allocation environment with drift and transaction cost accounting."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.rl.config import RLConfig
from src.rl.features import MacroPortfolioDataset


def project_capped_simplex(
    raw_scores: np.ndarray,
    max_weights: np.ndarray,
    temperature: float = 1.0,
    is_probabilities: bool = False,
) -> np.ndarray:
    """Projects raw logits or non-negative weights onto the long-only capped simplex."""
    scores = np.asarray(raw_scores, dtype=np.float64).ravel()
    caps = np.asarray(max_weights, dtype=np.float64).ravel()

    if is_probabilities:
        w = np.maximum(scores, 0.0)
        total = float(w.sum())
        w = w / total if total > 1e-12 else np.ones_like(w) / len(w)
    else:
        scaled = (scores - np.max(scores)) / max(temperature, 1e-4)
        exp_s = np.exp(np.clip(scaled, -30.0, 30.0))
        w = exp_s / np.sum(exp_s)

    # Iteratively cap constrained assets and redistribute excess to uncapped assets
    free_mask = np.ones(len(w), dtype=bool)
    for _ in range(len(w) + 2):
        over = (w > caps + 1e-9) & free_mask
        if not np.any(over):
            break
        w[over] = caps[over]
        free_mask[over] = False
        rem_mass = 1.0 - float(np.sum(w[~free_mask]))
        free_sum = float(np.sum(w[free_mask]))
        if rem_mass <= 0.0 or not np.any(free_mask):
            break
        if free_sum > 1e-12:
            w[free_mask] = w[free_mask] * (rem_mass / free_sum)
        else:
            w[free_mask] = rem_mass / float(np.sum(free_mask))

    w = np.clip(w, 0.0, caps)
    s = float(np.sum(w))
    return w / s if s > 1e-12 else np.ones_like(w) / len(w)


class MacroPortfolioEnv:
    """Multi-asset portfolio environment with Gymnasium-standard reset/step signatures."""

    def __init__(self, dataset: MacroPortfolioDataset, config: Optional[RLConfig] = None):
        self.dataset = dataset
        self.config = config or RLConfig()
        self.num_assets = self.config.num_assets
        self.max_weights = np.asarray(self.config.max_weights_vector, dtype=np.float64)
        self.cost_rate = float(self.config.cost_bps) * 1e-4

        self.cash_idx = list(self.config.assets).index(self.config.cash_proxy_ticker)
        self.eq_bench_idx = list(self.config.assets).index(self.config.benchmark_equity_ticker)
        self.bond_bench_idx = list(self.config.assets).index(self.config.benchmark_bond_ticker)

        # Observation concatenates market/macro features + current drifted weights + current drawdown
        self.obs_dim = int(self.dataset.features.shape[1]) + self.num_assets + 1
        self.action_dim = self.num_assets

        self.step_idx: int = 0
        self.current_weights: np.ndarray = np.zeros(self.num_assets, dtype=np.float64)
        self.nav: float = 1.0
        self.peak_nav: float = 1.0
        self.bench_nav: float = 1.0
        self.ledger: List[Dict[str, Any]] = []

    def _get_obs(self) -> np.ndarray:
        idx = min(self.step_idx, len(self.dataset.features) - 1)
        feat = self.dataset.features[idx]
        dd = (self.nav / max(self.peak_nav, 1e-12)) - 1.0
        obs = np.concatenate(
            [feat, self.current_weights.astype(np.float32), np.array([dd], dtype=np.float32)],
            axis=0,
        )
        return obs.astype(np.float32)

    def reset(self, seed: Optional[int] = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        if seed is not None:
            np.random.seed(seed)
        self.step_idx = 0
        # Start from a balanced prior (equal across defensive + capped equities)
        init_raw = np.ones(self.num_assets, dtype=np.float64) / self.num_assets
        self.current_weights = project_capped_simplex(
            init_raw, self.max_weights, is_probabilities=True
        )
        self.nav = 1.0
        self.peak_nav = 1.0
        self.bench_nav = 1.0
        self.ledger = []
        return self._get_obs(), {"date": str(self.dataset.dates[0].date()), "nav": self.nav}

    def step(
        self,
        action: np.ndarray,
        is_direct_weights: bool = False,
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        target_w = project_capped_simplex(
            action,
            self.max_weights,
            is_probabilities=is_direct_weights,
        )

        # One-way turnover and transaction cost
        l1_trade = float(np.sum(np.abs(target_w - self.current_weights)))
        one_way_turnover = 0.5 * l1_trade
        tx_cost = self.cost_rate * l1_trade

        asset_rets = self.dataset.step_returns[self.step_idx]
        gross_ret = float(np.dot(target_w, asset_rets))
        net_ret = (1.0 + gross_ret) * (1.0 - tx_cost) - 1.0

        # 60/40 reference return over the same step
        bench_ret = 0.60 * float(asset_rets[self.eq_bench_idx]) + 0.40 * float(asset_rets[self.bond_bench_idx])
        rf_ret = float(asset_rets[self.cash_idx])

        self.nav *= 1.0 + net_ret
        self.peak_nav = max(self.peak_nav, self.nav)
        self.bench_nav *= 1.0 + bench_ret
        current_dd = 1.0 - (self.nav / max(self.peak_nav, 1e-12))

        # Drifted weights at end of holding period
        grown = target_w * (1.0 + asset_rets)
        grown_sum = float(np.sum(grown))
        self.current_weights = grown / grown_sum if grown_sum > 1e-12 else target_w.copy()

        # Risk-aware reward combining net log growth, relative alpha vs 60/40, downside semi-variance, and drawdown control
        log_ret = float(np.log(max(1.0 + net_ret, 1e-6)))
        rel_alpha = net_ret - bench_ret
        downside = min(0.0, net_ret - rf_ret)
        dd_excess = max(0.0, current_dd - self.config.drawdown_threshold)

        reward = (
            log_ret
            + self.config.relative_bench_weight * rel_alpha
            - self.config.downside_penalty * (downside ** 2)
            - self.config.drawdown_penalty * dd_excess
            - self.config.turnover_penalty * one_way_turnover
        )

        date_str = str(self.dataset.dates[self.step_idx].date())
        info = {
            "date": date_str,
            "gross_return": gross_ret,
            "net_return": net_ret,
            "bench_60_40_return": bench_ret,
            "rf_return": rf_ret,
            "one_way_turnover": one_way_turnover,
            "tx_cost": tx_cost,
            "nav": self.nav,
            "drawdown": -current_dd,
            "weights": {sym: float(target_w[i]) for i, sym in enumerate(self.config.assets)},
        }
        self.ledger.append(info)

        self.step_idx += 1
        terminated = self.step_idx >= len(self.dataset.dates)
        truncated = False
        next_obs = self._get_obs()
        return next_obs, float(reward * 100.0), terminated, truncated, info
