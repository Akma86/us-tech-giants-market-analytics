# CLI Commands & Pipeline Execution Handbook

A complete reference guide for managing the US Stock Market Analytics quantitative pipeline, databases (SQLite & MongoDB), incremental daily updaters, and research workflows.

---

## 📑 Quick Reference Table

| Script | Purpose | Typical Execution Time | Primary Output |
| :--- | :--- | :--- | :--- |
| [`scripts/daily_update.py`](file:///d:/MAIN%20DATA/Documents/Untuk%20Portofolio%20Github/Risk%20Return%20US%20Stock/scripts/daily_update.py) | Incremental daily update for recent market bars | **~2 – 60 seconds** | SQLite & MongoDB (Port 27018) |
| [`start_market_mongo.bat`](file:///d:/MAIN%20DATA/Documents/Untuk%20Portofolio%20Github/Risk%20Return%20US%20Stock/start_market_mongo.bat) | Starts dedicated MongoDB instance on port 27018 | Background Daemon | `mongodb://localhost:27018/` |
| [`scripts/mongo_manager.py`](file:///d:/MAIN%20DATA/Documents/Untuk%20Portofolio%20Github/Risk%20Return%20US%20Stock/scripts/mongo_manager.py) | Checks MongoDB status and collection counts | **< 1 second** | Terminal status |
| [`scripts/fetch_data.py`](file:///d:/MAIN%20DATA/Documents/Untuk%20Portofolio%20Github/Risk%20Return%20US%20Stock/scripts/fetch_data.py) | Downloads Big 5 Tech Giants raw CSVs & master CSV | ~10 seconds | `data/raw/*.csv` |
| [`scripts/fetch_earnings_dates.py`](file:///d:/MAIN%20DATA/Documents/Untuk%20Portofolio%20Github/Risk%20Return%20US%20Stock/scripts/fetch_earnings_dates.py) | Fetches quarterly earnings reports & surprise % | ~15 seconds | `data/raw/earnings/*.csv` |
| [`scripts/init_universe.py`](file:///d:/MAIN%20DATA/Documents/Untuk%20Portofolio%20Github/Risk%20Return%20US%20Stock/scripts/init_universe.py) | Catalogs 2,200 NASDAQ & NYSE active stocks | ~5 seconds | `tickers` table in DB |
| [`scripts/download_bulk_universe.py`](file:///d:/MAIN%20DATA/Documents/Untuk%20Portofolio%20Github/Risk%20Return%20US%20Stock/scripts/download_bulk_universe.py) | Bulk historical downloader from IPO with auto-resume | ~15–20 minutes | 9.44M+ rows in SQLite & MongoDB |
| [`scripts/sync_to_mongo.py`](file:///d:/MAIN%20DATA/Documents/Untuk%20Portofolio%20Github/Risk%20Return%20US%20Stock/scripts/sync_to_mongo.py) | Full migration from SQLite to MongoDB | ~30 seconds | Syncs collections |

---

## 1. Daily Market Updates (Routine Maintenance)

The incremental daily updater (`daily_update.py`) checks the latest recorded trading day in your database and **fetches only the new trading bars** without re-downloading years of history.

### A. Run Daily Update for All 2,200 Stocks
```powershell
python scripts/daily_update.py --mongo
```
*Fetches the latest trading bars for all active equities and synchronizes directly to both SQLite and MongoDB (Port 27018).*

### B. Update Only Specific Focus Stocks (Ultra Fast, ~2 seconds)
```powershell
python scripts/daily_update.py --symbols AAPL,MSFT,NVDA,GOOGL,AMZN --mongo
```

### C. Update with Custom Lookback Period
If you were away for a vacation or missed several trading days:
```powershell
# Re-sync the past 14 days
python scripts/daily_update.py --lookback 14 --mongo
```

---

## 2. Automating Daily Updates (Hands-Free)

You can set Windows Task Scheduler to run the daily update automatically every weekday after the US market closes.

> **US Market Close Context:**
> - US markets close at **4:00 PM EST** (which is **04:00 AM WIB** the next day).
> - Recommended run time: **05:00 AM WIB** (Monday – Friday).

### Quick Setup via PowerShell (Admin):
```powershell
$action = New-ScheduledTaskAction -Execute "python.exe" -Argument "scripts/daily_update.py --mongo" -WorkingDirectory "d:\MAIN DATA\Documents\Untuk Portofolio Github\Risk Return US Stock"
$trigger = New-ScheduledTaskTrigger -Daily -At "05:00AM"
Register-ScheduledTask -TaskName "US_Stock_Daily_Market_Sync" -Action $action -Trigger $trigger -Description "Daily incremental US stock market sync to SQLite and MongoDB"
```

Or simply run the update manually anytime after market close with:
```powershell
python scripts/daily_update.py --mongo
```

---

## 3. Dedicated MongoDB Management (Port 27018)

This project uses an isolated MongoDB database running on **port 27018** to prevent any conflicts with your personal databases on default port 27017.

### Start the Dedicated MongoDB Service:
```powershell
.\start_market_mongo.bat
```
*Or via command line:*
```powershell
& "C:\Program Files\MongoDB\Server\8.2\bin\mongod.exe" --dbpath "data/database/mongodb_market_data" --port 27018
```

### Check MongoDB Health & Record Counts:
```powershell
python scripts/mongo_manager.py
```

### Connect via MongoDB Compass GUI:
- **Connection URI**: `mongodb://localhost:27018/`
- **Database**: `us_equities_db`
- **Collections**:
  - `daily_prices` (9.44M+ historical daily bars)
  - `tickers` (2,200 equity directory)
  - `earnings` (485 quarterly earnings reports)

---

## 4. SQLite Database Diagnostics & Queries

The primary relational store is located at [`data/database/us_equities.db`](file:///d:/MAIN%20DATA/Documents/Untuk%20Portofolio%20Github/Risk%20Return%20US%20Stock/data/database/us_equities.db).

### Check SQLite Summary Statistics:
```powershell
python -c "import sys; sys.path.append('scripts'); from db_manager import USStockDatabase; print(USStockDatabase().get_database_stats())"
```

### View Recent Pipeline Execution Telemetry:
```powershell
python -c "import sqlite3; conn = sqlite3.connect('data/database/us_equities.db'); c = conn.cursor(); c.execute('SELECT log_id, timestamp, job_type, symbols_processed, rows_affected, status FROM pipeline_logs ORDER BY log_id DESC LIMIT 5'); [print(row) for row in c.fetchall()]; conn.close()"
```

---

## 5. Feature Engineering & Historical Datasets

### Re-generate Raw Big 5 CSV Files:
```powershell
python scripts/fetch_data.py
```

### Re-generate Quarterly Earnings Event Study Files:
```powershell
python scripts/fetch_earnings_dates.py
```

### Re-build Quantitative Features (Returns, Volatility, Drawdowns):
Open and run all cells in [`notebooks/02_feature_engineering_and_market_analytics.ipynb`](file:///d:/MAIN%20DATA/Documents/Untuk%20Portofolio%20Github/Risk%20Return%20US%20Stock/notebooks/02_feature_engineering_and_market_analytics.ipynb), or query directly from Python:
```python
from scripts.db_manager import USStockDatabase
db = USStockDatabase()
df_nvda = db.get_price_history('NVDA', start_date='2020-01-01')
print(df_nvda.tail())
```

---

## 6. Troubleshooting & Best Practices

1. **Missing MongoDB Connection:**
   If running `daily_update.py --mongo` displays a warning that MongoDB is unreachable:
   - Double-check that MongoDB is running on port 27018. Run `.\start_market_mongo.bat` in a separate terminal.
2. **Missing Tickers during Bulk Download:**
   - Any warning such as `['XYZ']: Period 'max' is invalid` indicates that the instrument recently IPO'd or is a warrant without long historical bars. The pipeline automatically skips it and saves all other 2,199 equities safely.
3. **Git Protection:**
   - Large database files (`*.db`, `mongodb_market_data/`) are tracked in `.gitignore` and protected by `.gitkeep` placeholders so your GitHub commits stay clean, lightweight, and under file size limits.
