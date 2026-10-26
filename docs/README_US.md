# StockLens US — Financial Knowledge Graph & Market Intelligence

> **Active development track: United States.** Explore how the 11 US equity sectors connect to products, commodities, suppliers, customers, financial fundamentals, sentiment, and stock movements.

**Status:** Research blueprint / 3-day prototype target  
**Geography:** United States only  
**Classification:** [GICS — S&P Dow Jones Indices](https://www.spglobal.com/spdji/en/landing/topic/gics/)  
**Stack:** Python · DuckDB/Parquet · NetworkX · Streamlit · Plotly  
**Indonesia companion:** [`README_INDONESIA.md`](README_INDONESIA.md) — separate later-phase research.

## US project objective

Trace **documented relationships and testable exposures** from US-listed companies through industry inputs, demand, financial results and market behavior. A stock-price correlation does **not** prove a supply contract or causal mechanism.

### Core questions

1. Which raw materials, suppliers, services and buyers matter to each US sub-industry?
2. How are WTI/Brent, natural gas, copper, fuel, electricity, interest rates and demand associated with company costs and earnings?
3. Which public filings substantiate specific supplier, customer or operating exposures?
4. What happened around abnormal stock-return events, and what evidence supports each proposed explanation?
5. How do transmission paths connect two or more sectors?

### MVP boundaries

- Include **all 11 GICS sector nodes** and their structural relationship templates.
- Start with **15–25 selected US companies** and **10–15 factor/commodity nodes**.
- Prefer **5–15 genuinely source-verified company edges** over 50 unverified supplier claims.
- Analyze **January 2023–September 2026** as a practical starter period, extending back where credible series exist.
- No Indonesia tickers, IDX data, or cross-market time alignment in this phase.

## Relationship ontology

### Entity types

| Entity type | Examples | Typical attributes |
| --- | --- | --- |
| `Sector` | Information Technology, Energy | classification system, code |
| `Industry` / `SubIndustry` | Semiconductors, Airlines | classification code, parent sector |
| `Company` | NVIDIA, Tesla, BBCA | ticker, exchange, country, identifiers |
| `Product` / `Service` | Battery, cloud service, jet fuel | category, unit |
| `Commodity` / `Material` | Copper, lithium, natural gas | price benchmark, unit, currency |
| `Facility` | Refinery, mine, data center | geography, capacity |
| `Supplier` / `Customer` | Other company nodes with relationship roles | disclosure evidence |
| `FinancialMetric` | Revenue, COGS, gross margin | reporting period, unit, accounting basis |
| `MacroIndicator` | Fed funds rate, CPI | release timestamp, revision vintage |
| `Event` | Earnings, rate decision, supply disruption | announcement timestamp, event type |
| `Source` | 10-K, annual report, statistical release | URL, publisher, retrieved date |

### Edge types

| Edge type | Meaning | Evidence standard |
| --- | --- | --- |
| `BELONGS_TO` | Company → classified sector | Exchange / classification provider |
| `PRODUCES` | Company → product/service | Filing, annual report |
| `USES_MATERIAL` | Product/process → input | Technical or industry source |
| `BUYS_FROM` | Company → company supplier | Explicit disclosure or contract |
| `SELLS_TO` | Company → customer | Explicit disclosure or contract |
| `OPERATES` | Company → facility | Company / regulatory disclosure |
| `HAS_EXPOSURE_TO` | Company → economic driver | Documented cost/revenue rationale; may be approximate |
| `REPORTS_METRIC` | Company → financial metric | Filing or financial data record |
| `AFFECTED_BY_EVENT` | Event → affected entity | Research hypothesis or supported analysis (mark status) |
| `MENTIONS` | News/source → company | Traceable text / metadata |
| `CORRELATED_WITH` | Variable → variable | Explicit sample, period, method, coefficient |

**Mandatory edge metadata:** `relationship_id`, `source_id`, `valid_from`, `valid_to`, `evidence_status`, `confidence`, `retrieved_at`, `notes`. Add `direction`, `units`, `lag`, and `model_version` where appropriate. Avoid numerical "impact" scores without a calibrated model.

## The 11 sectors and their relationships

The following lists are **industry-level research targets**, not assertions that named example companies necessarily purchase from specific suppliers. Validate named-company links individually.

### 1. Information Technology

**Examples:** Apple, Microsoft, NVIDIA, AMD, Broadcom.  
**Sub-industries:** Semiconductors, semiconductor equipment, hardware, networking, enterprise software, cybersecurity, IT services, electronic equipment.

| Business area | Inputs / supply-side connections | Demand / revenue-side connections |
| --- | --- | --- |
| Semiconductors | Silicon wafers, specialty gases, chemicals, copper, advanced packaging, fabrication equipment | Data centers, consumer electronics, vehicles, industrial devices |
| Semiconductor equipment | Precision metals, optics, robotics, electronics | Semiconductor fabs and capacity expansion |
| Consumer hardware | Chips, glass, aluminum, displays, batteries, rare-earth magnets | Consumers, distributors, enterprises |
| Servers and networking | Chips, circuit boards, optical fiber, cooling, power | Data centers, telecom, enterprise IT |
| Software and cybersecurity | Engineers, cloud computing, third-party software, electricity | IT budgets, subscriptions, security demand |
| IT consulting | Personnel, cloud licenses, enterprise software | Digital transformation budgets |

**Track:** Copper, aluminum, memory prices, electricity, semiconductor sales, cloud/data-center capex, smartphone/PC shipments, gross margin, R&D, enterprise spending, USD, export controls, tariffs, AI-product sentiment.

**Other sectors:** Utilities (electricity); Materials (specialty chemicals/metals); Industrials (factory and cooling equipment); Communication Services (networking/cloud customers); Consumer Discretionary (devices and EV electronics).

**Caveat:** Hardware, semiconductors, and software have substantially different input structures.

### 2. Health Care

**Examples:** Eli Lilly, Johnson & Johnson, Pfizer, Abbott, UnitedHealth.  
**Sub-industries:** Pharmaceuticals, biotechnology, medical devices, hospitals, diagnostics, insurers, distributors.

| Business area | Inputs / operating dependencies | Demand / revenue drivers |
| --- | --- | --- |
| Pharmaceuticals | Active pharmaceutical ingredients, chemical inputs, trials, manufacturing | Prescriptions, patents, reimbursement, approvals |
| Biotechnology | Research labor, laboratories, clinical trials, funding | Trial outcomes, licensing, approvals |
| Medical devices | Metals, polymers, electronics, sterilization | Surgery volumes, hospital procurement |
| Hospitals | Clinical labor, pharmaceuticals, energy, property | Admissions, procedures, reimbursement |
| Insurers | Provider networks, claims, IT, regulatory capital | Premiums, members, claims ratios |
| Diagnostics | Reagents, instruments, lab logistics | Testing volumes and health-system spending |
| Distributors | Warehousing, cold-chain shipping, fuel | Pharmacy and hospital demand |

**Track:** Titanium, stainless steel, petrochemical inputs, labor inflation, utilization, approvals, patent expiries, clinical trial announcements, R&D, loss/medical cost ratio, product-level sales, recalls.

**Other sectors:** Materials (chemicals); Technology (diagnostics/health IT); Industrials (equipment/logistics); Financials (insurance and financing); Real Estate (hospitals and laboratories).

**Caveat:** Regulatory and clinical catalysts can dominate raw-material changes for biotechnology stocks.

### 3. Financials

**Examples:** JPMorgan Chase, Bank of America, Goldman Sachs, Berkshire Hathaway, Visa.  
**Sub-industries:** Commercial banking, investment banking, asset management, insurance, payments, consumer finance, brokers/exchanges.

| Business area | Dependence | Revenue / risk drivers |
| --- | --- | --- |
| Commercial banking | Deposits, wholesale funding, lending | Net interest margin, credit losses, loan growth |
| Investment banking | Capital markets, deal pipelines | Advisory and underwriting fees |
| Asset management | Market values, inflows/outflows | AUM and management fees |
| Insurance | Claims, reinsurance, catastrophe exposure | Premiums, underwriting result, investment income |
| Payments | Merchants, networks, fraud controls | Transaction volume and fees |
| Consumer finance | Borrowing cost, borrower quality | Loan balances, delinquencies, spreads |
| Brokerage/exchanges | Market participation and volatility | Trading, clearing, data fees |

**Track:** Fed rate, 2Y/10Y Treasury yields, yield curve, credit spreads, deposits, loan losses, unemployment, mortgages, card spending, capital ratios, return on equity, regulatory news.

**Other sectors:** Real Estate (mortgages); Consumer Discretionary (auto/consumer loans); Industrials (equipment/project finance); Energy (financing/hedging); Technology (payments/security).

**Caveat:** Rate increases are not automatically positive for banks; funding cost and credit deterioration matter.

### 4. Consumer Discretionary

**Examples:** Tesla, Amazon, Nike, Home Depot, McDonald's.  
**Sub-industries:** Autos/EVs, apparel, restaurants, hotels, e-commerce, home improvement, leisure.

| Business area | Input costs | Demand indicators |
| --- | --- | --- |
| Automotive | Steel, aluminum, copper, rubber, chips, batteries | Unit sales, financing rates, consumer confidence |
| EVs | Lithium, nickel, graphite, cells, motors | EV adoption, subsidies, charging |
| Apparel | Cotton, polyester, dyes, wages, freight | Clothing sales, household spending |
| Hotels | Labor, electricity, food, property | Occupancy, RevPAR, tourism |
| Restaurants | Food commodities, packaging, rent, wages | Transactions, same-store sales |
| E-commerce | Warehousing, shipping, cloud, advertising | Orders, spending, conversion |
| Home improvement | Lumber, metals, appliances, transportation | Housing turnover, renovations |

**Track:** Steel, aluminum, lithium, rubber, lumber, cotton, gasoline, wages, consumer confidence, credit conditions, inventories, average transaction value, pricing versus unit demand.

**Other sectors:** Materials (physical goods); Industrials (freight); Financials (consumer credit); Real Estate (shops/hotels); Energy (transport fuel); Communication Services (advertising).

### 5. Consumer Staples

**Examples:** Walmart, Costco, Coca-Cola, PepsiCo, Procter & Gamble.  
**Sub-industries:** Food, beverages, household care, essential retailers, agricultural processors, tobacco.

| Business area | Input costs | Demand / operations |
| --- | --- | --- |
| Food manufacturing | Wheat, corn, sugar, edible oils, packaging | Volume, pricing, grocery consumption |
| Beverages | Sugar, coffee, water, aluminum, PET | Beverage volume, mix, promotions |
| Household care | Chemicals, pulp, paper, plastics | Household consumption and brands |
| Grocery retail | Inventory, refrigeration, fuel | Store traffic, basket size |
| Agricultural processing | Soybeans, corn, wheat, energy | Crop supply, processing margins |
| Tobacco | Tobacco leaf, packaging, excise duties | Volume, pricing, regulation |

**Track:** Coffee, cocoa, wheat, corn, sugar, soybeans, palm oil, pulp, aluminum, packaging, diesel, crop yields, drought, food inflation, gross margins, inventory turns, recalls.

**Other sectors:** Materials (packaging/fertilizers); Energy (fuel/feedstocks); Industrials (trucking); Utilities (refrigeration); Financials (payment/working capital).

### 6. Energy

**Examples:** ExxonMobil, Chevron, ConocoPhillips, SLB, Williams Companies.  
**Sub-industries:** Exploration/production, refining, natural gas, pipelines, oilfield services, LNG, consumable fuels.

| Business area | Inputs / operating costs | Revenue drivers |
| --- | --- | --- |
| Exploration & production | Rigs, steel pipe, chemicals, labor, energy | Realized oil/gas prices, volumes |
| Refining | Crude, catalysts, hydrogen, natural gas | Gasoline/diesel/jet-fuel spreads |
| Gas production | Drilling, compression, pipelines | Gas price and industrial/power demand |
| Pipelines | Steel, compressors, maintenance | Volumes, tariffs, contracts |
| Oilfield services | Specialized machinery, steel, talent | Drilling activity and producer capex |
| LNG | Gas feedstock, refrigeration, compressors | LNG price/contracts and export volumes |
| Coal | Mining equipment, diesel, labor | Thermal/metallurgical coal prices |

**Track:** WTI, Brent, Henry Hub, diesel, gasoline, jet fuel, LNG, coal, OPEC output, inventories, rig counts, refinery utilization, production/lifting costs, crack spreads, sanctions and geopolitical events.

**Other sectors:** Industrials (transport fuel); Materials (chemical feedstocks, mining energy); Utilities (gas/fuels); Discretionary (air travel/auto fuel); Staples (packaging/distribution); Financials (project finance).

**Caveat:** Producers, refiners, and pipeline companies can react differently to the same crude-price shock.

### 7. Industrials

**Examples:** Caterpillar, Boeing, GE Aerospace, UPS, Deere.  
**Sub-industries:** Machinery, aerospace, defense, airlines, trucking, rail, shipping, construction, electrical equipment, waste management, professional services.

| Business area | Input costs | Demand drivers |
| --- | --- | --- |
| Heavy machinery | Steel, copper, hydraulics, engines | Mining, construction, infrastructure |
| Aerospace | Titanium, aluminum, composites, chips | Aircraft orders and fleet renewal |
| Defense | Specialty alloys, electronics, labor | Government procurement |
| Airlines | Jet fuel, labor, aircraft leases | Traffic, fares, load factor |
| Trucking/rail | Diesel, tires, steel, wages | Freight volume and industrial activity |
| Shipping | Marine fuel, terminals, containers | Trade volume and freight rates |
| Construction | Cement, steel, copper, equipment | Infrastructure and building activity |
| Electrical equipment | Copper, steel, semiconductors | Grid and manufacturing capex |

**Track:** Steel, copper, aluminum, titanium, rubber, cement, diesel, jet fuel, shipping rates, PMI, industrial production, construction spending, backlogs, orders, utilization, labor strikes, tariffs.

**Other sectors:** Materials (metals); Energy (fuel); Technology (automation); Real Estate (construction/warehouses); Staples (distribution); Utilities (grid equipment).

### 8. Utilities

**Examples:** NextEra Energy, Duke Energy, Southern Company, American Water Works.  
**Sub-industries:** Regulated electricity, gas utilities, water, renewable power, independent generation, grid infrastructure.

| Business area | Inputs | Revenue / cost drivers |
| --- | --- | --- |
| Regulated electric utility | Fuel, transformers, grid equipment, labor | Tariffs, allowed returns, electricity load |
| Gas utility | Natural gas, pipelines, storage | Distribution volume and allowed tariffs |
| Water utility | Chemicals, electricity, pumps | Water use, tariffs, capex |
| Renewable generation | Panels, turbines, batteries, metals | PPA contracts, capacity, output |
| Merchant power | Fuel, generation equipment | Wholesale electricity price and utilization |
| Grid network | Copper, aluminum, transformers | Grid expansion and replacement capex |

**Track:** Natural gas, coal, uranium, wholesale power, electricity demand, load by customer class, copper, transformer lead times, weather, Treasury yields, debt costs, allowed return on equity, capex, regulatory orders.

**Other sectors:** Technology (data-center power); Materials (metals/fuels); Industrials (turbines/grid construction); Real Estate (building consumption); Financials (debt finance).

### 9. Real Estate

**Examples:** Prologis, Equinix, American Tower, Realty Income, Welltower.  
**Sub-industries:** Residential, office, industrial REITs, retail REITs, data centers, healthcare property, storage, towers.

| Business area | Dependencies | Revenue / valuation drivers |
| --- | --- | --- |
| Residential | Mortgage rates, construction labor/materials | Rent, occupancy, household formation |
| Office | Tenant employment, debt cost | Leasing, occupancy, renewals |
| Industrial REIT | Logistics demand, construction | Warehouse rents and utilization |
| Retail REIT | Consumer spending and tenant health | Leases, foot traffic, occupancy |
| Data-center REIT | Electricity, cooling, connectivity | Contracted capacity and demand |
| Healthcare REIT | Operators, medical use, facility costs | Tenant cash flow, leases |
| Tower REIT | Telecom investment and infrastructure | Carrier leases and utilization |

**Track:** Mortgage/long bond yields, credit spreads, property cap rates, vacancy, rent growth, FFO/AFFO, NOI, housing starts, lumber, steel, cement, labor, work-from-home trends, refinancing schedules.

**Other sectors:** Financials (loans); Materials (construction inputs); Industrials (buildings/warehouses); Technology (data centers); Utilities (power/water); Discretionary (retail/hotels).

### 10. Materials

**Examples:** Freeport-McMoRan, Newmont, Nucor, Dow, Linde.  
**Sub-industries:** Mining, metals, steel, aluminum, chemicals, fertilizers, packaging, cement, forest products, industrial gases.

| Business area | Input costs | Revenue drivers |
| --- | --- | --- |
| Copper/gold mining | Diesel, power, labor, reagents | Realized metal prices, production |
| Steel | Iron ore/scrap, coking coal, gas | Auto, construction, machinery demand |
| Aluminum | Bauxite, alumina, large electricity load | Packaging, transport, construction |
| Chemicals | Hydrocarbons, feedstocks, energy | Industrial, semiconductor, healthcare demand |
| Fertilizers | Natural gas, ammonia, phosphate, potash | Crop prices, agriculture demand |
| Packaging | Pulp, plastics, aluminum | Food, beverage, retail orders |
| Cement/aggregates | Limestone, kiln fuel, electricity | Construction and infrastructure |
| Forest products | Timber, fuel, labor | Housing, pulp, paper demand |
| Industrial gases | Power, gas processing, transport | Chipmaking, medical, metallurgy |

**Track:** Copper, aluminum, iron ore, zinc, nickel, gold, coal, natural gas, ammonia, phosphate, potash, pulp, lumber, mining costs, inventory, industrial activity, China demand, tariffs and export restrictions.

**Other sectors:** Technology (electronics materials); Discretionary (batteries/vehicles/housing); Industrials (machinery/construction); Energy (pipes and chemicals); Staples (fertilizers/packaging); Utilities (grid materials).

### 11. Communication Services

**Examples:** Alphabet, Meta, Netflix, Disney, Verizon.  
**Sub-industries:** Telecom, broadband, digital advertising, search/social platforms, streaming, entertainment, gaming, publishing.

| Business area | Inputs / costs | Revenue drivers |
| --- | --- | --- |
| Telecom | Spectrum, towers, fiber, network electronics | Subscribers, ARPU, data usage |
| Search/social/ads | Data centers, engineers, AI compute, moderation | Engagement, ad budgets/prices |
| Streaming | Content licensing, production, cloud/CDN | Subscribers, retention, advertising |
| Film/TV | Production crews, studios, rights | Box office, licensing, distribution |
| Gaming | Developers, GPUs, cloud, platforms | Game sales, subscriptions, purchases |
| Broadband | Fiber/coax, equipment, technicians | Connections, pricing, churn |
| Publishing | Content production/distribution | Advertising, circulation, subscriptions |

**Track:** Digital advertising spend, data-center capex, power use, network equipment, fiber deployment, subscriber growth, churn, ARPU, engagement, content amortization, privacy policy and regulation.

**Other sectors:** Technology (chips/cloud); Utilities (power); Discretionary (advertiser demand); Financials (ads/payments); Real Estate (towers/data centers); Industrials (equipment/construction).

**Classification note:** Alphabet and Meta are commonly categorized under GICS Communication Services rather than Information Technology.

## Cross-sector dependency map

The following is a **compact set of prominent links**, not an exhaustive list of commercial transactions. Each pair can have multiple directional edges.

| Origin sector | Linked sector | Mechanism |
| --- | --- | --- |
| Technology | Utilities | Electricity used by chip fabs and data centers |
| Technology | Materials | Copper, silicon, specialty chemicals |
| Technology | Industrials | Factory equipment, networking and cooling infrastructure |
| Technology | Communication Services | Chips, servers, cloud and network services |
| Health Care | Materials | Chemical ingredients, polymers, medical metals |
| Health Care | Technology | Diagnostics, software and medical electronics |
| Health Care | Real Estate | Hospitals and laboratory property |
| Financials | Real Estate | Mortgages, financing and refinancing |
| Financials | Discretionary | Credit cards and auto lending |
| Financials | Energy | Project financing, commodity hedging |
| Discretionary | Materials | Battery, apparel, automobile and housing inputs |
| Discretionary | Industrials | Logistics, vehicles and freight |
| Staples | Materials | Food packaging and fertilizer |
| Staples | Industrials | Warehousing, refrigerated trucking |
| Energy | Industrials | Diesel, marine and jet fuel |
| Energy | Utilities | Generation fuel |
| Energy | Materials | Petrochemical feedstocks and mining energy |
| Industrials | Utilities | Grid equipment and construction |
| Industrials | Real Estate | Warehouses, factories and construction |
| Utilities | Materials | Copper, aluminum, fuel and treatment chemicals |
| Real Estate | Materials | Cement, lumber, glass and steel |
| Communication Services | Technology | AI compute, networking and cloud infrastructure |
| Communication Services | Real Estate | Data centers, fiber facilities and towers |

**Graph traversal example:** `Oil → Refiner → Jet fuel → Airline → Operating margin → Equity return`.

## Shared economic factors

Create global driver nodes used across many sectors.

| Factor family | Candidate time series | High relevance |
| --- | --- | --- |
| Rates and credit | Fed policy rate, 2Y/10Y Treasuries, spreads, mortgages | Financials, Real Estate, Utilities, Discretionary |
| Inflation and labor | CPI, PPI, wages, unemployment, job openings | Health Care, Staples, Industrials |
| Activity | GDP, PMI, industrial production, retail sales | Industrials, Materials, Energy |
| FX | Broad USD index, currency baskets | Multinationals, Indonesian issuers |
| Energy | WTI, Brent, Henry Hub, diesel, jet fuel, coal | Energy, Transport, Utilities, Materials |
| Metals | Copper, aluminum, steel, nickel, gold | Materials, Technology, Industrials |
| Agriculture | Wheat, corn, soy, coffee, cocoa, sugar | Staples, Restaurants |
| Freight | Container rates, trucking rates, shipping volumes | Industrials, Retail, Staples |
| Climate | Temperature, drought, rainfall, hurricanes | Utilities, Agriculture, Insurance |
| Tech demand | Chip sales, cloud capex, data-center electricity | Technology, Communication, Utilities |
| Housing | Starts, permits, rents, occupancy | Real Estate, Financials, Materials |
| Regulation/events | Tariffs, approvals, product recalls, policies | Sector-dependent |
| Expectations | Earnings surprises, estimate revisions, options volatility | All sectors |

## US data sources

| Purpose | Starting source | Note |
|---|---|---|
| Company 10-K, 10-Q, 8-K, filing dates | [SEC EDGAR](https://www.sec.gov/edgar/search/) / [SEC APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | Verify supplier claims in filings; no comprehensive public supplier API |
| Stock prices and benchmark (^GSPC) | [yfinance](https://ranaroussi.github.io/yfinance/) | Research prototype; respect licensing and corporate actions |
| Interest rates, CPI, industrial production, commodity series | [FRED](https://fred.stlouisfed.org/) | Track observation date, release time and vintage |
| Petroleum, fuel, electricity and gas | [EIA API](https://www.eia.gov/opendata/) | Distinguish spot commodity price from company procurement price |
| Mineral production / reserves | [USGS Mineral Commodity Summaries](https://www.usgs.gov/centers/national-minerals-information-center/mineral-commodity-summaries) | Often annual |
| Commodity long histories | [World Bank Pink Sheet](https://www.worldbank.org/en/research/commodity-markets) | Availability differs by commodity |
| Industry-to-industry transactions | [BEA Input-Output Accounts](https://www.bea.gov/industry/input-output-accounts-data) | Industry-level estimates, not company contracts |
| US inflation and employment | [BLS](https://www.bls.gov/data/) | Publication date matters |
| Retail spending / trade | [US Census](https://www.census.gov/retail/) | Monthly series |
| Agriculture | [USDA NASS](https://www.nass.usda.gov/Data_and_Statistics/) | Crop-specific availability |
| Corporate sentiment | Timestamped releases / licensed news archives | Preserve URL, timestamp, and evidence |

## Data and graph schema

Use a graph for sparse entity relationships and columnar SQL tables for large time series.

```text
entities
  entity_id, entity_type, canonical_name, ticker, exchange,
  country, sector_code, external_id

relationships
  relationship_id, source_entity_id, target_entity_id,
  relationship_type, evidence_status, valid_from, valid_to,
  confidence, source_id, notes

evidence
  source_id, source_title, source_url, publisher,
  published_at, retrieved_at, page_or_excerpt, license

market_prices
  ticker, trade_date, exchange, open, high, low, close,
  volume, currency, adjusted_flag, provider

commodity_prices
  commodity_id, observation_date, benchmark, price,
  currency, unit, frequency, provider

financial_metrics
  company_id, period_end, filing_date, metric_name,
  amount, currency, accounting_standard, segment

macro_indicators
  indicator_id, observation_date, release_timestamp,
  vintage_timestamp, value, unit, provider

events
  event_id, announcement_timestamp, event_type,
  headline, source_id, region

event_entities
  event_id, entity_id, link_type, evidence_status
```

**Important design choice:** A `CORRELATED_WITH` relationship should include the estimation window, coefficient, lag, p-value or uncertainty interval, controls, and method. Do not treat statistical estimates as immutable business facts.

### Suggested seed CSV format

`entities.csv`

```csv
entity_id,entity_type,canonical_name,country
sector_energy,Sector,Energy,US
commodity_oil,Commodity,Crude oil,
industry_airlines,Industry,Airlines,US
```

`relationships.csv` (example **industry-level hypotheses**, not verified company contracts)

```csv
relationship_id,source_entity_id,target_entity_id,relationship_type,evidence_status,notes
r001,industry_airlines,commodity_oil,HAS_EXPOSURE_TO,structural_hypothesis,Exposure is primarily to refined jet fuel rather than spot crude
r002,sector_energy,commodity_oil,HAS_EXPOSURE_TO,structural_hypothesis,Producer and refiner sensitivities differ
```

## Analytical methodology

### A. Baseline exploration

1. Download stock and benchmark returns; normalize currencies and exchange dates.
2. Calculate returns, volatility, drawdowns and unusual trading volume.
3. Compare companies **to local sector and market benchmarks**, not only to each other.
4. Examine lead/lag correlations between each economic factor and returns or operating metrics.

### B. Market model

For stock \(i\) and local benchmark \(m\):

\[
R_{i,t}=\alpha_i+\beta_iR_{m,t}+\varepsilon_{i,t}
\]

Use estimated residuals as a starting point for unusual-movement detection, not as a conclusive explanation.

### C. Event studies

For a verified event at time \(t=0\), estimate the stock's baseline behavior using a prior window and evaluate abnormal returns around the event:

\[
AR_{i,t}=R_{i,t}-(\hat\alpha_i+\hat\beta_iR_{m,t})
\]

\[
CAR_i(a,b)=\sum_{t=a}^{b}AR_{i,t}
\]

Check announcement timestamps, trading-session alignment, overlapping events, and data that may have been revised after publication.

### D. Company operating exposure

Connect input prices to reported revenue, costs, and margin **only when the company has identifiable economic exposure**. Test lagged relationships and account for contracts, hedging, pass-through pricing, inventory, and segment mix. The relevant commodity spot price might differ from the firm's actual contract price.

### E. Evidence hierarchy

| Status | Meaning |
| --- | --- |
| `verified` | Directly supported by authoritative filing/contract/source |
| `supported_inference` | Plausible link based on documented mechanism but not direct contract |
| `statistical_association` | Estimated relationship with stated methodology |
| `hypothesis` | Research idea not yet validated |
| `disputed` | Contradictory evidence or uncertain status |

Avoid assigning a confidence percentage without a calibrated and validated scoring approach.

## Three-day US-only implementation sprint

### Day 1 — Graph foundation
- [ ] Create sector, company, commodity, product, source and event schemas.
- [ ] Import 11 GICS sector nodes plus 15–25 US company seed nodes.
- [ ] Enter sector-level relationships as **structural hypotheses**, never as verified direct supplier contracts.
- [ ] Find and cite a small number of verified company relationships in SEC filings.

### Day 2 — Time series and analysis
- [ ] Download and QA US stock prices and S&P 500 benchmark.
- [ ] Load crude oil, natural gas, copper and Treasury yields with explicit units.
- [ ] Calculate returns, volatility, abnormal moves and lagged correlations.
- [ ] Investigate 2–3 well-sourced company/event cases.

### Day 3 — Usable demo
- [ ] Add a searchable graph UI with nodes and edges.
- [ ] Clicking a company reveals its sourced relationships and time series.
- [ ] Add evidence panel (URL, relationship status, valid dates).
- [ ] Produce charts, methodology, limitations, and a demo README screenshot.

**Deliverables:** `data/us/entities.csv`, `data/us/relationships.csv`, `data/us/evidence.csv`, `data/us/prices.parquet`, dashboard, and analysis notebooks.

## US-only repository layout

```text
stocklens/
├── README.md                   # Active US project
├── README_INDONESIA.md         # Indonesia extension, not current sprint
├── data/
│   ├── us/
│   │   ├── entities.csv
│   │   ├── relationships.csv
│   │   ├── evidence.csv
│   │   └── prices.parquet
│   └── id/                     # Future work
├── src/
│   ├── graph_builder.py
│   ├── ingest_us.py
│   └── analyze_us.py
├── app/
│   └── Home.py
├── notebooks/
├── tests/
└── docs/
```

## Quality checks and limitations

- **Correlation is not causation.** A synchronized price change is not proof of a supplier relationship or economic impact.
- **Classification differences.** Map GICS and IDX-IC explicitly; avoid pretending they match perfectly.
- **Point-in-time correctness.** Use information publicly available *before* the measured return; honor publication time zones and trading calendars.
- **Market-hour mismatch.** The US exchanges have different hours and holidays; avoid same-date look-ahead bias.
- **Corporate actions.** Use split/dividend-adjusted market data consistently, while keeping the adjustment method visible.
- **Financial statement revisions.** Track filing dates, amendments, revisions, and reporting periods.
- **Supplier network incompleteness.** Many commercial relationships are confidential, indirect, short-lived, or never disclosed.
- **Economic pass-through.** Input-price changes may be hedged, contracted, inventoried, or passed on to customers.
- **Sector heterogeneity.** A sector is not a homogeneous production function; analyze sub-industries and company segments.
- **Data licensing.** Do not redistribute proprietary data or scraped content without permission.
- **Historical comparability.** Series availability and definitions differ by commodity and country. No blanket claim of data since 1900.
- **No trading guarantees.** The research is exploratory; not financial advice or an automated trading strategy.

## Future phase

Indonesia remains independent until its source and sector mappings have been validated. See [README_INDONESIA.md](README_INDONESIA.md). Cross-border spillover analysis should be a separate integration step, not part of this MVP.
