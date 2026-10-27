# PROJECT: StockLens — AI Bubble Early Warning & Financial Contagion Intelligence

You are a senior quantitative researcher, financial data engineer, data scientist, and full-stack Python developer.

I want you to build an evidence-driven **AI Bubble Early Warning and Financial Contagion Intelligence System**.

This project is part of StockLens, a financial knowledge graph and stock market movement intelligence platform.

## 1. Main objective

Build a research platform to investigate:

1. Are AI-related US stocks becoming overvalued relative to their fundamentals?
2. Are current AI market conditions similar to the 1995–2002 dot-com bubble?
3. Which AI companies are financially sustainable, and which depend heavily on speculative expectations or external funding?
4. Which stocks tend to rise or fall together?
5. Which companies could face direct or indirect financial pressure if AI investment slows?
6. Are there statistically meaningful early warning indicators of market fragility?
7. Can we detect changes in market behavior before major drawdowns?
8. How sensitive are AI-related companies to interest rates, financing conditions, and economic slowdowns?

**Important:** Do not assume an AI bubble exists. Treat the existence, size, and timing of a bubble as open empirical research questions.

The system must distinguish between observed facts, statistical associations, economic hypotheses, and causal evidence.

## 2. Scope

Focus exclusively on US-listed companies initially.

Use historical datasets covering approximately 1995–2003 for dot-com comparisons and 2015–present for contemporary AI analysis, subject to verified data availability.

Prioritize these industry groups:

### Semiconductor and chip infrastructure
- NVIDIA (NVDA)
- AMD (AMD)
- Broadcom (AVGO)
- Intel (INTC)
- Micron (MU)
- Applied Materials (AMAT)
- Lam Research (LRCX)

### Cloud and hyperscalers
- Microsoft (MSFT)
- Alphabet (GOOGL)
- Amazon (AMZN)
- Oracle (ORCL)
- Meta (META)

### Enterprise AI and software
- Palantir (PLTR)
- Salesforce (CRM)
- ServiceNow (NOW)
- Snowflake (SNOW)

### Power, electrical infrastructure, and data centers
- Vertiv (VRT)
- Eaton (ETN)
- Constellation Energy (CEG)
- Equinix (EQIX)
- Digital Realty (DLR)

### Networking, storage, and related hardware
- Arista Networks (ANET)
- Dell Technologies (DELL)
- Super Micro Computer (SMCI)

Do not assume all companies have equivalent AI revenue exposure. Build an evidence-based AI exposure classification and record uncertainty.

Allow users to expand the stock universe through configuration files.

## 3. Research module A — AI valuation analysis

Collect and calculate:

- Market capitalization
- Enterprise value
- Price-to-sales
- Forward and trailing P/E
- EV/Revenue
- EV/EBITDA
- Price-to-free-cash-flow
- Revenue growth
- Earnings growth
- Gross margin
- Operating margin
- Free cash flow margin
- Return on invested capital
- R&D/revenue
- Capital expenditure/revenue
- Capex/depreciation
- Stock-based compensation/revenue
- Net debt/EBITDA
- Share dilution
- Analyst earnings revisions, where reliable data is available

Analyze how valuation multiples change over time and relative to company growth, profitability, industry peers, and interest-rate conditions.

Implement a reverse DCF model to estimate the growth, margin, and terminal assumptions implied by current valuations.

Never interpret a high valuation multiple alone as definitive proof of a bubble.

## 4. Research module B — Dot-com bubble comparison

Build a historical comparison of the dot-com boom and crash against the contemporary AI investment cycle.

Analyze:

- IPO issuance activity
- Average first-day IPO returns
- Market concentration
- Valuation dispersion
- Revenue growth versus profitability
- Cash burn and financing dependence
- Interest rates and monetary tightening
- Profitability of market leaders
- Retail speculation proxies
- Earnings expectations
- Margin trends
- Price momentum and market drawdowns

Include historical failed and delisted companies where data access permits.

Avoid survivorship bias, look-ahead bias, and misleading comparisons between different accounting standards or market structures.

Use separate normalization procedures and disclose limitations when historical series are not directly comparable.

## 5. Research module C — AI supply chain knowledge graph

Build a directed, typed, source-backed knowledge graph.

Node types:

- Company
- Sector
- Industry
- Product
- Service
- Supplier
- Customer
- Commodity
- Infrastructure
- Financial metric
- Economic indicator
- News event
- Risk factor

Relationship types:

