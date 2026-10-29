/* =========================================================================
   US EQUITY ATLAS · DATA ANALYST EDITION (100% US EQUITIES & US MACRO)
   ========================================================================= */

(function () {
  "use strict";

  let DATASET = null;
  let activeRange = "ALL";

  const SERIES_COLORS = {
    NVDA: "#5e8519",
    AAPL: "#18201e",
    MSFT: "#147b54",
    GOOGL: "#2563eb",
    AMZN: "#d97706",
    META: "#7c3aed",
    TSLA: "#c54d3a",
    AVGO: "#0d9488",
    AMD: "#db2777",
    ORCL: "#4f46e5",
    "^GSPC": "#18201e",
    "^TNX": "#c54d3a",
    "^VIX": "#7c3aed",
  };

  function fmtPct(v, digits = 2, showPlus = true) {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
    const n = Number(v);
    const sign = showPlus && n > 0 ? "+" : "";
    return `${sign}${n.toFixed(digits)}%`;
  }

  function fmtNum(v, digits = 2) {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
    return Number(v).toLocaleString("en-US", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  }

  function fmtPrice(v, ticker) {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
    const n = Number(v);
    if (ticker === "^TNX") return `${n.toFixed(2)}%`;
    if (ticker === "^VIX") return `${n.toFixed(2)} pts`;
    return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function clsSigned(v) {
    const n = Number(v);
    if (Number.isNaN(n) || n === 0) return "mono";
    return n > 0 ? "pos" : "neg";
  }

  /* =======================================================================
     SVG MULTI-LINE CHART HELPER (EDITORIAL PAPER THEME)
     ======================================================================= */
  function renderMultiLineChart(containerId, seriesList, options = {}) {
    const el = document.getElementById(containerId);
    if (!el) return;

    const width = 600;
    const height = options.height || 250;
    const padL = 52;
    const padR = 18;
    const padT = 16;
    const padB = 28;
    const plotW = width - padL - padR;
    const plotH = height - padT - padB;

    const validSeries = seriesList.filter((s) => s.points && s.points.length > 1);
    if (!validSeries.length) {
      el.innerHTML = `<div style="padding:24px;color:#53615c;">No time-series points available.</div>`;
      return;
    }

    let minY = Infinity;
    let maxY = -Infinity;
    validSeries.forEach((s) => {
      s.points.forEach((pt) => {
        if (pt.y !== null && pt.y !== undefined && !Number.isNaN(pt.y)) {
          if (pt.y < minY) minY = pt.y;
          if (pt.y > maxY) maxY = pt.y;
        }
      });
    });

    if (options.zeroLine) {
      minY = Math.min(minY, 0);
      maxY = Math.max(maxY, 0);
    }

    if (!Number.isFinite(minY) || !Number.isFinite(maxY)) {
      minY = 0;
      maxY = 100;
    }
    if (Math.abs(maxY - minY) < 1e-6) {
      maxY += 1;
      minY -= 1;
    }

    const ySpan = maxY - minY;
    const yTicks = 5;
    let gridHtml = "";

    for (let i = 0; i <= yTicks; i++) {
      const val = minY + (ySpan * i) / yTicks;
      const y = padT + plotH - (plotH * i) / yTicks;
      const label = options.yFormat ? options.yFormat(val) : val.toFixed(0);
      gridHtml += `
        <line x1="${padL}" y1="${y.toFixed(1)}" x2="${width - padR}" y2="${y.toFixed(1)}"
              stroke="#dfe2da" stroke-width="1" />
        <text x="${padL - 6}" y="${(y + 4).toFixed(1)}" text-anchor="end"
              fill="#53615c" font-size="10" font-family="DM Mono, monospace">${label}</text>
      `;
    }

    if (options.baseline !== undefined && options.baseline >= minY && options.baseline <= maxY) {
      const by = padT + plotH - ((options.baseline - minY) / ySpan) * plotH;
      gridHtml += `
        <line x1="${padL}" y1="${by.toFixed(1)}" x2="${width - padR}" y2="${by.toFixed(1)}"
              stroke="#18201e" stroke-width="1.2" stroke-dasharray="4,4" />
      `;
    }

    const refPoints = validSeries[0].points;
    const dateStart = refPoints[0]?.d || "";
    const dateMid = refPoints[Math.floor(refPoints.length / 2)]?.d || "";
    const dateEnd = refPoints[refPoints.length - 1]?.d || "";

    let pathsHtml = "";
    validSeries.forEach((s) => {
      const pts = s.points;
      const n = pts.length;
      const coords = [];
      for (let i = 0; i < n; i++) {
        const yv = pts[i].y;
        if (yv === null || yv === undefined || Number.isNaN(yv)) continue;
        const x = padL + (i / Math.max(1, n - 1)) * plotW;
        const y = padT + plotH - ((yv - minY) / ySpan) * plotH;
        coords.push(`${x.toFixed(1)},${y.toFixed(1)}`);
      }
      if (coords.length > 1) {
        pathsHtml += `
          <polyline fill="none" stroke="${s.color}" stroke-width="${s.width || 2.1}"
                    ${s.dashed ? 'stroke-dasharray="5,4"' : ""}
                    points="${coords.join(" ")}" />
        `;
      }
    });

    const legendHtml = validSeries
      .map((s) => {
        const lastPt = s.points[s.points.length - 1];
        const lastVal =
          lastPt && lastPt.y !== undefined
            ? options.yFormat
              ? options.yFormat(lastPt.y)
              : lastPt.y.toFixed(1)
            : "";
        return `
          <span class="legend-item">
            <span class="legend-swatch" style="background:${s.color}"></span>
            <span>${s.label} <strong>(${lastVal})</strong></span>
          </span>
        `;
      })
      .join("");

    el.innerHTML = `
      <svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}">
        ${gridHtml}
        ${pathsHtml}
        <text x="${padL}" y="${height - 6}" fill="#53615c" font-size="10" font-family="DM Mono, monospace">${dateStart}</text>
        <text x="${padL + plotW / 2}" y="${height - 6}" text-anchor="middle" fill="#53615c" font-size="10" font-family="DM Mono, monospace">${dateMid}</text>
        <text x="${width - padR}" y="${height - 6}" text-anchor="end" fill="#53615c" font-size="10" font-family="DM Mono, monospace">${dateEnd}</text>
      </svg>
      <div class="chart-legend">${legendHtml}</div>
    `;
  }

  /* =======================================================================
     TAB 1: OVERVIEW & DATA ENGINEERING AUDIT
     ======================================================================= */
  function renderOverviewTab() {
    if (!DATASET) return;

    const meta = DATASET.metadata || {};
    const summaries = DATASET.asset_summaries || [];

    const obsEl = document.getElementById("kpi-total-obs");
    if (obsEl && meta.total_observations) {
      obsEl.textContent = Number(meta.total_observations).toLocaleString("en-US");
    }
    const rangeEl = document.getElementById("meta-sample-range");
    if (rangeEl && meta.sample_start && meta.sample_end) {
      rangeEl.textContent = `${meta.sample_start} → ${meta.sample_end}`;
    }

    const stocksOnly = summaries.filter((s) => s.role === "Equity");
    const topCagr = [...stocksOnly].sort((a, b) => b.cagr_pct - a.cagr_pct)[0];
    const secondCagr = [...stocksOnly].sort((a, b) => b.cagr_pct - a.cagr_pct)[1];
    const topSharpe = [...stocksOnly].sort((a, b) => b.sharpe_ratio - a.sharpe_ratio)[0];
    const sp500 = summaries.find((s) => s.ticker === "^GSPC");
    const macro = DATASET.macro_analysis || {};

    const kpiRow = document.getElementById("overview-kpi-row");
    if (kpiRow) {
      kpiRow.innerHTML = `
        <div class="kpi-card">
          <span class="kpi-label">#1 US GROWTH LEADER</span>
          <strong class="kpi-val pos">${topCagr ? topCagr.ticker : "NVDA"} (${fmtPct(topCagr?.cagr_pct)} CAGR)</strong>
          <span class="kpi-sub">Total Return: ${fmtPct(topCagr?.total_return_pct)} · Sharpe ${fmtNum(topCagr?.sharpe_ratio)}</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">#2 US GROWTH LEADER</span>
          <strong class="kpi-val pos">${secondCagr ? secondCagr.ticker : "AVGO"} (${fmtPct(secondCagr?.cagr_pct)} CAGR)</strong>
          <span class="kpi-sub">Total Return: ${fmtPct(secondCagr?.total_return_pct)} · Beta ${fmtNum(secondCagr?.beta)}</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">S&P 500 (^GSPC) BENCHMARK</span>
          <strong class="kpi-val ${clsSigned(sp500?.total_return_pct)}">${fmtPct(sp500?.total_return_pct)}</strong>
          <span class="kpi-sub">CAGR: ${fmtPct(sp500?.cagr_pct)} · Ann. Vol: ${fmtPct(sp500?.annualized_volatility_pct, 2, false)}</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">US 10Y TREASURY YIELD (^TNX)</span>
          <strong class="kpi-val mono">${fmtNum(macro.tnx_start)}% → ${fmtNum(macro.tnx_latest)}%</strong>
          <span class="kpi-sub">Cycle Range: ${fmtNum(macro.tnx_min)}% – ${fmtNum(macro.tnx_max)}% (${macro.yield_spike_days_count || 0} Spike Days)</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">CBOE VOLATILITY INDEX (^VIX)</span>
          <strong class="kpi-val mono">${fmtNum(macro.vix_latest)} pts</strong>
          <span class="kpi-sub">Sample Peak: ${fmtNum(macro.vix_max)} pts · ${macro.high_vix_days_count || 0} High-Fear Sessions</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">BEST RISK-ADJUSTED SHARPE</span>
          <strong class="kpi-val pos">${topSharpe ? topSharpe.ticker : "NVDA"} (${fmtNum(topSharpe?.sharpe_ratio)})</strong>
          <span class="kpi-sub">Annualized Alpha: ${fmtPct(topSharpe?.alpha_annual_pct)} vs ^GSPC</span>
        </div>
      `;
    }

    renderOverviewCumulativeChart();
    renderRiskReturnScatter();
    renderCleaningAuditTable();
    renderAssetSummaryTable();
  }

  function renderOverviewCumulativeChart() {
    const modeSelect = document.getElementById("ov-return-mode");
    const mode = modeSelect ? modeSelect.value : "raw";
    const field = mode === "excess" ? "exc_idx" : "idx";

    const tickersToShow = [
      { ticker: "AAPL", label: "AAPL" },
      { ticker: "MSFT", label: "MSFT" },
      { ticker: "GOOGL", label: "GOOGL" },
      { ticker: "AMZN", label: "AMZN" },
      { ticker: "META", label: "META" },
      { ticker: "ORCL", label: "ORCL" },
      { ticker: "^GSPC", label: "S&P 500 (^GSPC)", dashed: true },
    ];

    const seriesList = tickersToShow.map((item) => {
      const raw = DATASET.time_series[item.ticker] || [];
      return {
        label: item.label,
        color: SERIES_COLORS[item.ticker] || "#18201e",
        dashed: item.dashed,
        width: item.dashed ? 2.4 : 2.0,
        points: raw.map((r) => ({ d: r.d, y: r[field] })),
      };
    });

    renderMultiLineChart("ov-cumulative-chart", seriesList, {
      baseline: 100,
      yFormat: (v) => v.toFixed(0),
    });
  }

  function renderRiskReturnScatter() {
    const el = document.getElementById("ov-risk-return-chart");
    if (!el || !DATASET) return;

    const items = (DATASET.asset_summaries || []).filter((s) => s.role !== "Macro");
    const width = 600;
    const height = 250;
    const padL = 52;
    const padR = 28;
    const padT = 18;
    const padB = 32;
    const plotW = width - padL - padR;
    const plotH = height - padT - padB;

    const vols = items.map((s) => s.annualized_volatility_pct);
    const cagrs = items.map((s) => s.cagr_pct);
    const minX = Math.max(0, Math.min(...vols) - 4);
    const maxX = Math.max(...vols) + 6;
    const minY = Math.min(0, Math.min(...cagrs) - 4);
    const maxY = Math.max(...cagrs) + 8;

    let grid = "";
    for (let i = 0; i <= 4; i++) {
      const yv = minY + ((maxY - minY) * i) / 4;
      const y = padT + plotH - (plotH * i) / 4;
      grid += `
        <line x1="${padL}" y1="${y.toFixed(1)}" x2="${width - padR}" y2="${y.toFixed(1)}"
              stroke="#dfe2da" stroke-width="1" />
        <text x="${padL - 6}" y="${(y + 4).toFixed(1)}" text-anchor="end"
              fill="#53615c" font-size="10" font-family="DM Mono, monospace">${yv.toFixed(0)}%</text>
      `;
    }

    for (let i = 0; i <= 4; i++) {
      const xv = minX + ((maxX - minX) * i) / 4;
      const x = padL + (plotW * i) / 4;
      grid += `
        <text x="${x.toFixed(1)}" y="${height - 6}" text-anchor="middle"
              fill="#53615c" font-size="10" font-family="DM Mono, monospace">${xv.toFixed(0)}% Vol</text>
      `;
    }

    const dots = items
      .map((s) => {
        const x = padL + ((s.annualized_volatility_pct - minX) / (maxX - minX)) * plotW;
        const y = padT + plotH - ((s.cagr_pct - minY) / (maxY - minY)) * plotH;
        const r = Math.max(5.5, Math.min(13, 5.5 + Math.max(0, s.sharpe_ratio) * 3.8));
        const col = s.role === "Benchmark" ? "#18201e" : "#5e8519";
        return `
          <g>
            <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r.toFixed(1)}"
                    fill="${col}" fill-opacity="0.82" stroke="#18201e" stroke-width="1.2" />
            <text x="${(x + r + 4).toFixed(1)}" y="${(y + 3).toFixed(1)}"
                  fill="#18201e" font-size="10" font-family="DM Mono, monospace" font-weight="700">${s.ticker}</text>
          </g>
        `;
      })
      .join("");

    el.innerHTML = `
      <svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}">
        ${grid}
        ${dots}
      </svg>
      <div class="chart-legend">
        <span class="legend-item"><span class="legend-swatch" style="background:#5e8519"></span>10 US Mega-Cap Equities (Bubble = Sharpe Ratio)</span>
        <span class="legend-item"><span class="legend-swatch" style="background:#18201e"></span>S&P 500 Benchmark (^GSPC)</span>
      </div>
    `;
  }

  function renderCleaningAuditTable() {
    const tbody = document.getElementById("cleaning-audit-tbody");
    if (!tbody || !DATASET) return;

    tbody.innerHTML = (DATASET.cleaning_audit || [])
      .map(
        (r) => `
        <tr>
          <td class="mono"><strong>${r.ticker}</strong></td>
          <td>${r.name}</td>
          <td><span class="tag-pill">${r.role}</span> ${r.sector}</td>
          <td class="mono">${Number(r.raw_rows).toLocaleString("en-US")}</td>
          <td class="mono">${r.missing_aligned} aligned</td>
          <td class="mono pos">${r.duplicates_removed}</td>
          <td class="mono"><strong>${Number(r.clean_trading_days).toLocaleString("en-US")}</strong> days</td>
          <td class="mono">${r.first_date} → ${r.last_date}</td>
          <td class="mono">${Number(r.adj_factor_initial).toFixed(4)}</td>
          <td>${r.corporate_action_note}</td>
        </tr>
      `
      )
      .join("");
  }

  function renderAssetSummaryTable() {
    const tbody = document.getElementById("asset-summary-tbody");
    if (!tbody || !DATASET) return;

    const filterEl = document.getElementById("ov-role-filter");
    const roleFilter = filterEl ? filterEl.value : "All";

    const rows = (DATASET.asset_summaries || []).filter((r) => {
      if (roleFilter === "All") return true;
      if (roleFilter === "Equity") return r.role === "Equity";
      return r.role !== "Equity";
    });

    tbody.innerHTML = rows
      .map(
        (r) => `
        <tr>
          <td class="mono"><strong>${r.ticker}</strong></td>
          <td>${r.name}</td>
          <td>${r.sector}</td>
          <td class="mono">${fmtPrice(r.latest_price, r.ticker)}</td>
          <td class="${clsSigned(r.total_return_pct)}">${fmtPct(r.total_return_pct)}</td>
          <td class="${clsSigned(r.excess_return_pct)}">${fmtPct(r.excess_return_pct)}</td>
          <td class="${clsSigned(r.cagr_pct)}">${fmtPct(r.cagr_pct)}</td>
          <td class="mono">${fmtPct(r.annualized_volatility_pct, 2, false)}</td>
          <td class="mono"><strong>${fmtNum(r.sharpe_ratio)}</strong></td>
          <td class="neg">${fmtPct(r.max_drawdown_pct)}</td>
          <td class="mono">${fmtNum(r.skewness)}</td>
          <td class="mono">${fmtNum(r.kurtosis)}</td>
        </tr>
      `
      )
      .join("");
  }

  /* =======================================================================
     TAB 2: INTERACTIVE US STOCK EXPLORER & FEATURE ENGINEERING
     ======================================================================= */
  function filterPointsByRange(points, rangeCode) {
    if (!points || !points.length || rangeCode === "ALL") return points;
    const count = rangeCode === "1Y" ? 52 : rangeCode === "3Y" ? 155 : points.length;
    return points.slice(Math.max(0, points.length - count));
  }

  function renderExplorerTab() {
    if (!DATASET) return;

    const tickerEl = document.getElementById("exp-ticker-select");
    const compareEl = document.getElementById("exp-compare-select");
    const ticker = tickerEl ? tickerEl.value : "NVDA";
    const compareTicker = compareEl ? compareEl.value : "^GSPC";

    const summary = (DATASET.asset_summaries || []).find((s) => s.ticker === ticker) || {};
    const kpiStrip = document.getElementById("exp-kpi-strip");
    if (kpiStrip) {
      kpiStrip.innerHTML = `
        <div class="kpi-card">
          <span class="kpi-label">${summary.ticker || ticker} LATEST CLOSE</span>
          <strong class="kpi-val">${fmtPrice(summary.latest_price, ticker)}</strong>
          <span class="kpi-sub">${summary.name || ""} · ${summary.sector || ""}</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">TOTAL RETURN (NOMINAL / EXCESS)</span>
          <strong class="kpi-val ${clsSigned(summary.total_return_pct)}">${fmtPct(summary.total_return_pct)}</strong>
          <span class="kpi-sub">Excess vs 10Y Treasury: ${fmtPct(summary.excess_return_pct)}</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">VOLATILITY & MAX DRAWDOWN</span>
          <strong class="kpi-val neg">${fmtPct(summary.max_drawdown_pct)} Max DD</strong>
          <span class="kpi-sub">Annualized Volatility: ${fmtPct(summary.annualized_volatility_pct, 2, false)}</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">CAPM BETA & ANNUAL ALPHA</span>
          <strong class="kpi-val ${clsSigned(summary.alpha_annual_pct)}">α = ${fmtPct(summary.alpha_annual_pct)}</strong>
          <span class="kpi-sub">Beta (β) = ${fmtNum(summary.beta)} vs S&P 500 (^GSPC)</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">ANOMALY SPIKES DETECTED</span>
          <strong class="kpi-val mono">${summary.volume_anomalies_count || 0} Vol Spikes</strong>
          <span class="kpi-sub">${summary.return_3sigma_outliers || 0} Tail Shocks (>3σ)</span>
        </div>
      `;
    }

    const rawA = filterPointsByRange(DATASET.time_series[ticker] || [], activeRange);
    const rawB = filterPointsByRange(DATASET.time_series[compareTicker] || [], activeRange);

    const baseLocalA = rawA[0]?.idx || 100;
    const baseExcA = rawA[0]?.exc_idx || 100;
    const baseLocalB = rawB[0]?.idx || 100;

    renderMultiLineChart(
      "exp-price-chart",
      [
        {
          label: `${ticker} Nominal Index`,
          color: "#18201e",
          width: 2.3,
          points: rawA.map((r) => ({ d: r.d, y: (r.idx / baseLocalA) * 100 })),
        },
        {
          label: `${ticker} Rate-Adj Excess Index`,
          color: "#5e8519",
          dashed: true,
          width: 1.9,
          points: rawA.map((r) => ({ d: r.d, y: (r.exc_idx / baseExcA) * 100 })),
        },
        {
          label: `${compareTicker} Benchmark/Peer`,
          color: "#c54d3a",
          width: 2.0,
          points: rawB.map((r) => ({ d: r.d, y: (r.idx / baseLocalB) * 100 })),
        },
      ],
      { baseline: 100, yFormat: (v) => v.toFixed(0) }
    );

    renderMultiLineChart(
      "exp-vol-chart",
      [
        {
          label: `${ticker} 30D Annualized Volatility (%)`,
          color: "#5e8519",
          width: 2.1,
          points: rawA.map((r) => ({ d: r.d, y: r.vol30 })),
        },
        {
          label: `${ticker} Drawdown (%)`,
          color: "#c54d3a",
          width: 1.9,
          points: rawA.map((r) => ({ d: r.d, y: r.dd })),
        },
      ],
      { baseline: 0, yFormat: (v) => `${v.toFixed(0)}%` }
    );

    renderMultiLineChart(
      "exp-vz-chart",
      [
        {
          label: `${ticker} 20D Volume Z-Score`,
          color: "#18201e",
          width: 2.0,
          points: rawA.map((r) => ({ d: r.d, y: r.vz })),
        },
      ],
      { baseline: 2.5, zeroLine: true, yFormat: (v) => `${v.toFixed(1)}σ` }
    );

    renderCorrelationMatrix();
  }

  function renderCorrelationMatrix() {
    const wrap = document.getElementById("exp-corr-matrix");
    if (!wrap || !DATASET || !DATASET.correlation_matrix) return;

    const { tickers, rows } = DATASET.correlation_matrix;
    const ths = tickers.map((t) => `<th class="mono">${t}</th>`).join("");
    const trs = rows
      .map((row) => {
        const tds = row.values
          .map((v) => {
            const val = Number(v);
            let bg = "transparent";
            if (val > 0.08) {
              bg = `rgba(122, 175, 24, ${Math.min(0.42, val * 0.42).toFixed(2)})`;
            } else if (val < -0.08) {
              bg = `rgba(197, 77, 58, ${Math.min(0.42, Math.abs(val) * 0.55).toFixed(2)})`;
            }
            return `<td class="mono" style="background:${bg};text-align:center;">${val.toFixed(2)}</td>`;
          })
          .join("");
        return `<tr><td class="mono"><strong>${row.ticker}</strong></td>${tds}</tr>`;
      })
      .join("");

    wrap.innerHTML = `
      <table class="data-table">
        <thead>
          <tr><th>Ticker</th>${ths}</tr>
        </thead>
        <tbody>${trs}</tbody>
      </table>
    `;
  }

  /* =======================================================================
     TAB 3: MARKET-ADJUSTED RETURNS (CAPM) & US MACRO (^TNX & ^VIX)
     ======================================================================= */
  function renderComparisonTab() {
    if (!DATASET) return;
    renderCapmSection();
    renderMacroSection();
  }

  function renderCapmSection() {
    const selectEl = document.getElementById("capm-stock-select");
    const ticker = selectEl ? selectEl.value : "NVDA";
    const stockPts = DATASET.time_series[ticker] || [];
    const bmkPts = DATASET.time_series["^GSPC"] || [];

    renderMultiLineChart(
      "capm-residual-chart",
      [
        {
          label: `${ticker} Nominal Cumulative Index`,
          color: "#18201e",
          width: 2.2,
          points: stockPts.map((r) => ({ d: r.d, y: r.idx })),
        },
        {
          label: `${ticker} Market-Adjusted Residual Index (α + ε)`,
          color: "#5e8519",
          width: 2.2,
          points: stockPts.map((r) => ({ d: r.d, y: r.res_idx })),
        },
        {
          label: `S&P 500 (^GSPC) Benchmark`,
          color: "#c54d3a",
          dashed: true,
          width: 1.9,
          points: bmkPts.map((r) => ({ d: r.d, y: r.idx })),
        },
      ],
      { baseline: 100, yFormat: (v) => v.toFixed(0) }
    );

    const tbody = document.getElementById("capm-table-tbody");
    if (tbody) {
      tbody.innerHTML = (DATASET.capm_table || [])
        .map(
          (r) => `
          <tr>
            <td class="mono"><strong>${r.ticker}</strong></td>
            <td class="mono">${r.benchmark}</td>
            <td class="mono"><strong>${fmtNum(r.beta)}</strong></td>
            <td class="${clsSigned(r.alpha_annual_pct)}">${fmtPct(r.alpha_annual_pct)}</td>
            <td class="mono">${fmtPct(r.r_squared_pct, 1, false)}</td>
            <td class="mono">${fmtPct(r.idiosyncratic_vol_pct, 1, false)}</td>
            <td class="mono">${fmtNum(r.information_ratio)}</td>
            <td class="${clsSigned(r.raw_total_return_pct)}">${fmtPct(r.raw_total_return_pct)}</td>
            <td class="${clsSigned(r.market_adjusted_cum_residual_pct)}">${fmtPct(r.market_adjusted_cum_residual_pct)}</td>
          </tr>
        `
        )
        .join("");
    }
  }

  function renderMacroSection() {
    const macro = DATASET.macro_analysis || {};
    const badge = document.getElementById("macro-fx-badge");
    if (badge && macro.tnx_start !== undefined) {
      badge.textContent = `US 10Y Yield (^TNX): ${fmtNum(macro.tnx_start)}% → ${fmtNum(macro.tnx_latest)}% · VIX: ${fmtNum(macro.vix_latest)}`;
    }

    const narr = document.getElementById("macro-narrative-text");
    if (narr) {
      narr.textContent = macro.narrative || "";
    }

    const spPts = DATASET.time_series["^GSPC"] || [];
    const tnxPts = DATASET.time_series["^TNX"] || [];
    const vixPts = DATASET.time_series["^VIX"] || [];

    renderMultiLineChart(
      "macro-fx-chart",
      [
        {
          label: "S&P 500 (^GSPC) Index (Base=100)",
          color: "#18201e",
          width: 2.3,
          points: spPts.map((r) => ({ d: r.d, y: r.idx })),
        },
        {
          label: "US 10Y Treasury Yield (^TNX, Base=100)",
          color: "#c54d3a",
          width: 2.0,
          points: tnxPts.map((r) => ({ d: r.d, y: r.idx })),
        },
        {
          label: "CBOE VIX Fear Index (^VIX, Base=100)",
          color: "#7c3aed",
          dashed: true,
          width: 1.8,
          points: vixPts.map((r) => ({ d: r.d, y: r.idx })),
        },
      ],
      { baseline: 100, yFormat: (v) => v.toFixed(0) }
    );

    const corrSeries = macro.rolling_60d_corr || [];
    renderMultiLineChart(
      "macro-rolling-corr-chart",
      [
        {
          label: "60D Corr (S&P 500 vs Δ10Y Yield)",
          color: "#5e8519",
          width: 2.1,
          points: corrSeries.map((r) => ({ d: r.date, y: r.corr_tnx })),
        },
        {
          label: "60D Corr (S&P 500 vs ΔVIX)",
          color: "#c54d3a",
          dashed: true,
          width: 1.9,
          points: corrSeries.map((r) => ({ d: r.date, y: r.corr_vix })),
        },
      ],
      { baseline: 0, zeroLine: true, yFormat: (v) => v.toFixed(2) }
    );

    const tbody = document.getElementById("macro-regime-tbody");
    if (tbody) {
      tbody.innerHTML = (macro.regime_impacts || [])
        .map(
          (r) => `
          <tr>
            <td class="mono"><strong>${r.ticker}</strong></td>
            <td>${r.name}</td>
            <td>${r.sector}</td>
            <td class="${clsSigned(r.corr_with_tnx_change)}">${fmtNum(r.corr_with_tnx_change, 3)}</td>
            <td class="${clsSigned(r.corr_with_vix_change)}">${fmtNum(r.corr_with_vix_change, 3)}</td>
            <td class="${clsSigned(r.avg_ret_yield_spike_pct)}">${fmtPct(r.avg_ret_yield_spike_pct, 3)}</td>
            <td class="${clsSigned(r.avg_ret_yield_drop_pct)}">${fmtPct(r.avg_ret_yield_drop_pct, 3)}</td>
            <td class="${clsSigned(r.avg_ret_high_vix_pct)}">${fmtPct(r.avg_ret_high_vix_pct, 3)}</td>
            <td class="${clsSigned(r.raw_cum_return_pct)}">${fmtPct(r.raw_cum_return_pct)}</td>
            <td class="${clsSigned(r.excess_cum_return_pct)}">${fmtPct(r.excess_cum_return_pct)}</td>
          </tr>
        `
        )
        .join("");
    }
  }

  /* =======================================================================
     TAB 4: 10 VERIFIED US EVENTS, UNUSUAL SPIKES & SPOT-CHECKS
     ======================================================================= */
  function renderEventsTab() {
    if (!DATASET) return;

    const eventsGrid = document.getElementById("verified-events-grid");
    if (eventsGrid) {
      eventsGrid.innerHTML = (DATASET.verified_events || [])
        .map(
          (ev) => `
          <div class="event-card">
            <div class="event-top">
              <span class="event-id-badge">${ev.event_id} · ${ev.matched_trading_date} · ${ev.ticker}</span>
              <span class="tag-pill">${ev.category}</span>
            </div>
            <div class="event-title">${ev.title}</div>
            <p class="event-desc">${ev.explanation}</p>
            <div class="event-metrics">
              <div class="event-metric-item">
                <span>ACTUAL DAY RETURN</span>
                <strong class="${clsSigned(ev.actual_day_return_pct)}">${fmtPct(ev.actual_day_return_pct)}</strong>
              </div>
              <div class="event-metric-item">
                <span>ABNORMAL RETURN (T0)</span>
                <strong class="${clsSigned(ev.abnormal_return_t0_pct)}">${fmtPct(ev.abnormal_return_t0_pct)}</strong>
              </div>
              <div class="event-metric-item">
                <span>5-DAY CAR</span>
                <strong class="${clsSigned(ev.car_5d_pct)}">${fmtPct(ev.car_5d_pct)}</strong>
              </div>
              <div class="event-metric-item">
                <span>Z-SCORE (RET / VOL)</span>
                <strong class="mono">${fmtNum(ev.return_zscore)}σ / ${fmtNum(ev.volume_zscore)}σ</strong>
              </div>
            </div>
            <div class="event-source">Verified Source: ${ev.source}</div>
          </div>
        `
        )
        .join("");
    }

    renderAnomaliesTable();
    renderSpotCheckTable();
  }

  function renderAnomaliesTable() {
    const tbody = document.getElementById("anomalies-tbody");
    if (!tbody || !DATASET) return;

    const filterEl = document.getElementById("anom-ticker-filter");
    const tk = filterEl ? filterEl.value : "All";

    const rows = (DATASET.unusual_movements || []).filter(
      (r) => tk === "All" || r.ticker === tk
    );

    tbody.innerHTML = rows
      .map(
        (r, idx) => `
        <tr>
          <td class="mono">#${idx + 1}</td>
          <td class="mono"><strong>${r.date}</strong></td>
          <td class="mono"><strong>${r.ticker}</strong></td>
          <td>${r.name}</td>
          <td class="mono">$${fmtNum(r.close)}</td>
          <td class="${clsSigned(r.daily_return_pct)}">${fmtPct(r.daily_return_pct)}</td>
          <td class="${clsSigned(r.return_zscore)}">${fmtNum(r.return_zscore)}σ</td>
          <td class="mono"><strong>+${fmtNum(r.volume_zscore)}σ</strong></td>
          <td class="${clsSigned(r.benchmark_return_pct)}">${fmtPct(r.benchmark_return_pct)}</td>
          <td><span class="tag-pill">${r.anomaly_type}</span></td>
        </tr>
      `
      )
      .join("");
  }

  function renderSpotCheckTable() {
    const tbody = document.getElementById("spot-check-tbody");
    if (!tbody || !DATASET) return;

    tbody.innerHTML = (DATASET.spot_checks || [])
      .map(
        (s) => `
        <tr>
          <td class="mono"><strong>${s.check_id}</strong></td>
          <td><strong>${s.metric}</strong></td>
          <td class="mono">${s.ticker} · ${s.date}</td>
          <td class="mono">${s.formula}</td>
          <td class="mono">${s.inputs}</td>
          <td class="mono pos">${s.manual_value}</td>
          <td class="mono pos">${s.pipeline_value}</td>
          <td class="mono">${Number(s.difference).toFixed(6)}</td>
          <td><span class="badge-verified">✓ ${s.status}</span></td>
        </tr>
      `
      )
      .join("");
  }

  /* =======================================================================
     NAVIGATION & EVENT LISTENERS
     ======================================================================= */
  function switchPlatformMode(mode) {
    const secLanding = document.getElementById("section-landing");
    const secAnalyst = document.getElementById("section-analyst");
    const secDeep = document.getElementById("section-deepquant");
    const btnLanding = document.getElementById("btn-mode-landing");
    const btnAnalyst = document.getElementById("btn-mode-analyst");
    const btnDeep = document.getElementById("btn-mode-deepquant");

    if (secLanding) secLanding.hidden = mode !== "landing";
    if (secAnalyst) secAnalyst.hidden = mode !== "analyst";
    if (secDeep) secDeep.hidden = mode !== "deepquant";

    if (btnLanding) btnLanding.classList.toggle("is-active", mode === "landing");
    if (btnAnalyst) btnAnalyst.classList.toggle("is-active", mode === "analyst");
    if (btnDeep) btnDeep.classList.toggle("is-active", mode === "deepquant");

    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function switchDashboardTab(tabId) {
    const tabs = ["overview", "explorer", "comparison", "events"];
    tabs.forEach((t) => {
      const panel = document.getElementById(`tab-${t}`);
      if (panel) panel.hidden = t !== tabId;
    });

    document.querySelectorAll(".nav-tab").forEach((btn) => {
      btn.classList.toggle("is-active", btn.getAttribute("data-tab") === tabId);
    });

    if (tabId === "overview") renderOverviewTab();
    if (tabId === "explorer") renderExplorerTab();
    if (tabId === "comparison") renderComparisonTab();
    if (tabId === "events") renderEventsTab();
  }

  function bindEvents() {
    const btnLanding = document.getElementById("btn-mode-landing");
    const btnAnalyst = document.getElementById("btn-mode-analyst");
    const btnDeep = document.getElementById("btn-mode-deepquant");
    const btnBack = document.getElementById("btn-back-to-analyst");
    const brandHome = document.getElementById("brand-home-link");
    const btnEnterAnalyst = document.getElementById("btn-landing-enter-analyst");
    const btnEnterDeep = document.getElementById("btn-landing-enter-deep");

    if (btnLanding) btnLanding.addEventListener("click", () => switchPlatformMode("landing"));
    if (btnAnalyst) btnAnalyst.addEventListener("click", () => switchPlatformMode("analyst"));
    if (btnDeep) btnDeep.addEventListener("click", () => switchPlatformMode("deepquant"));
    if (btnBack) btnBack.addEventListener("click", () => switchPlatformMode("analyst"));
    if (btnEnterAnalyst) btnEnterAnalyst.addEventListener("click", () => switchPlatformMode("analyst"));
    if (btnEnterDeep) btnEnterDeep.addEventListener("click", () => switchPlatformMode("deepquant"));
    if (brandHome) {
      brandHome.addEventListener("click", (e) => {
        e.preventDefault();
        switchPlatformMode("landing");
      });
    }

    document.querySelectorAll(".clickable-card[data-goto-tab]").forEach((card) => {
      card.addEventListener("click", () => {
        const target = card.getAttribute("data-goto-tab");
        switchPlatformMode("analyst");
        if (target) switchDashboardTab(target);
      });
    });

    document.querySelectorAll(".nav-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        const target = btn.getAttribute("data-tab");
        if (target) switchDashboardTab(target);
      });
    });

    const retMode = document.getElementById("ov-return-mode");
    if (retMode) retMode.addEventListener("change", renderOverviewCumulativeChart);

    const roleFilter = document.getElementById("ov-role-filter");
    if (roleFilter) roleFilter.addEventListener("change", renderAssetSummaryTable);

    const expTicker = document.getElementById("exp-ticker-select");
    const expCompare = document.getElementById("exp-compare-select");
    if (expTicker) expTicker.addEventListener("change", renderExplorerTab);
    if (expCompare) expCompare.addEventListener("change", renderExplorerTab);

    document.querySelectorAll("#exp-range-pills button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document
          .querySelectorAll("#exp-range-pills button")
          .forEach((b) => b.classList.remove("is-active"));
        btn.classList.add("is-active");
        activeRange = btn.getAttribute("data-range") || "ALL";
        renderExplorerTab();
      });
    });

    const capmSelect = document.getElementById("capm-stock-select");
    if (capmSelect) capmSelect.addEventListener("change", renderCapmSection);

    const anomFilter = document.getElementById("anom-ticker-filter");
    if (anomFilter) anomFilter.addEventListener("change", renderAnomaliesTable);
  }

  async function init() {
    bindEvents();
    try {
      const res = await fetch("data/analyst_dataset.json");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      DATASET = await res.json();
      renderOverviewTab();
      renderExplorerTab();
      renderComparisonTab();
      renderEventsTab();
    } catch (err) {
      console.error("Failed to load analyst_dataset.json:", err);
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
