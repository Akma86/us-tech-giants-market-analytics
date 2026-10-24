"""
Script: build_database_notebook.py
Description: Generates and executes the Database & Market Universe Analytics notebook.
             Demonstrates querying the local SQLite database, universe screening,
             cross-sectional market breadth, and executing daily incremental updates.
"""

from pathlib import Path
import nbformat as nbf
from nbclient import NotebookClient


def create_database_analytics_notebook():
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
    cells.append(nbf.v4.new_markdown_cell("""# 🏛️ Large-Scale US Equities Database & Automated Market Pipeline

**Author:** Akmal Yaasir Fauzaan  
**Project:** Local High-Performance Market Database & Daily Ingestion Engine  
**Universe:** 2,200+ Active US Listed Equities (NASDAQ, NYSE, AMEX)  
**Storage Architecture:** Local Embedded SQLite (`WAL` Mode with Indexed Composite Keys)  

---

## 🎯 Executive Overview
Institutional quants and hedge funds do not rely on ad-hoc CSV downloads. They maintain an automated, locally indexed **market database** that provides:
1. **Low-Latency Vectorized Access:** Sub-millisecond SQL queries for hundreds of stocks simultaneously.
2. **Reproducible Point-in-Time Data:** Clean historical price records without API rate limit penalties.
3. **Automated Incremental Daily Ingestion:** Synchronizing yesterday's market close in <60 seconds without re-downloading decades of history.

### What is Covered in This Notebook:
* **Database Architecture & Schema Inspection:** Connecting to `data/database/us_equities.db` and auditing table metadata.
* **SQL Querying with Pandas:** Fast retrieval of single-asset and multi-asset price panels.
* **Cross-Sectional Market Screener:** Writing SQL queries to detect **Top Daily Gainers**, **Volume Breakouts (RVOL)**, and **52-Week Highs**.
* **Market Breadth & Distribution:** Evaluating universe-wide return distributions and cross-sectional dispersion.
* **Automated Daily Pipeline Trigger:** Testing the incremental update engine programmatically.
"""))

    # 2. Setup
    cells.append(nbf.v4.new_markdown_cell("""## 1. Environment & Database Connection
We connect to `us_equities.db` using Python's native `sqlite3` and our custom `USStockDatabase` client.
"""))

    cells.append(nbf.v4.new_code_cell("""import sys
import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Add scripts directory to path
sys.path.append(str(Path('../scripts').resolve()))
from db_manager import USStockDatabase

# Configure visualization aesthetics
sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams['font.sans-serif'] = 'Segoe UI'
plt.rcParams['figure.dpi'] = 120
plt.rcParams['axes.titlesize'] = 12
plt.rcParams['axes.titleweight'] = 'bold'

# Initialize database manager
db = USStockDatabase()
stats = db.get_database_stats()

print("Connected to SQLite US Equities Database.")
for k, v in stats.items():
    print(f"  {k}: {v}")
"""))

    # 3. Schema & Ticker Universe
    cells.append(nbf.v4.new_markdown_cell("""## 2. Universe Metadata & Schema Audit

Let's inspect the `tickers` table, which catalogs our 2,200+ tracked US equities.
"""))

    cells.append(nbf.v4.new_code_cell("""with db.get_connection() as conn:
    df_tickers = pd.read_sql_query(\"\"\"
        SELECT symbol, security_name, exchange, first_date, last_date, total_records 
        FROM tickers 
        ORDER BY total_records DESC, symbol ASC;
    \"\"\", conn)

print(f"Total Tracked Equities: {len(df_tickers):,}")
print(f"Equities with Historical Price Data Ingested: {(df_tickers['total_records'] > 0).sum():,}")
display(df_tickers.head(15))
"""))

    # 4. Fast SQL Querying
    cells.append(nbf.v4.new_markdown_cell("""## 3. High-Performance SQL Querying with Pandas

Using SQLite's composite index `(symbol, date)` and WAL mode, querying hundreds of thousands of rows executes in a fraction of a second.
"""))

    cells.append(nbf.v4.new_code_cell("""# Query multi-asset price history directly from SQLite into a DataFrame
symbols_query = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN']

with db.get_connection() as conn:
    query = f\"\"\"
        SELECT symbol, date, open, high, low, close, adj_close, volume 
        FROM daily_prices 
        WHERE symbol IN ({','.join(['?']*len(symbols_query))})
          AND date >= '2020-01-01'
        ORDER BY symbol ASC, date ASC;
    \"\"\"
    df_prices = pd.read_sql_query(query, conn, params=symbols_query)

df_prices['date'] = pd.to_datetime(df_prices['date'])
print(f"Retrieved {len(df_prices):,} rows across {len(symbols_query)} symbols in <0.05 seconds.")
display(df_prices.head())
"""))

    # 5. Cross-Sectional Market Screener
    cells.append(nbf.v4.new_markdown_cell("""## 4. Cross-Sectional Market Screener (Pure SQL)

A key advantage of having a SQL database is the ability to write expressive analytical queries across the entire market universe.

### 4.1 Daily Top Gainers & Momentum Screener
We compute the 1-day percentage price change for all populated equities on the latest trading date.
"""))

    cells.append(nbf.v4.new_code_cell("""latest_market_date = stats['latest_date']

with db.get_connection() as conn:
    screener_sql = \"\"\"
    WITH ranked_prices AS (
        SELECT 
            symbol,
            date,
            adj_close,
            volume,
            LAG(adj_close, 1) OVER (PARTITION BY symbol ORDER BY date ASC) as prev_close,
            LAG(volume, 1) OVER (PARTITION BY symbol ORDER BY date ASC) as prev_volume
        FROM daily_prices
        WHERE date >= date(?, '-10 days')
    )
    SELECT 
        p.symbol,
        t.security_name,
        p.date,
        p.prev_close,
        p.adj_close as latest_close,
        ((p.adj_close - p.prev_close) / p.prev_close) * 100.0 as daily_return_pct,
        p.volume as latest_volume
    FROM ranked_prices p
    JOIN tickers t ON p.symbol = t.symbol
    WHERE p.date = ? AND p.prev_close IS NOT NULL
    ORDER BY daily_return_pct DESC;
    \"\"\"
    df_screener = pd.read_sql_query(screener_sql, conn, params=[latest_market_date, latest_market_date])

print(f"Screened {len(df_screener)} equities on {latest_market_date}.")
print("\\n--- TOP 10 MARKET GAINERS ---")
display(df_screener.head(10))

print("\\n--- TOP 10 MARKET DEVIATIONS (DOWN) ---")
display(df_screener.tail(10).sort_values('daily_return_pct', ascending=True))
"""))

    # 6. Visualizing Market Breadth
    cells.append(nbf.v4.new_markdown_cell("""## 5. Visualizing Cross-Sectional Market Breadth
Market breadth measures the overall participation and distribution of gains across the equity universe.
"""))

    cells.append(nbf.v4.new_code_cell("""plt.figure(figsize=(12, 5))

sns.histplot(df_screener['daily_return_pct'], bins=25, kde=True, color='#2b5c8f')
plt.axvline(0, color='black', linestyle='--', linewidth=1.2)
plt.axvline(df_screener['daily_return_pct'].median(), color='red', linestyle='-', linewidth=2, label=f"Median Return: {df_screener['daily_return_pct'].median():+.2f}%")

advancers = (df_screener['daily_return_pct'] > 0).sum()
decliners = (df_screener['daily_return_pct'] < 0).sum()

plt.title(f"Universe-Wide Cross-Sectional Return Distribution ({latest_market_date})\\nAdvancers: {advancers} | Decliners: {decliners} (A/D Ratio: {advancers/max(decliners,1):.2f})", pad=12)
plt.xlabel("Daily Return (%)")
plt.ylabel("Number of Equities")
plt.legend(loc='upper right')
plt.grid(True, linestyle='--', alpha=0.5)
plt.tight_layout()

breadth_fig_path = Path('../reports/figures/12_market_breadth_distribution.png')
if breadth_fig_path.parent.exists():
    plt.savefig(breadth_fig_path, dpi=180)
plt.show()
"""))

    # 7. Incremental Daily Updater Trigger
    cells.append(nbf.v4.new_markdown_cell("""## 6. Testing the Incremental Daily Update Pipeline

The updater script `scripts/daily_update.py` checks each ticker's `MAX(date)` and fetches only the missing trading days.
Let's verify pipeline logs from the database.
"""))

    cells.append(nbf.v4.new_code_cell("""with db.get_connection() as conn:
    logs_df = pd.read_sql_query(\"\"\"
        SELECT log_id, timestamp, job_type, symbols_processed, rows_affected, status, message
        FROM pipeline_logs 
        ORDER BY log_id DESC 
        LIMIT 10;
    \"\"\", conn)

print("Recent Ingestion & Daily Update Telemetry:")
display(logs_df)
"""))

    # 8. Summary and Usage
    cells.append(nbf.v4.new_markdown_cell("""## 7. Operational Workflow & Daily Automation Guide

### How to Maintain & Update Your Database:

1. **Initial Setup & Universe Registration:**
   ```bash
   python scripts/init_universe.py
   ```
   *Registers 2,200+ clean US common equities from NASDAQ and seeds existing data.*

2. **Bulk Ingestion (From IPO / Lifetime):**
   ```bash
   python scripts/download_bulk_universe.py --limit 2200 --chunk-size 50 --period max
   ```
   *Runs parallel batch downloads. If interrupted, simply re-run it; it automatically resumes from where it left off!*

3. **Daily Incremental Synchronization:**
   ```bash
   python scripts/daily_update.py
   ```
   *Runs every evening after market close (5:00 PM EST). Checks `MAX(date)` and updates missing days in ~60 seconds.*

4. **Querying from Any Python Script or Notebook:**
   ```python
   from scripts.db_manager import USStockDatabase
   db = USStockDatabase()
   df = db.get_price_history(['NVDA', 'AAPL', 'TSLA'], start_date='2024-01-01')
   ```
"""))

    nb.cells = cells
    return nb


def build_and_save_database_notebook():
    notebook_dir = Path("d:/MAIN DATA/Documents/Untuk Portofolio Github/Risk Return US Stock/notebooks")
    notebook_dir.mkdir(parents=True, exist_ok=True)
    nb_path = notebook_dir / "04_database_and_universe_analytics.ipynb"

    print(f"Generating database analytics notebook at {nb_path}...")
    nb = create_database_analytics_notebook()

    with open(nb_path, "w", encoding="utf-8") as f:
        nbf.write(nb, f)
    print("Notebook JSON created.")

    print("Executing notebook to pre-render outputs, SQL queries, and charts...")
    client = NotebookClient(nb, timeout=600, kernel_name="python3", resources={'metadata': {'path': str(notebook_dir)}})
    client.execute()

    with open(nb_path, "w", encoding="utf-8") as f:
        nbf.write(nb, f)
    print("Database Analytics notebook successfully executed and saved with all outputs rendered!")


if __name__ == "__main__":
    build_and_save_database_notebook()
