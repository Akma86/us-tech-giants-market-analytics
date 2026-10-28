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
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

FILE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = FILE_DIR.parent if (FILE_DIR.parent / "data").exists() else FILE_DIR
DATABASE_PATH = PROJECT_ROOT / "data" / "database" / "us_equities.db"
STATIC_DIR = FILE_DIR if (FILE_DIR / "index.html").exists() else (PROJECT_ROOT / "website")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.sector_metadata import SECTOR_DEFINITIONS
try:
    from website.news_service import get_stock_news, backfill_stock_news
except ImportError:
    from news_service import get_stock_news, backfill_stock_news

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


# ==============================================================================
# STOCKLENS US: KNOWLEDGE GRAPH & QUANTITATIVE ANALYTICS HANDLERS
# ==============================================================================
_KG_INSTANCE = None
_ANALYTICS_INSTANCE = None


def get_kg():
    global _KG_INSTANCE
    if _KG_INSTANCE is None:
        from src.graph_builder import FinancialKnowledgeGraph
        _KG_INSTANCE = FinancialKnowledgeGraph()
    return _KG_INSTANCE


def get_analytics():
    global _ANALYTICS_INSTANCE
    if _ANALYTICS_INSTANCE is None:
        from src.analyze_us import FinancialAnalyticsEngine
        _ANALYTICS_INSTANCE = FinancialAnalyticsEngine()
    return _ANALYTICS_INSTANCE


def stocklens_overview() -> dict[str, object]:
    kg = get_kg()
    engine = get_analytics()
    con = engine.get_connection()
    total_prices = con.execute("SELECT count(*) FROM market_prices").fetchone()[0]
    return {
        "total_nodes": kg.graph.number_of_nodes(),
        "total_edges": kg.graph.number_of_edges(),
        "total_evidence": len(kg.evidence_df),
        "total_prices": total_prices,
        "sectors": 11,
    }


def stocklens_graph(query: dict[str, list[str]]) -> dict[str, object]:
    kg = get_kg()
    entity_filter = query.get("type", ["All"])[0]
    search = query.get("q", [""])[0].lower().strip()

    nodes = []
    edges = []

    matched_ids = set()
    for n, d in kg.graph.nodes(data=True):
        e_type = d.get("entity_type", "Unknown")
        if entity_filter != "All" and e_type != entity_filter:
            continue
        if search:
            name = d.get("name", "").lower()
            ticker = d.get("ticker", "").lower()
            if search not in n.lower() and search not in name and search not in ticker:
                continue
        matched_ids.add(n)

    if entity_filter != "All" or search:
        active_ids = set(matched_ids)
        for n in matched_ids:
            active_ids.update(kg.graph.predecessors(n))
            active_ids.update(kg.graph.successors(n))
    else:
        active_ids = set(kg.graph.nodes())

    in_deg = dict(kg.graph.in_degree())
    out_deg = dict(kg.graph.out_degree())

    for n in active_ids:
        d = kg.graph.nodes[n]
        nodes.append({
            "id": n,
            "name": d.get("name", n),
            "type": d.get("entity_type", "Unknown"),
            "ticker": d.get("ticker", ""),
            "exchange": d.get("exchange", ""),
            "sector_code": d.get("sector_code", ""),
            "color": d.get("color", "#94A3B8"),
            "degree": in_deg.get(n, 0) + out_deg.get(n, 0),
            "in_degree": in_deg.get(n, 0),
            "out_degree": out_deg.get(n, 0),
        })

    target_year = query.get("year", [""])[0].strip()
    target_year = int(target_year) if target_year.isdigit() else None
    time_range = query.get("range", ["ALL"])[0].upper().strip()

    for u, v, k, d in kg.graph.edges(keys=True, data=True):
        if u in active_ids and v in active_ids:
            v_from = d.get("valid_from", "")
            v_to = d.get("valid_to", "")
            
            # Temporal Year Filter
            if target_year is not None:
                if v_from and v_from[:4].isdigit() and int(v_from[:4]) > target_year:
                    continue
                if v_to and v_to[:4].isdigit() and int(v_to[:4]) < target_year:
                    continue

            # Temporal Range Filter
            if time_range == "1W":
                if not (v_from and v_from >= "2025-01-01"):
                    continue
            elif time_range == "1M":
                if not (v_from and v_from >= "2024-06-01"):
                    continue
            elif time_range == "1Y":
                if not (v_from and v_from >= "2023-01-01"):
                    continue
            elif time_range == "5Y":
                if not (v_from and v_from >= "2019-01-01"):
                    continue

            edges.append({
                "id": d.get("rel_id", f"{u}_{v}"),
                "source": u,
                "target": v,
                "rel_type": d.get("rel_type", "RELATED_TO"),
                "weight": float(d.get("weight", 1.0)),
                "lag_days": int(d.get("lag_days", 0)),
                "evidence_status": d.get("evidence_status", "hypothesis"),
                "valid_from": v_from,
                "valid_to": v_to,
                "headline": d.get("headline", ""),
                "source_url": d.get("source_url", ""),
                "notes": d.get("notes", ""),
                "citations": d.get("citation_keys", []),
                "color": d.get("color", "#64748B"),
            })

    # When filtering by year/range, indicate active nodes
    connected_node_ids = {e["source"] for e in edges} | {e["target"] for e in edges}
    for n in nodes:
        n["is_active"] = (n["id"] in connected_node_ids) if (target_year or time_range != "ALL") else True

    return {"nodes": nodes, "edges": edges, "filtered_year": target_year, "range": time_range}


