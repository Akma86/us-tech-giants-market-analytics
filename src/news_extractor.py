"""
Module: news_extractor.py
Description: Autonomous AI-powered Relation Extraction engine using OpenRouter LLMs.
             Analyzes live company news from Finnhub/NewsAPI to extract new supply chain,
             partnership, competition, and commodity exposure relationships.
Author: Akmal Yaasir Fauzaan
Project: StockLens US - Financial Knowledge Graph & Market Intelligence
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "database" / "us_equities.db"
def get_openrouter_api_key() -> str:
    """Retrieves OpenRouter key from environment or local gitignored website/.api_keys.json."""
    env_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if env_key:
        return env_key
    local_cfg = PROJECT_ROOT / "website" / ".api_keys.json"
    if local_cfg.exists():
        try:
            cfg = json.loads(local_cfg.read_text(encoding="utf-8"))
            return cfg.get("openrouter_api_key", "").strip()
        except Exception:
            pass
    return ""

# Canonical Entity Aliases for robust Entity Resolution
ENTITY_ALIASES: dict[str, str] = {
    # Companies
    "apple": "co_aapl", "aapl": "co_aapl", "iphone": "prod_smartphones",
    "microsoft": "co_msft", "msft": "co_msft", "azure": "prod_cloud_compute",
    "nvidia": "co_nvda", "nvda": "co_nvda", "gpu": "prod_gpu", "blackwell": "prod_gpu", "hopper": "prod_gpu",
    "amd": "co_amd", "advanced micro devices": "co_amd",
    "broadcom": "co_avgo", "avgo": "co_avgo",
    "google": "co_googl", "alphabet": "co_googl", "googl": "co_googl", "gcp": "prod_cloud_compute",
    "meta": "co_meta", "facebook": "co_meta", "llama": "co_meta",
    "amazon": "co_amzn", "amzn": "co_amzn", "aws": "prod_cloud_compute",
    "tesla": "co_tsla", "tsla": "co_tsla", "ev": "ind_auto_ev", "battery": "prod_ev_batteries",
    "jpmorgan": "co_jpm", "jpm": "co_jpm", "chase": "co_jpm",
    "bank of america": "co_bac", "bac": "co_bac",
    "exxon": "co_xom", "exxonmobil": "co_xom", "xom": "co_xom",
    "chevron": "co_cvx", "cvx": "co_cvx",
    "caterpillar": "co_cat", "cat": "co_cat",
    "boeing": "co_ba", "ba": "co_ba",
    "delta": "co_dal", "delta air lines": "co_dal", "dal": "co_dal",
    "freeport": "co_fcx", "fcx": "co_fcx",
    "eli lilly": "co_lly", "lly": "co_lly", "mounjaro": "prod_glp1", "zepbound": "prod_glp1",
    # Commodities
    "crude oil": "commodity_wti", "oil": "commodity_wti", "wti": "commodity_wti", "brent": "commodity_brent",
    "jet fuel": "commodity_jet_fuel", "kerosene": "commodity_jet_fuel",
    "copper": "commodity_copper", "lithium": "commodity_lithium", "gold": "commodity_gold",
    "natural gas": "commodity_gas", "silicon": "commodity_silicon",
    # Macro
    "treasury": "macro_us10y", "yield curve": "macro_us10y", "10-year": "macro_us10y",
    "fed": "macro_fed_funds", "federal reserve": "macro_fed_funds", "interest rate": "macro_fed_funds",
    "cpi": "macro_cpi", "inflation": "macro_cpi",
}


def init_dynamic_db(conn: sqlite3.Connection) -> None:
    """Ensures dynamic_relationships table exists in SQLite database."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dynamic_relationships (
            rel_id TEXT PRIMARY KEY,
            source_entity_id TEXT NOT NULL,
            target_entity_id TEXT NOT NULL,
            relationship_type TEXT NOT NULL,
            evidence_status TEXT DEFAULT 'ai_inferred',
            valid_from TEXT NOT NULL,
            valid_to TEXT,
            confidence REAL DEFAULT 0.85,
            source_url TEXT,
            headline TEXT,
            notes TEXT,
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()


def resolve_entity(name_or_text: str) -> Optional[str]:
    """Resolves natural language entity mention into canonical entity_id."""
    clean = re.sub(r"[^\w\s]", "", name_or_text.lower()).strip()
    if clean in ENTITY_ALIASES:
        return ENTITY_ALIASES[clean]
    for alias, eid in ENTITY_ALIASES.items():
        if alias in clean or clean in alias:
            return eid
    return None


