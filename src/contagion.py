"""
Module: contagion.py
Description: Systemic Shock & Contagion Diffusion Simulator for StockLens US.
             Simulates positive or negative economic shocks propagating across
             supply chains, commodity exposures, and competitor networks.
Author: Akmal Yaasir Fauzaan
Project: StockLens US - Financial Knowledge Graph & Market Intelligence
"""

from __future__ import annotations

from collections import deque
from typing import Any, Optional
import networkx as nx


# Transmission Elasticity by Relationship Type
# Positive (+1.0): Shock transmits in the SAME direction (negative shock -> negative impact)
# Negative (-1.0): Shock transmits in the OPPOSITE direction (negative shock -> positive gain for competitor / producer)
RELATIONSHIP_ELASTICITY: dict[str, float] = {
    "SUPPLIES_TO": 1.0,               # Supplier bottleneck hurts downstream buyer
    "SELLS_TO": 1.0,                  # Supplier shortage hurts buyer
    "BUYS_FROM": 0.85,                # Customer order cuts hurt supplier
    "PRODUCES": 1.0,                  # Producer issue hurts product availability
    "USES_MATERIAL": 0.9,             # Material shortage/price spike compresses product margin
    "CONSUMES_PRODUCT": 0.9,          # Product bottleneck hits consumer
    "COMPETES_WITH": -0.85,           # Competitor distress yields market share gain for rival!
    "HAS_EXPOSURE_TO": 1.0,           # Exposure to commodity or macro factor
    "BELONGS_TO": 0.4,                # Sector/Industry broad spillover
    "PART_OF_SECTOR": 0.4,
    "BELONGS_TO_INDUSTRY": 0.5,
    "TRANSMITS_COST_TO": 1.0,         # Cost push inflation
    "INTEREST_RATE_SENSITIVITY": 0.8,
}

# Special handling for commodity shocks:
# If a commodity surges / suffers supply shock, producers benefit while consumers suffer
COMMODITY_PRODUCERS: dict[str, set[str]] = {
    "commodity_wti": {"co_xom", "co_cvx", "ind_oil_gas_ep", "sector_energy"},
    "commodity_brent": {"co_xom", "co_cvx", "ind_oil_gas_ep", "sector_energy"},
    "commodity_copper": {"co_fcx", "sector_mat"},
    "commodity_gas": {"co_xom", "co_cvx"},
    "commodity_gold": {"sector_mat"},
}

COMMODITY_CONSUMERS: dict[str, set[str]] = {
    "commodity_wti": {"co_dal", "ind_airlines", "sector_ind"},
    "commodity_jet_fuel": {"co_dal", "ind_airlines"},
    "commodity_copper": {"co_nvda", "co_aapl", "prod_gpu", "sector_it"},
    "commodity_lithium": {"co_tsla", "prod_ev_batteries"},
    "commodity_silicon": {"co_nvda", "co_amd", "co_avgo", "ind_semis"},
}


