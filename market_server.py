"""Local web server for exploring the complete SQLite US equity universe.

The server deliberately exposes only the small JSON responses the dashboard
needs; the 1.5 GB SQLite database is never made available as a static file.
"""

from __future__ import annotations

import json
import mimetypes
import sqlite3
from datetime import date, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from scripts.sector_metadata import SECTOR_DEFINITIONS


ROOT = Path(__file__).resolve().parent
DATABASE_PATH = ROOT / "data" / "database" / "us_equities.db"
STATIC_FILES = {"index.html", "assets/dashboard.css", "assets/dashboard.js", "assets/favicon.svg"}
RANGE_DAYS = {"1M": 42, "6M": 220, "1Y": 390, "5Y": 1850}


def connect_database() -> sqlite3.Connection:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError("The local SQLite database was not found.")
    connection = sqlite3.connect(f"{DATABASE_PATH.as_uri()}?mode=ro", uri=True, timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


def sector_expression() -> str:
    return "COALESCE(NULLIF(TRIM(t.sector), ''), 'Unclassified')"


def has_sector_metadata(conn: sqlite3.Connection) -> bool:
    return "sector" in {row[1] for row in conn.execute("PRAGMA table_info(tickers)")}


def metadata_required(conn: sqlite3.Connection) -> None:
    if not has_sector_metadata(conn):
        raise RuntimeError(
            "Sector metadata is missing. Run `python scripts/sector_metadata.py` once, then restart the server."
        )


def stock_select_sql() -> str:
    sector = sector_expression()
    return f"""
        SELECT
            t.symbol,
            TRIM(t.security_name) AS security_name,
            t.exchange,
            {sector} AS sector,
            COALESCE(t.industry, '') AS industry,
            t.first_date,
            t.last_date,
            t.total_records,
            CASE WHEN t.total_records > 0 THEN 1 ELSE 0 END AS has_price_history,
            p.close AS close,
            p.adj_close AS adj_close,
            p.volume AS volume,
            p.date AS price_date,
            (
                p.close / NULLIF((
                    SELECT prior.close
                    FROM daily_prices AS prior
                    WHERE prior.symbol = t.symbol AND prior.date < p.date
                    ORDER BY prior.date DESC LIMIT 1
                ), 0) - 1
            ) AS daily_change
        FROM tickers AS t
        LEFT JOIN daily_prices AS p ON p.symbol = t.symbol AND p.date = t.last_date
    """


def overview(conn: sqlite3.Connection) -> dict[str, object]:
    metadata_required(conn)
    total = conn.execute("SELECT COUNT(*) FROM tickers").fetchone()[0]
    price_history_stocks = conn.execute("SELECT COUNT(*) FROM tickers WHERE total_records > 0").fetchone()[0]
    active_filter = "WHERE t.total_records > 0"
    earliest, latest = conn.execute(
        f"SELECT MIN(t.first_date), MAX(t.last_date) FROM tickers AS t {active_filter}"
    ).fetchone()
    sector_rows = conn.execute(
        f"""
        SELECT {sector_expression()} AS sector, COUNT(*) AS count
        FROM tickers AS t
        
        GROUP BY {sector_expression()}
        """
    ).fetchall()
    sector_counts = {row["sector"]: row["count"] for row in sector_rows}
    ordered_sectors = [
        {"key": key, "label_id": label_id, "count": sector_counts.pop(key, 0)}
        for key, label_id in SECTOR_DEFINITIONS
    ]
    for key, count in sorted(sector_counts.items()):
        ordered_sectors.append({"key": key, "label_id": "Belum terklasifikasi", "count": count})

    updated_at = conn.execute("SELECT MAX(sector_updated_at) FROM tickers").fetchone()[0]
    return {
        "total_stocks": total,
        "stocks_with_history": price_history_stocks,
        "earliest_date": earliest,
        "latest_date": latest,
        "sectors": ordered_sectors,
        "sector_updated_at": updated_at,
    }


def stocks(conn: sqlite3.Connection, query: dict[str, list[str]]) -> dict[str, object]:
    metadata_required(conn)
    sector = query.get("sector", ["All"])[0].strip()
    search = query.get("q", [""])[0].strip()
    page = max(1, int(query.get("page", ["1"])[0] or 1))
    page_size = min(100, max(10, int(query.get("page_size", ["40"])[0] or 40)))
    where = ["1 = 1"]
    params: list[object] = []
    if sector and sector != "All":
        where.append(f"{sector_expression()} = ?")
        params.append(sector)
    if search:
        where.append("(t.symbol LIKE ? OR t.security_name LIKE ?)")
        needle = f"%{search}%"
        params.extend([needle, needle])
    where_sql = " WHERE " + " AND ".join(where)
    total = conn.execute(f"SELECT COUNT(*) FROM tickers AS t {where_sql}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = conn.execute(
        stock_select_sql() + where_sql + " ORDER BY t.symbol ASC LIMIT ? OFFSET ?",
        [*params, page_size, offset],
    ).fetchall()
    return {
        "items": [dict(row) for row in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


def stock(conn: sqlite3.Connection, symbol: str) -> dict[str, object]:
    metadata_required(conn)
    row = conn.execute(
        stock_select_sql() + " WHERE t.symbol = ?",
        [symbol],
    ).fetchone()
    if not row:
        raise LookupError(f"Ticker '{symbol}' was not found in the local database.")
    return dict(row)


def history(conn: sqlite3.Connection, symbol: str, selected_range: str) -> dict[str, object]:
    selected_range = selected_range.upper()
    if selected_range not in {*RANGE_DAYS, "ALL"}:
        raise ValueError("Range must be one of 1M, 6M, 1Y, 5Y, or ALL.")
    last_date = conn.execute(
        "SELECT last_date FROM tickers WHERE symbol = ?", [symbol]
    ).fetchone()
    if not last_date:
        raise LookupError(f"Ticker '{symbol}' was not found in the local database.")
    if not last_date[0]:
        return {"symbol": symbol, "range": selected_range, "rows": []}
    params: list[object] = [symbol]
    where = "symbol = ?"
    if selected_range != "ALL":
        cutoff = date.fromisoformat(last_date[0]) - timedelta(days=RANGE_DAYS[selected_range])
        where += " AND date >= ?"
        params.append(cutoff.isoformat())
    rows = conn.execute(
        f"SELECT date, close, adj_close, volume FROM daily_prices WHERE {where} ORDER BY date ASC", params
    ).fetchall()
    return {"symbol": symbol, "range": selected_range, "rows": [dict(row) for row in rows]}


class MarketRequestHandler(BaseHTTPRequestHandler):
    server_version = "US-Equity-Explorer/1.0"

    def do_GET(self) -> None:  # noqa: N802 - inherited HTTP handler name
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api(parsed.path, parse_qs(parsed.query))
            return
        self.serve_static(parsed.path)

    def handle_api(self, path: str, query: dict[str, list[str]]) -> None:
        try:
            with connect_database() as conn:
                if path == "/api/overview":
                    payload = overview(conn)
                elif path == "/api/stocks":
                    payload = stocks(conn, query)
                elif path == "/api/stock":
                    payload = stock(conn, query.get("symbol", [""])[0].strip().upper())
                elif path == "/api/history":
                    payload = history(
                        conn,
                        query.get("symbol", [""])[0].strip().upper(),
                        query.get("range", ["1Y"])[0],
                    )
                else:
                    self.respond_json({"error": "Unknown API route."}, HTTPStatus.NOT_FOUND)
                    return
            self.respond_json(payload)
        except LookupError as error:
            self.respond_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
        except (RuntimeError, ValueError, FileNotFoundError) as error:
            self.respond_json({"error": str(error)}, HTTPStatus.CONFLICT)
        except sqlite3.Error as error:
            self.respond_json({"error": f"Database error: {error}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def serve_static(self, path: str) -> None:
        relative = "index.html" if path in {"", "/"} else path.lstrip("/")
        if relative not in STATIC_FILES:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        candidate = (ROOT / relative).resolve()
        if not candidate.is_file() or ROOT not in candidate.parents:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        body = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def respond_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[web] {self.address_string()} - {format % args}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run the local US Equity Explorer dashboard.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    parser.add_argument("--port", default=8000, type=int, help="HTTP port (default: 8000)")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), MarketRequestHandler)
    print(f"US Equity Explorer running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop the server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
