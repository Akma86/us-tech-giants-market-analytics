"""
Module: graph_builder.py
Description: Financial Knowledge Graph engine for StockLens US.
             Constructs and traverses NetworkX MultiDiGraphs connecting
             Sectors, Industries, Equities, Commodities, Macro Factors, and Products.
Author: Akmal Yaasir Fauzaan
Project: StockLens US - Financial Knowledge Graph & Market Intelligence
"""

from pathlib import Path
from typing import Any, Optional
import networkx as nx
import pandas as pd
import plotly.graph_objects as go

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_US_DIR = PROJECT_ROOT / "data" / "us"

ENTITY_COLORS = {
    "Sector": "#6366F1",          # Indigo
    "Industry": "#8B5CF6",        # Violet
    "Company": "#10B981",         # Emerald Green
    "Commodity": "#F59E0B",       # Amber
    "MacroIndicator": "#EF4444",   # Crimson Rose
    "Product": "#06B6D4"          # Cyan
}

RELATIONSHIP_COLORS = {
    "PART_OF_SECTOR": "#94A3B8",
    "BELONGS_TO_INDUSTRY": "#94A3B8",
    "SUPPLIES_TO": "#10B981",
    "EXPOSED_TO_COMMODITY": "#F59E0B",
    "PRODUCES_PRODUCT": "#06B6D4",
    "CONSUMES_PRODUCT": "#3B82F6",
    "INTEREST_RATE_SENSITIVITY": "#EF4444",
    "TRANSMITS_COST_TO": "#EC4899",
    "COMPETES_WITH": "#F97316"
}


