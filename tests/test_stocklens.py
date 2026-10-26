"""
Unit and Integration Test Suite for StockLens US.
Tests data integrity, DuckDB queries, Graph traversal, and Quantitative models.
"""

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import duckdb

from src.graph_builder import FinancialKnowledgeGraph
from src.analyze_us import FinancialAnalyticsEngine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_US_DIR = PROJECT_ROOT / "data" / "us"


class TestStockLensUS(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.kg = FinancialKnowledgeGraph(DATA_US_DIR)
        cls.engine = FinancialAnalyticsEngine()

    @classmethod
    def tearDownClass(cls):
        cls.engine.close()

    # --- 1. DATA & DUCKDB TESTS ---
    def test_data_files_exist(self):
        """Verifies all CSV, Parquet, and DuckDB files exist."""
        self.assertTrue((DATA_US_DIR / "entities.csv").exists(), "Missing entities.csv")
        self.assertTrue((DATA_US_DIR / "relationships.csv").exists(), "Missing relationships.csv")
        self.assertTrue((DATA_US_DIR / "evidence.csv").exists(), "Missing evidence.csv")
        self.assertTrue((DATA_US_DIR / "prices.parquet").exists(), "Missing prices.parquet")
        self.assertTrue((DATA_US_DIR / "stocklens.duckdb").exists(), "Missing stocklens.duckdb")

    def test_duckdb_tables_and_counts(self):
        """Queries DuckDB to verify tables and minimum record counts."""
        con = duckdb.connect(str(DATA_US_DIR / "stocklens.duckdb"), read_only=True)
        tables = con.execute("SHOW TABLES;").df()["name"].tolist()
        self.assertIn("entities", tables)
        self.assertIn("relationships", tables)
        self.assertIn("evidence", tables)
        self.assertIn("market_prices", tables)

        n_entities = con.execute("SELECT count(*) FROM entities;").fetchone()[0]
        n_rel = con.execute("SELECT count(*) FROM relationships;").fetchone()[0]
        n_prices = con.execute("SELECT count(*) FROM market_prices;").fetchone()[0]
        con.close()

        self.assertGreaterEqual(n_entities, 50, "Entities count below expectation")
        self.assertGreaterEqual(n_rel, 50, "Relationships count below expectation")
        self.assertGreaterEqual(n_prices, 10000, "Price rows below expectation")

    # --- 2. GRAPH ENGINE TESTS ---
    def test_graph_structure(self):
        """Validates node attributes, edge connectivity, and entity types."""
        self.assertGreaterEqual(self.kg.graph.number_of_nodes(), 75)
        self.assertGreaterEqual(self.kg.graph.number_of_edges(), 60)

        # Ensure major entities exist
        for ticker_node in ["co_aapl", "co_msft", "co_nvda", "co_dal", "commodity_wti"]:
            self.assertTrue(self.kg.graph.has_node(ticker_node), f"Node {ticker_node} not in graph")
            attrs = self.kg.graph.nodes[ticker_node]
            self.assertIn("name", attrs)
            self.assertIn("entity_type", attrs)

    def test_transmission_path_finder(self):
        """Verifies multi-hop path search between Crude Oil and Delta Air Lines."""
        paths = self.kg.find_transmission_paths("commodity_wti", "co_dal", max_hops=4)
        self.assertGreaterEqual(len(paths), 1, "Should find at least 1 path from WTI to DAL")

        first_path = paths[0]
        self.assertGreaterEqual(len(first_path), 1)
        self.assertEqual(first_path[0]["from_id"], "commodity_wti")
        self.assertEqual(first_path[-1]["to_id"], "co_dal")

    def test_centrality_calculation(self):
        """Ensures PageRank and Betweenness metrics compute without error."""
        metrics = self.kg.calculate_centrality_metrics()
        self.assertFalse(metrics.empty)
        self.assertIn("pagerank", metrics.columns)
        self.assertIn("betweenness", metrics.columns)
        self.assertGreater(metrics["pagerank"].sum(), 0.9)  # PageRank sum close to 1.0

    # --- 3. QUANTITATIVE ANALYTICS TESTS ---
    def test_market_model_ols(self):
        """Validates market model regression output for Microsoft (MSFT)."""
        res = self.engine.run_market_model("MSFT", "^GSPC", start_date="2022-01-01")
        self.assertEqual(res["ticker"], "MSFT")
        self.assertGreater(res["beta"], 0.5)  # MSFT tech beta generally > 0.5
        self.assertLess(res["beta"], 2.5)
        self.assertGreater(res["r_squared"], 0.3)
        self.assertGreater(res["sample_size"], 100)

    def test_event_study_engine(self):
        """Validates Event Study abnormal return calculation."""
        # Test NVDA Blackwell announcement event date 2024-03-18
        ev = self.engine.run_event_study("NVDA", "2024-03-18", pre_event_window=3, post_event_window=5)
        self.assertEqual(ev["ticker"], "NVDA")
        self.assertIn("car", ev)
        self.assertIn("t_statistic", ev)
        self.assertIn("p_value", ev)
        self.assertEqual(len(ev["event_series"]), 9)  # 3 pre + day 0 + 5 post = 9 days

    def test_lead_lag_cross_correlation(self):
        """Validates cross-correlation across lag horizons."""
        ll = self.engine.run_lead_lag_correlation("XOM", "CL=F", lags=[-5, 0, 5])
        self.assertEqual(ll["equity_ticker"], "XOM")
        self.assertEqual(ll["macro_ticker"], "CL=F")
        self.assertEqual(len(ll["lag_matrix"]), 3)
        # Exxon Mobil daily return coincident with WTI oil should have positive correlation
        coincident = [r for r in ll["lag_matrix"] if r["lag_days"] == 0][0]
        self.assertGreater(coincident["correlation"], 0.20, "XOM vs WTI 0d correlation should be positive (> 0.20)")
        self.assertLess(coincident["p_value"], 0.001, "Correlation must be statistically significant (p < 0.001)")


if __name__ == "__main__":
    unittest.main()