def stocklens_contagion(query: dict[str, list[str]]) -> dict[str, object]:
    from src.contagion import ContagionSimulator
    kg = get_kg()
    sim = ContagionSimulator(kg.graph)
    node_id = query.get("node", ["co_nvda"])[0].strip()
    shock_type = query.get("shock_type", ["negative"])[0].strip()
    mag = float(query.get("magnitude", ["1.0"])[0] or 1.0)
    return sim.run_shock_simulation(node_id, shock_type=shock_type, shock_magnitude=mag)


def stocklens_sync_news_relations() -> dict[str, object]:
    from src.news_extractor import scan_and_update_graph
    res = scan_and_update_graph()
    kg = get_kg()
    kg.load_data()
    kg.build_graph()
    return res


def stocklens_paths(query: dict[str, list[str]]) -> dict[str, object]:
    kg = get_kg()
    source = query.get("source", ["commodity_wti"])[0]
    target = query.get("target", ["co_dal"])[0]
    max_hops = int(query.get("max_hops", ["4"])[0] or 4)
    paths = kg.find_transmission_paths(source, target, max_hops=max_hops)
    return {
        "source": source,
        "target": target,
        "count": len(paths),
        "paths": paths,
    }


def stocklens_centrality() -> dict[str, object]:
    kg = get_kg()
    df = kg.calculate_centrality_metrics()
    return {"items": df.to_dict(orient="records")}


