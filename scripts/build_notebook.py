"""
Script: build_notebook.py
Description: Generates the introductory Jupyter notebook for dataset inspection and EDA,
             and executes it to pre-render tables, statistics, and visualizations.
"""

from pathlib import Path
import nbformat as nbf
from nbclient import NotebookClient


def create_inspection_notebook():
    nb = nbf.v4.new_notebook()
    nb.metadata = {
        "language_info": {
            "name": "python",
            "version": "3.12"
        },
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        }
    }

    cells = []

    # 1. Title & Introduction
    cells.append(nbf.v4.new_markdown_cell("""# 📊 US Tech Giants (Big 5) — Dataset Inspection & Exploratory Data Analysis (EDA)

**Author:** Akmal Yaasir Fauzaan  
**Project:** Historical Risk-Return Analysis of US Stock Market Leaders  
**Target Equities:** Apple (`AAPL`), Microsoft (`MSFT`), NVIDIA (`NVDA`), Alphabet (`GOOGL`), Amazon (`AMZN`)  
**Data Scope:** Inception (IPO date) through October 2026  

---

## 🎯 Purpose of This Notebook
As an initial step in our financial data analytics portfolio, this notebook performs a thorough **data inspection** and **exploratory data analysis (EDA)** on the historical stock market records of five major US technology enterprises.

### What You Will Learn in This Inspection:
1. **Dataset Structure & File Architecture:** Understanding what tabular stock market data looks like, what file formats are used, and how trading dates are recorded.
2. **Data Dictionary & Column Semantics:** Demystifying financial terms such as *Open, High, Low, Close, Adjusted Close, Volume, Dividends,* and *Stock Splits*.
3. **Data Quality & Integrity Assessment:** Checking for missing values, duplicate entries, data type mismatches, and date coverage.
4. **IPO Timelines & Growth Trajectories:** Examining the different inception eras (from Apple's 1980 IPO to Google's 2004 IPO) and how stock splits impact raw share prices.
5. **Preliminary Risk & Return Signals:** Calculating daily percentage returns, volatility distributions, and multi-asset correlation matrices.
"""))

    # 2. Imports and Environment Setup
    cells.append(nbf.v4.new_markdown_cell("""## 1. Environment & Library Setup
We load standard Python data science libraries:
* **`pandas`**: High-performance tabular data manipulation and time series indexing.
* **`numpy`**: Fast vectorized numerical computations.
* **`matplotlib.pyplot` & `seaborn`**: Professional aesthetic plotting.
"""))

    cells.append(nbf.v4.new_code_cell("""import os
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Configure display and plot styling
pd.set_option('display.max_columns', None)
pd.set_option('display.float_format', lambda x: f'{x:,.4f}')

sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams['font.sans-serif'] = 'Segoe UI'
plt.rcParams['figure.dpi'] = 120
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['axes.titleweight'] = 'bold'
plt.rcParams['axes.labelsize'] = 11

print("Environment libraries successfully loaded.")
"""))

    # 3. Data Loading
    cells.append(nbf.v4.new_markdown_cell("""## 2. Dataset Loading & File System Architecture

Our repository organizes data systematically:
* `data/raw/`: Contains original, unmodified CSV files extracted directly via Yahoo Finance (`AAPL.csv`, `MSFT.csv`, `NVDA.csv`, `GOOGL.csv`, `AMZN.csv`).
* `data/raw/us_tech_giants_daily_history.csv`: A consolidated master dataset that merges all 5 equities with a standardized schema for streamlined multi-asset analysis.

Let's load the consolidated dataset into a Pandas DataFrame.
"""))

    cells.append(nbf.v4.new_code_cell("""# Resolve project paths dynamically
data_path = Path('../data/raw/us_tech_giants_daily_history.csv')
if not data_path.exists():
    data_path = Path('data/raw/us_tech_giants_daily_history.csv')

df = pd.read_csv(data_path)
df['Date'] = pd.to_datetime(df['Date'])

print(f"Total Rows (Observations): {len(df):,}")
print(f"Total Columns (Variables): {df.shape[1]}")
print(f"Unique Tickers: {df['Ticker'].unique().tolist()}")
"""))

    # 4. Preview Data
    cells.append(nbf.v4.new_markdown_cell("""### Preview First and Last Records
Checking both `.head()` and `.tail()` ensures the dates are properly sorted and that historical records begin at the earliest IPOs.
"""))

    cells.append(nbf.v4.new_code_cell("""print("--- FIRST 5 ROWS (Earliest records - Apple IPO in Dec 1980) ---")
display(df.head())

print("\\n--- LAST 5 ROWS (Most recent trading day) ---")
display(df.tail())
"""))

    # 5. Data Dictionary & Types
    cells.append(nbf.v4.new_markdown_cell("""## 3. Data Dictionary & Column Types

What type of file is this dataset?
* **File Format:** CSV (Comma-Separated Values), plain-text tabular structure.
* **Granularity:** Daily trading frequency. Note that stock exchanges (NASDAQ & NYSE) are **closed on weekends and federal holidays**, meaning dates are non-continuous calendar days but continuous *trading days*.

| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| **`Date`** | `datetime64[ns]` | Trading session date (YYYY-MM-DD). |
| **`Ticker`** | `object (str)` | Stock ticker symbol (`AAPL`, `MSFT`, `NVDA`, `GOOGL`, `AMZN`). |
| **`Company`** | `object (str)` | Full legal entity name. |
| **`Sector`** | `object (str)` | GICS economic sector classification. |
| **`Open`** | `float64` | Stock price at market opening bell (9:30 AM EST). |
| **`High`** | `float64` | Highest transaction price recorded during the trading day. |
| **`Low`** | `float64` | Lowest transaction price recorded during the trading day. |
| **`Close`** | `float64` | Unadjusted closing price at the final bell (4:00 PM EST). |
| **`Adj Close`** | `float64` | **Adjusted Close Price**: Price amended for corporate actions (stock splits and dividends). **Essential for risk & return modeling.** |
| **`Volume`** | `int64` | Number of shares exchanged between buyers and sellers. |
| **`Dividends`** | `float64` | Cash dividend payment per share on ex-dividend dates. |
| **`Stock Splits`**| `float64` | Multiplier for stock split events (e.g., 2.0 for 2-for-1 split). |

Let's check `df.info()` to verify system memory usage and column storage types:
"""))

    cells.append(nbf.v4.new_code_cell("""df.info()
"""))

    # 6. Data Integrity & Missing Values
    cells.append(nbf.v4.new_markdown_cell("""## 4. Data Quality & Integrity Audit

A critical responsibility of a data analyst before performing quantitative modeling is validating data cleanliness:
1. **Missing / Null Values:** Are there gaps in price reporting?
2. **Duplicate Records:** Are there multiple rows for the same `(Date, Ticker)` pair?
3. **Logic Sanity Checks:** Is `High >= Low`? Is `Volume >= 0`?
"""))

    cells.append(nbf.v4.new_code_cell("""# 1. Null Value Audit
null_summary = pd.DataFrame({
    'Null_Count': df.isnull().sum(),
    'Null_Percentage': (df.isnull().sum() / len(df)) * 100
})

# 2. Duplicate Check
duplicate_rows = df.duplicated(subset=['Date', 'Ticker']).sum()

# 3. Logic Sanity Check (High should always be >= Low and Volume >= 0)
invalid_prices = (df['High'] < df['Low']).sum()
negative_volume = (df['Volume'] < 0).sum()

print("=== DATA INTEGRITY AUDIT RESULTS ===")
print(f"Total Rows Audited: {len(df):,}")
print(f"Duplicate (Date, Ticker) Pairs: {duplicate_rows}")
print(f"Anomalous Price Rows (High < Low): {invalid_prices}")
print(f"Negative Volume Records: {negative_volume}\\n")
print("Null Values Per Column:")
display(null_summary)
"""))

    # 7. IPO Coverage & Summary Stats
    cells.append(nbf.v4.new_markdown_cell("""## 5. Timeline Coverage & Inception (IPO) Dates

Each of these companies went public during a distinct technological era:
* **Apple (`AAPL`):** Dec 12, 1980 (Personal computing revolution)
* **Microsoft (`MSFT`):** Mar 13, 1986 (Operating system dominance)
* **Amazon (`AMZN`):** May 15, 1997 (Early e-commerce & dot-com boom)
* **NVIDIA (`NVDA`):** Jan 22, 1999 (GPU graphics & 3D gaming acceleration)
* **Alphabet / Google (`GOOGL`):** Aug 19, 2004 (Search engine & mobile era)

Let's inspect the exact date span, total trading sessions, and earliest vs. current prices for each asset.
"""))

    cells.append(nbf.v4.new_code_cell("""timeline_summary = df.groupby('Ticker').agg(
    Company=('Company', 'first'),
    First_Trading_Day=('Date', 'min'),
    Latest_Trading_Day=('Date', 'max'),
    Trading_Sessions=('Date', 'count'),
    Earliest_Unadj_Close=('Close', 'first'),
    Earliest_Adj_Close=('Adj Close', 'first'),
    Latest_Close=('Close', 'last'),
    Latest_Adj_Close=('Adj Close', 'last')
).reset_index()

display(timeline_summary)
"""))

    # 8. Understanding Stock Splits & Adjusted Close
    cells.append(nbf.v4.new_markdown_cell("""### 💡 Financial Insight: Raw Close vs. Adjusted Close
Notice above that for **AAPL**, the earliest `Close` was **$22.00**, but the earliest `Adj Close` was **$0.0988**! Why?

> **Stock Splits:** When a stock becomes very expensive, companies split shares (e.g., 2-for-1 or 10-for-1) so smaller investors can afford them. The company's total market value doesn't change, but each share price is divided by the split ratio while the number of shares increases proportionally.
> 
> **Adjusted Close (`Adj Close`)** backward-adjusts all historical prices for all historical stock splits and cash dividend payouts.  
> **Rule for Analysts:** **ALWAYS use `Adj Close` when calculating returns and volatility**, otherwise stock splits will look like artificial 50% or 90% crashes in raw price!

Let's inspect all stock split events that occurred across these 5 companies.
"""))

    cells.append(nbf.v4.new_code_cell("""splits_df = df[df['Stock Splits'] > 0][['Date', 'Ticker', 'Company', 'Close', 'Stock Splits']].sort_values(by=['Ticker', 'Date'])
print(f"Total Stock Split Events Recorded: {len(splits_df)}")
display(splits_df)
"""))

    # 9. Exploratory Visualizations: Price Trends
    cells.append(nbf.v4.new_markdown_cell("""## 6. Exploratory Data Visualizations

### 6.1 Historical Price Trajectories: Linear vs. Logarithmic Scales
* **Linear Scale:** Shows absolute dollar value growth, highlighting recent exponential rallies.
* **Logarithmic Scale:** Compresses large dollar values, allowing equal percentage gains (e.g. 10x growth) to look equal across all historical decades.
"""))

    cells.append(nbf.v4.new_code_cell("""fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# Plot 1: Linear Scale
for ticker in df['Ticker'].unique():
    subset = df[df['Ticker'] == ticker]
    axes[0].plot(subset['Date'], subset['Adj Close'], label=ticker, linewidth=1.5)

axes[0].set_title("Adjusted Close Price Trajectory (Linear Scale)")
axes[0].set_xlabel("Year")
axes[0].set_ylabel("Price in USD ($)")
axes[0].legend(loc="upper left")
axes[0].grid(True, linestyle="--", alpha=0.5)

# Plot 2: Logarithmic Scale
for ticker in df['Ticker'].unique():
    subset = df[df['Ticker'] == ticker]
    axes[1].plot(subset['Date'], subset['Adj Close'], label=ticker, linewidth=1.5)

axes[1].set_yscale('log')
axes[1].set_title("Adjusted Close Price Trajectory (Logarithmic Scale)")
axes[1].set_xlabel("Year")
axes[1].set_ylabel("Price in USD ($) - Log Scale")
axes[1].legend(loc="upper left")
axes[1].grid(True, linestyle="--", alpha=0.5)

plt.tight_layout()
output_fig_path = Path('../reports/figures/01_price_trajectories.png')
if output_fig_path.parent.exists():
    plt.savefig(output_fig_path, dpi=200)
plt.show()
"""))

    # 10. Trading Volume Analysis
    cells.append(nbf.v4.new_markdown_cell("""### 6.2 Daily Trading Volume & Liquidity Trends
Volume indicates the liquidity and market participation of an equity. High-volume periods often coincide with major earnings announcements, product releases, or market stress events (such as the 2008 Financial Crisis or the 2020 pandemic).
"""))

    cells.append(nbf.v4.new_code_cell("""plt.figure(figsize=(15, 6))

for ticker in df['Ticker'].unique():
    subset = df[df['Ticker'] == ticker]
    # Apply a 30-day moving average to smooth extreme daily spikes
    smoothed_volume = subset['Volume'].rolling(window=30).mean()
    plt.plot(subset['Date'], smoothed_volume / 1e6, label=f"{ticker} (30D MA)", alpha=0.8, linewidth=1.2)

plt.title("Daily Trading Volume (30-Day Moving Average in Millions of Shares)")
plt.xlabel("Year")
plt.ylabel("Volume (Millions of Shares)")
plt.legend(loc="upper left")
plt.grid(True, linestyle="--", alpha=0.5)
plt.tight_layout()

vol_fig_path = Path('../reports/figures/02_trading_volume_trends.png')
if vol_fig_path.parent.exists():
    plt.savefig(vol_fig_path, dpi=200)
plt.show()
"""))

    # 11. Daily Returns Calculation
    cells.append(nbf.v4.new_markdown_cell("""## 7. Preliminary Return & Risk Metric Calculation

In financial risk analysis, raw prices are non-stationary. Instead, we analyze **Daily Percentage Returns**:

$$R_t = \\frac{P_t - P_{t-1}}{P_{t-1}} = \\frac{P_t}{P_{t-1}} - 1$$

Where $P_t$ is the `Adj Close` price on trading day $t$.
"""))

    cells.append(nbf.v4.new_code_cell("""# Calculate daily percentage returns grouped by Ticker
df['Daily_Return'] = df.groupby('Ticker')['Adj Close'].pct_change()

# Display sample returns
df[['Date', 'Ticker', 'Adj Close', 'Daily_Return']].dropna().head(10)
"""))

    # 12. Return Distribution & Volatility
    cells.append(nbf.v4.new_markdown_cell("""### 7.1 Daily Return Distribution & Volatility Metrics
We compute standard financial statistics:
* **Mean Daily Return:** Average day-to-day percentage gain.
* **Daily Volatility (Std Dev):** Measure of market dispersion/risk.
* **Annualized Volatility:** $\\sigma_{\\text{daily}} \\times \\sqrt{252}$ (252 is the number of US trading days per year).
* **Skewness:** Asymmetry of the return distribution.
* **Kurtosis:** Tendency toward "fat tails" (extreme outliers / crash risks).
"""))

    cells.append(nbf.v4.new_code_cell("""return_stats = df.groupby('Ticker')['Daily_Return'].agg(
    Count='count',
    Mean_Daily_Return='mean',
    Daily_Volatility='std',
    Min_Return='min',
    Max_Return='max',
    Skewness='skew',
    Kurtosis=lambda x: x.kurtosis()
).reset_index()

# Annualize metrics assuming 252 trading days per year
return_stats['Annualized_Return_Approx'] = return_stats['Mean_Daily_Return'] * 252
return_stats['Annualized_Volatility'] = return_stats['Daily_Volatility'] * np.sqrt(252)

display(return_stats)
"""))

    # 13. Return Distribution Visualization
    cells.append(nbf.v4.new_markdown_cell("""### 7.2 Return Distribution Histograms
Notice the bell-curve shape centered near 0% with extended tails representing black swan events and earnings surprises.
"""))

    cells.append(nbf.v4.new_code_cell("""plt.figure(figsize=(14, 6))

for ticker in df['Ticker'].unique():
    subset = df[df['Ticker'] == ticker]['Daily_Return'].dropna()
    # Filter within -10% and +10% for clear visualization
    sns.kdeplot(subset, label=f"{ticker} ($\\sigma$={subset.std():.3f})", linewidth=1.8)

plt.title("Probability Density Distribution of Daily Returns (Kernel Density Estimation)")
plt.xlabel("Daily Return (Decimal)")
plt.ylabel("Density")
plt.xlim(-0.10, 0.10)
plt.legend(loc="upper right")
plt.grid(True, linestyle="--", alpha=0.5)
plt.tight_layout()

dist_fig_path = Path('../reports/figures/03_return_distributions.png')
if dist_fig_path.parent.exists():
    plt.savefig(dist_fig_path, dpi=200)
plt.show()
"""))

    # 14. Correlation Matrix
    cells.append(nbf.v4.new_markdown_cell("""## 8. Multi-Asset Correlation Analysis

In modern portfolio management (Markowitz Modern Portfolio Theory), **correlation** between assets is fundamental. Lower correlation allows an investor to diversify risk without sacrificing expected return.

To compute this accurately, we pivot the daily returns into a matrix where each column represents one stock, filtering to the overlapping period (since Google's IPO in 2004).
"""))

    cells.append(nbf.v4.new_code_cell("""# Pivot daily returns into date-indexed multi-column format
returns_pivot = df.pivot(index='Date', columns='Ticker', values='Daily_Return')

# Drop rows where any stock has NaN (focusing on the shared period from 2004 onwards)
shared_returns = returns_pivot.dropna()

# Compute Pearson correlation matrix
corr_matrix = shared_returns.corr()

plt.figure(figsize=(8, 6))
sns.heatmap(corr_matrix, annot=True, cmap="coolwarm", vmin=0.3, vmax=0.9, fmt=".3f", linewidths=1)
plt.title(f"Correlation Matrix of Daily Returns\\n(Overlapping Period: {shared_returns.index.min().strftime('%Y-%m-%d')} to {shared_returns.index.max().strftime('%Y-%m-%d')})")
plt.tight_layout()

corr_fig_path = Path('../reports/figures/04_correlation_matrix.png')
if corr_fig_path.parent.exists():
    plt.savefig(corr_fig_path, dpi=200)
plt.show()
"""))

    # 15. Key Takeaways and Roadmap
    cells.append(nbf.v4.new_markdown_cell("""## 9. Key Findings & Analysis Roadmap

### Summary of Dataset Inspection:
1. **Pristine Data Quality:** 0 missing values across 41,762 trading observations spanning over 40+ years of tech market history.
2. **Temporal Breadth:** AAPL begins in 1980, MSFT in 1986, AMZN in 1997, NVDA in 1999, and GOOGL in 2004.
3. **Price Adjustments:** Corporate stock splits (e.g., Apple's 7-for-1 in 2014, NVIDIA's 10-for-1 in 2024) make `Adj Close` the strictly required metric for return calculations.
4. **Correlation Insight:** All five tech giants exhibit positive moderate-to-high correlation (~0.45 to ~0.65), reflecting shared systemic exposure to technological and macroeconomic cycles.

### Next Steps in This Project Portfolio:
* **Notebook 02:** Cumulative Returns, Compound Annual Growth Rate (CAGR), and Maximum Drawdown (MDD) during crisis periods (Dot-com Crash, 2008 GFC, 2020 COVID shock, 2022 Tech correction).
* **Notebook 03:** Risk-Adjusted Performance: Sharpe Ratio, Sortino Ratio, and Value at Risk (VaR).
* **Notebook 04:** Modern Portfolio Theory (MPT) & Monte Carlo Simulation: Constructing the **Markowitz Efficient Frontier** and optimal portfolio weightings.
"""))

    nb.cells = cells
    return nb


def build_and_save_notebook():
    notebook_dir = Path("d:/MAIN DATA/Documents/Untuk Portofolio Github/Risk Return US Stock/notebooks")
    notebook_dir.mkdir(parents=True, exist_ok=True)
    nb_path = notebook_dir / "01_dataset_inspection_and_eda.ipynb"

    print(f"Creating notebook structure at {nb_path}...")
    nb = create_inspection_notebook()

    with open(nb_path, "w", encoding="utf-8") as f:
        nbf.write(nb, f)
    print("Notebook JSON created.")

    print("Executing notebook to pre-render outputs and figures...")
    client = NotebookClient(nb, timeout=600, kernel_name="python3", resources={'metadata': {'path': str(notebook_dir)}})
    client.execute()

    with open(nb_path, "w", encoding="utf-8") as f:
        nbf.write(nb, f)
    print("Notebook successfully executed and saved with all outputs rendered!")


if __name__ == "__main__":
    build_and_save_notebook()
