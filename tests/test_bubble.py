"""
Unit and Integration Tests for AI Bubble Early Warning & Contagion Suite
Tests AIValuationEngine, Reverse DCF model, DotComComparisonEngine,
FragilityIndexEngine, and AIContagionEngine.
"""

import unittest
from pathlib import Path

from src.bubble_valuation import AIValuationEngine, AI_UNIVERSE
from src.dotcom_comparison import DotComComparisonEngine
from src.fragility_index import FragilityIndexEngine
from src.bubble_contagion import AIContagionEngine


class TestAIBubbleSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.val_engine = AIValuationEngine()
        cls.dotcom_engine = DotComComparisonEngine()
        cls.fragility_engine = FragilityIndexEngine()
        cls.contagion_engine = AIContagionEngine()

    # --- 1. REVERSE DCF & VALUATION TESTS ---
    def test_ai_universe_coverage(self):
        """Verifies coverage of all 5 key industry groups in AI universe."""
        self.assertGreaterEqual(len(AI_UNIVERSE), 20)
        for sym in ["NVDA", "MSFT", "PLTR", "VRT", "SMCI", "ASML"]:
            self.assertIn(sym, AI_UNIVERSE)
            self.assertIn("subsector", AI_UNIVERSE[sym])
            self.assertIn("ai_exposure", AI_UNIVERSE[sym])

    def test_reverse_dcf_model(self):
        """Validates mathematical correctness of Reverse DCF growth rate solver."""
        # Test case: NVDA price $200, 2.5B shares ($500B equity value), $20B FCF, 9% WACC, 3% terminal growth
        res = self.val_engine.calculate_reverse_dcf(
            current_price=200.0,
            shares_outstanding=2.5e9,
            fcf_annual=20e9,
            wacc=0.09,
            terminal_growth=0.03
        )
        self.assertIn("implied_5y_fcf_cagr_pct", res)
        self.assertIn("assessment", res)
        self.assertIn("verdict", res)
        # With current price of $200 ($500B EV) and $20B FCF (EV/FCF = 25x), growth requirement is ~7-15%
        self.assertGreater(res["implied_5y_fcf_cagr_pct"], 0.0)
        self.assertLess(res["implied_5y_fcf_cagr_pct"], 50.0)

    def test_single_stock_valuation_fetch(self):
        """Validates live/realtime fetching for a core AI stock (NVDA)."""
        data = self.val_engine.fetch_stock_valuation("NVDA")
        self.assertEqual(data["symbol"], "NVDA")
        self.assertGreater(data["current_price"], 0.0)
        self.assertGreater(data["market_cap_billions"], 500.0)
        self.assertIn("reverse_dcf", data)
        self.assertTrue(data["is_realtime"])

    # --- 2. DOT-COM COMPARISON TESTS ---
    def test_dotcom_comparison_matrix(self):
        """Validates empirical comparison dimensions between Dot-Com and AI era."""
        res = self.dotcom_engine.get_comparison_matrix()
        self.assertIn("matrix", res)
        self.assertIn("synthesis", res)
        self.assertGreaterEqual(len(res["matrix"]), 5)
        # Check specific indicator categories
        categories = [m["category"] for m in res["matrix"]]
        self.assertIn("Market Concentration", categories)
        self.assertIn("Valuation Multiples", categories)
        self.assertIn("Cash Flow & Profitability", categories)

    def test_dotcom_drawdown_series(self):
        """Verifies normalized 100-base trajectory data generation."""
        res = self.dotcom_engine.get_drawdown_comparison_series()
        self.assertIn("dotcom_cycle", res)
        self.assertIn("modern_ai_cycle", res)
        self.assertGreater(len(res["dotcom_cycle"]["data"]), 50)
        self.assertGreater(len(res["modern_ai_cycle"]["data"]), 50)

    def test_safe_haven_rotation_matrix(self):
        """Verifies empirical Safe Haven and Capital Rotation matrix."""
        res = self.dotcom_engine.get_safe_haven_rotation_matrix()
        self.assertIn("assets", res)
        self.assertIn("benchmark_comparison", res)
        self.assertGreaterEqual(len(res["assets"]), 10)
        symbols = [a["symbol"] for a in res["assets"]]
        self.assertIn("BRK-B", symbols)
        self.assertIn("XOM", symbols)
        self.assertIn("JNJ", symbols)
        for a in res["assets"]:
            self.assertGreater(a["resilience_score"], 0)
            self.assertGreater(a["dotcom_return_pct"], 0)

    # --- 3. FRAGILITY INDEX TESTS ---
    def test_fragility_index_calculation(self):
        """Validates 0-100 composite Fragility Index and 6 sub-indicators."""
        res = self.fragility_engine.calculate_fragility_index()
        self.assertIn("composite_score", res)
        self.assertIn("regime", res)
        self.assertIn("components", res)
        self.assertEqual(len(res["components"]), 6)
        self.assertGreaterEqual(res["composite_score"], 0.0)
        self.assertLessEqual(res["composite_score"], 100.0)
        # Sum of component weights must equal 1.0
        total_w = sum(c["weight"] for c in res["components"])
        self.assertAlmostEqual(total_w, 1.0, places=2)

    # --- 4. CONTAGION & STRESS TESTING TESTS ---
    def test_contagion_stress_test_scenario_a(self):
        """Validates Capex reduction shock waterfall and tier sensitivities."""
        res = self.contagion_engine.run_stress_test("scenario_a", capex_cut_pct=20.0)
        self.assertEqual(res["scenario_id"], "scenario_a")
        self.assertIn("impact_waterfall", res)
        self.assertGreater(len(res["impact_waterfall"]), 15)
        # Server and hardware suppliers should be hit harder than hyperscalers
        symbols = [r["symbol"] for r in res["impact_waterfall"]]
        self.assertIn("SMCI", symbols)
        self.assertIn("NVDA", symbols)
        smci = [r for r in res["impact_waterfall"] if r["symbol"] == "SMCI"][0]
        self.assertLess(smci["projected_revenue_impact_pct"], -10.0)


if __name__ == "__main__":
    unittest.main()
