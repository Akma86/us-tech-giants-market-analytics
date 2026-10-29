# 📊 US Equity Atlas · Data Analyst Portfolio Edition

**10 US Mega-Cap Leaders (`AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, AVGO, AMD, ORCL`) × S&P 500 (`^GSPC`) × US 10-Year Treasury Yield (`^TNX`) × CBOE Volatility Index (`^VIX`)**

---

## 🎯 Project Overview & 3-Day Syllabus Checklist

This folder is a self-contained, Vercel-ready **US Equity Data Analyst Portfolio** and **Streamlit Dashboard** styled in the signature **US ATLAS Editorial Paper, Ink & Lime Theme** (`#f2f1eb` paper, `#18201e` ink, `#b8f54a` lime, `Playfair Display` + `Manrope` + `DM Mono`). It covers **22,295 cleaned daily observations** (`2020-01-02` to `2026-10-28`):

### ✅ Day 1 — Data Engineering + Exploratory Data Analysis (4/4 Complete)
- **[x] Historical US prices:** 10 US mega-cap equities (`AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, AVGO, AMD, ORCL`) + `S&P 500 (^GSPC)` + `US 10Y Treasury Yield (^TNX)` + `CBOE VIX (^VIX)`.
- **[x] Clean and validate data:** Official NYSE/NASDAQ calendar alignment (`1,715` sessions), duplicate removal (`0` duplicates), missing-value hygiene, and stock-split adjustments (`NVDA` 40× cumulative splits, `TSLA` 15× cumulative splits, `AMZN`/`GOOGL` 20:1 splits, `AVGO` 10:1 split, `AAPL` 4:1 split).
- **[x] Feature engineering:** Daily & log returns, cumulative nominal & rate-adjusted excess return indices, 30-day rolling annualized volatility, 20-day volume anomaly Z-scores, and peak-to-trough drawdowns.
- **[x] Exploratory analysis:** Multi-stock cumulative growth trajectories, Risk vs Return scatter plot (bubble = Sharpe ratio), and 13×13 correlation matrix.

### ✅ Day 2 — US Market Intelligence & Econometrics (4/4 Complete)
- **[x] Market-adjusted returns:** Single-Index CAPM decomposition ($R_{i,t} = \alpha_i + \beta_i R_{m,t} + \epsilon_{i,t}$) vs `S&P 500 (^GSPC)` isolating systematic market Beta ($\beta$) from firm-specific idiosyncratic residuals ($\epsilon_{i,t}$).
- **[x] Macroeconomic analysis:** US 10-Year Treasury Yield (`^TNX`) & CBOE Volatility (`^VIX`) regime relationships with the S&P 500 and the 10 US equities, including 60-day rolling correlations and yield-spike / high-VIX conditional returns.
- **[x] Unusual-movement detection:** Automated Z-score scanner ranking extreme return tail shocks ($|Z_{\text{ret}}| \ge 3.1\sigma$) and institutional volume spikes ($Z_{\text{vol}} \ge 3.4\sigma$).
- **[x] Event investigation:** 10 manually verified US market catalysts (SEC Form 10-K/8-K earnings shocks, stock splits, CPI inflation shocks & Federal Reserve FOMC actions) with exact $T_0$ abnormal return and 5-day Cumulative Abnormal Return (CAR).

### ✅ Day 3 — Interactive Dashboard + Validation + Deployment (4/4 Complete)
- **[x] Interactive Dashboard (`Overview`, `Explorer`, `Comparison`, `Events`):** Provided both as a zero-latency **Vercel Web App (`index.html` + `assets/app.js`)** and a **Python Streamlit App (`streamlit_app.py`)**.
- **[x] Integrate processed datasets:** Interactive ticker filtering, benchmark/peer comparison, return basis toggle (`Nominal` vs `Excess Return over 10Y Treasury`), and downloadable cleaned CSV (`data/us_market_clean.csv`).
- **[x] Validate analytical results:** 6 closed-form mathematical spot-checks proving `0.000000` discrepancy between manual calculations and pipeline outputs.
- **[x] Two-Section Architecture:**
  - **Section 1 (Live & Complete):** US Equity Data Analyst Portfolio (Day 1–3).
  - **Section 2 (Phase 2 Landing Page):** *Deep Quant & AI Bubble Contagion Terminal (Under Active Development / Coming Soon)* previewing the 2,228-stock SQLite engine, SEC 10-K Supply-Chain Graph, and Lead-Lag Contagion Lab.
