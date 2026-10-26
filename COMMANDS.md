# ⚡ US Stock Market Analytics: CLI Commands & Operations Cheatsheet

A quick reference manual for managing the **2,000+ US Stock Analytics Platform**, local databases (**SQLite WAL** & **dedicated MongoDB Port 27018**), incremental daily market pipelines, and research workflows.

*For full extended architecture and Windows Task Scheduler guides, see [docs/COMMAND_CHEATSHEET.md](docs/COMMAND_CHEATSHEET.md).*

---

## 📑 Core Commands at a Glance

| Action | Command | Purpose |
| :--- | :--- | :--- |
| **Launch Streamlit Dashboard** | `streamlit run app/Home.py --server.port 8501` | **StockLens US** Institutional Financial Knowledge Graph & Analytics |
| **Run StockLens Tests** | `python tests/test_stocklens.py` | Runs 8 unit & integration tests (Graph, DuckDB, OLS, Event Study) |
| **Run Ingestion (DuckDB/Parquet)** | `python src/ingest_us.py` | Ingests equities, commodities, and macro series into DuckDB & Parquet |
| **Re-build Notebook 05** | `python scripts/build_research_notebook.py` | Generates & executes `05_financial_knowledge_graph_analytics.ipynb` |
| **Launch Web Dashboard** | `python website/market_server.py --port 8000` | (Local explorer) Opens US Equity Atlas web dashboard at `http://127.0.0.1:8000` |
| **Start Dedicated MongoDB** | `.\scripts\start_market_mongo.bat` | Starts MongoDB on port **27018** (isolated from port 27017) |
| **Run Daily Update** | `python scripts/daily_update.py --mongo` | Fetches new daily price bars for 2,200 stocks (<60s) |
| **Check SQLite Stats** | `python -c "import sys; sys.path.append('scripts'); from db_manager import USStockDatabase; print(USStockDatabase().get_database_stats())"` | Shows total records, coverage, date range |
| **Check Mongo Stats** | `python -c "import sys; sys.path.append('scripts'); from mongo_manager import MongoStockDatabase; print(MongoStockDatabase().get_stats())"` | Verifies MongoDB collections and document counts |
| **Re-run Bulk Ingestion** | `python scripts/download_bulk_universe.py --limit 2200 --chunk-size 30 --period max` | Auto-resumes lifetime download from respective IPOs |
| **Re-fetch Big 5 CSVs** | `python scripts/fetch_data.py` | Pulls AAPL, MSFT, NVDA, GOOGL, AMZN into `data/raw/` |
| **Re-fetch Earnings** | `python scripts/fetch_earnings_dates.py` | Extracts quarterly earnings and EPS surprise history |
| **Full SQLite->Mongo Sync** | `python scripts/sync_to_mongo.py` | Mirrors all SQLite records to MongoDB |

---

## 1. Daily Market Routine (Cara Update Tiap Hari)

Setelah bursa saham AS tutup (jam 04:00 WIB / 16:00 EST), cukup jalankan satu perintah ini:

```powershell
python scripts/daily_update.py --mongo
```

**Karakteristik Daily Updater:**
- Hanya menarik baris tanggal baru (sejak update terakhir).
- Berjalan sangat cepat (**kurang dari 60 detik** untuk seluruh 2.200 saham).
- Otomatis memperbarui **SQLite** (`us_equities.db`) dan **MongoDB** Port 27018 (`us_equities_db`).

---

## 2. Otomatisasi Harian Tanpa Buka Terminal (Hands-Free)

Untuk mengatur agar Windows mengupdate data secara otomatis setiap subuh (jam 05:00 WIB) setelah pasar AS selesai:

Buka PowerShell sebagai Administrator dan jalankan:
```powershell
$Action = New-ScheduledTaskAction -Execute "python.exe" -Argument "scripts\daily_update.py --mongo" -WorkingDirectory "d:\MAIN DATA\Documents\Untuk Portofolio Github\Risk Return US Stock"
$Trigger = New-ScheduledTaskTrigger -Daily -At "05:00AM"
Register-ScheduledTask -TaskName "US_Stock_Daily_Update" -Action $Action -Trigger $Trigger -Description "Daily incremental market update for US equities"
```

---

## 3. Dedicated MongoDB (Port 27018)

- **Connection URI**: `mongodb://localhost:27018/`
- **Database**: `us_equities_db`
- **Data Folder**: `data/database/mongodb_market_data` (terisolasi dari database rumah sakit / proyek pribadi di port 27017).
- **Collections**:
  - `daily_prices`: 9.44M+ historical daily records
  - `tickers`: 2,200 stock profiles
  - `earnings`: 485 quarterly earnings reports

---

## 4. Querying dari Python / Notebook

```python
import sys
sys.path.append("scripts")

# Query SQLite
from db_manager import USStockDatabase
db = USStockDatabase()
df_sqlite = db.get_price_history(symbols=["NVDA", "AAPL"], start_date="2020-01-01")

# Query MongoDB Port 27018
from mongo_manager import MongoStockDatabase
mongo = MongoStockDatabase()
df_mongo = mongo.get_price_history(symbols=["MSFT"], start_date="2024-01-01")
```

---

## 5. StockLens US: Financial Knowledge Graph & Columnar Analytics

### Menjalankan Streamlit Dashboard
```powershell
streamlit run app/Home.py --server.port 8501
```
Akses dashboard di browser melalui: `http://localhost:8501`
Fitur dashboard:
- **Interactive Knowledge Graph:** Filter sektor GICS, node centrality, pencarian entitas.
- **Economic Transmission Path Finder:** Menelusuri rantai transmisi guncangan komoditas ke emiten saham beserta kutipan SEC 10-K.
- **Market Model OLS:** Estimasi Alpha, Beta, R-squared, Idiosyncratic Risk terhadap S&P 500 (`^GSPC`).
- **Event Study Lab:** Evaluasi Abnormal Returns (AR) dan Cumulative Abnormal Returns (CAR) di sekitar event katalis.
- **Lead/Lag Macro Spectrum:** Analisis korelasi silang lag $\pm 20$ hari (minyak/yields memimpin pergerakan saham).
- **SEC 10-K Evidence Drawer:** Katalog kutipan resmi Form 10-K dari US SEC EDGAR.

### Menjalankan Unit & Integration Tests
```powershell
python tests/test_stocklens.py
```

### Menjalankan Script Ingest & Analytics
```powershell
# Pipeline ingest Parquet & DuckDB
python src/ingest_us.py

# Query graph & path tracing via CLI
python src/graph_builder.py

# Quantitative regressions & lead-lag via CLI
python src/analyze_us.py

# Re-render research notebook 05
python scripts/build_research_notebook.py
```

