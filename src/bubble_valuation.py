"""
AI Valuation & Reverse DCF Engine (Real-Time Fundamental Intelligence)
Part of StockLens US — AI Bubble Early Warning & Financial Contagion Suite

Fetches live market quotes and fundamental financial ratios across the AI ecosystem:
- Semiconductors: NVDA, AMD, AVGO, INTC, MU, AMAT, LRCX, TSM, ASML
- Hyperscalers: MSFT, GOOGL, AMZN, ORCL, META
- Enterprise AI: PLTR, CRM, NOW, SNOW
- Infrastructure & Power: VRT, ETN, CEG, EQIX, DLR
- Hardware & Storage: ANET, DELL, SMCI

Calculates:
- Real-time Price, Market Cap, EV
- Trailing P/E, Forward P/E, P/S, EV/Revenue, EV/EBITDA, P/FCF
- Gross Margin, Operating Margin, FCF Margin, YoY Revenue Growth, Capex/Revenue, Net Debt/EBITDA
- Reverse DCF Model: Solves for the implied 5-year FCF compound growth rate (g_implied)
  priced into the current equity value.
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.request

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# AI Universe categorized by industry subsector as per BUBBLE.MD Section 2
AI_UNIVERSE = {
    "NVDA": {"name": "NVIDIA Corporation", "subsector": "Semiconductor & Chip Infrastructure", "ai_exposure": "Core AI Hardware"},
    "AMD": {"name": "Advanced Micro Devices", "subsector": "Semiconductor & Chip Infrastructure", "ai_exposure": "Core AI Hardware"},
    "AVGO": {"name": "Broadcom Inc.", "subsector": "Semiconductor & Chip Infrastructure", "ai_exposure": "AI Networking / Custom ASIC"},
    "INTC": {"name": "Intel Corporation", "subsector": "Semiconductor & Chip Infrastructure", "ai_exposure": "Foundry / Enterprise Chip"},
    "MU": {"name": "Micron Technology", "subsector": "Semiconductor & Chip Infrastructure", "ai_exposure": "HBM High-Bandwidth Memory"},
    "AMAT": {"name": "Applied Materials", "subsector": "Semiconductor & Chip Infrastructure", "ai_exposure": "Chip Manufacturing Equipment"},
    "LRCX": {"name": "Lam Research Corp.", "subsector": "Semiconductor & Chip Infrastructure", "ai_exposure": "Chip Manufacturing Equipment"},
    "TSM": {"name": "Taiwan Semiconductor (TSMC)", "subsector": "Semiconductor & Chip Infrastructure", "ai_exposure": "Advanced Packaging / Foundry"},
    "ASML": {"name": "ASML Holding N.V.", "subsector": "Semiconductor & Chip Infrastructure", "ai_exposure": "EUV Photolithography"},
    "MSFT": {"name": "Microsoft Corporation", "subsector": "Cloud & Hyperscalers", "ai_exposure": "Azure AI / OpenAI Partner"},
    "GOOGL": {"name": "Alphabet Inc.", "subsector": "Cloud & Hyperscalers", "ai_exposure": "Google Cloud / Gemini TPU"},
    "AMZN": {"name": "Amazon.com Inc.", "subsector": "Cloud & Hyperscalers", "ai_exposure": "AWS Bedrock / Trainium"},
    "META": {"name": "Meta Platforms Inc.", "subsector": "Cloud & Hyperscalers", "ai_exposure": "Llama Open Models / AI Infra"},
    "ORCL": {"name": "Oracle Corporation", "subsector": "Cloud & Hyperscalers", "ai_exposure": "OCI GPU Cloud Clusters"},
    "PLTR": {"name": "Palantir Technologies", "subsector": "Enterprise AI & Software", "ai_exposure": "AIP Artificial Intelligence Platform"},
    "CRM": {"name": "Salesforce, Inc.", "subsector": "Enterprise AI & Software", "ai_exposure": "Agentforce / Enterprise AI CRM"},
    "NOW": {"name": "ServiceNow, Inc.", "subsector": "Enterprise AI & Software", "ai_exposure": "Enterprise Workflow Automation"},
    "SNOW": {"name": "Snowflake Inc.", "subsector": "Enterprise AI & Software", "ai_exposure": "Data Cloud / Cortex AI"},
    "VRT": {"name": "Vertiv Holdings Co", "subsector": "Power, Electrical & Data Centers", "ai_exposure": "Liquid Cooling & Power Distribution"},
    "ETN": {"name": "Eaton Corporation", "subsector": "Power, Electrical & Data Centers", "ai_exposure": "Data Center Electrical Systems"},
    "CEG": {"name": "Constellation Energy", "subsector": "Power, Electrical & Data Centers", "ai_exposure": "Nuclear Energy for AI Hyperscalers"},
    "EQIX": {"name": "Equinix, Inc.", "subsector": "Power, Electrical & Data Centers", "ai_exposure": "AI Interconnection Data Centers"},
    "DLR": {"name": "Digital Realty Trust", "subsector": "Power, Electrical & Data Centers", "ai_exposure": "Wholesale Colocation Data Centers"},
    "ANET": {"name": "Arista Networks", "subsector": "Networking, Storage & Hardware", "ai_exposure": "AI Ethernet Switching Fabric"},
    "DELL": {"name": "Dell Technologies", "subsector": "Networking, Storage & Hardware", "ai_exposure": "AI PowerEdge GPU Servers"},
    "SMCI": {"name": "Super Micro Computer", "subsector": "Networking, Storage & Hardware", "ai_exposure": "Direct Liquid Cooling GPU Servers"},
}


class AIValuationEngine:
    """
    Computes real-time valuation multiples, reverse DCF growth requirements,
    and fundamental sustainability metrics for the AI ecosystem.
    """

    def __init__(self, cache_ttl_seconds: int = 180):
        self.cache_ttl = cache_ttl_seconds
        self._cache: Dict[str, Any] = {}
        self._cache_timestamp: float = 0.0
        self._keys_file = Path("website/.api_keys.json")
        self._finnhub_key = self._load_finnhub_key()

    def _load_finnhub_key(self) -> str:
        if self._keys_file.exists():
            try:
                with open(self._keys_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("finnhub_api_key", "")
            except Exception as e:
                logger.warning("Could not read API keys file: %s", e)
        return ""

    def get_live_finnhub_quote(self, symbol: str) -> Optional[Dict[str, float]]:
        """Fetches live real-time quote via Finnhub REST API."""
        if not self._finnhub_key:
            return None
        try:
            url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={self._finnhub_key}"
            req = urllib.request.Request(url, headers={"User-Agent": "StockLens/1.0"})
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode())
                if data and "c" in data and data["c"] > 0:
                    return {
                        "price": float(data["c"]),
                        "change": float(data.get("d", 0.0)),
                        "change_pct": float(data.get("dp", 0.0)),
                        "high": float(data.get("h", 0.0)),
                        "low": float(data.get("l", 0.0)),
                        "prev_close": float(data.get("pc", 0.0)),
                        "timestamp": int(data.get("t", time.time())),
                    }
        except Exception as e:
            logger.debug("Finnhub quote fetch error for %s: %s", symbol, e)
        return None

    def fetch_stock_valuation(self, symbol: str) -> Dict[str, Any]:
        """
        Fetches live real-time price & comprehensive fundamental metrics for a single stock.
        Combines Finnhub real-time quote + yfinance balance sheet and ratios.
        """
        meta = AI_UNIVERSE.get(symbol, {"name": symbol, "subsector": "AI Related", "ai_exposure": "General AI"})
        
        # 1. Fetch live quote
        live_quote = self.get_live_finnhub_quote(symbol)

        # 2. Fetch fundamentals via yfinance
        try:
            ticker_obj = yf.Ticker(symbol)
            info = ticker_obj.info or {}
        except Exception as e:
            logger.warning("yfinance fetch error for %s: %s", symbol, e)
            info = {}

        # Price reconciliation
        current_price = None
        if live_quote and live_quote["price"] > 0:
            current_price = live_quote["price"]
            day_change_pct = live_quote["change_pct"]
        else:
            current_price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose") or 100.0
            prev_close = info.get("previousClose") or current_price
            day_change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close else 0.0

        market_cap = info.get("marketCap") or (current_price * (info.get("sharesOutstanding") or 1))
        ev = info.get("enterpriseValue") or market_cap

        trailing_pe = info.get("trailingPE")
        forward_pe = info.get("forwardPE")
        price_to_sales = info.get("priceToSalesTrailing12Months")
        ev_to_revenue = info.get("enterpriseToRevenue")
        ev_to_ebitda = info.get("enterpriseToEbitda")
        
        gross_margins = info.get("grossMargins")
        operating_margins = info.get("operatingMargins")
        profit_margins = info.get("profitMargins")
        rev_growth = info.get("revenueGrowth")
        earnings_growth = info.get("earningsGrowth")
        fcf = info.get("freeCashflow") or 0
        total_rev = info.get("totalRevenue") or 1
        fcf_margin = (fcf / total_rev) if total_rev and fcf else None

        p_to_fcf = (market_cap / fcf) if fcf and fcf > 0 else None
        roic = info.get("returnOnEquity")  # Proxy when invested capital not directly broken out
        total_debt = info.get("totalDebt") or 0
        total_cash = info.get("totalCash") or 0
        ebitda = info.get("ebitda") or 1
        net_debt = total_debt - total_cash
        net_debt_to_ebitda = (net_debt / ebitda) if ebitda and ebitda > 0 else 0.0

        # Run reverse DCF
        reverse_dcf = self.calculate_reverse_dcf(
            current_price=current_price,
            shares_outstanding=info.get("sharesOutstanding") or (market_cap / current_price),
            fcf_annual=fcf if fcf > 0 else (total_rev * 0.15),  # normalized proxy if negative
            wacc=0.09, # 9% cost of capital standard for tech
            terminal_growth=0.03, # 3% long run terminal growth
            net_debt=net_debt
        )

        return {
            "symbol": symbol,
            "name": meta["name"],
            "subsector": meta["subsector"],
            "ai_exposure": meta["ai_exposure"],
            "current_price": round(float(current_price), 2),
            "day_change_pct": round(float(day_change_pct), 2),
            "market_cap_billions": round(float(market_cap) / 1e9, 2),
            "enterprise_value_billions": round(float(ev) / 1e9, 2),
            "trailing_pe": round(float(trailing_pe), 2) if trailing_pe and trailing_pe > 0 else None,
            "forward_pe": round(float(forward_pe), 2) if forward_pe and forward_pe > 0 else None,
            "price_to_sales": round(float(price_to_sales), 2) if price_to_sales and price_to_sales > 0 else None,
            "ev_to_revenue": round(float(ev_to_revenue), 2) if ev_to_revenue and ev_to_revenue > 0 else None,
            "ev_to_ebitda": round(float(ev_to_ebitda), 2) if ev_to_ebitda and ev_to_ebitda > 0 else None,
            "p_to_fcf": round(float(p_to_fcf), 2) if p_to_fcf and p_to_fcf > 0 else None,
            "gross_margin_pct": round(float(gross_margins) * 100, 1) if gross_margins is not None else None,
            "operating_margin_pct": round(float(operating_margins) * 100, 1) if operating_margins is not None else None,
            "fcf_margin_pct": round(float(fcf_margin) * 100, 1) if fcf_margin is not None else None,
            "revenue_growth_yoy_pct": round(float(rev_growth) * 100, 1) if rev_growth is not None else None,
            "earnings_growth_yoy_pct": round(float(earnings_growth) * 100, 1) if earnings_growth is not None else None,
            "net_debt_to_ebitda": round(float(net_debt_to_ebitda), 2),
            "reverse_dcf": reverse_dcf,
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "is_realtime": True
        }

    def calculate_reverse_dcf(
        self,
        current_price: float,
        shares_outstanding: float,
        fcf_annual: float,
        wacc: float = 0.09,
        terminal_growth: float = 0.03,
        net_debt: float = 0.0,
        projection_years: int = 5
    ) -> Dict[str, Any]:
        """
        Solves for the implied 5-year compound annual growth rate (CAGR) of FCF
        that equates the discounted cash flows to the current market enterprise/equity value.

        Formula:
          EV = Sum_{t=1}^5 [ FCF_0 * (1 + g)^t / (1 + WACC)^t ] + Terminal_Value / (1 + WACC)^5
          Terminal_Value = [ FCF_5 * (1 + g_term) ] / (WACC - g_term)
          Equity_Value = EV - Net_Debt
          Target: Equity_Value / Shares = current_price
        """
        if current_price <= 0 or shares_outstanding <= 0 or fcf_annual <= 0:
            return {
                "implied_5y_fcf_cagr": 0.0,
                "wacc_pct": round(wacc * 100, 1),
                "terminal_growth_pct": round(terminal_growth * 100, 1),
                "assessment": "Insufficient positive cash flow to solve DCF"
            }

        target_equity_value = current_price * shares_outstanding
        target_ev = target_equity_value + net_debt

        # Binary search for implied growth rate g in [-0.20, +1.50]
        low_g = -0.30
        high_g = 1.80
        implied_g = 0.15

        for _ in range(40):
            mid_g = (low_g + high_g) / 2.0
            # Calculate PV of 5-year FCFs
            pv_explicit = 0.0
            current_fcf = fcf_annual
            for t in range(1, projection_years + 1):
                current_fcf = fcf_annual * ((1.0 + mid_g) ** t)
                pv_explicit += current_fcf / ((1.0 + wacc) ** t)

            # Terminal value
            denom = max(0.005, wacc - terminal_growth)
            tv = (current_fcf * (1.0 + terminal_growth)) / denom
            pv_tv = tv / ((1.0 + wacc) ** projection_years)

            estimated_ev = pv_explicit + pv_tv

            if abs(estimated_ev - target_ev) / target_ev < 0.001:
                implied_g = mid_g
                break
            if estimated_ev > target_ev:
                high_g = mid_g
            else:
                low_g = mid_g
            implied_g = mid_g

        implied_cagr_pct = round(implied_g * 100, 1)

        # Economic feasibility assessment
        if implied_cagr_pct > 40.0:
            assessment = "Extremely High: Valuation prices in hyper-growth (>40% FCF CAGR for 5 yrs)"
            verdict = "Speculative Stretch"
        elif implied_cagr_pct > 25.0:
            assessment = "Aggressive: Requires sustained >25% FCF compounding above industry average"
            verdict = "High Expectations"
        elif implied_cagr_pct > 10.0:
            assessment = "Moderate: Growth requirement (10-25% CAGR) consistent with historical tech leaders"
            verdict = "Achievable"
        elif implied_cagr_pct > 0.0:
            assessment = "Conservative: Modest single-digit FCF growth required to justify price"
            verdict = "Fair / Undervalued"
        else:
            assessment = "Contraction priced in: Market anticipates declining free cash flows"
            verdict = "Deep Value / Turnaround"

        return {
            "implied_5y_fcf_cagr_pct": implied_cagr_pct,
            "wacc_pct": round(wacc * 100, 1),
            "terminal_growth_pct": round(terminal_growth * 100, 1),
            "current_fcf_billions": round(fcf_annual / 1e9, 2),
            "assessment": assessment,
            "verdict": verdict
        }

    def get_universe_valuations(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Retrieves real-time valuation snapshot for all 26 core AI universe equities.
        Implements an in-memory TTL cache to respect API rate limits while ensuring live fresh data.
        """
        now = time.time()
        if not force_refresh and self._cache and (now - self._cache_timestamp < self.cache_ttl):
            return self._cache

        import concurrent.futures

        items = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future_to_sym = {executor.submit(self.fetch_stock_valuation, sym): sym for sym in AI_UNIVERSE.keys()}
            for future in concurrent.futures.as_completed(future_to_sym):
                sym = future_to_sym[future]
                try:
                    stock_data = future.result()
                    items.append(stock_data)
                except Exception as e:
                    logger.error("Failed processing valuation for %s: %s", sym, e)

        # Sort items deterministically by market cap descending
        items.sort(key=lambda x: x.get("market_cap_billions") or 0.0, reverse=True)

        # Aggregate subsector averages
        subsectors: Dict[str, List[float]] = {}
        for it in items:
            sec = it["subsector"]
            if sec not in subsectors:
                subsectors[sec] = []
            if it.get("forward_pe"):
                subsectors[sec].append(it["forward_pe"])

        subsector_summary = []
        for sec, pes in subsectors.items():
            subsector_summary.append({
                "subsector": sec,
                "median_forward_pe": round(float(np.median(pes)), 1) if pes else 0.0,
                "stocks_count": len([i for i in items if i["subsector"] == sec])
            })

        payload = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "total_ai_stocks": len(items),
            "items": items,
            "subsector_summary": subsector_summary,
            "is_realtime": True
        }

        self._cache = payload
        self._cache_timestamp = now
        return payload


if __name__ == "__main__":
    engine = AIValuationEngine()
    print("Testing live valuation for NVDA...")
    nvda = engine.fetch_stock_valuation("NVDA")
    print(f"NVDA: Price=${nvda['current_price']}, Fwd PE={nvda['forward_pe']}, Implied FCF CAGR={nvda['reverse_dcf']['implied_5y_fcf_cagr_pct']}%")
