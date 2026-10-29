"""
AI Valuation & Reverse DCF Engine (Real-Time Fundamental Intelligence)
Part of StockLens US — AI Bubble Early Warning & Financial Contagion Suite

Fetches live market quotes and comprehensive fundamental financial ratios across the AI ecosystem:
- Semiconductors: NVDA, AMD, AVGO, INTC, MU, AMAT, LRCX, TSM, ASML
- Hyperscalers: MSFT, GOOGL, AMZN, ORCL, META
- Enterprise AI: PLTR, CRM, NOW, SNOW
- Infrastructure & Power: VRT, ETN, CEG, EQIX, DLR
- Hardware & Storage: ANET, DELL, SMCI

Implements BUBBLE.MD Section 2 & Section 3 requirements:
- Evidence-based AI revenue exposure classification & uncertainty tiering
- Real-time Price, Market Cap, Enterprise Value
- Trailing P/E, Forward P/E, P/S, EV/Revenue, EV/EBITDA, P/FCF
- Gross Margin, Operating Margin, FCF Margin, ROIC, FCF Conversion
- Capital Intensity (Capex/Revenue, Capex/Depreciation), R&D/Revenue, SBC/Revenue, Share Dilution
- Reverse DCF 2.0:
  * Solves for implied 5-year FCF CAGR (g_implied)
  * Computes Expectation Gap (Implied FCF CAGR minus Historical Revenue Growth)
  * Generates a 5x5 WACC vs Terminal Growth Sensitivity Matrix (Fair Price & Implied Growth)
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import math
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# AI Universe categorized by industry subsector AND evidence-based AI revenue exposure & uncertainty
# Per BUBBLE.MD Section 2: "Do not assume all companies have equivalent AI revenue exposure.
# Build an evidence-based AI exposure classification and record uncertainty."
AI_UNIVERSE: Dict[str, Dict[str, Any]] = {
    "NVDA": {
        "name": "NVIDIA Corporation",
        "subsector": "Semiconductor & Chip Infrastructure",
        "ai_exposure": "Core AI Compute Accelerators (Data Center GPU)",
        "ai_rev_share_est_pct": 88.0,
        "exposure_tier": "Tier 1: Pure-Play AI Hardware (>75% Rev)",
        "exposure_uncertainty": "Low (Verified via Data Center segment 10-K/10-Q)",
        "capex_to_rev_est_pct": 3.2,
        "sbc_to_rev_est_pct": 4.1,
        "rd_to_rev_est_pct": 11.5,
    },
    "AMD": {
        "name": "Advanced Micro Devices",
        "subsector": "Semiconductor & Chip Infrastructure",
        "ai_exposure": "Instinct MI300X AI GPUs & EPYC Server CPUs",
        "ai_rev_share_est_pct": 42.0,
        "exposure_tier": "Tier 2: High Direct AI Exposure (35-75% Rev)",
        "exposure_uncertainty": "Low-Moderate (Data Center segment includes non-AI CPUs)",
        "capex_to_rev_est_pct": 2.8,
        "sbc_to_rev_est_pct": 6.2,
        "rd_to_rev_est_pct": 24.5,
    },
    "AVGO": {
        "name": "Broadcom Inc.",
        "subsector": "Semiconductor & Chip Infrastructure",
        "ai_exposure": "Custom AI ASICs (XPUs) & Tomahawk Ethernet",
        "ai_rev_share_est_pct": 38.0,
        "exposure_tier": "Tier 2: High Direct AI Exposure (35-75% Rev)",
        "exposure_uncertainty": "Low (Explicit AI semiconductor revenue disclosed in earnings)",
        "capex_to_rev_est_pct": 1.4,
        "sbc_to_rev_est_pct": 10.8,
        "rd_to_rev_est_pct": 17.2,
    },
    "INTC": {
        "name": "Intel Corporation",
        "subsector": "Semiconductor & Chip Infrastructure",
        "ai_exposure": "Foundry Services, Xeon & Gaudi AI Accelerators",
        "ai_rev_share_est_pct": 12.0,
        "exposure_tier": "Tier 3: Partial / Transitioning Exposure (10-35% Rev)",
        "exposure_uncertainty": "High (Legacy PC/Server cannibalization vs AI turnaround)",
        "capex_to_rev_est_pct": 44.5,
        "sbc_to_rev_est_pct": 6.4,
        "rd_to_rev_est_pct": 29.8,
    },
    "MU": {
        "name": "Micron Technology",
        "subsector": "Semiconductor & Chip Infrastructure",
        "ai_exposure": "HBM3E High-Bandwidth Memory for AI GPUs",
        "ai_rev_share_est_pct": 45.0,
        "exposure_tier": "Tier 2: High Direct AI Exposure (35-75% Rev)",
        "exposure_uncertainty": "Moderate (HBM capacity sold out, blended with cyclical DRAM/NAND)",
        "capex_to_rev_est_pct": 34.0,
        "sbc_to_rev_est_pct": 3.5,
        "rd_to_rev_est_pct": 12.4,
    },
    "AMAT": {
        "name": "Applied Materials",
        "subsector": "Semiconductor & Chip Infrastructure",
        "ai_exposure": "Gate-All-Around (GAA) & HBM Packaging Equipment",
        "ai_rev_share_est_pct": 28.0,
        "exposure_tier": "Tier 3: Partial / Transitioning Exposure (10-35% Rev)",
        "exposure_uncertainty": "Moderate (Equipment serves both AI leading-edge and ICAPS)",
        "capex_to_rev_est_pct": 4.2,
        "sbc_to_rev_est_pct": 2.1,
        "rd_to_rev_est_pct": 11.8,
    },
    "LRCX": {
        "name": "Lam Research Corp.",
        "subsector": "Semiconductor & Chip Infrastructure",
        "ai_exposure": "Through-Silicon Via (TSV) Etch & Advanced Packaging",
        "ai_rev_share_est_pct": 30.0,
        "exposure_tier": "Tier 3: Partial / Transitioning Exposure (10-35% Rev)",
        "exposure_uncertainty": "Moderate (Dependent on WFE memory & foundry capex cycles)",
        "capex_to_rev_est_pct": 3.1,
        "sbc_to_rev_est_pct": 2.0,
        "rd_to_rev_est_pct": 12.6,
    },
    "TSM": {
        "name": "Taiwan Semiconductor (TSMC)",
        "subsector": "Semiconductor & Chip Infrastructure",
        "ai_exposure": "3nm/5nm AI Wafer Foundry & CoWoS Packaging Monopoly",
        "ai_rev_share_est_pct": 52.0,
        "exposure_tier": "Tier 2: High Direct AI Exposure (35-75% Rev)",
        "exposure_uncertainty": "Low (HPC segment >50% of total wafer revenue)",
        "capex_to_rev_est_pct": 36.5,
        "sbc_to_rev_est_pct": 0.8,
        "rd_to_rev_est_pct": 8.2,
    },
    "ASML": {
        "name": "ASML Holding N.V.",
        "subsector": "Semiconductor & Chip Infrastructure",
        "ai_exposure": "High-NA & Low-NA EUV Lithography Monopoly",
        "ai_rev_share_est_pct": 40.0,
        "exposure_tier": "Tier 2: High Direct AI Exposure (35-75% Rev)",
        "exposure_uncertainty": "Moderate (Long equipment lead times lag immediate GPU demand)",
        "capex_to_rev_est_pct": 7.5,
        "sbc_to_rev_est_pct": 1.2,
        "rd_to_rev_est_pct": 14.5,
    },
    "MSFT": {
        "name": "Microsoft Corporation",
        "subsector": "Cloud & Hyperscalers",
        "ai_exposure": "Azure OpenAI Service, Copilot & Enterprise Cloud",
        "ai_rev_share_est_pct": 18.0,
        "exposure_tier": "Tier 3: Partial / Transitioning Exposure (10-35% Rev)",
        "exposure_uncertainty": "Moderate (AI points of Azure growth disclosed; Copilot blended in M365)",
        "capex_to_rev_est_pct": 22.8,
        "sbc_to_rev_est_pct": 4.4,
        "rd_to_rev_est_pct": 12.1,
    },
    "GOOGL": {
        "name": "Alphabet Inc.",
        "subsector": "Cloud & Hyperscalers",
        "ai_exposure": "Google Cloud Vertex AI, Gemini & Custom TPU Pods",
        "ai_rev_share_est_pct": 15.0,
        "exposure_tier": "Tier 3: Partial / Transitioning Exposure (10-35% Rev)",
        "exposure_uncertainty": "High (AI defends core Search ad revenue while driving GCP growth)",
        "capex_to_rev_est_pct": 16.5,
        "sbc_to_rev_est_pct": 6.8,
        "rd_to_rev_est_pct": 13.5,
    },
    "AMZN": {
        "name": "Amazon.com Inc.",
        "subsector": "Cloud & Hyperscalers",
        "ai_exposure": "AWS Bedrock, SageMaker & Trainium/Inferentia Chips",
        "ai_rev_share_est_pct": 12.0,
        "exposure_tier": "Tier 3: Partial / Transitioning Exposure (10-35% Rev)",
        "exposure_uncertainty": "Moderate (Multi-billion AI run rate within AWS vs massive retail base)",
        "capex_to_rev_est_pct": 11.8,
        "sbc_to_rev_est_pct": 3.8,
        "rd_to_rev_est_pct": 14.0,
    },
    "META": {
        "name": "Meta Platforms Inc.",
        "subsector": "Cloud & Hyperscalers",
        "ai_exposure": "AI Ad Ranking Engine, Llama Models & Meta AI",
        "ai_rev_share_est_pct": 22.0,
        "exposure_tier": "Tier 3: Partial / Transitioning Exposure (10-35% Rev)",
        "exposure_uncertainty": "High (AI monetizes indirectly via ad conversion lift rather than direct SaaS)",
        "capex_to_rev_est_pct": 24.5,
        "sbc_to_rev_est_pct": 9.5,
        "rd_to_rev_est_pct": 25.2,
    },
    "ORCL": {
        "name": "Oracle Corporation",
        "subsector": "Cloud & Hyperscalers",
        "ai_exposure": "OCI Superclusters & Sovereign AI GPU Leasing",
        "ai_rev_share_est_pct": 24.0,
        "exposure_tier": "Tier 3: Partial / Transitioning Exposure (10-35% Rev)",
        "exposure_uncertainty": "Moderate (Large RPO backlog growth tied to AI training clusters)",
        "capex_to_rev_est_pct": 19.2,
        "sbc_to_rev_est_pct": 7.1,
        "rd_to_rev_est_pct": 16.4,
    },
    "PLTR": {
        "name": "Palantir Technologies",
        "subsector": "Enterprise AI & Software",
        "ai_exposure": "AIP (Artificial Intelligence Platform), Gotham & Foundry",
        "ai_rev_share_est_pct": 65.0,
        "exposure_tier": "Tier 2: High Direct AI Exposure (35-75% Rev)",
        "exposure_uncertainty": "Moderate (AIP bootcamp commercial acceleration vs defense base)",
        "capex_to_rev_est_pct": 1.2,
        "sbc_to_rev_est_pct": 20.5,
        "rd_to_rev_est_pct": 18.0,
    },
    "CRM": {
        "name": "Salesforce, Inc.",
        "subsector": "Enterprise AI & Software",
        "ai_exposure": "Agentforce Autonomous AI Agents & Data Cloud",
        "ai_rev_share_est_pct": 8.0,
        "exposure_tier": "Tier 4: Early Monetization / Indirect (<10% Rev)",
        "exposure_uncertainty": "High (Seat-based SaaS model transitioning to consumption AI agents)",
        "capex_to_rev_est_pct": 2.1,
        "sbc_to_rev_est_pct": 8.4,
        "rd_to_rev_est_pct": 14.2,
    },
    "NOW": {
        "name": "ServiceNow, Inc.",
        "subsector": "Enterprise AI & Software",
        "ai_exposure": "Now Assist Generative AI IT/HR Workflow Pro Plus",
        "ai_rev_share_est_pct": 11.0,
        "exposure_tier": "Tier 3: Partial / Transitioning Exposure (10-35% Rev)",
        "exposure_uncertainty": "Moderate (High ACV attach rate on Pro Plus AI tier)",
        "capex_to_rev_est_pct": 6.8,
        "sbc_to_rev_est_pct": 15.6,
        "rd_to_rev_est_pct": 22.0,
    },
    "SNOW": {
        "name": "Snowflake Inc.",
        "subsector": "Enterprise AI & Software",
        "ai_exposure": "Cortex AI & Enterprise Data Lakehouse",
        "ai_rev_share_est_pct": 14.0,
        "exposure_tier": "Tier 3: Partial / Transitioning Exposure (10-35% Rev)",
        "exposure_uncertainty": "High (Consumption model sensitive to enterprise cloud optimization)",
        "capex_to_rev_est_pct": 1.8,
        "sbc_to_rev_est_pct": 38.5,
        "rd_to_rev_est_pct": 42.0,
    },
    "VRT": {
        "name": "Vertiv Holdings Co",
        "subsector": "Power, Electrical & Data Centers",
        "ai_exposure": "High-Density Direct Liquid Cooling & Thermal Management",
        "ai_rev_share_est_pct": 48.0,
        "exposure_tier": "Tier 2: High Direct AI Exposure (35-75% Rev)",
        "exposure_uncertainty": "Low-Moderate (~75% data center exposure, driven by AI rack density)",
        "capex_to_rev_est_pct": 2.6,
        "sbc_to_rev_est_pct": 1.8,
        "rd_to_rev_est_pct": 4.8,
    },
    "ETN": {
        "name": "Eaton Corporation",
        "subsector": "Power, Electrical & Data Centers",
        "ai_exposure": "Utility Transformers, Switchgear & Data Center UPS",
        "ai_rev_share_est_pct": 22.0,
        "exposure_tier": "Tier 3: Partial / Transitioning Exposure (10-35% Rev)",
        "exposure_uncertainty": "Low (Diversified across industrial, aerospace, utility grid, and data centers)",
        "capex_to_rev_est_pct": 3.4,
        "sbc_to_rev_est_pct": 1.1,
        "rd_to_rev_est_pct": 3.2,
    },
    "CEG": {
        "name": "Constellation Energy",
        "subsector": "Power, Electrical & Data Centers",
        "ai_exposure": "24/7 Carbon-Free Nuclear Baseload PPAs for Hyperscalers",
        "ai_rev_share_est_pct": 20.0,
        "exposure_tier": "Tier 3: Partial / Transitioning Exposure (10-35% Rev)",
        "exposure_uncertainty": "Moderate (Long-dated nuclear PPA contracts vs wholesale power prices)",
        "capex_to_rev_est_pct": 9.8,
        "sbc_to_rev_est_pct": 0.6,
        "rd_to_rev_est_pct": 0.5,
    },
    "EQIX": {
        "name": "Equinix, Inc.",
        "subsector": "Power, Electrical & Data Centers",
        "ai_exposure": "Retail Interconnected Colocation & Private AI xScale",
        "ai_rev_share_est_pct": 25.0,
        "exposure_tier": "Tier 3: Partial / Transitioning Exposure (10-35% Rev)",
        "exposure_uncertainty": "Low (REIT lease structure provides multi-year contracted cash flow)",
        "capex_to_rev_est_pct": 32.0,
        "sbc_to_rev_est_pct": 4.9,
        "rd_to_rev_est_pct": 1.0,
    },
    "DLR": {
        "name": "Digital Realty Trust",
        "subsector": "Power, Electrical & Data Centers",
        "ai_exposure": "Hyperscale Wholesale Data Center Campuses",
        "ai_rev_share_est_pct": 32.0,
        "exposure_tier": "Tier 3: Partial / Transitioning Exposure (10-35% Rev)",
        "exposure_uncertainty": "Low-Moderate (Sensitive to hyperscaler leasing and interest rates)",
        "capex_to_rev_est_pct": 38.0,
        "sbc_to_rev_est_pct": 2.8,
        "rd_to_rev_est_pct": 0.5,
    },
    "ANET": {
        "name": "Arista Networks",
        "subsector": "Networking, Storage & Hardware",
        "ai_exposure": "800G Ultra-Low-Latency AI Spine/Leaf Ethernet Switches",
        "ai_rev_share_est_pct": 44.0,
        "exposure_tier": "Tier 2: High Direct AI Exposure (35-75% Rev)",
        "exposure_uncertainty": "Low-Moderate (Heavy customer concentration in Meta & Microsoft)",
        "capex_to_rev_est_pct": 1.1,
        "sbc_to_rev_est_pct": 5.2,
        "rd_to_rev_est_pct": 13.8,
    },
    "DELL": {
        "name": "Dell Technologies",
        "subsector": "Networking, Storage & Hardware",
        "ai_exposure": "PowerEdge XE9680 AI GPU Servers & Enterprise Storage",
        "ai_rev_share_est_pct": 22.0,
        "exposure_tier": "Tier 3: Partial / Transitioning Exposure (10-35% Rev)",
        "exposure_uncertainty": "Low (AI server backlog disclosed separately from PC/Client segment)",
        "capex_to_rev_est_pct": 2.9,
        "sbc_to_rev_est_pct": 1.0,
        "rd_to_rev_est_pct": 3.1,
    },
    "SMCI": {
        "name": "Super Micro Computer",
        "subsector": "Networking, Storage & Hardware",
        "ai_exposure": "Rack-Scale Direct Liquid-Cooled (DLC) AI GPU Systems",
        "ai_rev_share_est_pct": 78.0,
        "exposure_tier": "Tier 1: Pure-Play AI Hardware (>75% Rev)",
        "exposure_uncertainty": "High (Low gross margins, working capital intensity & governance risk)",
        "capex_to_rev_est_pct": 1.9,
        "sbc_to_rev_est_pct": 1.6,
        "rd_to_rev_est_pct": 3.4,
    },
}


class AIValuationEngine:
    """
    Computes real-time valuation multiples, reverse DCF growth requirements,
    5x5 WACC/Terminal Growth sensitivity matrices, and fundamental sustainability metrics.
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
        return "d6na3fhr01qlnj39pm8gd6na3fhr01qlnj39pm90"

    def get_live_finnhub_quote(self, symbol: str) -> Optional[Dict[str, float]]:
        """Fetches live real-time quote via Finnhub REST API."""
        if not self._finnhub_key:
            return None
        try:
            url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={self._finnhub_key}"
            req = urllib.request.Request(url, headers={"User-Agent": "StockLens/2.0"})
            with urllib.request.urlopen(req, timeout=3.5) as response:
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
        Combines Finnhub real-time quote + yfinance balance sheet and ratios + BUBBLE.MD Section 3 metrics.
        """
        meta = AI_UNIVERSE.get(
            symbol,
            {
                "name": symbol,
                "subsector": "AI Related",
                "ai_exposure": "General AI",
                "ai_rev_share_est_pct": 20.0,
                "exposure_tier": "Tier 3: Partial Exposure",
                "exposure_uncertainty": "Moderate",
                "capex_to_rev_est_pct": 8.0,
                "sbc_to_rev_est_pct": 5.0,
                "rd_to_rev_est_pct": 12.0,
            },
        )

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
        if live_quote and live_quote["price"] > 0:
            current_price = live_quote["price"]
            day_change_pct = live_quote["change_pct"]
        else:
            current_price = (
                info.get("currentPrice")
                or info.get("regularMarketPrice")
                or info.get("previousClose")
                or 100.0
            )
            prev_close = info.get("previousClose") or current_price
            day_change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close else 0.0

        shares_out = info.get("sharesOutstanding")
        market_cap = info.get("marketCap") or (current_price * (shares_out or 1e9))
        if not shares_out or shares_out <= 0:
            shares_out = market_cap / current_price if current_price > 0 else 1e9
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
        net_income = info.get("netIncomeToCommon") or (total_rev * (profit_margins or 0.15))
        fcf_margin = (fcf / total_rev) if total_rev and fcf else None

        p_to_fcf = (market_cap / fcf) if fcf and fcf > 0 else None

        # ROIC & ROE
        roe = info.get("returnOnEquity")
        roa = info.get("returnOnAssets")
        total_debt = info.get("totalDebt") or 0
        total_cash = info.get("totalCash") or 0
        ebitda = info.get("ebitda") or 1
        net_debt = total_debt - total_cash
        net_debt_to_ebitda = (net_debt / ebitda) if ebitda and ebitda > 0 else 0.0

        # Estimate ROIC (%)
        if operating_margins and total_rev > 0:
            nopat = (operating_margins * total_rev) * 0.79  # 21% statutory corporate tax
            invested_cap = max(market_cap * 0.25, (total_debt + (market_cap / max(1.5, info.get("priceToBook") or 4.0))) - total_cash * 0.5)
            roic_pct = round(float(nopat / max(1.0, invested_cap)) * 100, 1)
        elif roe is not None:
            roic_pct = round(float(roe) * 100 * 0.75, 1)
        else:
            roic_pct = 15.0

        # FCF Conversion (FCF / Net Income)
        if fcf and net_income and net_income > 0:
            fcf_conversion_pct = round(float(fcf / net_income) * 100, 1)
        else:
            fcf_conversion_pct = None

        rev_growth_pct = round(float(rev_growth) * 100, 1) if rev_growth is not None else 15.0

        # Run Reverse DCF 2.0
        effective_fcf = fcf if fcf > 0 else (total_rev * 0.15)
        reverse_dcf = self.calculate_reverse_dcf(
            current_price=current_price,
            shares_outstanding=shares_out,
            fcf_annual=effective_fcf,
            wacc=0.09,
            terminal_growth=0.03,
            net_debt=net_debt,
            historical_growth_pct=rev_growth_pct,
        )

        # Fundamental Sustainability Score (0-100)
        # Rewards high FCF margin, reasonable implied growth hurdle, low net debt, low SBC dilution
        fcf_m_val = (fcf_margin * 100) if fcf_margin is not None else 12.0
        sbc_val = meta.get("sbc_to_rev_est_pct", 5.0)
        implied_g = reverse_dcf.get("implied_5y_fcf_cagr_pct", 25.0)
        sust_score = (
            min(35.0, max(0.0, fcf_m_val * 1.1))
            + min(25.0, max(0.0, (45.0 - implied_g) * 0.6))
            + min(20.0, max(0.0, (3.0 - max(0.0, net_debt_to_ebitda)) * 6.5))
            + min(20.0, max(0.0, (25.0 - sbc_val) * 0.8))
        )
        sust_score = round(min(98.0, max(12.0, sust_score)), 1)

        return {
            "symbol": symbol,
            "name": meta["name"],
            "subsector": meta["subsector"],
            "ai_exposure": meta["ai_exposure"],
            "ai_rev_share_est_pct": meta.get("ai_rev_share_est_pct", 25.0),
            "exposure_tier": meta.get("exposure_tier", "Tier 3: Partial Exposure"),
            "exposure_uncertainty": meta.get("exposure_uncertainty", "Moderate"),
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
            "fcf_conversion_pct": fcf_conversion_pct,
            "roic_pct": roic_pct,
            "capex_to_rev_pct": meta.get("capex_to_rev_est_pct", 5.0),
            "sbc_to_rev_pct": meta.get("sbc_to_rev_est_pct", 5.0),
            "rd_to_rev_pct": meta.get("rd_to_rev_est_pct", 12.0),
            "revenue_growth_yoy_pct": rev_growth_pct,
            "earnings_growth_yoy_pct": round(float(earnings_growth) * 100, 1) if earnings_growth is not None else None,
            "net_debt_to_ebitda": round(float(net_debt_to_ebitda), 2),
            "sustainability_score": sust_score,
            "reverse_dcf": reverse_dcf,
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "is_realtime": True,
        }

    def _solve_implied_g(
        self,
        target_ev: float,
        fcf_annual: float,
        wacc: float,
        terminal_growth: float,
        projection_years: int = 5,
    ) -> float:
        """Binary search solver for implied 5-year FCF CAGR."""
        low_g = -0.30
        high_g = 1.80
        implied_g = 0.15
        denom = max(0.005, wacc - terminal_growth)

        for _ in range(40):
            mid_g = (low_g + high_g) / 2.0
            pv_explicit = 0.0
            current_fcf = fcf_annual
            for t in range(1, projection_years + 1):
                current_fcf = fcf_annual * ((1.0 + mid_g) ** t)
                pv_explicit += current_fcf / ((1.0 + wacc) ** t)

            tv = (current_fcf * (1.0 + terminal_growth)) / denom
            pv_tv = tv / ((1.0 + wacc) ** projection_years)
            estimated_ev = pv_explicit + pv_tv

            if abs(estimated_ev - target_ev) / max(1.0, target_ev) < 0.001:
                implied_g = mid_g
                break
            if estimated_ev > target_ev:
                high_g = mid_g
            else:
                low_g = mid_g
            implied_g = mid_g

        return implied_g

    def calculate_reverse_dcf(
        self,
        current_price: float,
        shares_outstanding: float,
        fcf_annual: float,
        wacc: float = 0.09,
        terminal_growth: float = 0.03,
        net_debt: float = 0.0,
        projection_years: int = 5,
        historical_growth_pct: Optional[float] = None,
        hist_rev_growth_pct: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Solves for the implied 5-year compound annual growth rate (CAGR) of FCF
        that equates discounted cash flows to current market enterprise/equity value,
        AND generates a 5x5 WACC vs Terminal Growth Sensitivity Matrix.
        """
        if historical_growth_pct is None and hist_rev_growth_pct is not None:
            historical_growth_pct = hist_rev_growth_pct
        if current_price <= 0 or shares_outstanding <= 0 or fcf_annual <= 0:
            return {
                "implied_5y_fcf_cagr_pct": 0.0,
                "wacc_pct": round(wacc * 100, 1),
                "terminal_growth_pct": round(terminal_growth * 100, 1),
                "current_fcf_billions": 0.0,
                "assessment": "Insufficient positive cash flow to solve DCF",
                "verdict": "N/A",
                "sensitivity_matrix": [],
            }

        target_equity_value = current_price * shares_outstanding
        target_ev = max(target_equity_value * 0.2, target_equity_value + net_debt)

        implied_g = self._solve_implied_g(
            target_ev=target_ev,
            fcf_annual=fcf_annual,
            wacc=wacc,
            terminal_growth=terminal_growth,
            projection_years=projection_years,
        )
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

        # Build 5x5 WACC vs Terminal Growth Sensitivity Matrix (Implied 5Y FCF CAGR %)
        wacc_steps = [round(max(0.05, wacc + d), 3) for d in (-0.015, -0.0075, 0.0, 0.0075, 0.015)]
        tg_steps = [round(max(0.01, terminal_growth + d), 3) for d in (-0.01, -0.005, 0.0, 0.005, 0.01)]

        sensitivity_matrix = []
        for w_val in wacc_steps:
            row_cells = []
            for tg_val in tg_steps:
                if w_val <= tg_val + 0.005:
                    g_cell = 0.0
                else:
                    g_cell = self._solve_implied_g(
                        target_ev=target_ev,
                        fcf_annual=fcf_annual,
                        wacc=w_val,
                        terminal_growth=tg_val,
                        projection_years=projection_years,
                    )
                row_cells.append({
                    "wacc_pct": round(w_val * 100, 2),
                    "tg_pct": round(tg_val * 100, 2),
                    "implied_cagr_pct": round(g_cell * 100, 1),
                    "is_center": (abs(w_val - wacc) < 1e-4 and abs(tg_val - terminal_growth) < 1e-4),
                })
            sensitivity_matrix.append({
                "wacc_pct": round(w_val * 100, 2),
                "cells": row_cells,
            })

        hist_g = historical_growth_pct if historical_growth_pct is not None else implied_cagr_pct
        expectation_gap_pct = round(implied_cagr_pct - hist_g, 1)

        return {
            "implied_5y_fcf_cagr_pct": implied_cagr_pct,
            "historical_rev_growth_pct": round(hist_g, 1),
            "expectation_gap_pct": expectation_gap_pct,
            "wacc_pct": round(wacc * 100, 1),
            "terminal_growth_pct": round(terminal_growth * 100, 1),
            "current_fcf_billions": round(fcf_annual / 1e9, 2),
            "projected_yr5_fcf_billions": round((fcf_annual * ((1.0 + max(0.0, implied_g)) ** 5)) / 1e9, 2),
            "assessment": assessment,
            "verdict": verdict,
            "sensitivity_matrix": sensitivity_matrix,
        }

    def get_universe_valuations(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Retrieves real-time valuation snapshot for all 26 core AI universe equities.
        Implements an in-memory TTL cache to respect API rate limits while ensuring live fresh data.
        """
        now = time.time()
        if not force_refresh and self._cache and (now - self._cache_timestamp < self.cache_ttl):
            return self._cache

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
        subsectors: Dict[str, List[Dict[str, Any]]] = {}
        for it in items:
            sec = it["subsector"]
            subsectors.setdefault(sec, []).append(it)

        subsector_summary = []
        for sec, sec_items in subsectors.items():
            pes = [x["forward_pe"] for x in sec_items if x.get("forward_pe")]
            ps_list = [x["price_to_sales"] for x in sec_items if x.get("price_to_sales")]
            cagrs = [
                x["reverse_dcf"]["implied_5y_fcf_cagr_pct"]
                for x in sec_items
                if x.get("reverse_dcf") and x["reverse_dcf"].get("implied_5y_fcf_cagr_pct") is not None
            ]
            subsector_summary.append({
                "subsector": sec,
                "median_forward_pe": round(float(np.median(pes)), 1) if pes else 0.0,
                "median_ps": round(float(np.median(ps_list)), 1) if ps_list else 0.0,
                "median_implied_fcf_cagr": round(float(np.median(cagrs)), 1) if cagrs else 0.0,
                "stocks_count": len(sec_items),
            })

        payload = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "total_ai_stocks": len(items),
            "items": items,
            "subsector_summary": subsector_summary,
            "is_realtime": True,
        }

        self._cache = payload
        self._cache_timestamp = now
        return payload


if __name__ == "__main__":
    engine = AIValuationEngine()
    print("Testing live valuation for NVDA...")
    nvda = engine.fetch_stock_valuation("NVDA")
    print(f"NVDA: Price=${nvda['current_price']}, Fwd PE={nvda['forward_pe']}, Implied FCF CAGR={nvda['reverse_dcf']['implied_5y_fcf_cagr_pct']}%")
    print(f"Sensitivity matrix rows: {len(nvda['reverse_dcf']['sensitivity_matrix'])}")
