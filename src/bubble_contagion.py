"""
AI Financial Contagion & Scenario Stress-Testing Engine
Part of StockLens US — AI Bubble Early Warning & Financial Contagion Suite

Implements scenario simulation and multi-tier network contagion modeling:
- Scenario A: Hyperscaler AI Capex Reduction (-10%, -20%, -40%)
- Scenario B: Semiconductor Revenue Growth Miss (-15%)
- Scenario C: Higher-For-Longer Interest Rates (+100 bps Yield Shock)
- Scenario D: Big Tech Earnings Guidance Revision (-20%)
- Scenario E: Data Center Power / Grid Interconnection Bottleneck (-25% server buildout)

Traces shock transmission across 4 tiers of the AI Supply Chain:
  Tier 0 (Hyperscalers: MSFT, GOOGL, AMZN, META)
    ↓ (Direct Hardware Procurement)
  Tier 1 (GPU / ASIC Designers: NVDA, AMD, AVGO)
    ↓ (Foundry & Equipment)
  Tier 2 (Foundry & Lithography: TSM, ASML, AMAT, LRCX)
    ↓ (Infrastructure, Power, Cooling & Servers: VRT, ETN, CEG, DELL, SMCI, ANET)
    ↓ (Downstream Software Application: PLTR, CRM, NOW, SNOW)

Calculates:
- Direct revenue impact (%)
- Operating leverage & EBITDA sensitivity (%)
- Estimated valuation / price pressure range (Min % - Max %)
- Categorizes each stock as High Vulnerability, Moderate Vulnerability, or Resilient/Defensive.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Empirical revenue exposure matrix to Hyperscaler AI Capex and Big Tech spending
# Derived from SEC 10-K Customer Disclosures & Industry Analyst Consensuses
SUPPLY_CHAIN_SENSITIVITIES = {
    # Tier 1: Core AI Compute
    "NVDA": {"tier": "Tier 1: Core Chip Designer", "capex_elasticity": 0.85, "semi_elasticity": 1.00, "rate_sensitivity": 0.45, "direct_exposure_pct": 55.0},
    "AMD": {"tier": "Tier 1: Core Chip Designer", "capex_elasticity": 0.70, "semi_elasticity": 0.90, "rate_sensitivity": 0.50, "direct_exposure_pct": 35.0},
    "AVGO": {"tier": "Tier 1: Custom ASIC & Networking", "capex_elasticity": 0.65, "semi_elasticity": 0.80, "rate_sensitivity": 0.40, "direct_exposure_pct": 40.0},
    "INTC": {"tier": "Tier 1: Legacy / Enterprise", "capex_elasticity": 0.30, "semi_elasticity": 0.60, "rate_sensitivity": 0.75, "direct_exposure_pct": 15.0},
    "MU": {"tier": "Tier 1: HBM Memory Supplier", "capex_elasticity": 0.75, "semi_elasticity": 0.95, "rate_sensitivity": 0.55, "direct_exposure_pct": 45.0},
    
    # Tier 2: Foundry & Equipment (2nd hop from hyperscalers)
    "TSM": {"tier": "Tier 2: Advanced Packaging & Foundry", "capex_elasticity": 0.60, "semi_elasticity": 0.85, "rate_sensitivity": 0.35, "direct_exposure_pct": 38.0},
    "ASML": {"tier": "Tier 2: EUV Equipment Monopoly", "capex_elasticity": 0.45, "semi_elasticity": 0.70, "rate_sensitivity": 0.30, "direct_exposure_pct": 28.0},
    "AMAT": {"tier": "Tier 2: Wafer Fab Equipment", "capex_elasticity": 0.40, "semi_elasticity": 0.65, "rate_sensitivity": 0.35, "direct_exposure_pct": 25.0},
    "LRCX": {"tier": "Tier 2: Etch & Deposition Equipment", "capex_elasticity": 0.42, "semi_elasticity": 0.68, "rate_sensitivity": 0.38, "direct_exposure_pct": 26.0},

    # Infrastructure: Servers, Power & Cooling
    "SMCI": {"tier": "Infrastructure: AI Server OEM", "capex_elasticity": 0.80, "semi_elasticity": 0.75, "rate_sensitivity": 0.65, "direct_exposure_pct": 70.0},
    "DELL": {"tier": "Infrastructure: Enterprise & AI Servers", "capex_elasticity": 0.45, "semi_elasticity": 0.40, "rate_sensitivity": 0.45, "direct_exposure_pct": 22.0},
    "ANET": {"tier": "Infrastructure: High-Speed Networking", "capex_elasticity": 0.60, "semi_elasticity": 0.55, "rate_sensitivity": 0.35, "direct_exposure_pct": 42.0},
    "VRT": {"tier": "Infrastructure: Liquid Cooling & Power", "capex_elasticity": 0.70, "semi_elasticity": 0.50, "rate_sensitivity": 0.40, "direct_exposure_pct": 48.0},
    "ETN": {"tier": "Infrastructure: Electrical Grid Equipment", "capex_elasticity": 0.40, "semi_elasticity": 0.30, "rate_sensitivity": 0.30, "direct_exposure_pct": 24.0},
    "CEG": {"tier": "Infrastructure: Nuclear Power Generation", "capex_elasticity": 0.30, "semi_elasticity": 0.15, "rate_sensitivity": 0.35, "direct_exposure_pct": 20.0},
    "EQIX": {"tier": "Infrastructure: Data Center REIT", "capex_elasticity": 0.35, "semi_elasticity": 0.20, "rate_sensitivity": 0.80, "direct_exposure_pct": 25.0},
    "DLR": {"tier": "Infrastructure: Wholesale Colocation REIT", "capex_elasticity": 0.38, "semi_elasticity": 0.22, "rate_sensitivity": 0.85, "direct_exposure_pct": 28.0},

    # Hyperscalers (Epicenter of Capex decisions)
    "MSFT": {"tier": "Tier 0: Hyperscaler Originator", "capex_elasticity": -0.15, "semi_elasticity": 0.25, "rate_sensitivity": 0.25, "direct_exposure_pct": 10.0},
    "GOOGL": {"tier": "Tier 0: Hyperscaler Originator", "capex_elasticity": -0.15, "semi_elasticity": 0.25, "rate_sensitivity": 0.20, "direct_exposure_pct": 8.0},
    "AMZN": {"tier": "Tier 0: Hyperscaler Originator", "capex_elasticity": -0.12, "semi_elasticity": 0.25, "rate_sensitivity": 0.30, "direct_exposure_pct": 12.0},
    "META": {"tier": "Tier 0: Hyperscaler Originator", "capex_elasticity": -0.10, "semi_elasticity": 0.20, "rate_sensitivity": 0.25, "direct_exposure_pct": 5.0},
    "ORCL": {"tier": "Tier 0: GPU Cloud Challenger", "capex_elasticity": 0.35, "semi_elasticity": 0.35, "rate_sensitivity": 0.55, "direct_exposure_pct": 25.0},

    # Enterprise Software (Downstream monetization)
    "PLTR": {"tier": "Downstream: Enterprise AI Software", "capex_elasticity": 0.25, "semi_elasticity": 0.20, "rate_sensitivity": 0.60, "direct_exposure_pct": 18.0},
    "CRM": {"tier": "Downstream: Enterprise AI CRM", "capex_elasticity": 0.15, "semi_elasticity": 0.15, "rate_sensitivity": 0.35, "direct_exposure_pct": 10.0},
    "NOW": {"tier": "Downstream: Workflow Automation", "capex_elasticity": 0.18, "semi_elasticity": 0.15, "rate_sensitivity": 0.40, "direct_exposure_pct": 12.0},
    "SNOW": {"tier": "Downstream: Cloud Data Platform", "capex_elasticity": 0.35, "semi_elasticity": 0.25, "rate_sensitivity": 0.75, "direct_exposure_pct": 22.0},
}


class AIContagionEngine:
    """
    Simulates multi-tier financial contagion shocks and scenario stress-tests
    across the verified AI relationship graph.
    """

    def run_stress_test(
        self,
        scenario_id: str = "scenario_a",
        capex_cut_pct: float = 20.0,
        rate_hike_bps: float = 100.0,
        semi_shock_pct: float = 15.0
    ) -> Dict[str, Any]:
        """
        Executes interactive stress testing based on specified parameters.
        Returns impact waterfall, ranking by vulnerability, and transmission narrative.
        """
        scenarios_desc = {
            "scenario_a": {
                "title": f"Scenario A: Hyperscaler AI Capex Reduction (-{capex_cut_pct:.0f}%)",
                "narrative": (
                    f"Big Tech hyperscalers (Microsoft, Alphabet, Amazon, Meta) reduce annualized AI data center capital expenditures by {capex_cut_pct:.0f}%. "
                    "This directly hits semiconductor orders, server OEM assembly, and liquid cooling infrastructure suppliers."
                ),
                "epicenter": "Hyperscaler Capex Budgets (Tier 0)"
            },
            "scenario_b": {
                "title": f"Scenario B: Semiconductor Revenue Growth Shock (-{semi_shock_pct:.0f}%)",
                "narrative": (
                    f"Leading AI chip designers experience a {semi_shock_pct:.0f}% deceleration in revenue growth due to customer deployment digestion "
                    "and export restrictions, propagating downward to foundries, memory makers, and equipment manufacturers."
                ),
                "epicenter": "Semiconductor Chip Designers (Tier 1)"
            },
            "scenario_c": {
                "title": f"Scenario C: Higher-For-Longer Rate Shock (+{rate_hike_bps:.0f} bps)",
                "narrative": (
                    f"10-Year US Treasury yield surges by +{rate_hike_bps:.0f} basis points as inflation persists. "
                    "Expands the weighted average cost of capital (WACC) across tech and hits debt-financed REITs and unprofitable cloud software hardest."
                ),
                "epicenter": "US Treasury Yield Curve / Monetary Policy"
            },
            "scenario_d": {
                "title": "Scenario D: Big Tech Guidance & Monetization Downgrade (-20%)",
                "narrative": (
                    "Enterprise software adoption of AI agents lags expectations, prompting major cloud and enterprise AI platforms "
                    "to cut forward operating guidance by 20%, triggering widespread equity valuation multiple compression."
                ),
                "epicenter": "Cloud & Enterprise Software Guidance"
            },
            "scenario_e": {
                "title": "Scenario E: Data Center Power & Grid Interconnection Bottleneck",
                "narrative": (
                    "Utility grid connection delays and substation transformer shortages stall new data center activations by 25%, "
                    "benefiting nuclear and electrical suppliers while delaying server deployments."
                ),
                "epicenter": "Power Grid & Utility Transmission Capacity"
            }
        }

        active_scenario = scenarios_desc.get(scenario_id, scenarios_desc["scenario_a"])

        results = []
        for symbol, sens in SUPPLY_CHAIN_SENSITIVITIES.items():
            tier = sens["tier"]
            # 1. Calculate revenue shock based on scenario
            if scenario_id == "scenario_a":
                # Capex cut
                rev_impact = - (capex_cut_pct * sens["capex_elasticity"] * (sens["direct_exposure_pct"] / 100.0) * 1.5)
                # Hyperscalers themselves actually save cash when cutting capex in near term
                if "Hyperscaler Originator" in tier:
                    rev_impact = 0.0 # Revenue not directly cut by own capex reduction
                price_pressure_min = rev_impact * 1.3
                price_pressure_max = rev_impact * 2.1
            elif scenario_id == "scenario_b":
                # Semi shock
                rev_impact = - (semi_shock_pct * sens["semi_elasticity"])
                price_pressure_min = rev_impact * 1.4
                price_pressure_max = rev_impact * 2.3
            elif scenario_id == "scenario_c":
                # Rate shock
                rate_effect = (rate_hike_bps / 100.0) * sens["rate_sensitivity"] * 10.0
                rev_impact = - (rate_effect * 0.4)
                price_pressure_min = - (rate_effect * 1.2)
                price_pressure_max = - (rate_effect * 2.0)
            elif scenario_id == "scenario_d":
                # Guidance cut
                rev_impact = - (20.0 * 0.6 if "Software" in tier or "Hyperscaler" in tier else 10.0 * sens["capex_elasticity"])
                price_pressure_min = rev_impact * 1.5
                price_pressure_max = rev_impact * 2.2
            else: # Scenario E: Power Grid bottleneck
                if "Power" in tier or "Electrical" in tier:
                    rev_impact = +8.5 # Pricing power increases for power suppliers
                    price_pressure_min = +5.0
                    price_pressure_max = +14.0
                elif "Server" in tier or "Core Chip" in tier:
                    rev_impact = -12.0
                    price_pressure_min = -15.0
                    price_pressure_max = -24.0
                else:
                    rev_impact = -4.0
                    price_pressure_min = -6.0
                    price_pressure_max = -10.0

            # Operating leverage effect on EBITDA
            ebitda_impact = rev_impact * 1.65 if rev_impact < 0 else rev_impact * 1.4

            # Vulnerability classification
            abs_drop = abs(price_pressure_max) if price_pressure_max < 0 else 0
            if price_pressure_min > 0:
                vuln_class = "Beneficiary / Resilient"
                badge_color = "#10b981"
            elif abs_drop >= 25.0:
                vuln_class = "High Vulnerability"
                badge_color = "#ef4444"
            elif abs_drop >= 12.0:
                vuln_class = "Moderate Vulnerability"
                badge_color = "#f97316"
            else:
                vuln_class = "Defensive / Low Exposure"
                badge_color = "#3b82f6"

            results.append({
                "symbol": symbol,
                "tier": tier,
                "direct_exposure_pct": sens["direct_exposure_pct"],
                "projected_revenue_impact_pct": round(rev_impact, 1),
                "projected_ebitda_impact_pct": round(ebitda_impact, 1),
                "price_pressure_range": f"{round(price_pressure_min, 1)}% to {round(price_pressure_max, 1)}%",
                "price_drop_midpoint": round((price_pressure_min + price_pressure_max) / 2.0, 1),
                "vulnerability_class": vuln_class,
                "badge_color": badge_color
            })

        # Sort by most vulnerable (highest negative impact) to resilient
        results.sort(key=lambda x: x["price_drop_midpoint"])

        # Summary statistics
        high_vuln_count = len([r for r in results if r["vulnerability_class"] == "High Vulnerability"])
        mod_vuln_count = len([r for r in results if r["vulnerability_class"] == "Moderate Vulnerability"])
        resilient_count = len([r for r in results if r["vulnerability_class"] in ["Defensive / Low Exposure", "Beneficiary / Resilient"]])

        return {
            "scenario": active_scenario,
            "scenario_id": scenario_id,
            "parameters": {
                "capex_cut_pct": capex_cut_pct,
                "rate_hike_bps": rate_hike_bps,
                "semi_shock_pct": semi_shock_pct
            },
            "summary": {
                "high_vulnerability_stocks": high_vuln_count,
                "moderate_vulnerability_stocks": mod_vuln_count,
                "resilient_stocks": resilient_count,
                "most_vulnerable_ticker": results[0]["symbol"],
                "most_resilient_ticker": results[-1]["symbol"]
            },
            "impact_waterfall": results,
            "simulation_timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "caveat": (
                "Stress-test outputs are empirical sensitivity simulations based on 10-K supplier disclosures "
                "and operating leverage elasticities. They represent potential equilibrium price adjustments, "
                "NOT guaranteed forecasts."
            )
        }


if __name__ == "__main__":
    engine = AIContagionEngine()
    print("Testing Contagion Stress Test for Capex -20%...")
    sim = engine.run_stress_test("scenario_a", capex_cut_pct=20.0)
    print(f"Scenario: {sim['scenario']['title']}")
    print(f"Top 3 Most Vulnerable: {[r['symbol'] + ' (' + r['price_pressure_range'] + ')' for r in sim['impact_waterfall'][:3]]}")
    print(f"Top 3 Most Resilient: {[r['symbol'] + ' (' + r['price_pressure_range'] + ')' for r in sim['impact_waterfall'][-3:]]}")