- SUPPLIES_TO
- BUYS_FROM
- PRODUCES
- DEPENDS_ON
- COMPETES_WITH
- CUSTOMER_OF
- EXPOSED_TO
- FINANCED_BY
- BENEFITS_FROM
- COST_PRESSURE_FROM
- STATISTICALLY_ASSOCIATED_WITH
- POTENTIALLY_AFFECTED_BY

Example pathways to investigate:

AI model demand → GPU demand → Semiconductor sales → Foundry capacity → Semiconductor equipment → Materials and power consumption.

Hyperscaler AI capex → Data center construction → Cooling infrastructure → Electrical equipment → Power generation → Grid investment.

AI spending slowdown → Hyperscaler capex revisions → GPU order expectations → Supplier revenue forecasts → Valuation revisions.

These are hypotheses until supported by evidence.

Each graph relationship must store:

- Source entity
- Target entity
- Relationship type
- Direction
- Economic mechanism
- Source URL
- Evidence publication timestamp
- Valid-from and valid-to dates
- Evidence classification
- Confidence level
- Last verification date

Never invent supplier contracts, revenue concentration, or customer relationships.

## 6. Research module D — Quantitative stock relationships

I want to know:

"When stock A rises or falls, which other stocks tend to rise, fall, or react later?"

Implement:

1. Pearson correlation
2. Spearman correlation
3. Rolling 30/60/120-session correlations
4. Conditional positive and negative return probabilities
5. Conditional average returns
6. Relative risk ratios and conditional probability lift
7. Market- and industry-adjusted return correlations
8. Lead-lag regression
9. Partial correlations
10. Factor models
11. Event-window correlation changes
12. Network centrality and community detection
13. Changes in graph connectivity during market stress

Calculate:

P(Return_B > 0 | Return_A > threshold)

P(Return_B < 0 | Return_A < -threshold)

E(Return_B | Return_A > threshold)

Corr(Return_A,t, Return_B,t+k)

Include multiple thresholds such as 1%, 3%, 5%, and stock-specific volatility-adjusted thresholds.

For every relationship, report:

- Effect size
- Sample size
- Time window
- Confidence interval
- Statistical significance when applicable
- Baseline probability
- Multiple-testing correction
- Out-of-sample stability

Avoid treating same-day correlation as a directly tradable predictive signal.

Account for common market and sector factors, nonstationarity, overlapping events, trading calendars, and data leakage.

## 7. Research module E — Financial contagion and stress testing

Create interactive hypothetical scenarios:

Scenario A: AI capital expenditure decreases by 10%, 20%, or 40%.

Scenario B: AI semiconductor revenue growth falls below expectations.

Scenario C: US interest rates remain higher than expected.

Scenario D: Large AI companies revise earnings guidance downward.

Scenario E: Data center construction experiences a substantial slowdown.

Scenario F: A major AI infrastructure supplier experiences financial distress.

Model potential transmission through the verified relationship network.

Separate:

- Direct revenue exposure
- Operating cost exposure
- Contractual dependency
- Financial leverage
- Estimated statistical sensitivity
- Hypothesized indirect impact

Build sensitivity ranges instead of claiming exact future stock prices.

Do not equate a 20% capex reduction with a 20% supplier revenue decline unless empirically justified.

## 8. Research module F — Early warning indicators

Investigate combinations of:

- Valuation expansion relative to earnings
- Growth expectation revisions
- Concentration of index returns
- Increasing pairwise correlation
- Weakening market breadth
- Excessive IPO speculation
- Increasing leverage
- Deteriorating cash conversion
- Capex growth exceeding realized monetization
- Increasing credit spreads
- Rising implied volatility
- Investor sentiment deterioration
- Negative earnings revisions
- Divergence between share-price performance and fundamentals

Create an explainable composite **AI Market Fragility Index**.

The index must show:

- Component indicators
- Normalization methodology
- Historical percentile
- Direction of deterioration
- Data freshness
- Missing data
- Component weights
- Sensitivity to alternative weights

The index must NOT claim to predict the exact date of a market crash.

Avoid arbitrary green/yellow/red thresholds unless they are explicitly labeled as illustrative or supported by historical validation.

## 9. Required dashboard

Use Streamlit and Plotly.

Create the following pages:

1. Executive Overview
2. AI Stock Universe
3. Valuation & Fundamentals
4. Dot-Com vs AI Comparison
5. Stock Correlation Network
6. Financial Knowledge Graph
7. Market Fragility Indicators
8. AI Supply Chain Exposure
9. Scenario & Stress Testing
10. Research Evidence and Data Quality

