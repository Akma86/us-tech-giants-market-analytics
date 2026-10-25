# US Tech Giants & Equity Universe: Command Reference & Automation Guide

This guide provides a comprehensive operational manual and command cheatsheet for managing the **2,000+ US Stock Analytics Platform**, local databases (**SQLite WAL** & **dedicated MongoDB**), and incremental daily market pipelines.

---

## 1. System Status & Database Metrics

The platform currently operates two synchronized, high-performance database engines:

| Metric | SQLite (`us_equities.db`) | Dedicated MongoDB (`us_equities_db`) |
| :--- | :--- | :--- |
| **Connection / Path** | `data/database/us_equities.db` | `mongodb://localhost:27018/` |
| **Cataloged Tickers** | `2,200` common stocks | `2,200` tickers |
| **Stocks with Full Lifetime History** | `2,199` stocks (99.95%) | `2,199` stocks (99.95%) |
| **Total Price Bars** | **`9,446,636` records** | **`9,446,636` documents** |
| **Historical Range** | **Jan 02, 1962 – Present** | **Jan 02, 1962 – Present** |
| **Storage Engine** | SQLite WAL (Write-Ahead Log) | WiredTiger (Compressed) |
| **File / Collection Size** | `~1.46 GB` | Dedicated directory: `data/database/mongodb_market_data` |

*Note: Out of 2,200 equities, only 1 micro-cap warrant (`BCTXL`) was safely omitted due to lack of multi-year history.*

---

## 2. Dedicated MongoDB Service Management

The project uses an isolated MongoDB instance running on **Port 27018** (avoiding any collision with standard databases on port 27017).

### Start MongoDB Instance (Port 27018)
Run the pre-configured Windows batch file:
```cmd
scripts\start_market_mongo.bat
```
*Or via PowerShell directly:*
```powershell
& "C:\Program Files\MongoDB\Server\8.2\bin\mongod.exe" --dbpath "d:\MAIN DATA\Documents\Untuk Portofolio Github\Risk Return US Stock\data\database\mongodb_market_data" --port 27018
```

### Connect with MongoDB Compass or VS Code Extension
Use the connection string:
```text
mongodb://localhost:27018/
```
Inside, you will find the `us_equities_db` database with 3 collections:
- `daily_prices`: 9,446,636 documents with compound indexes `(symbol, date)` and `(date)`.
- `tickers`: 2,200 stock metadata records.
- `earnings`: 485 historical quarterly earnings reports.

---

## 3. Daily Automated Updates (Incremental Pipeline)

To keep both SQLite and MongoDB updated with today's new closing prices, use `scripts/daily_update.py`.

### How It Works:
1. Queries the database for the latest recorded date per ticker.
2. Downloads **only the missing recent bars** (default lookback: 7 days to account for weekends/holidays) using multi-threaded batching.
3. Automatically updates SQLite and MongoDB simultaneously.
4. **Execution time**: Under **60 seconds** for all 2,200 stocks!

### Run Daily Update (SQLite Only):
```powershell
python scripts/daily_update.py
```

### Run Daily Update (SQLite + MongoDB):
```powershell
python scripts/daily_update.py --mongo
```

---

## 4. Scheduling Automated Daily Updates (Hands-Free)

You can set Windows to run the update automatically every trading day after US market close (e.g., at 05:00 WIB / 18:00 EST).

### Option A: Via PowerShell (Automated Setup)
Open PowerShell as Administrator and run:
```powershell
$Action = New-ScheduledTaskAction -Execute "python.exe" -Argument "scripts\daily_update.py --mongo" -WorkingDirectory "d:\MAIN DATA\Documents\Untuk Portofolio Github\Risk Return US Stock"
$Trigger = New-ScheduledTaskTrigger -Daily -At "05:00AM"
Register-ScheduledTask -TaskName "US_Stock_Daily_Update" -Action $Action -Trigger $Trigger -Description "Daily incremental market update for US equities"
```

### Option B: Via Windows Task Scheduler GUI
1. Press `Win + R`, type `taskschd.msc`, and press Enter.
2. Click **Create Basic Task...** on the right panel.
3. Name: `US Equities Daily Sync`.
4. Trigger: **Daily** at `05:00 AM` (after US market settlement).
5. Action: **Start a program**:
   - **Program/script**: `python.exe` (or `C:\Program Files\Python312\python.exe`)
   - **Add arguments**: `scripts\daily_update.py --mongo`
   - **Start in**: `d:\MAIN DATA\Documents\Untuk Portofolio Github\Risk Return US Stock`
6. Click **Finish**.

---

## 5. Complete Script Cheatsheet

| Script | Purpose | Command |
| :--- | :--- | :--- |
| **Web Dashboard** | (Local explorer) Launch US Equity Atlas | `python website/market_server.py --port 8000` |
| **Check Database Stats** | Instant health check of SQLite & MongoDB records | `python -c "import sys; sys.path.append('scripts'); from db_manager import USStockDatabase; print(USStockDatabase().get_database_stats())"` |
| **Check Mongo Stats** | Verify MongoDB Port 27018 collections | `python -c "import sys; sys.path.append('scripts'); from mongo_manager import MongoStockDatabase; print(MongoStockDatabase().get_stats())"` |
| **Daily Market Update** | Incrementally sync missing bars (<60s) | `python scripts/daily_update.py --mongo` |
| **Big 5 CSV Extraction** | Re-fetch Apple, Microsoft, Nvidia, Google, Amazon | `python scripts/fetch_data.py` |
| **Earnings History** | Re-fetch quarterly earnings & EPS surprises | `python scripts/fetch_earnings_dates.py` |
| **Initialize Universe** | Scrape active NASDAQ/NYSE listings (2,200 stocks) | `python scripts/init_universe.py --limit 2200` |
| **Bulk Lifetime Downloader** | Download all historical IPO data with auto-resume | `python scripts/download_bulk_universe.py --limit 2200 --chunk-size 30 --period max` |
| **SQLite to Mongo Sync** | Full migration/mirroring from SQLite to MongoDB | `python scripts/sync_to_mongo.py` |

---

## 6. Querying Data via Python

### Example 1: Query SQLite from Python or Notebooks
```python
import sys
sys.path.append("scripts")
from db_manager import USStockDatabase

db = USStockDatabase()

# Fetch entire historical price series for NVDA and AAPL
df = db.get_price_history(symbols=["NVDA", "AAPL"], start_date="2020-01-01")
print(df.head())
```

### Example 2: Query Dedicated MongoDB from Python
```python
import sys
sys.path.append("scripts")
from mongo_manager import MongoStockDatabase

mongo = MongoStockDatabase()

# Fetch latest prices from MongoDB
df_mongo = mongo.get_price_history(symbols=["MSFT", "GOOGL"], start_date="2024-01-01")
print(df_mongo.tail())
```

---

## 7. Analysis & Jupyter Notebooks

Launch Jupyter to explore the pre-built analytics and visualizations:
```powershell
jupyter lab
# Or standard jupyter notebook:
jupyter notebook
```

Available analytical notebooks:
1. `notebooks/01_dataset_inspection_and_eda.ipynb`: Data quality checks, dividend adjustments, volume profiles.
2. `notebooks/02_feature_engineering_and_market_analytics.ipynb`: Garman-Klass volatility, rolling Sharpe, maximum drawdowns, technical indicators.
3. `notebooks/03_earnings_impact_and_event_study.ipynb`: Post-Earnings Announcement Drift (PEAD) and event study charts.
4. `notebooks/04_database_and_universe_analytics.ipynb`: SQL screeners, 52-week highs, volume breakouts, and market breadth across all 2,200 stocks.
