# StockLens US · Deep Quantitative Terminal & Knowledge Graph

**StockLens US** is an institutional market intelligence suite and financial knowledge graph platform built for deep quantitative exploration across the **entire universe of 2,200+ US equities** across 11 GICS sectors.

Powered by a high-throughput **SQLite WAL market database (`data/database/us_equities.db`)**, columnar calculations, and primary SEC regulatory filings.

---

## 🔬 Platform Views & Modules

1. **📊 Equity Atlas (2,200 Stocks & Sector Taxonomy)**:
   - Full market universe explorer across 11 GICS sectors with lifetime daily trading histories (dating back to 1962).
   - High-frequency rolling volatility, maximum drawdown profiles, volume moving averages, and sector taxonomies.

2. **🕸️ Financial Knowledge Graph**:
   - Interactive force-directed canvas visualizing multi-tier relationships (customer, supplier, competitor, joint venture).
   - Network centrality algorithms (*PageRank*, *Betweenness*, *In-Degree*, *Out-Degree*) identifying systemic market God Nodes.

3. **⚡ Transmission Paths & Lead-Lag Diffusion Engine**:
   - Shock propagation simulation tracing price discovery and supply disruptions across multi-hop corporate links.
   - Cross-asset multi-horizon diffusion analysis across $T+1, T+2, T+5, T+10,$ and $T+20$ trading sessions.

4. **📈 Quantitative Models**:
   - Long-memory Hurst Exponent persistence ($H > 0.5$ trending vs $H < 0.5$ mean-reverting).
   - GARCH(1,1) volatility clustering and Value-at-Risk (Parametric & Historical VaR at 95% and 99%).
   - Tail-risk Extreme Value Theory (EVT) modeling.

5. **⚠️ AI Bubble & Contagion Radar**:
   - Multi-metric valuation scanner comparing the 2026 AI supercycle against the 2000 Dot-Com peak across 10 structural dimensions.
   - Reverse DCF 2.0 ($5 \times 5$ WACC vs Terminal Growth matrix) backsolving market-implied growth rates.
   - Contagion stress testing and defensive anti-crash safe-haven rankings.

6. **📑 SEC Form 10-K Evidence**:
   - Ground-truth regulatory citations verifying supply contracts, revenue exposure percentages, and single-supplier risks.

---

## 🚀 How to Run Locally

### Prerequisites
- Python 3.10+
- SQLite market database located at `data/database/us_equities.db`

### Launch Server
```bash
python stocklens/market_server.py --port 8000
```

Once running:
- **StockLens Terminal**: Open [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Data Analyst Portfolio**: Open [http://127.0.0.1:8000/portfolio/](http://127.0.0.1:8000/portfolio/)

---

## 🔗 Related Applications

- **Data Analyst Portfolio (`portfolio/`)**: Dedicated static portfolio website showcasing the 10 US mega-cap technology leaders, CAPM regressions, macro factor regimes, and mathematical spot-check audits.

