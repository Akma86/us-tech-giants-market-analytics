"""
Unit and Integration Tests for AI Bubble Early Warning & Contagion Suite
Tests AIValuationEngine (Reverse DCF 2.0 + 5x5 Sensitivity Matrix + Capital Intensity),
DotComComparisonEngine (10 Dimensions + 34 Safe Havens + 2,200-Stock SQLite Scanner),
FragilityIndexEngine (Empirical SQLite Correlation + Historical Trajectory + Weight Presets),
and AIContagionEngine (Scenarios A-F + Conditional Tail Co-Movement Matrix with FDR).
"""

import unittest

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

    # --- 1. REVERSE DCF 2.0 & VALUATION TESTS ---
    def test_ai_universe_coverage(self):
        """Verifies coverage of all 5 key industry groups and evidence-based AI revenue share metadata."""
        self.assertGreaterEqual(len(AI_UNIVERSE), 26)
        for sym in ["NVDA", "MSFT", "PLTR", "VRT", "SMCI", "ASML"]:
            self.assertIn(sym, AI_UNIVERSE)
            self.assertIn("subsector", AI_UNIVERSE[sym])
            self.assertIn("ai_rev_share_est_pct", AI_UNIVERSE[sym])
            self.assertIn("exposure_tier", AI_UNIVERSE[sym])

    def test_reverse_dcf_model_and_sensitivity_matrix(self):
        """Validates Reverse DCF 2.0 solver and 5x5 WACC vs Terminal Growth sensitivity surface."""
        res = self.val_engine.calculate_reverse_dcf(
            current_price=200.0,
            shares_outstanding=2.5e9,
            fcf_annual=20e9,
            wacc=0.095,
            terminal_growth=0.035,
            hist_rev_growth_pct=18.0
        )
        self.assertIn("implied_5y_fcf_cagr_pct", res)
        self.assertIn("expectation_gap_pct", res)
        self.assertIn("projected_yr5_fcf_billions", res)
        self.assertIn("sensitivity_matrix", res)
        self.assertEqual(len(res["sensitivity_matrix"]), 5)
        self.assertEqual(len(res["sensitivity_matrix"][0]["cells"]), 5)
        self.assertGreater(res["implied_5y_fcf_cagr_pct"], 0.0)
        self.assertLess(res["implied_5y_fcf_cagr_pct"], 50.0)

    def test_single_stock_valuation_fetch(self):
        """Validates live/realtime fetching and capital intensity ratios for NVDA."""
        data = self.val_engine.fetch_stock_valuation("NVDA")
        self.assertEqual(data["symbol"], "NVDA")
        self.assertGreater(data["current_price"], 0.0)
        self.assertGreater(data["market_cap_billions"], 500.0)
        self.assertIn("roic_pct", data)
        self.assertIn("capex_to_rev_pct", data)
        self.assertIn("sbc_to_rev_pct", data)
        self.assertIn("sustainability_score", data)
        self.assertIn("reverse_dcf", data)
        self.assertTrue(data["is_realtime"])

    # --- 2. DOT-COM COMPARISON & SQLITE SCANNER TESTS ---
    def test_dotcom_comparison_matrix_10_dimensions(self):
        """Validates all 10 empirical comparison dimensions between Dot-Com and AI era."""
        res = self.dotcom_engine.get_comparison_matrix()
        self.assertIn("matrix", res)
        self.assertIn("synthesis", res)
        self.assertEqual(len(res["matrix"]), 10)
        self.assertIn("survivorship_bias_disclosure", res["historical_stats"])

    def test_dotcom_drawdown_series(self):
        """Verifies normalized 100-base trajectory data generation."""
        res = self.dotcom_engine.get_drawdown_comparison_series()
        self.assertIn("dotcom_cycle", res)
        self.assertIn("modern_ai_cycle", res)
        self.assertGreater(len(res["dotcom_cycle"]["data"]), 50)
        self.assertGreater(len(res["modern_ai_cycle"]["data"]), 50)

    def test_safe_haven_rotation_matrix_and_sqlite_tail(self):
        """Verifies 34 Safe Haven & Counter-Cyclical assets with SQLite NVDA-crash tail metrics."""
        res = self.dotcom_engine.get_safe_haven_rotation_matrix()
        self.assertIn("assets", res)
        self.assertIn("benchmark_comparison", res)
        self.assertEqual(len(res["assets"]), 34)
        symbols = [a["symbol"] for a in res["assets"]]
        for sym in ["FCN", "AZO", "BRO", "DGX", "DHI", "AEM", "CHD", "CAH", "BRK-B", "LMT", "UNH", "NEM"]:
            self.assertIn(sym, symbols)
        for a in res["assets"]:
            self.assertGreater(a["resilience_score"], 0)
            self.assertGreater(a["dotcom_return_pct"], 0)
            self.assertIn("corr_with_nvda", a)
            self.assertIn("avg_ret_on_nvda_crash_pct", a)

    def test_sqlite_database_crash_scanner(self):
        """Verifies the 2,200-stock SQLite empirical anti-crash discovery scanner."""
        scan = self.dotcom_engine.scan_database_for_crash_hedges(
            max_nvda_corr=0.25, min_dotcom_return=20.0, limit=25
        )
        self.assertEqual(scan["total_db_stocks_scanned"], 2200)
        self.assertGreater(scan["matching_filter_count"], 20)
        self.assertGreater(len(scan["results"]), 10)
        top = scan["results"][0]
        self.assertIn("dotcom_return_pct", top)
        self.assertIn("corr_with_nvda", top)
        self.assertIn("avg_ret_on_nvda_crash_pct", top)

    # --- 3. FRAGILITY INDEX 2.0 TESTS ---
    def test_fragility_index_and_sensitivity_presets(self):
        """Validates 0-100 composite Fragility Index, historical trajectory, and 5 weight schemes."""
        res = self.fragility_engine.calculate_fragility_index()
        self.assertIn("composite_score", res)
        self.assertIn("regime", res)
        self.assertIn("components", res)
        self.assertIn("weight_sensitivity_presets", res)
        self.assertIn("historical_trajectory", res)
        self.assertEqual(len(res["components"]), 6)
        self.assertEqual(len(res["weight_sensitivity_presets"]), 5)
        self.assertGreater(len(res["historical_trajectory"]), 20)
        total_w = sum(c["weight"] for c in res["components"])
        self.assertAlmostEqual(total_w, 1.0, places=2)

    # --- 4. CONTAGION, SCENARIO F & CONDITIONAL TAIL MATRIX TESTS ---
    def test_contagion_stress_test_scenarios_a_and_f(self):
        """Validates Capex reduction (Scenario A) and GPU Supplier Distress (Scenario F)."""
        res_a = self.contagion_engine.run_stress_test("scenario_a", capex_cut_pct=20.0)
        self.assertEqual(res_a["scenario_id"], "scenario_a")
        self.assertGreater(len(res_a["impact_waterfall"]), 15)

        res_f = self.contagion_engine.run_stress_test("scenario_f")
        self.assertEqual(res_f["scenario_id"], "scenario_f")
        smci_f = [r for r in res_f["impact_waterfall"] if r["symbol"] == "SMCI"][0]
        self.assertLess(smci_f["projected_revenue_impact_pct"], -15.0)

    def test_conditional_tail_contagion_matrix(self):
        """Validates empirical conditional tail co-movement matrix and Benjamini-Hochberg FDR q-values."""
        tail = self.contagion_engine.get_tail_contagion_matrix("NVDA", 3.5)
        self.assertEqual(tail["trigger_symbol"], "NVDA")
        self.assertGreater(tail["downside_events_count"], 50)
        self.assertGreater(len(tail["pairs"]), 15)
        first_pair = tail["pairs"][0]
        self.assertIn("downside_prob_pct", first_pair)
        self.assertIn("downside_expected_ret_pct", first_pair)
        self.assertIn("fdr_q_value", first_pair)
        self.assertIn("oos_regime", first_pair)


if __name__ == "__main__":
    unittest.main()