class ContagionSimulator:
    """Quantitative network shock propagation and contagion engine."""

    def __init__(self, graph: nx.MultiDiGraph):
        self.graph = graph

    def run_shock_simulation(
        self,
        source_node: str,
        shock_type: str = "negative",
        shock_magnitude: float = 1.0,
        max_hops: int = 3,
        attenuation: float = 0.65,
    ) -> dict[str, Any]:
        """Propagate a systemic shock through the Financial Knowledge Graph.

        Args:
            source_node: Entity ID originating the shock (e.g. 'co_nvda', 'commodity_wti')
            shock_type: 'negative' (distress/crash/shortage) or 'positive' (boom/windfall)
            shock_magnitude: Initial intensity [0.1 to 1.0]
            max_hops: Maximum transmission distance
            attenuation: Decay factor per hop (0.65 means 35% reduction per hop)

        Returns:
            Dictionary with affected nodes, 2-color styling, magnitude, and narrative explanations.
        """
        if source_node not in self.graph:
            raise KeyError(f"Source node '{source_node}' does not exist in knowledge graph.")

        initial_impact = -abs(shock_magnitude) if shock_type == "negative" else abs(shock_magnitude)

        # Track impact scores: entity_id -> float (-1.0 to +1.0)
        impact_scores: dict[str, float] = {source_node: initial_impact}
        transmission_paths: dict[str, list[dict[str, Any]]] = {source_node: []}
        visited_hops: dict[str, int] = {source_node: 0}

        # BFS queue: (current_node, current_impact, hop_distance)
        queue: deque[tuple[str, float, int]] = deque([(source_node, initial_impact, 0)])

        while queue:
            curr, curr_imp, hop = queue.popleft()
            if hop >= max_hops:
                continue

            # 1. Outgoing Edges
            for _, target, key, data in self.graph.out_edges(curr, keys=True, data=True):
                rel_type = data.get("rel_type", "RELATED_TO")
                elasticity = self._get_elasticity(curr, target, rel_type)
                decayed_imp = curr_imp * elasticity * (attenuation ** (hop + 1))

                self._accumulate_impact(
                    target, decayed_imp, hop + 1, curr, rel_type,
                    impact_scores, visited_hops, transmission_paths, queue
                )

            # 2. Incoming Edges (reverse propagation for supply chain dependencies)
            for source, _, key, data in self.graph.in_edges(curr, keys=True, data=True):
                rel_type = data.get("rel_type", "RELATED_TO")
                # When customer cuts orders (BUYS_FROM), supplier feels it;
                # When buyer is hit, supplier feels negative demand
                elasticity = self._get_reverse_elasticity(source, curr, rel_type)
                decayed_imp = curr_imp * elasticity * (attenuation ** (hop + 1))

                self._accumulate_impact(
                    source, decayed_imp, hop + 1, curr, f"REVERSE_{rel_type}",
                    impact_scores, visited_hops, transmission_paths, queue
                )

        # Build output structure
        return self._format_results(source_node, shock_type, impact_scores, transmission_paths)

    def _get_elasticity(self, source: str, target: str, rel_type: str) -> float:
        """Determines transmission sign and magnitude for outgoing edges."""
        # Special Commodity Producer vs Consumer logic
        if source in COMMODITY_PRODUCERS and target in COMMODITY_PRODUCERS[source]:
            # Negative shock (oil price surge/shortage) -> positive windfall for producer
            return -1.0
        if source in COMMODITY_CONSUMERS and target in COMMODITY_CONSUMERS[source]:
            # Negative shock (oil price surge) -> negative cost push for consumer
            return 1.0

        return RELATIONSHIP_ELASTICITY.get(rel_type, 0.7)

    def _get_reverse_elasticity(self, upstream: str, downstream: str, rel_type: str) -> float:
        """Determines transmission sign and magnitude for incoming edges."""
        # If downstream is a shocked commodity and upstream is a producer, producer reaps windfall gain!
        if downstream in COMMODITY_PRODUCERS and upstream in COMMODITY_PRODUCERS[downstream]:
            return -1.0  # Windfall revenue expansion (opposite sign)
        if downstream in COMMODITY_CONSUMERS and upstream in COMMODITY_CONSUMERS[downstream]:
            return 1.0   # Severe cost push (same sign)

        if rel_type in {"BUYS_FROM", "CONSUMES_PRODUCT"}:
            return 0.75  # Customer distress cascades to supplier
        if rel_type in {"SUPPLIES_TO", "SELLS_TO"}:
            return 0.85  # Downstream distress cascades upstream
        if rel_type == "COMPETES_WITH":
            return -0.85
        return 0.4

    def _accumulate_impact(
        self,
        node: str,
        delta: float,
        hop: int,
        parent: str,
        rel: str,
        scores: dict[str, float],
        hops: dict[str, int],
        paths: dict[str, list[dict[str, Any]]],
        queue: deque,
    ) -> None:
        if abs(delta) < 0.05:
            return  # Stop negligible transmissions

        if node not in scores:
            scores[node] = delta
            hops[node] = hop
            paths[node] = paths[parent] + [{"from": parent, "to": node, "rel": rel, "delta": round(delta, 3)}]
            queue.append((node, delta, hop))
        else:
            # Dampen additional converging paths
            scores[node] += delta * 0.5
            scores[node] = max(-1.0, min(1.0, scores[node]))

    def _format_results(
        self,
        source_node: str,
        shock_type: str,
        impact_scores: dict[str, float],
        paths: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        """Builds formatted payload for the web UI with 2-color styling and rankings."""
        source_data = self.graph.nodes.get(source_node, {})
        source_name = source_data.get("name", source_node)
        source_ticker = source_data.get("ticker", "")

        impacted_nodes = []
        top_losers = []
        top_gainers = []

        for node_id, score in impact_scores.items():
            if node_id not in self.graph.nodes:
                continue

            node_d = self.graph.nodes[node_id]
            is_epicenter = (node_id == source_node)

            if score <= -0.12:
                category = "VULNERABLE"
                color = "#EF4444"  # Vibrant Red
                status = "DOWN / NEGATIVE"
            elif score >= 0.12:
                category = "BENEFICIARY"
                color = "#10B981"  # Vibrant Green
                status = "UP / POSITIVE"
            else:
                category = "NEUTRAL"
                color = "#64748B"  # Muted Slate
                status = "NEUTRAL"

            narrative = self._generate_narrative(node_id, score, is_epicenter, source_name)

            item = {
                "id": node_id,
                "name": node_d.get("name", node_id),
                "ticker": node_d.get("ticker", ""),
                "type": node_d.get("entity_type", "Unknown"),
                "impact_score": round(score, 3),
                "category": category,
                "status": status,
                "color": color,
                "is_epicenter": is_epicenter,
                "narrative": narrative,
                "path": paths.get(node_id, []),
            }
            impacted_nodes.append(item)

            if not is_epicenter and node_d.get("entity_type") in {"Company", "Sector", "Industry"}:
                if score < -0.15:
                    top_losers.append(item)
                elif score > 0.15:
                    top_gainers.append(item)

        # Sort leaderboard
        top_losers.sort(key=lambda x: x["impact_score"])
        top_gainers.sort(key=lambda x: x["impact_score"], reverse=True)

        return {
            "epicenter": {
                "id": source_node,
                "name": source_name,
                "ticker": source_ticker,
                "type": source_data.get("entity_type", "Unknown"),
                "shock_type": shock_type,
            },
            "summary": {
                "total_impacted_entities": len(impacted_nodes),
                "vulnerable_count": len(top_losers),
                "beneficiary_count": len(top_gainers),
            },
            "nodes_map": {item["id"]: item for item in impacted_nodes},
            "top_vulnerable": top_losers[:8],
            "top_beneficiaries": top_gainers[:8],
        }

    def _generate_narrative(self, node_id: str, score: float, is_epicenter: bool, source_name: str) -> str:
        """Generates brief institutional market commentary for why an entity is impacted."""
        if is_epicenter:
            return f"Epicenter of systemic {('negative disruption' if score < 0 else 'positive expansion')}."

        d = self.graph.nodes.get(node_id, {})
        name = d.get("name", node_id)
        ticker = d.get("ticker", "")

        if score < 0:
            if "dal" in node_id or "airline" in name.lower():
                return f"Severe operating margin compression driven by fuel price shock from {source_name}."
            if "msft" in node_id or "meta" in node_id or "googl" in node_id:
                return f"Capex deployment and AI compute availability throttled by bottleneck in {source_name}."
            return f"Negative contagion transmitted downstream through supply chain exposure to {source_name}."
        else:
            if "amd" in node_id:
                return f"Gains competitive market share as customers seek secondary suppliers away from {source_name}."
            if "xom" in node_id or "energy" in name.lower():
                return f"Windfall cash flow expansion from higher realized commodity prices."
            return f"Beneficiary of alternative demand allocation and substitution effects."