For the stock relationship page, allow users to:

- Select stock A
- Set a return threshold
- Select a date range
- Choose same-session or lagged analysis
- See which stocks historically moved up or down
- Compare conditional results against baseline probabilities
- Explore a network of strongest relationships
- Open a detailed statistical report for each connection

For the knowledge graph, clicking a company should display its documented suppliers, customers, products, financial exposures, and supporting evidence.

## 10. Data sources

Prioritize reputable public and official sources:

- SEC EDGAR APIs for US company financial statements
- FRED for macroeconomic and financial indicators
- US Treasury for government yields
- EIA for energy prices and consumption
- World Bank for historical commodity benchmarks
- BEA for industry input-output relationships
- Jay Ritter's IPO research datasets for historical IPO analysis
- Company 10-K and 10-Q filings
- Official company earnings releases and investor presentations
- yfinance for preliminary stock price research, with licensing and coverage limitations clearly documented

Do not silently fabricate missing data.

If data is unavailable, record the limitation and use explicitly identified sample data only for UI testing.

Document historical ticker changes, delistings, corporate actions, reporting dates, point-in-time availability, and frequency conversions.

## 11. Technology

Use:

- Python 3.11+
- Pandas and NumPy
- DuckDB and Parquet
- NetworkX
- Statsmodels and SciPy
- Scikit-learn when justified
- Plotly
- Streamlit
- PyVis or another suitable graph visualization library
- Pytest

Keep the architecture modular and suitable for future Neo4j migration.

## 12. Engineering requirements

Build a clean repository with:

- README.md
- requirements.txt or pyproject.toml
- .env.example
- config/
- data/raw/
- data/processed/
- data/relationships/
- src/ingestion/
- src/validation/
- src/features/
- src/analysis/
- src/graph/
- src/scenarios/
- app/
- notebooks/
- tests/
- docs/

Add:

- Type hints
- Structured logging
- Clear exception handling
- Reproducible calculations
- Dataset provenance
- Unit tests for formulas
- Caching for API requests
- Data validation
- Sensible dependency management

Do not commit credentials, API keys, or large raw datasets to Git.

## 13. Implementation priorities

I want a realistic three-day MVP before expanding the full platform.

### Day 1 — Financial data and stock relationships

- Set up the repository
- Download and validate available stock prices
- Build financial return features
- Calculate correlation and conditional movement statistics
- Create a basic stock relationship network
- Add initial automated tests

### Day 2 — Valuation and economic relationships

- Collect available financial fundamentals
- Implement valuation metrics
- Build a smaller, verified AI supply chain graph
- Add initial macroeconomic indicators
- Create a limited dot-com comparison with documented source limitations

### Day 3 — Dashboard and validation

- Build a working Streamlit dashboard
- Integrate graphs and time-series views
- Implement one clearly labeled stress-test example
- Validate results and prevent data leakage
- Document known limitations
- Prepare the GitHub README

The full ten-page dashboard, exhaustive relationships, historical survivorship-adjusted analysis, and sophisticated contagion model are later milestones, not mandatory for the initial MVP.

## 14. Final deliverables

Provide:

1. A runnable local application.
2. Reproducible data ingestion scripts.
3. Quantitative stock relationship analysis.
4. A source-backed AI ecosystem knowledge graph.
5. An initial valuation monitoring module.
6. A historical dot-com comparison module.
7. A dashboard.
8. Documentation and tests.
9. A roadmap for extending the MVP into a serious research platform.

## 15. How to work

Begin by inspecting the existing repository if one exists.

Do not overwrite working files without inspecting them.

First create a concise implementation plan, dependency architecture, data availability assessment, and acceptance criteria.

Then implement the three-day MVP incrementally.

Run the code and tests whenever the environment permits. Fix errors rather than stopping at code generation.

When live data access or API credentials are unavailable, explain the blocker and provide a working alternative with clearly labeled mock data.

At the end of each implementation milestone, report:

- Files created or modified
- Functionality implemented
- Tests executed and results
- Real versus simulated data
- Known limitations
- Next development step

Prioritize mathematical correctness, reproducibility, financial reasoning, and explainability over visual complexity.

**The ultimate goal is not to predict a bubble confidently. It is to build an evidence-based monitoring system that helps researchers recognize changing valuation risk, financial fragility, and market interconnectedness before making investment decisions.**