def stocklens_market_model(query: dict[str, list[str]]) -> dict[str, object]:
    engine = get_analytics()
    ticker = query.get("ticker", ["NVDA"])[0].upper()
    benchmark = query.get("benchmark", ["^GSPC"])[0]
    start_date = query.get("start_date", ["2022-01-01"])[0]
    res = engine.run_market_model(ticker, benchmark, start_date=start_date)

    returns_df = engine.get_returns_matrix([ticker, benchmark], start_date=start_date).dropna()
    x_vals = returns_df[benchmark].tolist()
    y_vals = returns_df[ticker].tolist()
    dates = [str(d.date()) for d in returns_df.index]

    step = max(1, len(x_vals) // 250)
    sampled_points = [{"x": round(x_vals[i], 4), "y": round(y_vals[i], 4), "d": dates[i]} for i in range(0, len(x_vals), step)]

    min_x, max_x = min(x_vals), max(x_vals)
    line = [
        {"x": round(min_x, 4), "y": round(res["alpha_daily"] + res["beta"] * min_x, 4)},
        {"x": round(max_x, 4), "y": round(res["alpha_daily"] + res["beta"] * max_x, 4)},
    ]

    return {**res, "points": sampled_points, "line": line}


def stocklens_event_study(query: dict[str, list[str]]) -> dict[str, object]:
    engine = get_analytics()
    ticker = query.get("ticker", ["NVDA"])[0].upper()
    event_date = query.get("event_date", ["2024-03-18"])[0]
    pre_win = int(query.get("pre_window", ["3"])[0] or 3)
    post_win = int(query.get("post_window", ["5"])[0] or 5)
    return engine.run_event_study(ticker, event_date, pre_event_window=pre_win, post_event_window=post_win)


def stocklens_lead_lag(query: dict[str, list[str]]) -> dict[str, object]:
    engine = get_analytics()
    equity_ticker = query.get("equity", ["DAL"])[0].upper()
    macro_ticker = query.get("macro", ["CL=F"])[0]
    return engine.run_lead_lag_correlation(equity_ticker, macro_ticker)


def stocklens_evidence() -> dict[str, object]:
    kg = get_kg()
    return {"items": kg.evidence_df.to_dict(orient="records")}


def stocklens_universe_lead_lag(query: dict[str, list[str]]) -> dict[str, object]:
    engine = get_analytics()
    ticker = query.get("ticker", ["NVDA"])[0].strip().upper()
    thresh = float(query.get("threshold", ["0.025"])[0] or 0.025)
    horizon = int(query.get("horizon", ["5"])[0] or 5)
    return engine.run_universe_lead_lag(trigger_ticker=ticker, threshold=thresh, horizon_days=horizon)


# ==============================================================================
# AI BUBBLE & CONTAGION RADAR HANDLERS
# ==============================================================================
_BUBBLE_VALUATION = None
_DOTCOM_ENGINE = None
_FRAGILITY_ENGINE = None
_CONTAGION_ENGINE = None


def get_bubble_valuation():
    global _BUBBLE_VALUATION
    if _BUBBLE_VALUATION is None:
        from src.bubble_valuation import AIValuationEngine
        _BUBBLE_VALUATION = AIValuationEngine()
    return _BUBBLE_VALUATION


def get_dotcom_engine():
    global _DOTCOM_ENGINE
    if _DOTCOM_ENGINE is None:
        from src.dotcom_comparison import DotComComparisonEngine
        _DOTCOM_ENGINE = DotComComparisonEngine()
    return _DOTCOM_ENGINE


def get_fragility_engine():
    global _FRAGILITY_ENGINE
    if _FRAGILITY_ENGINE is None:
        from src.fragility_index import FragilityIndexEngine
        _FRAGILITY_ENGINE = FragilityIndexEngine()
    return _FRAGILITY_ENGINE


def get_bubble_contagion():
    global _CONTAGION_ENGINE
    if _CONTAGION_ENGINE is None:
        from src.bubble_contagion import AIContagionEngine
        _CONTAGION_ENGINE = AIContagionEngine()
    return _CONTAGION_ENGINE


def bubble_valuation(query: dict[str, list[str]]) -> dict[str, object]:
    engine = get_bubble_valuation()
    force = query.get("force_refresh", ["false"])[0].lower() == "true"
    return engine.get_universe_valuations(force_refresh=force)


def bubble_reverse_dcf(query: dict[str, list[str]]) -> dict[str, object]:
    engine = get_bubble_valuation()
    sym = query.get("symbol", ["NVDA"])[0].strip().upper()
    price = float(query.get("price", ["0"])[0] or 0)
    wacc = float(query.get("wacc", ["0.09"])[0] or 0.09)
    tg = float(query.get("terminal_growth", ["0.03"])[0] or 0.03)
    fcf = float(query.get("fcf", ["0"])[0] or 0)
    shares = float(query.get("shares", ["0"])[0] or 0)
    net_debt = float(query.get("net_debt", ["0"])[0] or 0)

    if price <= 0 or fcf <= 0 or shares <= 0:
        val = engine.fetch_stock_valuation(sym)
        price = price if price > 0 else val["current_price"]
        shares_out = (val["market_cap_billions"] * 1e9 / val["current_price"]) if val["current_price"] else 1e9
        fcf_ann = (val.get("p_to_fcf") and (val["market_cap_billions"] * 1e9 / val["p_to_fcf"])) or 4e10
        return engine.calculate_reverse_dcf(
            current_price=price,
            shares_outstanding=shares_out,
            fcf_annual=fcf_ann,
            wacc=wacc,
            terminal_growth=tg,
            net_debt=net_debt,
        )
    return engine.calculate_reverse_dcf(
        current_price=price,
        shares_outstanding=shares,
        fcf_annual=fcf,
        wacc=wacc,
        terminal_growth=tg,
        net_debt=net_debt,
    )


def bubble_dotcom_compare(query: dict[str, list[str]]) -> dict[str, object]:
    engine = get_dotcom_engine()
    mode = query.get("mode", ["all"])[0].lower()
    if mode == "matrix":
        return engine.get_comparison_matrix()
    elif mode == "trajectory":
        return engine.get_drawdown_comparison_series()
    return {
        "matrix": engine.get_comparison_matrix(),
        "drawdown": engine.get_drawdown_comparison_series(),
    }


def bubble_safe_havens(query: dict[str, list[str]]) -> dict[str, object]:
    engine = get_dotcom_engine()
    force_refresh = query.get("refresh", ["false"])[0].lower() in ("true", "1")
    return engine.get_safe_haven_rotation_matrix(force_refresh=force_refresh)


def bubble_database_scan(query: dict[str, list[str]]) -> dict[str, object]:
    engine = get_dotcom_engine()
    max_corr = float(query.get("max_nvda_corr", ["0.25"])[0] or 0.25)
    min_dotcom = float(query.get("min_dotcom_return", ["0.0"])[0] or 0.0)
    only_pos = query.get("only_positive_crash", ["false"])[0].lower() in ("true", "1")
    limit = int(query.get("limit", ["40"])[0] or 40)
    return engine.scan_database_for_crash_hedges(
        max_nvda_corr=max_corr,
        min_dotcom_return=min_dotcom,
        only_positive_on_nvda_crash=only_pos,
        limit=limit,
    )


def bubble_fragility_index(query: dict[str, list[str]]) -> dict[str, object]:
    engine = get_fragility_engine()
    custom_w = None
    if "valuation_w" in query:
        custom_w = {
            "valuation_stretch": float(query.get("valuation_w", ["0.25"])[0] or 0.25),
            "index_concentration": float(query.get("concentration_w", ["0.20"])[0] or 0.20),
            "capex_monetization_gap": float(query.get("capex_w", ["0.20"])[0] or 0.20),
            "real_yield_pressure": float(query.get("yield_w", ["0.15"])[0] or 0.15),
            "cross_asset_correlation": float(query.get("corr_w", ["0.10"])[0] or 0.10),
            "guidance_dispersion": float(query.get("guidance_w", ["0.10"])[0] or 0.10),
        }
    return engine.calculate_fragility_index(custom_weights=custom_w)


def bubble_stress_test(query: dict[str, list[str]]) -> dict[str, object]:
    engine = get_bubble_contagion()
    scenario_id = query.get("scenario_id", ["scenario_a"])[0].lower()
    capex_cut = float(query.get("capex_cut", ["20.0"])[0] or 20.0)
    rate_hike = float(query.get("rate_hike", ["100.0"])[0] or 100.0)
    semi_shock = float(query.get("semi_shock", ["15.0"])[0] or 15.0)
    return engine.run_stress_test(
        scenario_id=scenario_id,
        capex_cut_pct=capex_cut,
        rate_hike_bps=rate_hike,
        semi_shock_pct=semi_shock,
    )


def bubble_tail_contagion(query: dict[str, list[str]]) -> dict[str, object]:
    engine = get_bubble_contagion()
    trigger = query.get("trigger", ["NVDA"])[0].strip().upper() or "NVDA"
    threshold = float(query.get("threshold", ["3.5"])[0] or 3.5)
    return engine.get_tail_contagion_matrix(trigger_symbol=trigger, threshold_pct=threshold)


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
            # StockLens API Routes
            if path == "/api/stocklens/overview":
                self.respond_json(stocklens_overview())
                return
            elif path == "/api/stocklens/graph":
                self.respond_json(stocklens_graph(query))
                return
            elif path == "/api/stocklens/paths":
                self.respond_json(stocklens_paths(query))
                return
            elif path == "/api/stocklens/centrality":
                self.respond_json(stocklens_centrality())
                return
            elif path == "/api/stocklens/market_model":
                self.respond_json(stocklens_market_model(query))
                return
            elif path == "/api/stocklens/event_study":
                self.respond_json(stocklens_event_study(query))
                return
            elif path == "/api/stocklens/lead_lag":
                self.respond_json(stocklens_lead_lag(query))
                return
            elif path == "/api/stocklens/universe_lead_lag":
                self.respond_json(stocklens_universe_lead_lag(query))
                return
            elif path == "/api/stocklens/evidence":
                self.respond_json(stocklens_evidence())
                return
            elif path == "/api/stocklens/contagion":
                self.respond_json(stocklens_contagion(query))
                return
            elif path == "/api/stocklens/sync_news_relations":
                self.respond_json(stocklens_sync_news_relations())
                return
            elif path == "/api/bubble/valuation":
                self.respond_json(bubble_valuation(query))
                return
            elif path == "/api/bubble/reverse_dcf":
                self.respond_json(bubble_reverse_dcf(query))
                return
            elif path == "/api/bubble/dotcom_compare":
                self.respond_json(bubble_dotcom_compare(query))
                return
            elif path == "/api/bubble/safe_havens":
                self.respond_json(bubble_safe_havens(query))
                return
            elif path == "/api/bubble/database_scan":
                self.respond_json(bubble_database_scan(query))
                return
            elif path == "/api/bubble/fragility_index":
                self.respond_json(bubble_fragility_index(query))
                return
            elif path == "/api/bubble/stress_test":
                self.respond_json(bubble_stress_test(query))
                return
            elif path == "/api/bubble/tail_contagion":
                self.respond_json(bubble_tail_contagion(query))
                return
            elif path == "/api/news":
                sym = query.get("symbol", ["AAPL"])[0].strip().upper()
                c_name = query.get("name", [""])[0].strip()
                limit = int(query.get("limit", ["12"])[0] or 12)
                self.respond_json(get_stock_news(sym, company_name=c_name, limit=limit))
                return
            elif path == "/api/news/backfill":
                sym = query.get("symbol", ["AAPL"])[0].strip().upper()
                months = int(query.get("months", ["12"])[0] or 12)
                self.respond_json(backfill_stock_news(sym, months=months))
                return

            # SQLite Database Routes
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
        candidate = (STATIC_DIR / relative).resolve()
        if not candidate.is_file():
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
