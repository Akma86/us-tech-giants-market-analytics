"""
StockLens US — Financial Knowledge Graph & Market Intelligence Platform
Interactive Streamlit Application
Author: Akmal Yaasir Fauzaan
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Configure Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.graph_builder import FinancialKnowledgeGraph, ENTITY_COLORS
from src.analyze_us import FinancialAnalyticsEngine

# Page configuration
st.set_page_config(
    page_title="StockLens US — Financial Knowledge Graph",
    page_icon="🕸️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Institutional CSS
st.markdown("""
<style>
    /* Dark Theme Bloomberg/FactSet Style */
    .main {
        background-color: #0b0f19;
        color: #f1f5f9;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    .metric-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 16px 20px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    }
    .metric-value {
        font-size: 26px;
        font-weight: 700;
        color: #38bdf8;
        margin-top: 4px;
    }
    .metric-label {
        font-size: 13px;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .citation-badge {
        display: inline-block;
        background: rgba(99, 102, 241, 0.15);
        color: #818cf8;
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 6px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 600;
        margin-right: 6px;
    }
    .evidence-box {
        background: rgba(15, 23, 42, 0.8);
        border-left: 3px solid #10b981;
        padding: 14px 18px;
        border-radius: 0 8px 8px 0;
        margin-bottom: 12px;
        font-size: 13px;
        color: #cbd5e1;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 44px;
        background-color: rgba(30, 41, 59, 0.4);
        border-radius: 6px 6px 0px 0px;
        padding: 0 16px;
        color: #94a3b8;
    }
    .stTabs [aria-selected="true"] {
        background-color: rgba(56, 189, 248, 0.15);
        color: #38bdf8;
        border-bottom: 2px solid #38bdf8;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_kg():
    return FinancialKnowledgeGraph()


@st.cache_resource
def load_analytics_engine():
    return FinancialAnalyticsEngine()


kg = load_kg()
engine = load_analytics_engine()

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.markdown("## 🕸️ **StockLens US**")
    st.caption("Financial Knowledge Graph & Market Intelligence")
    st.divider()

    st.markdown("### 📊 Database Catalog")
    st.markdown(f"""
    - **Total Entities**: `{kg.graph.number_of_nodes()}`
    - **Relationships**: `{kg.graph.number_of_edges()}`
    - **SEC 10-K Citations**: `{len(kg.evidence_df)}`
    - **Price Observations**: `58,230+`
    - **Storage**: DuckDB + Apache Parquet
    """)
    st.divider()

    st.markdown("### 🏷️ Entity Legend")
    cols = st.columns(2)
    for i, (k, col) in enumerate(ENTITY_COLORS.items()):
        with cols[i % 2]:
            st.markdown(f"<span style='color:{col}'>●</span> **{k}**", unsafe_allow_html=True)

    st.divider()
    st.caption("StockLens US v1.0 • Built with Python, NetworkX, DuckDB & Streamlit")

# --- HEADER SECTION ---
st.title("StockLens US — Financial Knowledge Graph & Market Intelligence")
st.markdown(
    "Cross-asset economic intelligence connecting **11 GICS Sectors, 31 Blue-Chip Equities, Commodities, and Macro Indicators** "
    "grounded in verified **SEC Form 10-K filings** and quantitative econometric models."
)

# Top KPI Metric Cards
kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
with kpi_col1:
    st.markdown("""
    <div class="metric-card">
        <div class="metric-label">Graph Entities</div>
        <div class="metric-value">82 Nodes</div>
    </div>
    """, unsafe_allow_html=True)

with kpi_col2:
    st.markdown("""
    <div class="metric-card">
        <div class="metric-label">Verified Relations</div>
        <div class="metric-value">65 Edges</div>
    </div>
    """, unsafe_allow_html=True)

with kpi_col3:
    st.markdown("""
    <div class="metric-card">
        <div class="metric-label">SEC 10-K Citations</div>
        <div class="metric-value">13 Sources</div>
    </div>
    """, unsafe_allow_html=True)

with kpi_col4:
    st.markdown("""
    <div class="metric-card">
        <div class="metric-label">Columnar Store</div>
        <div class="metric-value">DuckDB + Parquet</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Main Navigation Tabs
tab_graph, tab_paths, tab_market, tab_events, tab_macro, tab_evidence = st.tabs([
    "🕸️ Knowledge Graph",
    "⚡ Transmission Paths",
    "📈 Market Model (OLS)",
    "🎯 Event Study Lab",
    "🔄 Lead/Lag Macro Analyzer",
    "📜 SEC 10-K Evidence"
])

# ==============================================================================
# TAB 1: KNOWLEDGE GRAPH EXPLORER
# ==============================================================================
with tab_graph:
    st.subheader("Interactive Financial Knowledge Graph")
    st.caption("Visualizing supply chain dependencies, product hierarchies, and macro commodity exposures.")

    filter_col1, filter_col2 = st.columns([1, 2])
    with filter_col1:
        entity_filter = st.selectbox(
            "Filter by Entity Type",
            ["All", "Sector", "Industry", "Company", "Commodity", "MacroIndicator", "Product"]
        )

    with filter_col2:
        search_query = st.text_input("Quick Search Node (e.g. NVDA, Oil, Azure, DAL, Copper)", "")

    highlight_nodes = []
    if search_query:
        matches = kg.search_entities(search_query)
        highlight_nodes = [m["id"] for m in matches]
        if matches:
            st.success(f"Matched {len(matches)} entities: {', '.join([m['name'] for m in matches[:5]])}")

    fig_kg = kg.build_plotly_figure(highlight_nodes=highlight_nodes, filter_type=entity_filter)
    st.plotly_chart(fig_kg, use_container_width=True)

    # Node Inspector & Centrality Table
    st.markdown("### 🔍 Centrality & Influence Rankings")
    centrality_df = kg.calculate_centrality_metrics()
    st.dataframe(
        centrality_df[["entity_id", "canonical_name", "entity_type", "ticker", "pagerank", "betweenness", "total_degree"]],
        use_container_width=True,
        hide_index=True
    )

# ==============================================================================
# TAB 2: TRANSMISSION PATHS
# ==============================================================================
with tab_paths:
    st.subheader("Multi-Hop Economic Transmission Path Finder")
    st.markdown(
        "Trace cost transmission, supply chain bottlenecks, and factor exposures from upstream commodities or macro indicators to downstream equities."
    )

    path_col1, path_col2, path_col3 = st.columns([2, 2, 1])

    all_nodes = sorted(list(kg.graph.nodes()))
    node_labels = {n: f"{kg.graph.nodes[n].get('name', n)} ({n})" for n in all_nodes}

    with path_col1:
        source_node = st.selectbox(
            "Source Entity (Origin Shock)",
            options=all_nodes,
            index=all_nodes.index("commodity_wti") if "commodity_wti" in all_nodes else 0,
            format_func=lambda x: node_labels.get(x, x)
        )

    with path_col2:
        target_node = st.selectbox(
            "Target Entity (Exposed Stock / Sector)",
            options=all_nodes,
            index=all_nodes.index("co_dal") if "co_dal" in all_nodes else 1,
            format_func=lambda x: node_labels.get(x, x)
        )

    with path_col3:
        max_hops = st.slider("Max Transmission Hops", min_value=1, max_value=6, value=4)

    if st.button("🚀 Find Transmission Paths", type="primary"):
        paths = kg.find_transmission_paths(source_node, target_node, max_hops=max_hops)
        if not paths:
            st.warning(f"No economic paths found between **{node_labels[source_node]}** and **{node_labels[target_node]}** within {max_hops} hops.")
        else:
            st.success(f"Discovered **{len(paths)}** economic transmission path(s):")
            for idx, path in enumerate(paths):
                with st.expander(f"Path #{idx + 1} — {len(path)} Hops (Lag: {path[-1]['cumulative_lag']} days)", expanded=(idx == 0)):
                    for hop in path:
                        st.markdown(f"""
                        **Hop {hop['hop']}**: `{hop['from_name']}` &rarr; **{hop['rel_type']}** &rarr; `{hop['to_name']}`
                        - **Status**: `{hop['evidence_status']}` | **Weight**: `{hop['weight']}` | **Lag**: `{hop['lag_days']}d`
                        - **Notes**: {hop['notes'] or 'Standard structural taxonomy relation'}
                        """)
                        if hop["evidence_details"]:
                            for ev in hop["evidence_details"]:
                                st.markdown(f"""
                                <div class="evidence-box">
                                    <span class="citation-badge">{ev.get('source_title', 'SEC Filing')}</span>
                                    <i>"{ev.get('page_or_excerpt', '')}"</i><br>
                                    <a href="{ev.get('source_url', '#')}" target="_blank" style="color:#38bdf8; text-decoration:none;">View Official Filing &rarr;</a>
                                </div>
                                """, unsafe_allow_html=True)
                        st.markdown("---")

# ==============================================================================
# TAB 3: MARKET MODEL (OLS)
# ==============================================================================
with tab_market:
    st.subheader("Market Model OLS Regression & Idiosyncratic Risk")
    st.markdown(
        r"Estimates $R_{i,t} = \alpha_i + \beta_i R_{m,t} + \varepsilon_{i,t}$ against the **S&P 500 Market Benchmark (`^GSPC`)**."
    )

    stock_tickers = sorted(kg.entities_df[kg.entities_df["entity_type"] == "Company"]["ticker"].dropna().unique().tolist())

    mm_col1, mm_col2, mm_col3 = st.columns([1, 1, 1])
    with mm_col1:
        sel_stock = st.selectbox("Select Equity Ticker", stock_tickers, index=stock_tickers.index("NVDA") if "NVDA" in stock_tickers else 0)
    with mm_col2:
        sel_benchmark = st.selectbox("Benchmark Index", ["^GSPC"], index=0)
    with mm_col3:
        sel_start_date = st.date_input("Start Date", value=pd.to_datetime("2022-01-01"))

    try:
        mm_res = engine.run_market_model(sel_stock, sel_benchmark, start_date=str(sel_start_date))

        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("Market Beta (β)", f"{mm_res['beta']:.2f}", help="Sensitivity to 1% S&P 500 move")
        m_col2.metric("Annualized Alpha (α)", f"{mm_res['alpha_annualized']:.2%}", help="Excess annualized return")
        m_col3.metric("R-Squared (R²)", f"{mm_res['r_squared']:.2%}", help="Variance explained by market")
        m_col4.metric("Idiosyncratic Vol", f"{mm_res['idiosyncratic_volatility_annualized']:.1%}", help="Firm-specific residual risk")

        # Scatter Plot with Regression Line
        returns_df = engine.get_returns_matrix([sel_stock, sel_benchmark], start_date=str(sel_start_date)).dropna()
        x_vals = returns_df[sel_benchmark]
        y_vals = returns_df[sel_stock]

        x_line = np.linspace(x_vals.min(), x_vals.max(), 100)
        y_line = mm_res["alpha_daily"] + mm_res["beta"] * x_line

        fig_scatter = go.Figure()
        fig_scatter.add_trace(go.Scatter(
            x=x_vals, y=y_vals,
            mode="markers",
            name="Daily Returns",
            marker=dict(size=5, color="#38bdf8", opacity=0.6)
        ))
        fig_scatter.add_trace(go.Scatter(
            x=x_line, y=y_line,
            mode="lines",
            name=f"OLS Fit (β={mm_res['beta']:.2f})",
            line=dict(color="#f43f5e", width=2.5)
        ))
        fig_scatter.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(15, 23, 42, 0.95)",
            plot_bgcolor="rgba(15, 23, 42, 0.95)",
            xaxis_title=f"{sel_benchmark} Daily Return",
            yaxis_title=f"{sel_stock} Daily Return",
            title=f"Market Model Regression: {sel_stock} vs {sel_benchmark}",
            height=480
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    except Exception as e:
        st.error(f"Error calculating Market Model: {e}")

# ==============================================================================
# TAB 4: EVENT STUDY LAB
# ==============================================================================
with tab_events:
    st.subheader("Event Study Lab — Abnormal Returns (AR) & CAR")
    st.markdown(
        "Quantify the statistical impact of corporate announcements, product launches, or macroeconomic shocks on equity returns."
    )

    preset_events = {
        "NVIDIA GTC Blackwell Architecture Keynote (2024-03-18)": ("NVDA", "2024-03-18"),
        "Microsoft Copilot & OpenAI Enterprise Launch (2023-07-18)": ("MSFT", "2023-07-18"),
        "Apple Vision Pro Announcement at WWDC (2023-06-05)": ("AAPL", "2023-06-05"),
        "Fed Rate Cut 50bps Benchmark Decision (2024-09-18)": ("JPM", "2024-09-18"),
        "Delta Q1 Jet Fuel Spike & Earnings (2022-04-13)": ("DAL", "2022-04-13")
    }

    ev_col1, ev_col2, ev_col3 = st.columns([2, 1, 1])
    with ev_col1:
        selected_preset = st.selectbox("Select Preset Event", list(preset_events.keys()))
    default_stock, default_date = preset_events[selected_preset]

    with ev_col2:
        ev_stock = st.selectbox("Stock", stock_tickers, index=stock_tickers.index(default_stock) if default_stock in stock_tickers else 0)
    with ev_col3:
        ev_date = st.date_input("Event Date (T0)", value=pd.to_datetime(default_date))

    w_col1, w_col2 = st.columns(2)
    with w_col1:
        pre_win = st.slider("Pre-Event Window (Trading Days)", 1, 15, 3)
    with w_col2:
        post_win = st.slider("Post-Event Window (Trading Days)", 1, 30, 7)

    try:
        ev_res = engine.run_event_study(
            ticker=ev_stock,
            event_date=str(ev_date),
            pre_event_window=pre_win,
            post_event_window=post_win
        )

        stat_badge = "✅ Statistically Significant (p < 0.05)" if ev_res["statistically_significant"] else "ℹ️ Not Statistically Significant"
        st.markdown(f"**CAR Result**: `{ev_res['car']:+.2%}` | **t-stat**: `{ev_res['t_statistic']:.2f}` | **p-value**: `{ev_res['p_value']:.4f}` | {stat_badge}")

        df_ev = pd.DataFrame(ev_res["event_series"])
        fig_car = go.Figure()
        fig_car.add_trace(go.Bar(
            x=df_ev["rel_day"], y=df_ev["abnormal_return"] * 100,
            name="Daily Abnormal Return (AR %)",
            marker_color="rgba(56, 189, 248, 0.7)"
        ))
        fig_car.add_trace(go.Scatter(
            x=df_ev["rel_day"], y=df_ev["car"] * 100,
            mode="lines+markers",
            name="Cumulative Abnormal Return (CAR %)",
            line=dict(color="#10b981", width=3)
        ))
        fig_car.add_vline(x=0, line_dash="dash", line_color="#f43f5e", annotation_text="Event T0")
        fig_car.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(15, 23, 42, 0.95)",
            plot_bgcolor="rgba(15, 23, 42, 0.95)",
            xaxis_title="Days Relative to Event (T0 = 0)",
            yaxis_title="Return (%)",
            title=f"Event Study: {ev_stock} around {ev_res['event_date']}",
            height=450
        )
        st.plotly_chart(fig_car, use_container_width=True)

    except Exception as e:
        st.error(f"Error executing event study: {e}")

# ==============================================================================
# TAB 5: LEAD/LAG MACRO ANALYZER
# ==============================================================================
with tab_macro:
    st.subheader("Commodity & Macro Factor Lead/Lag Cross-Correlation")
    st.markdown(
        "Analyze whether movements in oil, natural gas, copper, yields, or volatility **lead** or **lag** equity returns."
    )

    macro_options = {
        "CL=F": "Crude Oil WTI (CL=F)",
        "BZ=F": "Crude Oil Brent (BZ=F)",
        "NG=F": "Natural Gas Henry Hub (NG=F)",
        "HG=F": "Copper COMEX (HG=F)",
        "^TNX": "10-Year US Treasury Yield (^TNX)",
        "^VIX": "CBOE Volatility Index (^VIX)",
        "GC=F": "Gold COMEX (GC=F)"
    }

    ll_col1, ll_col2 = st.columns(2)
    with ll_col1:
        sel_ll_stock = st.selectbox("Select Equity", stock_tickers, index=stock_tickers.index("DAL") if "DAL" in stock_tickers else 0)
    with ll_col2:
        sel_ll_macro = st.selectbox("Select Macro/Commodity Factor", list(macro_options.keys()), format_func=lambda x: macro_options[x])

    try:
        ll_res = engine.run_lead_lag_correlation(sel_ll_stock, sel_ll_macro)
        opt_lag = ll_res["optimal_lag_days"]
        opt_interp = f"Factor Leads by {opt_lag}d" if opt_lag > 0 else "Coincident" if opt_lag == 0 else f"Equity Leads by {abs(opt_lag)}d"

        st.metric("Optimal Cross-Correlation Lag", f"{opt_lag} Days", delta=f"{ll_res['max_abs_correlation']:.3f} | {opt_interp}")

        df_ll = pd.DataFrame(ll_res["lag_matrix"])
        colors = ["#10b981" if c > 0 else "#f43f5e" for c in df_ll["correlation"]]

        fig_ll = go.Figure()
        fig_ll.add_trace(go.Bar(
            x=df_ll["lag_days"],
            y=df_ll["correlation"],
            marker_color=colors,
            hovertext=[f"{r['interpretation']}<br>Corr: {r['correlation']:.3f}<br>p-val: {r['p_value']:.4f}" for _, r in df_ll.iterrows()],
            hoverinfo="text"
        ))
        fig_ll.add_vline(x=0, line_dash="solid", line_color="rgba(255, 255, 255, 0.4)")
        fig_ll.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(15, 23, 42, 0.95)",
            plot_bgcolor="rgba(15, 23, 42, 0.95)",
            xaxis_title="Lag Horizon (Days: Negative = Stock Leads, Positive = Macro Leads)",
            yaxis_title="Pearson Correlation (r)",
            title=f"Cross-Correlation Spectrum: {sel_ll_stock} vs {macro_options[sel_ll_macro]}",
            height=450
        )
        st.plotly_chart(fig_ll, use_container_width=True)

    except Exception as e:
        st.error(f"Error computing lead/lag cross-correlation: {e}")

# ==============================================================================
# TAB 6: SEC 10-K EVIDENCE DRAWER
# ==============================================================================
with tab_evidence:
    st.subheader("Authoritative Evidence & SEC Form 10-K Catalog")
    st.markdown(
        "Every supply relationship and economic exposure in StockLens US is verified with authoritative citations."
    )

    if not kg.evidence_df.empty:
        for _, row in kg.evidence_df.iterrows():
            with st.expander(f"📑 {row.get('source_title', 'Citation')} — {row.get('publisher', 'Agency')}"):
                st.markdown(f"""
                - **Citation Key**: `{row.get('source_id', '')}`
                - **Publisher / Regulator**: {row.get('publisher', '')}
                - **Published Date**: {row.get('published_at', '')} | **Retrieved**: {row.get('retrieved_at', '')}
                - **License / Status**: `{row.get('license', 'Public Filing')}`
                - **Official EDGAR Link**: [View Document Filing]({row.get('source_url', '#')})
                """)
                st.markdown(f"""
                <div class="evidence-box">
                    <b>Verbatim Excerpt:</b><br>
                    <i>"{row.get('page_or_excerpt', '')}"</i>
                </div>
                """, unsafe_allow_html=True)
