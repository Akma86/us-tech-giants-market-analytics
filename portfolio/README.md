# US Equity Atlas · Data Analyst Portfolio

An institutional-grade **US Equity Market Analytics & Econometric Portfolio** covering **10 flagship US mega-cap technology leaders** (`NVDA`, `AAPL`, `MSFT`, `GOOGL`, `AMZN`, `META`, `TSLA`, `AVGO`, `AMD`, `ORCL`) benchmarked against the **S&P 500 (`^GSPC`)**, **US 10-Year Treasury Yield (`^TNX`)**, and **CBOE Volatility Index (`^VIX`)** across **22,295 cleaned daily observations** (2020–2026).

Styled in the **US ATLAS Editorial Paper, Ink & Lime** design system (`Playfair Display`, `Manrope`, `DM Mono`).

---

## 🏛️ Analytical Scope (4 Core Chapters)

1. **Chapter I · Overview & Data Hygiene**:
   - Ingestion and cleaning of 22,295 rows with **0 duplicates and 0 missing values**.
   - Risk-Return Scatter plot (Annualized Volatility vs Annualized Return with S&P 500 benchmark crosshair).
   - Dynamic 13×13 Pearson correlation matrix with sector/role filters.
   - Transparent Data Hygiene Audit table verifying ticker coverage, inception, clean row counts, and split adjustments.

2. **Chapter II · Stock Explorer & Feature Lab**:
   - Interactive ticker switcher across all 10 stocks + benchmarks.
   - Dynamic SVG Area Charts with gradient fills and endpoint markers.
   - Multi-metric view: *Raw Adjusted Price*, *Daily Return*, *Log Return*, *30D Rolling Volatility*, *20D Volume Z-Score*, and *Market-Adjusted Residual*.
   - Multi-horizon switcher: `1Y`, `3Y`, `5Y`, and `MAX`.

3. **Chapter III · Market-Adjusted CAPM & Macro Factor Regimes**:
   - Closed-form OLS excess-return Capital Asset Pricing Model ($R_{i,t}^e = \alpha_i + \beta_i R_{m,t}^e + \varepsilon_{i,t}$).
   - Alpha ($\alpha$) vs Beta ($\beta$) scatter plot and cumulative log-compounded residual index ($\Pi (1 + \varepsilon_{i,t})$).
   - Macroeconomic regime analysis evaluating the impact of interest rates (`^TNX`) and volatility (`^VIX`) across 3 distinct macroeconomic cycles (Zero-Rate Stimulus, Fed Tightening, AI Capex Supercycle).

4. **Chapter IV · 10 Catalysts, Movement Spikes & Mathematical Proofs**:
   - Ranked unusual-movement spike scanner (>3σ daily return & volume spikes).
   - 10 verified event studies cross-referenced with primary **SEC Form 10-K/8-K** filings and Federal Reserve FOMC rate decisions.
   - **Analytical Mathematical Spot-Check Audit Table**: Closed-form verification proving **`0.000000` numerical discrepancy** between raw inputs and pipeline outputs.

---

## 🚀 How to Run Locally

This portfolio website is 100% static and requires no backend server.

### Option 1: Python HTTP Server
```bash
python -m http.server 3000 --directory portfolio
```
Then visit `http://localhost:3000` in your web browser.

### Option 2: Node.js Serve
```bash
npx serve portfolio
```

---

## ☁️ Deployment to Vercel

To deploy this portfolio to Vercel:
1. In your Vercel Dashboard, import the repository `us-tech-giants-market-analytics`.
2. Under **Project Settings > General**:
   - Set **Root Directory** to `portfolio`.
3. Under **Build and Output Settings**:
   - Framework Preset: **Other**
   - Build Command: *(leave blank)*
   - Output Directory: `.`
4. Click **Deploy**. Vercel will deploy the site in ~3 seconds.

---

## 🔗 Related Applications

- **StockLens Deep Quant Terminal (`stocklens/`)**: Interactive quantitative analysis platform covering 2,200+ US equities, SEC 10-K financial knowledge graph, lead-lag transmission paths, and AI bubble contagion radar. Run locally with `python stocklens/market_server.py --port 8000`.