class FinancialKnowledgeGraph:
    """Institutional-grade Financial Knowledge Graph engine built on NetworkX."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or DATA_US_DIR
        self.graph = nx.MultiDiGraph()
        self.entities_df = pd.DataFrame()
        self.relationships_df = pd.DataFrame()
        self.evidence_df = pd.DataFrame()
        self.evidence_lookup = {}
        self.load_data()
        self.build_graph()

    def load_data(self):
        """Loads entities, relationships, and evidence CSV files."""
        ent_file = self.data_dir / "entities.csv"
        rel_file = self.data_dir / "relationships.csv"
        ev_file = self.data_dir / "evidence.csv"

        if not ent_file.exists() or not rel_file.exists():
            raise FileNotFoundError(f"Missing required graph files in {self.data_dir}")

        self.entities_df = pd.read_csv(ent_file)
        self.relationships_df = pd.read_csv(rel_file)

        # Check for dynamic relationships in SQLite
        db_file = PROJECT_ROOT / "data" / "database" / "us_equities.db"
        if db_file.exists():
            try:
                import sqlite3
                with sqlite3.connect(db_file) as conn:
                    tbl_check = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dynamic_relationships'").fetchone()
                    if tbl_check:
                        dyn_df = pd.read_sql_query("SELECT * FROM dynamic_relationships", conn)
                        if not dyn_df.empty:
                            self.relationships_df = pd.concat([self.relationships_df, dyn_df], ignore_index=True)
            except Exception as e:
                pass

        if ev_file.exists():
            self.evidence_df = pd.read_csv(ev_file)
            id_col = "source_id" if "source_id" in self.evidence_df.columns else "citation_key"
            self.evidence_lookup = self.evidence_df.set_index(id_col).to_dict(orient="index")

    def build_graph(self):
        """Populates the NetworkX MultiDiGraph with nodes and directed edges."""
        self.graph.clear()

        # Add Nodes
        for _, row in self.entities_df.iterrows():
            node_id = str(row["entity_id"]).strip()
            node_attrs = {
                "id": node_id,
                "entity_type": row.get("entity_type", "Unknown"),
                "name": row.get("canonical_name", node_id),
                "ticker": str(row["ticker"]) if pd.notna(row.get("ticker")) else "",
                "exchange": str(row["exchange"]) if pd.notna(row.get("exchange")) else "",
                "country": str(row["country"]) if pd.notna(row.get("country")) else "US",
                "sector_code": str(row["sector_code"]) if pd.notna(row.get("sector_code")) else "",
                "external_id": str(row["external_id"]) if pd.notna(row.get("external_id")) else "",
                "color": ENTITY_COLORS.get(row.get("entity_type"), "#94A3B8")
            }
            self.graph.add_node(node_id, **node_attrs)

        # Add Edges
        for idx, row in self.relationships_df.iterrows():
            source = str(row.get("source_entity_id") or row.get("source_id", "")).strip()
            target = str(row.get("target_entity_id") or row.get("target_id", "")).strip()
            if not self.graph.has_node(source) or not self.graph.has_node(target):
                continue

            rel_type = str(row.get("relationship_type") or row.get("rel_type", "RELATED_TO")).strip()
            weight = float(row.get("confidence") or row.get("weight", 1.0))
            raw_citations = str(row.get("source_id") if "source_entity_id" in row else row.get("citation_keys", ""))
            citations = [c.strip() for c in raw_citations.split(";") if c.strip()]
            valid_from = str(row.get("valid_from", "")) if pd.notna(row.get("valid_from")) else ""
            valid_to = str(row.get("valid_to", "")) if pd.notna(row.get("valid_to")) else ""
            
            edge_attrs = {
                "rel_id": str(row.get("relationship_id") or row.get("rel_id", f"rel_{idx}")),
                "rel_type": rel_type,
                "weight": weight,
                "direction": str(row.get("direction", "forward")),
                "lag_days": int(row.get("lag_days", 0)) if pd.notna(row.get("lag_days")) else 0,
                "evidence_status": str(row.get("evidence_status", "hypothesis")),
                "valid_from": valid_from,
                "valid_to": valid_to,
                "citation_keys": citations,
                "notes": str(row.get("notes", "")),
                "source_url": str(row.get("source_url", "")) if pd.notna(row.get("source_url")) else "",
                "headline": str(row.get("headline", "")) if pd.notna(row.get("headline")) else "",
                "color": RELATIONSHIP_COLORS.get(rel_type, "#64748B")
            }
            self.graph.add_edge(source, target, key=edge_attrs["rel_type"], **edge_attrs)

    def get_entity(self, entity_id: str) -> Optional[dict]:
        """Returns node attribute dictionary for a given entity_id."""
        if entity_id in self.graph.nodes:
            return self.graph.nodes[entity_id]
        return None

    def search_entities(self, query: str, entity_type: Optional[str] = None) -> list[dict]:
        """Searches entities by name, ticker, or entity_id."""
        q = query.lower().strip()
        results = []
        for n, d in self.graph.nodes(data=True):
            if entity_type and d.get("entity_type") != entity_type:
                continue
            if (q in n.lower() or 
                q in d.get("name", "").lower() or 
                q in d.get("ticker", "").lower()):
                results.append(d)
        return results

    def get_neighbors_with_edges(self, entity_id: str) -> dict[str, list[dict]]:
        """Retrieves incoming and outgoing edges with full relationship attributes."""
        if entity_id not in self.graph:
            return {"outgoing": [], "incoming": []}

        outgoing = []
        for _, target, key, data in self.graph.out_edges(entity_id, keys=True, data=True):
            target_data = self.graph.nodes.get(target, {})
            outgoing.append({
                "target_id": target,
                "target_name": target_data.get("name", target),
                "target_type": target_data.get("entity_type", "Unknown"),
                "target_ticker": target_data.get("ticker", ""),
                **data
            })

        incoming = []
        for source, _, key, data in self.graph.in_edges(entity_id, keys=True, data=True):
            source_data = self.graph.nodes.get(source, {})
            incoming.append({
                "source_id": source,
                "source_name": source_data.get("name", source),
                "source_type": source_data.get("entity_type", "Unknown"),
                "source_ticker": source_data.get("ticker", ""),
                **data
            })

        return {"outgoing": outgoing, "incoming": incoming}

    def find_transmission_paths(
        self, source_id: str, target_id: str, max_hops: int = 4, directed_only: bool = False
    ) -> list[list[dict]]:
        """
        Finds all simple economic transmission paths between source_id and target_id.
        Searches directed paths first; if none found and directed_only=False, searches undirected graph.
        Returns paths with edge metadata, lag accumulation, and evidence status.
        """
        if source_id not in self.graph or target_id not in self.graph:
            return []

        # Convert to DiGraph for directed search
        simple_graph = nx.DiGraph()
        for u, v, data in self.graph.edges(data=True):
            if not simple_graph.has_edge(u, v):
                simple_graph.add_edge(u, v, **data)

        raw_paths = []
        try:
            raw_paths = list(nx.all_simple_paths(simple_graph, source=source_id, target=target_id, cutoff=max_hops))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            raw_paths = []

        if not raw_paths and not directed_only:
            # Undirected fallback to trace reverse/bidirectional economic exposure
            undir = nx.Graph()
            for u, v, data in self.graph.edges(data=True):
                if not undir.has_edge(u, v):
                    undir.add_edge(u, v, **data)
            try:
                raw_paths = list(nx.all_simple_paths(undir, source=source_id, target=target_id, cutoff=max_hops))
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                raw_paths = []

        structured_paths = []
        for path in raw_paths:
            path_segments = []
            cumulative_lag = 0
            for i in range(len(path) - 1):
                u, v = path[i], path[i + 1]
                u_node = self.graph.nodes[u]
                v_node = self.graph.nodes[v]
                # Look for edge in either direction
                edge_data = {}
                step_direction = "forward"
                if self.graph.has_edge(u, v):
                    edge_data = list(self.graph[u][v].values())[0]
                    step_direction = "forward"
                elif self.graph.has_edge(v, u):
                    edge_data = list(self.graph[v][u].values())[0]
                    step_direction = "reverse"

                cumulative_lag += edge_data.get("lag_days", 0)
                citations = edge_data.get("citation_keys", [])
                evidence_details = [self.evidence_lookup.get(c) for c in citations if c in self.evidence_lookup]

                path_segments.append({
                    "hop": i + 1,
                    "from_id": u,
                    "from_name": u_node.get("name"),
                    "from_type": u_node.get("entity_type"),
                    "to_id": v,
                    "to_name": v_node.get("name"),
                    "to_type": v_node.get("entity_type"),
                    "rel_type": edge_data.get("rel_type", "RELATED_TO"),
                    "weight": edge_data.get("weight", 1.0),
                    "lag_days": edge_data.get("lag_days", 0),
                    "cumulative_lag": cumulative_lag,
                    "evidence_status": edge_data.get("evidence_status", "hypothesis"),
                    "step_direction": step_direction,
                    "notes": edge_data.get("notes", ""),
                    "citations": citations,
                    "evidence_details": evidence_details
                })
            structured_paths.append(path_segments)

        return structured_paths

    def calculate_centrality_metrics(self) -> pd.DataFrame:
        """Computes In-Degree, Out-Degree, Betweenness, and PageRank centralities."""
        # MultiDiGraph to simple DiGraph with weights for algorithmic calculation
        simple_graph = nx.DiGraph()
        for u, v, data in self.graph.edges(data=True):
            weight = data.get("weight", 1.0)
            if simple_graph.has_edge(u, v):
                simple_graph[u][v]["weight"] = max(simple_graph[u][v]["weight"], weight)
            else:
                simple_graph.add_edge(u, v, weight=weight)

        in_deg = dict(self.graph.in_degree())
        out_deg = dict(self.graph.out_degree())
        pagerank = nx.pagerank(simple_graph, alpha=0.85, max_iter=200)
        betweenness = nx.betweenness_centrality(simple_graph, normalized=True)

        rows = []
        for n, d in self.graph.nodes(data=True):
            rows.append({
                "entity_id": n,
                "canonical_name": d.get("name"),
                "entity_type": d.get("entity_type"),
                "ticker": d.get("ticker", ""),
                "in_degree": in_deg.get(n, 0),
                "out_degree": out_deg.get(n, 0),
                "total_degree": in_deg.get(n, 0) + out_deg.get(n, 0),
                "pagerank": round(pagerank.get(n, 0.0), 5),
                "betweenness": round(betweenness.get(n, 0.0), 5)
            })

        df = pd.DataFrame(rows).sort_values(by="pagerank", ascending=False)
        return df

    def get_evidence_detail(self, citation_key: str) -> Optional[dict]:
        """Fetches full citation and filing quote for a citation key."""
        return self.evidence_lookup.get(citation_key)

    def build_plotly_figure(
        self,
        highlight_nodes: Optional[list[str]] = None,
        filter_type: Optional[str] = None
    ) -> go.Figure:
        """
        Renders interactive 2D graph with spring layout, glowing highlights,
        and hover cards showing node degrees, sector, and ticker.
        """
        # Filter subgraph if requested
        if filter_type and filter_type != "All":
            selected_nodes = [
                n for n, d in self.graph.nodes(data=True)
                if d.get("entity_type") == filter_type
            ]
            # Include 1-hop neighbors of selected nodes
            expanded = set(selected_nodes)
            for n in selected_nodes:
                expanded.update(self.graph.predecessors(n))
                expanded.update(self.graph.successors(n))
            sub = self.graph.subgraph(expanded)
        else:
            sub = self.graph

        pos = nx.spring_layout(sub, seed=42, k=0.55, iterations=60)

        # Edge traces
        edge_x, edge_y = [], []
        edge_hover_x, edge_hover_y, edge_hover_text = [], []

        for u, v, data in sub.edges(data=True):
            if u not in pos or v not in pos:
                continue
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

            # Midpoint for hover tooltip
            mid_x, mid_y = (x0 + x1) / 2, (y0 + y1) / 2
            edge_hover_x.append(mid_x)
            edge_hover_y.append(mid_y)
            rel = data.get("rel_type", "RELATED")
            status = data.get("evidence_status", "hypothesis")
            citations = ", ".join(data.get("citation_keys", [])) or "None"
            edge_hover_text.append(f"<b>{u}</b> &rarr; <b>{v}</b><br>Type: {rel}<br>Status: {status}<br>Evidence: {citations}")

        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=1, color="rgba(148, 163, 184, 0.35)"),
            hoverinfo="none",
            mode="lines"
        )

        edge_hover_trace = go.Scatter(
            x=edge_hover_x, y=edge_hover_y,
            mode="markers",
            marker=dict(size=4, color="rgba(148, 163, 184, 0.0)"),
            hoverinfo="text",
            hovertext=edge_hover_text
        )

        # Node trace
        node_x, node_y, node_colors, node_sizes, node_texts, node_labels = [], [], [], [], [], []
        highlight_set = set(highlight_nodes or [])

        for node in sub.nodes():
            if node not in pos:
                continue
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            d = sub.nodes[node]
            e_type = d.get("entity_type", "Unknown")
            name = d.get("name", node)
            ticker = d.get("ticker", "")
            deg = sub.degree(node)

            is_highlight = node in highlight_set
            color = "#F43F5E" if is_highlight else d.get("color", ENTITY_COLORS.get(e_type, "#94A3B8"))
            base_size = 18 if is_highlight else (24 if e_type == "Sector" else 14 if e_type == "Company" else 10)

            node_colors.append(color)
            node_sizes.append(base_size + min(deg, 15))
            node_labels.append(ticker if ticker else name[:12])

            hover = (
                f"<b>{name}</b> ({node})<br>"
                f"Type: {e_type}<br>"
                f"Ticker: {ticker or 'N/A'}<br>"
                f"Exchange/Market: {d.get('exchange', 'N/A')}<br>"
                f"Degree Connections: {deg}"
            )
            node_texts.append(hover)

        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode="markers+text",
            text=node_labels,
            textposition="top center",
            textfont=dict(size=9, color="#CBD5E1"),
            hoverinfo="text",
            hovertext=node_texts,
            marker=dict(
                color=node_colors,
                size=node_sizes,
                line=dict(width=1.5, color="#0F172A")
            )
        )

        fig = go.Figure(
            data=[edge_trace, edge_hover_trace, node_trace],
            layout=go.Layout(
                template="plotly_dark",
                paper_bgcolor="rgba(15, 23, 42, 0.95)",
                plot_bgcolor="rgba(15, 23, 42, 0.95)",
                showlegend=False,
                hovermode="closest",
                margin=dict(b=10, l=10, r=10, t=20),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                height=650
            )
        )
        return fig


if __name__ == "__main__":
    kg = FinancialKnowledgeGraph()
    print(f"Graph loaded successfully: {kg.graph.number_of_nodes()} nodes, {kg.graph.number_of_edges()} edges")
    metrics = kg.calculate_centrality_metrics()
    print("\nTop 10 Entities by PageRank Centrality:")
    print(metrics[["entity_id", "canonical_name", "entity_type", "pagerank", "betweenness"]].head(10).to_string())

    print("\nTracing Transmission Path: Crude Oil (commodity_wti) -> Delta Air Lines (co_dal)")
    paths = kg.find_transmission_paths("commodity_wti", "co_dal", max_hops=4)
    print(f"Found {len(paths)} economic paths:")
    for i, p in enumerate(paths):
        print(f"\nPath #{i+1}:")
        for hop in p:
            print(f"  [{hop['from_name']}] --({hop['rel_type']}, lag={hop['lag_days']}d)--> [{hop['to_name']}] | Status: {hop['evidence_status']}")
