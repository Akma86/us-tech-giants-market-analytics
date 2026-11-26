"""Unit and causality tests for the Macro-Aware RL Portfolio Allocation Engine."""

from __future__ import annotations

import unittest
import numpy as np
import pandas as pd

from src.rl.config import RLConfig
from src.rl.env import MacroPortfolioEnv, project_capped_simplex
from src.rl.features import MacroPortfolioFeatureBuilder


class TestRLPortfolioPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = RLConfig()
        cls.builder = MacroPortfolioFeatureBuilder(cls.config)
        cls.prices = cls.builder.load_daily_asset_prices()
        cls.dataset = cls.builder.build_dataset(cls.prices)

    def test_simplex_and_single_stock_cap_constraints(self) -> None:
        max_w = np.asarray(self.config.max_weights_vector, dtype=np.float64)
        rng = np.random.default_rng(123)
        for _ in range(50):
            raw_logits = rng.normal(0.0, 5.0, size=self.config.num_assets)
            w = project_capped_simplex(raw_logits, max_w, is_probabilities=False)
            self.assertAlmostEqual(float(np.sum(w)), 1.0, places=6)
            self.assertTrue(np.all(w >= -1e-9))
            for i, sym in enumerate(self.config.assets):
                if sym in self.config.single_equities:
                    self.assertLessEqual(float(w[i]), self.config.max_single_stock_weight + 1e-6)

    def test_strict_causal_feature_invariance_no_lookahead(self) -> None:
        """Mutating future prices after cutoff date must not alter features at or before cutoff."""
        cutoff_idx = 600
        cutoff_date = self.prices.index[cutoff_idx]

        mutated_prices = self.prices.copy()
        future_mask = mutated_prices.index > cutoff_date
        mutated_prices.loc[future_mask, list(self.config.assets)] *= 3.5

        ds_orig = self.builder.build_dataset(self.prices)
        ds_mut = self.builder.build_dataset(mutated_prices)

        past_steps = ds_orig.dates <= cutoff_date
        self.assertGreater(int(np.sum(past_steps)), 20)
        np.testing.assert_allclose(
            ds_orig.features[past_steps],
            ds_mut.features[past_steps],
            rtol=1e-6,
            atol=1e-6,
        )

    def test_transaction_cost_accounting_identity(self) -> None:
        test_slice = self.dataset.slice_window("2022-01-01", "2023-12-31")
        cfg_zero = RLConfig(cost_bps=0.0)
        cfg_high = RLConfig(cost_bps=50.0)

        env_zero = MacroPortfolioEnv(test_slice, cfg_zero)
        env_high = MacroPortfolioEnv(test_slice, cfg_high)
        env_zero.reset(seed=7)
        env_high.reset(seed=7)

        rng = np.random.default_rng(7)
        for _ in range(10):
            logits = rng.normal(0.0, 1.5, size=self.config.num_assets)
            _, _, _, _, info_zero = env_zero.step(logits)
            _, _, _, _, info_high = env_high.step(logits)

            self.assertEqual(info_zero["tx_cost"], 0.0)
            if info_high["one_way_turnover"] > 1e-6:
                self.assertGreater(info_high["tx_cost"], 0.0)
                self.assertLess(info_high["net_return"], info_zero["net_return"])


if __name__ == "__main__":
    unittest.main()