def call_openrouter_extraction(headlines: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Calls OpenRouter with meta-llama/llama-3.3-70b-instruct to extract structured relations."""
    if not headlines:
        return []

    articles_text = "\n".join([
        f"- ID: {i+1} | Source: {h.get('source')} | Title: {h.get('headline')} | Summary: {h.get('summary', '')[:140]}"
        for i, h in enumerate(headlines[:8])
    ])

    system_prompt = (
        "You are an institutional financial knowledge graph relation extractor.\n"
        "Analyze the provided financial headlines and extract any verifiable business, economic, or supplier relationships.\n"
        "Supported relationship types:\n"
        "- SUPPLIES_TO (Supplier provides components/GPUs/hardware to customer)\n"
        "- BUYS_FROM (Customer purchases products/cloud compute/materials from vendor)\n"
        "- COMPETES_WITH (Direct commercial rivals in product/cloud/chip segment)\n"
        "- HAS_EXPOSURE_TO (Sensitivity of revenue or cost to commodity prices, interest rates, or fuel)\n"
        "- PARTNERSHIP_WITH (Strategic joint ventures or technology agreements)\n\n"
        "Output ONLY a JSON array of objects with keys:\n"
        "  'source': string (name of source company/commodity)\n"
        "  'target': string (name of target company/commodity/sector)\n"
        "  'relationship_type': string\n"
        "  'confidence': float (0.7 to 1.0)\n"
        "  'summary': string (1 concise sentence explaining the link)\n"
        "  'article_index': integer (1-based index matching input list)\n\n"
        "Do NOT include markdown wrappers, explanations, or prose outside the JSON."
    )

    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": "meta-llama/llama-3.3-70b-instruct",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract economic relationships from these news stories:\n\n{articles_text}"}
        ],
        "max_tokens": 600,
        "temperature": 0.1,
    }

    api_key = get_openrouter_api_key()
    if not api_key:
        print("Warning: OpenRouter API key not configured. Skipping LLM news extraction.")
        return []

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://127.0.0.1:8000",
            "X-Title": "US-Equity-Atlas-Extractor"
        }
    )

    with urllib.request.urlopen(req, timeout=14) as resp:
        resp_data = json.loads(resp.read().decode("utf-8"))

    content = resp_data["choices"][0]["message"]["content"].strip()
    
    # Clean potential markdown fences
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\n", "", content)
        content = re.sub(r"\n```$", "", content)

    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, list) else []
    except Exception as e:
        print(f"[NewsExtractor] Failed to parse LLM JSON: {e} | Content: {content[:100]}")
        return []


def scan_and_update_graph(sample_tickers: Optional[list[str]] = None) -> dict[str, Any]:
    """Scans news for target tickers, calls LLM extractor, and persists new edges."""
    tickers = sample_tickers or ["NVDA", "MSFT", "AAPL", "TSLA", "DAL", "XOM", "AMD", "GOOGL"]
    
    # Import news service safely
    try:
        from website.news_service import get_stock_news
    except ImportError:
        from news_service import get_stock_news

    all_articles = []
    for sym in tickers[:5]:  # Batch scan top active tickers
        res = get_stock_news(sym, limit=3)
        for item in res.get("items", []):
            item["ticker"] = sym
            all_articles.append(item)

    if not all_articles:
        return {"status": "no_news_found", "discovered": 0, "items": []}

    extracted = call_openrouter_extraction(all_articles)
    today_str = date.today().isoformat()
    discovered_edges = []

    with sqlite3.connect(DB_PATH) as conn:
        init_dynamic_db(conn)
        
        for rel in extracted:
            src_raw = rel.get("source", "")
            tgt_raw = rel.get("target", "")
            src_id = resolve_entity(src_raw)
            tgt_id = resolve_entity(tgt_raw)

            if not src_id or not tgt_id or src_id == tgt_id:
                continue

            rel_type = rel.get("relationship_type", "RELATED_TO").upper()
            confidence = float(rel.get("confidence", 0.85))
            summary = rel.get("summary", "")
            art_idx = int(rel.get("article_index", 1)) - 1
            article = all_articles[art_idx] if 0 <= art_idx < len(all_articles) else all_articles[0]

            rel_id = f"dyn_{src_id}_{tgt_id}_{int(time.time())}"

            conn.execute("""
                INSERT OR REPLACE INTO dynamic_relationships 
                (rel_id, source_entity_id, target_entity_id, relationship_type, evidence_status, valid_from, confidence, source_url, headline, notes)
                VALUES (?, ?, ?, ?, 'ai_inferred', ?, ?, ?, ?, ?)
            """, (
                rel_id, src_id, tgt_id, rel_type, today_str, confidence,
                article.get("url", ""), article.get("headline", ""), summary
            ))
            discovered_edges.append({
                "rel_id": rel_id,
                "source": src_id,
                "target": tgt_id,
                "type": rel_type,
                "confidence": confidence,
                "summary": summary,
                "headline": article.get("headline", "")
            })

        conn.commit()

    return {
        "status": "success",
        "discovered_count": len(discovered_edges),
        "edges": discovered_edges,
        "scanned_tickers": tickers[:5]
    }
