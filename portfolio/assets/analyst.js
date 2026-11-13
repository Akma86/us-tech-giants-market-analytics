/* =========================================================================
   US EQUITY ATLAS - QUANTITATIVE ENGINE & INTERACTIVE CHART SUITE
   ========================================================================= */

(function () {
  "use strict";

  let DATASET = null;
  let activeRange = "ALL";
  let tyRange = "ALL";
  let tyMode = "dual";
  let tyScale = "log";

  const SERIES_COLORS = {
    NVDA: "#47641f",
    AAPL: "#111a17",
    MSFT: "#116947",
    GOOGL: "#1d4ed8",
    AMZN: "#b45309",
    META: "#0f766e",
    TSLA: "#b43622",
    AVGO: "#0369a1",
    AMD: "#be123c",
    ORCL: "#52625b",
    "^GSPC": "#111a17",
    "^TNX": "#b43622",
    "^VIX": "#1d4ed8",
  };

  function escapeHtml(val) {
    return String(val ?? "").replace(/[&<>'"]/g, (ch) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "'": "&#39;",
      '"': "&quot;",
    })[ch]);
  }

  function fmtPct(v, digits = 2, showPlus = true) {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return "--";
    const n = Number(v);
    const sign = showPlus && n > 0 ? "+" : "";
    return `${sign}${n.toFixed(digits)}%`;
  }

  function fmtNum(v, digits = 2) {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return "--";
    return Number(v).toLocaleString("en-US", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  }

  function fmtPrice(v, ticker) {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return "--";
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

  function showEmptyState(containerId, message) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = `<div class="table-state-cell">${escapeHtml(message)}</div>`;
  }

  /* =======================================================================
     INTERACTIVE SVG MULTI-LINE CHART WITH HAIRLINE SCRUBBING & A11Y
     ======================================================================= */
  function renderMultiLineChart(containerId, seriesList, options = {}) {
    const el = document.getElementById(containerId);
    if (!el) return;

    const width = 620;
    const height = options.height || 260;
    const padL = 54;
    const padR = 22;
    const padT = 18;
    const padB = 30;
    const plotW = width - padL - padR;
    const plotH = height - padT - padB;

    const validSeries = seriesList.filter((s) => s.points && s.points.length > 1);
    if (!validSeries.length) {
      showEmptyState(containerId, "No time-series points available for the selected range.");
      return;
    }

    let minY = Infinity;
    let maxY = -Infinity;
    validSeries.forEach((s) => {
      s.points.forEach((pt) => {
        if (pt.y !== null && pt.y !== undefined && Number.isFinite(pt.y)) {
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
    const yTicks = 4;
    let gridHtml = "";

    for (let i = 0; i <= yTicks; i++) {
      const val = minY + (ySpan * i) / yTicks;
      const y = padT + plotH - (plotH * i) / yTicks;
      const label = options.yFormat ? options.yFormat(val) : val.toFixed(0);
      gridHtml += `
        <line x1="${padL}" y1="${y.toFixed(1)}" x2="${width - padR}" y2="${y.toFixed(1)}"
              stroke="rgba(17,26,23,0.1)" stroke-dasharray="2,3" />
        <text x="${padL - 8}" y="${(y + 3.5).toFixed(1)}" text-anchor="end"
              fill="#52625b" font-size="10" font-family="DM Mono, monospace">${escapeHtml(label)}</text>
      `;
    }

    if (options.baseline !== undefined && options.baseline >= minY && options.baseline <= maxY) {
      const by = padT + plotH - ((options.baseline - minY) / ySpan) * plotH;
      gridHtml += `
        <line x1="${padL}" y1="${by.toFixed(1)}" x2="${width - padR}" y2="${by.toFixed(1)}"
              stroke="rgba(17,26,23,0.45)" stroke-width="1.1" stroke-dasharray="4,4" />
      `;
    }

    const refPoints = validSeries[0].points;
    const dateStart = refPoints[0]?.d || "";
    const dateMid = refPoints[Math.floor(refPoints.length / 2)]?.d || "";
    const dateEnd = refPoints[refPoints.length - 1]?.d || "";

    const gradId = `grad-${containerId}`;
    const primaryColor = validSeries[0].color || "#47641f";
    const defsHtml = `
      <defs>
        <linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${primaryColor}" stop-opacity="0.18" />
          <stop offset="100%" stop-color="${primaryColor}" stop-opacity="0.0" />
        </linearGradient>
      </defs>
    `;

    const seriesMeta = validSeries.map((s) => {
      const n = s.points.length;
      const screenPts = [];
      const coords = [];
      let firstX = padL;
      let lastX = padL + plotW;
      let lastY = padT + plotH;

      for (let i = 0; i < n; i++) {
        const yv = s.points[i].y;
        const x = padL + (i / Math.max(1, n - 1)) * plotW;
        if (yv === null || yv === undefined || !Number.isFinite(yv)) {
          screenPts.push(null);
          continue;
        }
        const y = padT + plotH - ((yv - minY) / ySpan) * plotH;
        if (coords.length === 0) firstX = x;
        lastX = x;
        lastY = y;
        coords.push(`${x.toFixed(1)},${y.toFixed(1)}`);
        screenPts.push({ x, y, d: s.points[i].d, val: yv });
      }
      return { s, screenPts, coords, firstX, lastX, lastY };
    });

    let pathsHtml = "";
    seriesMeta.forEach(({ s, coords, firstX, lastX, lastY }, sIdx) => {
      if (coords.length > 1) {
        if (sIdx === 0) {
          const areaPts = `${firstX.toFixed(1)},${(padT + plotH).toFixed(1)} ${coords.join(" ")} ${lastX.toFixed(1)},${(padT + plotH).toFixed(1)}`;
          pathsHtml += `<polygon points="${areaPts}" fill="url(#${gradId})" />`;
        }
        pathsHtml += `
          <polyline fill="none" stroke="${s.color}" stroke-width="${s.width || 2.1}"
                    stroke-linecap="round" stroke-linejoin="round"
                    ${s.dashed ? 'stroke-dasharray="5,4"' : ""}
                    points="${coords.join(" ")}" />
          <circle cx="${lastX.toFixed(1)}" cy="${lastY.toFixed(1)}" r="3.4"
                  fill="${s.color}" stroke="#fbfaf5" stroke-width="1.4" />
        `;
      }
    });

    const legendHtml = validSeries
      .map((s) => {
        const lastPt = s.points[s.points.length - 1];
        const lastVal =
          lastPt && Number.isFinite(lastPt.y)
            ? options.yFormat
              ? options.yFormat(lastPt.y)
              : lastPt.y.toFixed(1)
            : "--";
        return `
          <span class="legend-item">
            <span class="legend-swatch ${s.dashed ? "is-dashed" : ""}" style="background:${s.color}; color:${s.color};"></span>
            <span>${escapeHtml(s.label)} <strong>${escapeHtml(lastVal)}</strong></span>
          </span>
        `;
      })
      .join("");

    const formatReadout = (idx) => {
      const clampedIdx = Math.max(0, Math.min(refPoints.length - 1, idx));
      const dateStr = refPoints[clampedIdx]?.d || "--";
      const vals = validSeries.map((s) => {
        const pt = s.points[clampedIdx];
        const v = pt && Number.isFinite(pt.y)
          ? (options.yFormat ? options.yFormat(pt.y) : pt.y.toFixed(1))
          : "--";
        return `<span style="color:${s.color};">${escapeHtml(s.label.split(" ")[0])}: <strong>${escapeHtml(v)}</strong></span>`;
      }).join(" ");
      return `<span>Date: <strong>${escapeHtml(dateStr)}</strong></span><span>${vals}</span>`;
    };

    el.innerHTML = `
      <div class="chart-readout" data-readout>${formatReadout(refPoints.length - 1)}</div>
      <div class="chart-interactive-surface" tabindex="0" role="img" aria-label="Interactive time-series chart from ${escapeHtml(dateStart)} to ${escapeHtml(dateEnd)}. Use pointer or Left/Right arrow keys to inspect dates.">
        <svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}">
          ${defsHtml}
          ${gridHtml}
          ${pathsHtml}
          <line data-crosshair x1="${padL + plotW}" y1="${padT}" x2="${padL + plotW}" y2="${padT + plotH}" stroke="rgba(17,26,23,0.45)" stroke-width="1.2" stroke-dasharray="3,3" opacity="0" />
          <g data-hover-dots></g>
          <text x="${padL}" y="${height - 6}" fill="#52625b" font-size="10" font-family="DM Mono, monospace">${escapeHtml(dateStart)}</text>
          <text x="${padL + plotW / 2}" y="${height - 6}" text-anchor="middle" fill="#52625b" font-size="10" font-family="DM Mono, monospace">${escapeHtml(dateMid)}</text>
          <text x="${width - padR}" y="${height - 6}" text-anchor="end" fill="#52625b" font-size="10" font-family="DM Mono, monospace">${escapeHtml(dateEnd)}</text>
        </svg>
      </div>
      <div class="chart-legend">${legendHtml}</div>
    `;

    const surface = el.querySelector(".chart-interactive-surface");
    const svg = el.querySelector("svg");
    const readout = el.querySelector("[data-readout]");
    const crosshair = el.querySelector("[data-crosshair]");
    const dotsLayer = el.querySelector("[data-hover-dots]");
    let currentIdx = refPoints.length - 1;

    const updateInspector = (idx, showCrosshair = true) => {
      currentIdx = Math.max(0, Math.min(refPoints.length - 1, idx));
      const xPos = padL + (currentIdx / Math.max(1, refPoints.length - 1)) * plotW;
      readout.innerHTML = formatReadout(currentIdx);
      if (crosshair) {
        crosshair.setAttribute("x1", xPos.toFixed(1));
        crosshair.setAttribute("x2", xPos.toFixed(1));
        crosshair.setAttribute("opacity", showCrosshair ? "1" : "0");
      }
      if (dotsLayer) {
        dotsLayer.innerHTML = showCrosshair
          ? seriesMeta
              .map(({ s, screenPts }) => {
                const pt = screenPts[currentIdx];
                if (!pt) return "";
                return `<circle cx="${pt.x.toFixed(1)}" cy="${pt.y.toFixed(1)}" r="4.2" fill="${s.color}" stroke="#fbfaf5" stroke-width="1.6" />`;
              })
              .join("")
          : "";
      }
    };

    const handlePointer = (clientX) => {
      const rect = svg.getBoundingClientRect();
      if (!rect.width) return;
      const svgX = ((clientX - rect.left) / rect.width) * width;
      const ratio = Math.max(0, Math.min(1, (svgX - padL) / plotW));
      const idx = Math.round(ratio * Math.max(1, refPoints.length - 1));
      updateInspector(idx, true);
    };

    surface.addEventListener("pointermove", (e) => handlePointer(e.clientX));
    surface.addEventListener("pointerdown", (e) => handlePointer(e.clientX));
    surface.addEventListener("pointerleave", () => updateInspector(refPoints.length - 1, false));
    surface.addEventListener("keydown", (e) => {
      const step = Math.max(1, Math.round(refPoints.length / 25));
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        updateInspector(currentIdx - step, true);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        updateInspector(currentIdx + step, true);
      }
    });
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
      rangeEl.textContent = `${meta.sample_start} to ${meta.sample_end}`;
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
          <span class="kpi-label">#1 Growth Leader</span>
          <strong class="kpi-val pos">${escapeHtml(topCagr ? topCagr.ticker : "NVDA")} &middot; ${fmtPct(topCagr?.cagr_pct)}</strong>
          <span class="kpi-sub">Cumulative: ${fmtPct(topCagr?.total_return_pct)} &middot; Sharpe ${fmtNum(topCagr?.sharpe_ratio)}</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">#2 Growth Leader</span>
          <strong class="kpi-val pos">${escapeHtml(secondCagr ? secondCagr.ticker : "AVGO")} &middot; ${fmtPct(secondCagr?.cagr_pct)}</strong>
          <span class="kpi-sub">Cumulative: ${fmtPct(secondCagr?.total_return_pct)} &middot; Beta ${fmtNum(secondCagr?.beta)}</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">S&amp;P 500 (^GSPC) Benchmark</span>
          <strong class="kpi-val ${clsSigned(sp500?.total_return_pct)}">${fmtPct(sp500?.total_return_pct)}</strong>
          <span class="kpi-sub">CAGR: ${fmtPct(sp500?.cagr_pct)} &middot; Ann. Vol: ${fmtPct(sp500?.annualized_volatility_pct, 2, false)}</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">US 10Y Treasury Yield (^TNX)</span>
          <strong class="kpi-val mono">${fmtNum(macro.tnx_start)}% -&gt; ${fmtNum(macro.tnx_latest)}%</strong>
          <span class="kpi-sub">Range: ${fmtNum(macro.tnx_min)}% to ${fmtNum(macro.tnx_max)}% (${macro.yield_spike_days_count || 0} Spikes)</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">CBOE Volatility Index (^VIX)</span>
          <strong class="kpi-val mono">${fmtNum(macro.vix_latest)} pts</strong>
          <span class="kpi-sub">Cycle Peak: ${fmtNum(macro.vix_max)} pts &middot; ${macro.high_vix_days_count || 0} High-Fear Days</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">Top Risk-Adjusted Sharpe</span>
          <strong class="kpi-val pos">${escapeHtml(topSharpe ? topSharpe.ticker : "NVDA")} (${fmtNum(topSharpe?.sharpe_ratio)})</strong>
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
      { ticker: "^GSPC", label: "^GSPC", dashed: true },
    ];

    const seriesList = tickersToShow.map((item) => {
      const raw = DATASET.time_series[item.ticker] || [];
      return {
        label: item.label,
        color: SERIES_COLORS[item.ticker] || "#111a17",
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
    if (!items.length) {
      showEmptyState("ov-risk-return-chart", "No equity summary metrics available.");
      return;
    }

    const width = 560;
    const height = 260;
    const padL = 48;
    const padR = 36;
    const padT = 18;
    const padB = 30;
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
              stroke="rgba(17,26,23,0.1)" stroke-dasharray="2,3" />
        <text x="${padL - 8}" y="${(y + 3.5).toFixed(1)}" text-anchor="end"
              fill="#52625b" font-size="10" font-family="DM Mono, monospace">${yv.toFixed(0)}%</text>
      `;
    }

    for (let i = 0; i <= 4; i++) {
      const xv = minX + ((maxX - minX) * i) / 4;
      const x = padL + (plotW * i) / 4;
      grid += `
        <text x="${x.toFixed(1)}" y="${height - 6}" text-anchor="middle"
              fill="#52625b" font-size="10" font-family="DM Mono, monospace">${xv.toFixed(0)}% Vol</text>
      `;
    }

    const dots = items
      .map((s) => {
        const x = padL + ((s.annualized_volatility_pct - minX) / (maxX - minX)) * plotW;
        const y = padT + plotH - ((s.cagr_pct - minY) / (maxY - minY)) * plotH;
        const r = Math.max(6, Math.min(14, 6 + Math.max(0, s.sharpe_ratio) * 4.2));
        const col = s.role === "Benchmark" ? "#111a17" : SERIES_COLORS[s.ticker] || "#47641f";
        return `
          <g class="scatter-node" tabindex="0" role="button" aria-label="${escapeHtml(s.ticker)}: CAGR ${fmtPct(s.cagr_pct)}, Ann Vol ${fmtPct(s.annualized_volatility_pct, 1, false)}, Sharpe ${fmtNum(s.sharpe_ratio)}"
             data-ticker="${escapeHtml(s.ticker)}" data-cagr="${fmtPct(s.cagr_pct)}" data-vol="${fmtPct(s.annualized_volatility_pct, 1, false)}" data-sharpe="${fmtNum(s.sharpe_ratio)}" style="cursor:pointer;">
            <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${(r + 3).toFixed(1)}"
                    fill="${col}" fill-opacity="0.14" />
            <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r.toFixed(1)}"
                    fill="${col}" fill-opacity="0.9" stroke="#fbfaf5" stroke-width="1.4" />
            <text x="${(x + r + 5).toFixed(1)}" y="${(y + 3.5).toFixed(1)}"
                  fill="#111a17" font-size="10" font-family="DM Mono, monospace" font-weight="700">${escapeHtml(s.ticker)}</text>
          </g>
        `;
      })
      .join("");

    const defaultLead = items.find((s) => s.ticker === "NVDA") || items[0];
    el.innerHTML = `
      <div class="chart-readout" data-scatter-readout>
        <span>Point: <strong>${escapeHtml(defaultLead.ticker)}</strong></span>
        <span>CAGR <strong>${fmtPct(defaultLead.cagr_pct)}</strong> &middot; Vol <strong>${fmtPct(defaultLead.annualized_volatility_pct, 1, false)}</strong> &middot; Sharpe <strong>${fmtNum(defaultLead.sharpe_ratio)}</strong></span>
      </div>
      <svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}">
        ${grid}
        ${dots}
      </svg>
      <div class="chart-legend">
        <span class="legend-item"><span class="legend-swatch" style="background:#47641f"></span>10 US Mega-Cap Equities (Radius = Sharpe Ratio)</span>
        <span class="legend-item"><span class="legend-swatch" style="background:#111a17"></span>S&amp;P 500 Benchmark (^GSPC)</span>
      </div>
    `;

    const readout = el.querySelector("[data-scatter-readout]");
    el.querySelectorAll(".scatter-node").forEach((node) => {
      const update = () => {
        if (!readout) return;
        readout.innerHTML = `<span>Point: <strong>${escapeHtml(node.dataset.ticker)}</strong></span><span>CAGR <strong>${escapeHtml(node.dataset.cagr)}</strong> &middot; Vol <strong>${escapeHtml(node.dataset.vol)}</strong> &middot; Sharpe <strong>${escapeHtml(node.dataset.sharpe)}</strong></span>`;
      };
      node.addEventListener("pointerenter", update);
      node.addEventListener("focus", update);
      node.addEventListener("click", () => {
        const tk = node.dataset.ticker;
        const sel = document.getElementById("exp-ticker-select");
        if (sel && tk) {
          sel.value = tk;
          switchDashboardTab("explorer");
        }
      });
    });
  }

  function renderCleaningAuditTable() {
    const tbody = document.getElementById("cleaning-audit-tbody");
    if (!tbody || !DATASET) return;
    const rows = DATASET.cleaning_audit || [];
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="10" class="table-state-cell">No cleaning audit records found.</td></tr>';
      return;
    }

    tbody.innerHTML = rows
      .map(
        (r) => `
        <tr>
          <td class="mono"><strong>${escapeHtml(r.ticker)}</strong></td>
          <td>${escapeHtml(r.name)}</td>
          <td><span class="tag-pill">${escapeHtml(r.role)}</span> ${escapeHtml(r.sector)}</td>
          <td class="mono">${Number(r.raw_rows).toLocaleString("en-US")}</td>
          <td class="mono">${escapeHtml(r.missing_aligned)} aligned</td>
          <td class="mono pos">${escapeHtml(r.duplicates_removed)}</td>
          <td class="mono"><strong>${Number(r.clean_trading_days).toLocaleString("en-US")}</strong> sessions</td>
          <td class="mono">${escapeHtml(r.first_date)} -&gt; ${escapeHtml(r.last_date)}</td>
          <td class="mono">${Number(r.adj_factor_initial).toFixed(4)}</td>
          <td>${escapeHtml(r.corporate_action_note)}</td>
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

    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="12" class="table-state-cell">No assets match the selected filter.</td></tr>';
      return;
    }

    tbody.innerHTML = rows
      .map(
        (r) => `
        <tr>
          <td class="mono"><strong>${escapeHtml(r.ticker)}</strong></td>
          <td>${escapeHtml(r.name)}</td>
          <td>${escapeHtml(r.sector)}</td>
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
          <span class="kpi-label">${escapeHtml(summary.ticker || ticker)} Latest Close</span>
          <strong class="kpi-val">${fmtPrice(summary.latest_price, ticker)}</strong>
          <span class="kpi-sub">${escapeHtml(summary.name || "")} &middot; ${escapeHtml(summary.sector || "")}</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">Total Return (Nominal / Excess)</span>
          <strong class="kpi-val ${clsSigned(summary.total_return_pct)}">${fmtPct(summary.total_return_pct)}</strong>
          <span class="kpi-sub">Excess vs 10Y Treasury: ${fmtPct(summary.excess_return_pct)}</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">Volatility &amp; Max Drawdown</span>
          <strong class="kpi-val neg">${fmtPct(summary.max_drawdown_pct)} Max DD</strong>
          <span class="kpi-sub">Annualized Volatility: ${fmtPct(summary.annualized_volatility_pct, 2, false)}</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">CAPM Beta &amp; Annual Alpha</span>
          <strong class="kpi-val ${clsSigned(summary.alpha_annual_pct)}">alpha = ${fmtPct(summary.alpha_annual_pct)}</strong>
          <span class="kpi-sub">Beta = ${fmtNum(summary.beta)} vs S&amp;P 500 (^GSPC)</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">Anomaly Spikes Detected</span>
          <strong class="kpi-val mono">${summary.volume_anomalies_count || 0} Vol Spikes</strong>
          <span class="kpi-sub">${summary.return_3sigma_outliers || 0} Tail Shocks (&gt;3 sigma)</span>
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
          label: `${ticker} Nominal`,
          color: "#47641f",
          width: 2.3,
          points: rawA.map((r) => ({ d: r.d, y: (r.idx / baseLocalA) * 100 })),
        },
        {
          label: `${ticker} Excess`,
          color: "#111a17",
          dashed: true,
          width: 1.9,
          points: rawA.map((r) => ({ d: r.d, y: (r.exc_idx / baseExcA) * 100 })),
        },
        {
          label: `${compareTicker} Peer`,
          color: "#b43622",
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
          label: `${ticker} 30D Vol (%)`,
          color: "#47641f",
          width: 2.1,
          points: rawA.map((r) => ({ d: r.d, y: r.vol30 })),
        },
        {
          label: `${ticker} Drawdown (%)`,
          color: "#b43622",
          dashed: true,
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
          label: `${ticker} 20D Vol Z-Score`,
          color: "#111a17",
          width: 2.0,
          points: rawA.map((r) => ({ d: r.d, y: r.vz })),
        },
      ],
      { baseline: 2.5, zeroLine: true, yFormat: (v) => `${v.toFixed(1)}s` }
    );

    renderCorrelationMatrix();
  }

  function renderCorrelationMatrix() {
    const wrap = document.getElementById("exp-corr-matrix");
    if (!wrap || !DATASET || !DATASET.correlation_matrix) return;

    const { tickers, rows } = DATASET.correlation_matrix;
    const ths = tickers.map((t) => `<th scope="col" class="mono">${escapeHtml(t)}</th>`).join("");
    const trs = rows
      .map((row) => {
        const tds = row.values
          .map((v) => {
            const val = Number(v);
            let bg = "transparent";
            if (val > 0.08) {
              bg = `rgba(71, 100, 31, ${Math.min(0.26, val * 0.28).toFixed(2)})`;
            } else if (val < -0.08) {
              bg = `rgba(180, 54, 34, ${Math.min(0.24, Math.abs(val) * 0.36).toFixed(2)})`;
            }
            return `<td class="mono" style="background:${bg};text-align:center;">${val.toFixed(2)}</td>`;
          })
          .join("");
        return `<tr><td class="mono"><strong>${escapeHtml(row.ticker)}</strong></td>${tds}</tr>`;
      })
      .join("");

    wrap.innerHTML = `
      <table class="data-table">
        <thead>
          <tr><th scope="col">Ticker</th>${ths}</tr>
        </thead>
        <tbody>${trs}</tbody>
      </table>
    `;
  }

  /* =======================================================================
     TAB 3: MARKET-ADJUSTED RETURNS (CAPM) & US MACRO
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
          label: `${ticker} Nominal`,
          color: "#111a17",
          width: 2.2,
          points: stockPts.map((r) => ({ d: r.d, y: r.idx })),
        },
        {
          label: `${ticker} Residual Alpha`,
          color: "#47641f",
          width: 2.2,
          points: stockPts.map((r) => ({ d: r.d, y: r.res_idx })),
        },
        {
          label: "S&P 500 (^GSPC)",
          color: "#b43622",
          dashed: true,
          width: 1.9,
          points: bmkPts.map((r) => ({ d: r.d, y: r.idx })),
        },
      ],
      { baseline: 100, yFormat: (v) => v.toFixed(0) }
    );

    const tbody = document.getElementById("capm-table-tbody");
    if (tbody) {
      const capmRows = DATASET.capm_table || [];
      if (!capmRows.length) {
        tbody.innerHTML = '<tr><td colspan="9" class="table-state-cell">No CAPM regression rows available.</td></tr>';
        return;
      }
      tbody.innerHTML = capmRows
        .map(
          (r) => `
          <tr>
            <td class="mono"><strong>${escapeHtml(r.ticker)}</strong></td>
            <td class="mono">${escapeHtml(r.benchmark)}</td>
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
      badge.textContent = `US 10Y Yield (^TNX): ${fmtNum(macro.tnx_start)}% -> ${fmtNum(macro.tnx_latest)}% · VIX: ${fmtNum(macro.vix_latest)}`;
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
          label: "S&P 500 (^GSPC)",
          color: "#111a17",
          width: 2.3,
          points: spPts.map((r) => ({ d: r.d, y: r.idx })),
        },
        {
          label: "10Y Yield (^TNX)",
          color: "#b43622",
          width: 2.0,
          points: tnxPts.map((r) => ({ d: r.d, y: r.idx })),
        },
        {
          label: "CBOE VIX (^VIX)",
          color: "#1d4ed8",
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
          label: "60D Corr (SPX vs d10Y)",
          color: "#47641f",
          width: 2.1,
          points: corrSeries.map((r) => ({ d: r.date, y: r.corr_tnx })),
        },
        {
          label: "60D Corr (SPX vs dVIX)",
          color: "#b43622",
          dashed: true,
          width: 1.9,
          points: corrSeries.map((r) => ({ d: r.date, y: r.corr_vix })),
        },
      ],
      { baseline: 0, zeroLine: true, yFormat: (v) => v.toFixed(2) }
    );

    const tbody = document.getElementById("macro-regime-tbody");
    if (tbody) {
      const regimes = macro.regime_impacts || [];
      if (!regimes.length) {
        tbody.innerHTML = '<tr><td colspan="10" class="table-state-cell">No macro regime impact records found.</td></tr>';
        return;
      }
      tbody.innerHTML = regimes
        .map(
          (r) => `
          <tr>
            <td class="mono"><strong>${escapeHtml(r.ticker)}</strong></td>
            <td>${escapeHtml(r.name)}</td>
            <td>${escapeHtml(r.sector)}</td>
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
     TAB 4: VERIFIED US EVENTS, UNUSUAL SPIKES & SPOT-CHECKS
     ======================================================================= */
  function renderEventsTab() {
    if (!DATASET) return;

    const eventsGrid = document.getElementById("verified-events-grid");
    if (eventsGrid) {
      const events = DATASET.verified_events || [];
      if (!events.length) {
        eventsGrid.innerHTML = '<div class="table-state-cell">No verified catalyst events found.</div>';
      } else {
        eventsGrid.innerHTML = events
          .map(
            (ev) => `
            <article class="event-card">
              <div class="event-top">
                <span class="event-id-badge">${escapeHtml(ev.matched_trading_date)} &middot; ${escapeHtml(ev.ticker)}</span>
                <span class="tag-pill">${escapeHtml(ev.category)}</span>
              </div>
              <h3 class="event-title">${escapeHtml(ev.title)}</h3>
              <p class="event-desc">${escapeHtml(ev.explanation)}</p>
              <div class="event-metrics">
                <div class="event-metric-item">
                  <span>Actual 1D Return</span>
                  <strong class="${clsSigned(ev.actual_day_return_pct)}">${fmtPct(ev.actual_day_return_pct)}</strong>
                </div>
                <div class="event-metric-item">
                  <span>Abnormal (T0)</span>
                  <strong class="${clsSigned(ev.abnormal_return_t0_pct)}">${fmtPct(ev.abnormal_return_t0_pct)}</strong>
                </div>
                <div class="event-metric-item">
                  <span>5-Day CAR</span>
                  <strong class="${clsSigned(ev.car_5d_pct)}">${fmtPct(ev.car_5d_pct)}</strong>
                </div>
                <div class="event-metric-item">
                  <span>Z-Score (Ret / Vol)</span>
                  <strong class="mono">${fmtNum(ev.return_zscore)}s / ${fmtNum(ev.volume_zscore)}s</strong>
                </div>
              </div>
              <div class="event-source">
                <span>Source: ${escapeHtml(ev.source)}</span>
                <strong>$${fmtNum(ev.close_price)}</strong>
              </div>
            </article>
          `
          )
          .join("");
      }
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

    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="10" class="table-state-cell">No anomaly events recorded for this ticker filter.</td></tr>';
      return;
    }

    tbody.innerHTML = rows
      .map(
        (r, idx) => `
        <tr>
          <td class="mono">#${idx + 1}</td>
          <td class="mono"><strong>${escapeHtml(r.date)}</strong></td>
          <td class="mono"><strong>${escapeHtml(r.ticker)}</strong></td>
          <td>${escapeHtml(r.name)}</td>
          <td class="mono">$${fmtNum(r.close)}</td>
          <td class="${clsSigned(r.daily_return_pct)}">${fmtPct(r.daily_return_pct)}</td>
          <td class="${clsSigned(r.return_zscore)}">${fmtNum(r.return_zscore)}s</td>
          <td class="mono"><strong>+${fmtNum(r.volume_zscore)}s</strong></td>
          <td class="${clsSigned(r.benchmark_return_pct)}">${fmtPct(r.benchmark_return_pct)}</td>
          <td><span class="tag-pill">${escapeHtml(r.anomaly_type)}</span></td>
        </tr>
      `
      )
      .join("");
  }

  function buildNiceLinearTicks(minV, maxV, count = 5) {
    const span = maxV - minV || 1;
    const rawStep = span / Math.max(count - 1, 1);
    const pow = Math.pow(10, Math.floor(Math.log10(Math.abs(rawStep))));
    const norm = rawStep / pow;
    const niceNorm = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10;
    const step = niceNorm * pow;
    const start = Math.floor(minV / step) * step;
    const ticks = [];
    for (let v = start; v <= maxV + step * 0.5 && ticks.length < 10; v += step) {
      if (v >= minV - step * 0.15) ticks.push(Number(v.toFixed(4)));
    }
    return ticks;
  }

  function formatCompactIndex(val) {
    const n = Number(val);
    if (!Number.isFinite(n)) return "--";
    if (n >= 1000) return Math.round(n).toLocaleString("en-US");
    if (n >= 100) return n.toFixed(0);
    if (n >= 10) return n.toFixed(1).replace(/\.0$/, "");
    return n.toFixed(2);
  }

  function renderHistoricalTreasurySection() {
    const hist = DATASET?.historical_treasury_sp500;
    const startEl = document.getElementById("ty-kpi-start");
    if (!hist || !hist.available || !Array.isArray(hist.series) || !hist.series.length) {
      if (startEl) startEl.textContent = "Unavailable";
      showEmptyState("treasury-sp500-chart", "Historical US Treasury dataset is not loaded.");
      return;
    }

    const cov = hist.coverage || {};
    const bm = hist.benchmarks || {};
    const pb = hist.price_benchmarks || {};
    const overlapEl = document.getElementById("ty-kpi-overlap");
    const extEl = document.getElementById("ty-kpi-extremes");
    const extSubEl = document.getElementById("ty-kpi-extremes-sub");
    const latEl = document.getElementById("ty-kpi-latest");
    const latSubEl = document.getElementById("ty-kpi-latest-sub");
    const sprEl = document.getElementById("ty-kpi-spread");
    const sprSubEl = document.getElementById("ty-kpi-spread-sub");
    const methodEl = document.getElementById("ty-method-note");

    if (startEl) startEl.textContent = (cov.treasury_start || "1919-01-01").slice(0, 7);
    if (overlapEl) {
      const trCagr = pb.ust10y_tr_cagr_1927_present_pct !== undefined ? ` · 10Y TR ${fmtPct(pb.ust10y_tr_cagr_1927_present_pct)}` : "";
      overlapEl.textContent = `${fmtNum(cov.treasury_months, 0)} mo · S&P ${(cov.sp500_overlap_start || "1927-12-01").slice(0, 7)} (${fmtNum(cov.sp500_overlap_months, 0)} mo)${trCagr}`;
    }
    if (extEl) extEl.textContent = `${fmtNum(bm.monthly_peak_yield_pct)}% / ${fmtNum(bm.monthly_trough_yield_pct)}%`;
    if (extSubEl) {
      extSubEl.textContent = `Peak ${bm.monthly_peak_yield_date || "1981-09"} (${fmtNum(bm.daily_peak_yield_pct)}% dly) · Low ${bm.monthly_trough_yield_date || "2020-07"} (${fmtNum(bm.daily_trough_yield_pct)}% dly)`;
    }
    if (latEl) latEl.textContent = `${fmtNum(bm.latest_daily_10y_yield_pct, 2)}% vs ${formatCompactIndex(bm.latest_daily_sp500_close)}`;
    if (latSubEl) {
      const iefStr = pb.latest_ief_close ? `IEF $${fmtNum(pb.latest_ief_close, 2)}` : "";
      const tltStr = pb.latest_tlt_close ? `TLT $${fmtNum(pb.latest_tlt_close, 2)}` : "";
      const znStr = pb.latest_zn_futures_close ? `ZN=F ${fmtNum(pb.latest_zn_futures_close, 2)}` : "";
      const pxSummary = [iefStr, tltStr, znStr].filter(Boolean).join(" · ");
      latSubEl.textContent = pxSummary ? `${pxSummary} (${bm.latest_daily_date || "--"})` : `10Y Yield ${fmtNum(bm.latest_10y_yield_pct)}% · Daily ${bm.latest_daily_date || "--"}`;
    }
    if (sprEl) {
      const sprText = bm.latest_spread_10y_3m_pct !== null && bm.latest_spread_10y_3m_pct !== undefined ? fmtPct(bm.latest_spread_10y_3m_pct) : "--";
      const realText = bm.latest_real_10y_yield_pct !== null && bm.latest_real_10y_yield_pct !== undefined ? fmtPct(bm.latest_real_10y_yield_pct) : "--";
      sprEl.textContent = `${sprText} / ${realText}`;
    }
    if (sprSubEl) {
      sprSubEl.textContent = `${fmtNum(bm.inversion_months_10y_3m, 0)} inverted mo (${fmtNum(bm.inversion_share_pct, 1)}%) since ${(cov.tbill_3m_start || "1934-01").slice(0, 7)}`;
    }
    if (methodEl) methodEl.textContent = hist.methodology || "";

    const tbody = document.getElementById("treasury-regime-tbody");
    if (tbody) {
      const regimes = hist.secular_regimes || [];
      if (!regimes.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="table-state-cell">No secular era regimes computed.</td></tr>';
      } else {
        tbody.innerHTML = regimes
          .map(
            (r) => `
          <tr>
            <td><strong>${escapeHtml(r.era)}</strong></td>
            <td>${escapeHtml(r.rate_regime)}</td>
            <td class="mono">${fmtNum(r.avg_10y_yield_pct)}% <span class="badge-note">(${fmtNum(r.min_10y_yield_pct)}–${fmtNum(r.max_10y_yield_pct)}%)</span></td>
            <td class="${clsSigned(r.sp500_cagr_pct)}">${fmtPct(r.sp500_cagr_pct)}</td>
            <td class="neg mono">${fmtPct(r.sp500_max_drawdown_pct)}</td>
            <td class="${clsSigned(r.corr_sp500_yoy_vs_10y_chg)}">${r.corr_sp500_yoy_vs_10y_chg !== null ? fmtNum(r.corr_sp500_yoy_vs_10y_chg, 3) : "--"}</td>
          </tr>
        `
          )
          .join("");
      }
    }

    const scaleWrap = document.getElementById("ty-scale-wrap");
    if (scaleWrap) scaleWrap.hidden = !(tyMode === "dual" || tyMode === "price_tr" || tyMode === "price_mkt");

    renderTreasurySp500Chart();
  }

  function renderTreasurySp500Chart() {
    const container = document.getElementById("treasury-sp500-chart");
    const hist = DATASET?.historical_treasury_sp500;
    if (!container || !hist || !hist.series) return;

    const minDateMap = {
      ALL: "1919-01-01",
      "1962": "1962-01-01",
      "1980": "1980-01-01",
      "2000": "2000-01-01",
      "2020": "2020-01-01",
    };
    let minDate = minDateMap[tyRange] || "1919-01-01";
    if (tyMode === "spread" && tyRange === "ALL") minDate = "1934-01-01";
    if (tyMode === "real" && tyRange === "ALL") minDate = "1948-01-01";
    if (tyMode === "price_mkt" && minDate < "2000-09-01") minDate = "2000-09-01";

    const pts = hist.series.filter((p) => p.d >= minDate);
    if (pts.length < 3) {
      showEmptyState("treasury-sp500-chart", "No points in selected window.");
      return;
    }

    const badge = document.getElementById("ty-source-badge");
    const titleEl = document.getElementById("ty-chart-title");
    if (titleEl) {
      if (tyMode === "dual") titleEl.textContent = "US 10Y / Long-Term Treasury Yield (%) vs S&P 500 Index (^GSPC)";
      else if (tyMode === "price_tr") titleEl.textContent = "10Y US Treasury Total Return Price Index (1919=100) vs S&P 500 (^GSPC)";
      else if (tyMode === "price_mkt") titleEl.textContent = "Market US Treasury Prices (IEF · TLT · ZN=F Futures) vs S&P 500 (^GSPC)";
      else if (tyMode === "spread") titleEl.textContent = "Yield Curve Spread (10Y minus 3M T-Bill) vs S&P 500 Peak-to-Trough Drawdown";
      else titleEl.textContent = "Real 10Y Treasury Yield (Nominal minus CPI YoY) vs S&P 500 YoY Return";
    }
    if (badge) {
      const modeTag = tyMode === "price_mkt" ? " · Futures/ETFs" : tyMode === "price_tr" ? " · TR Index" : "";
      badge.textContent = `${pts[0].d.slice(0, 7)} -> ${pts[pts.length - 1].d.slice(0, 7)} (${pts.length} mo${modeTag})`;
    }

    const width = 920;
    const height = 380;
    const padL = 64;
    const padR = 64;
    const padT = 22;
    const padB = 34;
    const plotW = width - padL - padR;
    const plotH = height - padT - padB;
    const n = pts.length;
    const mapX = (i) => padL + (i / Math.max(n - 1, 1)) * plotW;

    let leftSeries = [];
    let rightSeries = [];
    let auxSeries = null;
    let aux2Series = null;
    let leftLabel = "";
    let rightLabel = "";
    let auxLabel = "";
    let aux2Label = "";
    let leftColor = "#111a17";
    let rightColor = "#b43622";
    let auxColor = "#1d4ed8";
    let aux2Color = "#1d4ed8";
    const supportsScale = tyMode === "dual" || tyMode === "price_tr" || tyMode === "price_mkt";
    const useLogLeft = supportsScale && tyScale === "log";
    const useLogRight = tyMode === "price_tr" && tyScale === "log";

    if (tyMode === "dual") {
      leftSeries = pts.map((p) => p.sp);
      rightSeries = pts.map((p) => p.y10);
      auxSeries = pts.map((p) => p.y3m);
      leftLabel = `S&P 500 (^GSPC, ${useLogLeft ? "Log" : "Linear"})`;
      rightLabel = "US 10Y / LT Yield (%)";
      auxLabel = "3M T-Bill (%)";
    } else if (tyMode === "price_tr") {
      leftSeries = pts.map((p) => p.sp);
      rightSeries = pts.map((p) => p.tr);
      auxSeries = useLogRight ? pts.map((p) => p.px) : null;
      leftColor = "#111a17";
      rightColor = "#116947";
      auxColor = "#854d0e";
      leftLabel = `S&P 500 (^GSPC, ${useLogLeft ? "Log" : "Linear"})`;
      rightLabel = `10Y UST Total Return Index (1919=100, ${useLogRight ? "Log" : "Linear"})`;
      auxLabel = "10Y UST Clean Price Index (1919=100)";
    } else if (tyMode === "price_mkt") {
      leftSeries = pts.map((p) => p.sp);
      rightSeries = pts.map((p) => p.ief);
      auxSeries = pts.map((p) => p.tlt);
      aux2Series = pts.map((p) => p.zn);
      leftColor = "#111a17";
      rightColor = "#116947";
      auxColor = "#b43622";
      aux2Color = "#1d4ed8";
      leftLabel = `S&P 500 (^GSPC, ${useLogLeft ? "Log" : "Linear"})`;
      rightLabel = "IEF 7-10Y ETF ($)";
      auxLabel = "TLT 20+Y ETF ($)";
      aux2Label = "ZN=F 10Y Futures (pts)";
    } else if (tyMode === "spread") {
      leftSeries = pts.map((p) => p.sp_dd);
      rightSeries = pts.map((p) => p.spr);
      leftLabel = "S&P 500 Drawdown (%)";
      rightLabel = "10Y-3M Yield Spread (%)";
      leftColor = "#111a17";
      rightColor = "#116947";
    } else {
      leftSeries = pts.map((p) => p.sp_yoy);
      rightSeries = pts.map((p) => p.ry);
      leftLabel = "S&P 500 YoY Return (%)";
      rightLabel = "Real 10Y Yield (%)";
      leftColor = "#47641f";
      rightColor = "#b43622";
    }

    const validLeft = leftSeries.filter((v) => v !== null && Number.isFinite(v) && (!useLogLeft || v > 0));
    const validRight = rightSeries.filter((v) => v !== null && Number.isFinite(v) && (!useLogRight || v > 0));
    if (!validLeft.length || !validRight.length) {
      showEmptyState("treasury-sp500-chart", "Insufficient overlapping observations for selected mode.");
      return;
    }

    let lMin = Math.min(...validLeft);
    let lMax = Math.max(...validLeft);
    if (useLogLeft) {
      lMin = Math.max(1, lMin * 0.82);
      lMax = lMax * 1.15;
    } else {
      const lPad = (lMax - lMin || 1) * 0.08;
      lMin -= lPad;
      lMax += lPad;
      if (tyMode === "spread") lMax = Math.max(0, lMax);
    }

    const rVals = [...validRight];
    if (auxSeries) {
      auxSeries.forEach((v) => {
        if (v !== null && Number.isFinite(v) && (!useLogRight || v > 0)) rVals.push(v);
      });
    }
    if (aux2Series) {
      aux2Series.forEach((v) => {
        if (v !== null && Number.isFinite(v) && (!useLogRight || v > 0)) rVals.push(v);
      });
    }
    let rMin = Math.min(...rVals);
    let rMax = Math.max(...rVals);
    if (useLogRight) {
      rMin = Math.max(1, rMin * 0.85);
      rMax = rMax * 1.15;
    } else {
      const rPad = (rMax - rMin || 1) * 0.1;
      rMin = tyMode === "dual" || tyMode === "price_tr" || tyMode === "price_mkt" ? Math.max(0, rMin - rPad) : rMin - rPad;
      rMax += rPad;
    }

    const mapLeftY = (v) => {
      if (useLogLeft) {
        const lv = Math.log10(Math.max(v, 1));
        const lo = Math.log10(lMin);
        const hi = Math.log10(lMax);
        return padT + plotH - ((lv - lo) / (hi - lo || 1)) * plotH;
      }
      return padT + plotH - ((v - lMin) / (lMax - lMin || 1)) * plotH;
    };
    const mapRightY = (v) => {
      if (useLogRight) {
        const rv = Math.log10(Math.max(v, 1));
        const lo = Math.log10(rMin);
        const hi = Math.log10(rMax);
        return padT + plotH - ((rv - lo) / (hi - lo || 1)) * plotH;
      }
      return padT + plotH - ((v - rMin) / (rMax - rMin || 1)) * plotH;
    };

    // Build Left Y ticks with anti-overlap vertical spacing
    let leftTicks = [];
    if (useLogLeft) {
      const candidates = [5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 7500, 10000];
      let lastTickY = Infinity;
      candidates.forEach((c) => {
        if (c >= lMin * 0.95 && c <= lMax * 1.05) {
          const y = mapLeftY(c);
          if (Math.abs(lastTickY - y) >= 22) {
            leftTicks.push(c);
            lastTickY = y;
          }
        }
      });
      if (leftTicks.length < 3) leftTicks = buildNiceLinearTicks(lMin, lMax, 5);
    } else {
      leftTicks = buildNiceLinearTicks(lMin, lMax, 5);
    }

    let rightTicks = [];
    if (useLogRight) {
      const rCandidates = [50, 100, 250, 500, 1000, 2500, 5000, 10000, 15000];
      let lastRTickY = Infinity;
      rCandidates.forEach((c) => {
        if (c >= rMin * 0.95 && c <= rMax * 1.05) {
          const y = mapRightY(c);
          if (Math.abs(lastRTickY - y) >= 22) {
            rightTicks.push(c);
            lastRTickY = y;
          }
        }
      });
      if (rightTicks.length < 3) rightTicks = buildNiceLinearTicks(rMin, rMax, 5);
    } else {
      rightTicks = buildNiceLinearTicks(rMin, rMax, 5);
    }

    const gridSvg = leftTicks
      .map((tv) => {
        const y = mapLeftY(tv);
        if (y < padT - 4 || y > padT + plotH + 4) return "";
        const lbl = supportsScale ? formatCompactIndex(tv) : `${tv.toFixed(0)}%`;
        return `
          <line x1="${padL}" y1="${y.toFixed(1)}" x2="${width - padR}" y2="${y.toFixed(1)}" stroke="rgba(17,26,23,0.09)" stroke-dasharray="3 3" />
          <text x="${padL - 8}" y="${(y + 4).toFixed(1)}" text-anchor="end" font-family="DM Mono, monospace" font-size="11" fill="${leftColor}">${escapeHtml(lbl)}</text>
        `;
      })
      .join("");

    const rightAxisSvg = rightTicks
      .map((tv) => {
        const y = mapRightY(tv);
        if (y < padT - 4 || y > padT + plotH + 4) return "";
        const rLbl = tyMode === "price_tr" ? formatCompactIndex(tv) : tyMode === "price_mkt" ? `$${tv.toFixed(0)}` : `${tv.toFixed(1)}%`;
        return `<text x="${width - padR + 8}" y="${(y + 4).toFixed(1)}" text-anchor="start" font-family="DM Mono, monospace" font-size="11" fill="${rightColor}">${escapeHtml(rLbl)}</text>`;
      })
      .join("");

    // X-axis year ticks
    const stepIdx = Math.max(1, Math.floor((n - 1) / 6));
    const xIndices = [];
    for (let i = 0; i < n; i += stepIdx) xIndices.push(i);
    if (xIndices[xIndices.length - 1] !== n - 1) {
      if (mapX(n - 1) - mapX(xIndices[xIndices.length - 1]) < 64) xIndices.pop();
      xIndices.push(n - 1);
    }
    const xTicksSvg = xIndices
      .map((i) => {
        const x = mapX(i);
        const label = tyRange === "2020" ? pts[i].d.slice(0, 7) : pts[i].d.slice(0, 4);
        return `
          <line x1="${x.toFixed(1)}" y1="${padT + plotH}" x2="${x.toFixed(1)}" y2="${padT + plotH + 5}" stroke="rgba(17,26,23,0.28)" />
          <text x="${x.toFixed(1)}" y="${padT + plotH + 20}" text-anchor="middle" font-family="DM Mono, monospace" font-size="11" fill="#52625b">${escapeHtml(label)}</text>
        `;
      })
      .join("");

    const buildSegmentedPath = (arr, yMapper) => {
      let d = "";
      let pen = false;
      arr.forEach((v, i) => {
        const invLog = (yMapper === mapLeftY && useLogLeft && v <= 0) || (yMapper === mapRightY && useLogRight && v <= 0);
        if (v === null || !Number.isFinite(v) || invLog) {
          pen = false;
          return;
        }
        const x = mapX(i).toFixed(1);
        const y = yMapper(v).toFixed(1);
        d += pen ? ` L ${x} ${y}` : ` M ${x} ${y}`;
        pen = true;
      });
      return d.trim();
    };

    const leftPath = buildSegmentedPath(leftSeries, mapLeftY);
    const rightPath = buildSegmentedPath(rightSeries, mapRightY);
    const auxPath = auxSeries ? buildSegmentedPath(auxSeries, mapRightY) : "";
    const aux2Path = aux2Series ? buildSegmentedPath(aux2Series, mapRightY) : "";

    // Zero baseline for spread/real modes & inversion shading
    let extraSvg = "";
    if (tyMode === "spread" || tyMode === "real") {
      if (rMin < 0 && rMax > 0) {
        const zY = mapRightY(0);
        extraSvg += `<line x1="${padL}" y1="${zY.toFixed(1)}" x2="${width - padR}" y2="${zY.toFixed(1)}" stroke="#b43622" stroke-width="1" stroke-dasharray="5 3" opacity="0.7" />`;
      }
    }
    if (tyMode === "spread") {
      // Shade inverted curve zones below 0% on right axis
      const zY = mapRightY(0);
      let invSegments = "";
      let activeStart = -1;
      pts.forEach((p, idx) => {
        const isInv = p.spr !== null && p.spr < 0;
        if (isInv && activeStart === -1) activeStart = idx;
        if ((!isInv || idx === n - 1) && activeStart !== -1) {
          const endIdx = isInv ? idx : idx - 1;
          const x1 = mapX(activeStart).toFixed(1);
          const w = Math.max(2, mapX(endIdx) - mapX(activeStart)).toFixed(1);
          invSegments += `<rect x="${x1}" y="${padT}" width="${w}" height="${plotH}" fill="#b43622" opacity="0.09" />`;
          activeStart = -1;
        }
      });
      extraSvg += invSegments;
    } else if (tyMode === "dual" && tyRange === "ALL") {
      const idx1953 = pts.findIndex((p) => p.d >= "1953-04-01");
      const idx1981 = pts.findIndex((p) => p.d >= "1981-09-01");
      const idx2020 = pts.findIndex((p) => p.d >= "2020-07-01");
      [
        { i: idx1953, txt: "1953 GS10" },
        { i: idx1981, txt: "1981 Peak 15.3%" },
        { i: idx2020, txt: "2020 Low 0.6%" },
      ].forEach((m) => {
        if (m.i > 0) {
          const mx = mapX(m.i);
          const nearRight = mx > width - padR - 95;
          const anchor = nearRight ? "end" : "start";
          const tx = nearRight ? mx - 4 : mx + 4;
          extraSvg += `
            <line x1="${mx.toFixed(1)}" y1="${padT}" x2="${mx.toFixed(1)}" y2="${padT + plotH}" stroke="rgba(17,26,23,0.18)" stroke-dasharray="2 3" />
            <text x="${tx.toFixed(1)}" y="${padT + 13}" text-anchor="${anchor}" font-family="DM Mono, monospace" font-size="10" fill="#52625b">${escapeHtml(m.txt)}</text>
          `;
        }
      });
    }

    container.innerHTML = `
      <div class="chart-readout" id="ty-readout" aria-live="polite">
        <span id="ty-readout-date">Hover or use Left/Right arrows</span>
        <span id="ty-readout-vals"></span>
      </div>
      <div class="chart-interactive-surface" id="ty-surface" tabindex="0" role="region" aria-label="US Treasury Yield versus S and P 500 historical chart. Press left and right arrow keys to inspect each month.">
        <svg viewBox="0 0 ${width} ${height}" aria-hidden="true">
          <rect x="0" y="0" width="${width}" height="${height}" fill="#fbfaf5" rx="6" />
          ${gridSvg}
          ${rightAxisSvg}
          ${xTicksSvg}
          ${extraSvg}
          <line x1="${padL}" y1="${padT}" x2="${padL}" y2="${padT + plotH}" stroke="rgba(17,26,23,0.22)" />
          <line x1="${width - padR}" y1="${padT}" x2="${width - padR}" y2="${padT + plotH}" stroke="rgba(17,26,23,0.22)" />
          <line x1="${padL}" y1="${padT + plotH}" x2="${width - padR}" y2="${padT + plotH}" stroke="rgba(17,26,23,0.28)" />
          ${aux2Path ? `<path d="${aux2Path}" fill="none" stroke="${aux2Color}" stroke-width="1.6" stroke-dasharray="4 3" opacity="0.88" />` : ""}
          ${auxPath ? `<path d="${auxPath}" fill="none" stroke="${auxColor}" stroke-width="1.6" stroke-dasharray="${tyMode === "price_mkt" ? "none" : "4 3"}" opacity="0.85" />` : ""}
          ${rightPath ? `<path d="${rightPath}" fill="none" stroke="${rightColor}" stroke-width="2.1" stroke-linejoin="round" stroke-linecap="round" />` : ""}
          ${leftPath ? `<path d="${leftPath}" fill="none" stroke="${leftColor}" stroke-width="2.15" stroke-linejoin="round" stroke-linecap="round" />` : ""}
          <line id="ty-crosshair" x1="0" y1="${padT}" x2="0" y2="${padT + plotH}" stroke="#111a17" stroke-width="1.2" stroke-dasharray="3 3" visibility="hidden" />
          <circle id="ty-dot-left" r="4" fill="${leftColor}" stroke="#fbfaf5" stroke-width="1.5" visibility="hidden" />
          <circle id="ty-dot-right" r="4" fill="${rightColor}" stroke="#fbfaf5" stroke-width="1.5" visibility="hidden" />
        </svg>
      </div>
      <div class="chart-legend">
        <span class="legend-item"><span class="legend-swatch" style="background:${leftColor}"></span>${escapeHtml(leftLabel)}</span>
        <span class="legend-item"><span class="legend-swatch" style="background:${rightColor}"></span>${escapeHtml(rightLabel)}</span>
        ${auxPath ? `<span class="legend-item"><span class="legend-swatch ${tyMode === "price_mkt" ? "" : "is-dashed"}" style="${tyMode === "price_mkt" ? `background:${auxColor}` : `color:${auxColor}`}"></span>${escapeHtml(auxLabel)}</span>` : ""}
        ${aux2Path ? `<span class="legend-item"><span class="legend-swatch is-dashed" style="color:${aux2Color}"></span>${escapeHtml(aux2Label)}</span>` : ""}
        ${tyMode === "spread" ? `<span class="legend-item"><span class="legend-swatch" style="background:rgba(180,54,34,0.28); height:10px;"></span>Shaded: 10Y-3M Inversion</span>` : ""}
      </div>
    `;

    const surface = document.getElementById("ty-surface");
    const svgEl = surface?.querySelector("svg");
    const crosshair = document.getElementById("ty-crosshair");
    const dotL = document.getElementById("ty-dot-left");
    const dotR = document.getElementById("ty-dot-right");
    const roDate = document.getElementById("ty-readout-date");
    const roVals = document.getElementById("ty-readout-vals");
    let currentIdx = n - 1;

    function updateReadout(idx) {
      const clamped = Math.max(0, Math.min(n - 1, idx));
      currentIdx = clamped;
      const p = pts[clamped];
      const cx = mapX(clamped);
      if (crosshair) {
        crosshair.setAttribute("x1", cx.toFixed(1));
        crosshair.setAttribute("x2", cx.toFixed(1));
        crosshair.setAttribute("visibility", "visible");
      }
      const lv = leftSeries[clamped];
      if (dotL) {
        if (lv !== null && Number.isFinite(lv) && (!useLogLeft || lv > 0)) {
          dotL.setAttribute("cx", cx.toFixed(1));
          dotL.setAttribute("cy", mapLeftY(lv).toFixed(1));
          dotL.setAttribute("visibility", "visible");
        } else {
          dotL.setAttribute("visibility", "hidden");
        }
      }
      const rv = rightSeries[clamped];
      if (dotR) {
        if (rv !== null && Number.isFinite(rv) && (!useLogRight || rv > 0)) {
          dotR.setAttribute("cx", cx.toFixed(1));
          dotR.setAttribute("cy", mapRightY(rv).toFixed(1));
          dotR.setAttribute("visibility", "visible");
        } else {
          dotR.setAttribute("visibility", "hidden");
        }
      }
      if (roDate) {
        roDate.innerHTML = `<strong>${escapeHtml(p.d.slice(0, 7))}</strong> · ${escapeHtml(p.src || "FRED")}`;
      }
      if (roVals) {
        const spStr = p.sp !== null ? formatCompactIndex(p.sp) : "--";
        const y10Str = p.y10 !== null ? `${p.y10.toFixed(2)}%` : "--";
        const sprStr = p.spr !== null ? fmtPct(p.spr) : "--";
        const trStr = p.tr !== null && p.tr !== undefined ? formatCompactIndex(p.tr) : "--";
        const pxStr = p.px !== null && p.px !== undefined ? p.px.toFixed(2) : "--";
        if (tyMode === "price_mkt") {
          const iefStr = p.ief !== null && p.ief !== undefined ? `$${p.ief.toFixed(2)}` : "--";
          const tltStr = p.tlt !== null && p.tlt !== undefined ? `$${p.tlt.toFixed(2)}` : "--";
          const znStr = p.zn !== null && p.zn !== undefined ? p.zn.toFixed(2) : "--";
          const vustxStr = p.vustx !== null && p.vustx !== undefined ? `$${p.vustx.toFixed(2)}` : "--";
          roVals.innerHTML = `S&P 500: <strong>${spStr}</strong> · IEF: <strong>${iefStr}</strong> · TLT: <strong>${tltStr}</strong> · ZN=F: <strong>${znStr}</strong> · VUSTX: ${vustxStr} · 10Y: ${y10Str}`;
        } else if (tyMode === "price_tr") {
          const trYoyStr = p.tr_yoy !== null && p.tr_yoy !== undefined ? fmtPct(p.tr_yoy) : "--";
          roVals.innerHTML = `S&P 500: <strong>${spStr}</strong> · 10Y TR Idx: <strong>${trStr}</strong> · Clean Idx: ${pxStr} · TR YoY: ${trYoyStr} · 10Y Yield: ${y10Str}`;
        } else {
          const y3mStr = p.y3m !== null ? `${p.y3m.toFixed(2)}%` : "--";
          const realStr = p.ry !== null ? fmtPct(p.ry) : "--";
          const yoyStr = p.sp_yoy !== null ? fmtPct(p.sp_yoy) : "--";
          roVals.innerHTML = `S&P 500: <strong>${spStr}</strong> · 10Y: <strong>${y10Str}</strong> · 10Y TR Idx: ${trStr} · 3M: ${y3mStr} · Spr: ${sprStr} · Real: ${realStr} · YoY: ${yoyStr}`;
        }
      }
    }

    updateReadout(n - 1);

    if (surface && svgEl) {
      surface.addEventListener("pointermove", (e) => {
        const rect = svgEl.getBoundingClientRect();
        if (!rect.width) return;
        const svgX = ((e.clientX - rect.left) / rect.width) * width;
        const ratio = Math.max(0, Math.min(1, (svgX - padL) / plotW));
        updateReadout(Math.round(ratio * (n - 1)));
      });
      surface.addEventListener("pointerleave", () => updateReadout(n - 1));
      surface.addEventListener("keydown", (e) => {
        const step = e.shiftKey ? 12 : 1;
        if (e.key === "ArrowLeft") {
          e.preventDefault();
          updateReadout(currentIdx - step);
        } else if (e.key === "ArrowRight") {
          e.preventDefault();
          updateReadout(currentIdx + step);
        } else if (e.key === "Home") {
          e.preventDefault();
          updateReadout(0);
        } else if (e.key === "End") {
          e.preventDefault();
          updateReadout(n - 1);
        }
      });
    }
  }

  function renderSpotCheckTable() {
    const tbody = document.getElementById("spot-check-tbody");
    if (!tbody || !DATASET) return;
    const checks = DATASET.spot_checks || [];
    if (!checks.length) {
      tbody.innerHTML = '<tr><td colspan="9" class="table-state-cell">No spot-check audit rows available.</td></tr>';
      return;
    }

    tbody.innerHTML = checks
      .map(
        (s) => `
        <tr>
          <td class="mono"><strong>${escapeHtml(s.check_id)}</strong></td>
          <td><strong>${escapeHtml(s.metric)}</strong></td>
          <td class="mono">${escapeHtml(s.ticker)} &middot; ${escapeHtml(s.date)}</td>
          <td class="mono">${escapeHtml(s.formula)}</td>
          <td class="mono">${escapeHtml(s.inputs)}</td>
          <td class="mono pos">${escapeHtml(s.manual_value)}</td>
          <td class="mono pos">${escapeHtml(s.pipeline_value)}</td>
          <td class="mono">${Number(s.difference).toFixed(6)}</td>
          <td><span class="badge-verified">PASS: ${escapeHtml(s.status)}</span></td>
        </tr>
      `
      )
      .join("");
  }

  /* =======================================================================
     NAVIGATION, KEYBOARD A11Y & DATA LOADING
     ======================================================================= */
  function switchDashboardTab(tabId) {
    const tabs = ["overview", "explorer", "comparison", "events"];
    tabs.forEach((t) => {
      const panel = document.getElementById(`tab-${t}`);
      if (panel) panel.hidden = t !== tabId;
    });

    document.querySelectorAll(".analyst-nav-tab").forEach((btn) => {
      const active = btn.getAttribute("data-tab") === tabId;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-selected", String(active));
    });

    if (tabId === "overview") renderOverviewTab();
    if (tabId === "explorer") renderExplorerTab();
    if (tabId === "comparison") {
      renderComparisonTab();
      renderHistoricalTreasurySection();
    }
    if (tabId === "events") renderEventsTab();
  }

  function bindEvents() {
    const brandHome = document.getElementById("brand-home-link");
    if (brandHome) {
      brandHome.addEventListener("click", (e) => {
        e.preventDefault();
        switchDashboardTab("overview");
        window.scrollTo({ top: 0, behavior: "auto" });
      });
    }

    const tabBtns = [...document.querySelectorAll(".analyst-nav-tab")];
    tabBtns.forEach((btn, idx) => {
      btn.addEventListener("click", () => {
        const target = btn.getAttribute("data-tab");
        if (target) switchDashboardTab(target);
      });
      btn.addEventListener("keydown", (e) => {
        if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
          e.preventDefault();
          const dir = e.key === "ArrowRight" ? 1 : -1;
          const next = tabBtns[(idx + dir + tabBtns.length) % tabBtns.length];
          next.focus();
          const target = next.getAttribute("data-tab");
          if (target) switchDashboardTab(target);
        }
      });
    });

    document.querySelectorAll(".hero-ticker-pill[data-jump-ticker]").forEach((pill) => {
      pill.addEventListener("click", () => {
        const tk = pill.getAttribute("data-jump-ticker");
        const sel = document.getElementById("exp-ticker-select");
        if (sel && tk) {
          sel.value = tk;
          switchDashboardTab("explorer");
          document.getElementById("tab-explorer")?.scrollIntoView({ behavior: "auto", block: "start" });
        }
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
        document.querySelectorAll("#exp-range-pills button").forEach((b) => {
          b.classList.remove("is-active");
          b.setAttribute("aria-pressed", "false");
        });
        btn.classList.add("is-active");
        btn.setAttribute("aria-pressed", "true");
        activeRange = btn.getAttribute("data-range") || "ALL";
        renderExplorerTab();
      });
    });

    const capmSelect = document.getElementById("capm-stock-select");
    if (capmSelect) capmSelect.addEventListener("change", renderCapmSection);

    document.querySelectorAll("#ty-range-pills button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#ty-range-pills button").forEach((b) => {
          b.classList.remove("is-active");
          b.setAttribute("aria-pressed", "false");
        });
        btn.classList.add("is-active");
        btn.setAttribute("aria-pressed", "true");
        tyRange = btn.getAttribute("data-ty-range") || "ALL";
        renderTreasurySp500Chart();
      });
    });

    const tyModeSel = document.getElementById("ty-mode-select");
    if (tyModeSel) {
      tyModeSel.addEventListener("change", () => {
        tyMode = tyModeSel.value || "dual";
        const scaleWrap = document.getElementById("ty-scale-wrap");
        if (scaleWrap) scaleWrap.hidden = !(tyMode === "dual" || tyMode === "price_tr" || tyMode === "price_mkt");
        renderTreasurySp500Chart();
      });
    }

    document.querySelectorAll("#ty-scale-pills button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#ty-scale-pills button").forEach((b) => {
          b.classList.remove("is-active");
          b.setAttribute("aria-pressed", "false");
        });
        btn.classList.add("is-active");
        btn.setAttribute("aria-pressed", "true");
        tyScale = btn.getAttribute("data-ty-scale") || "log";
        renderTreasurySp500Chart();
      });
    });

    const anomFilter = document.getElementById("anom-ticker-filter");
    if (anomFilter) anomFilter.addEventListener("change", renderAnomaliesTable);

    const retryBtn = document.getElementById("retry-dataset-btn");
    if (retryBtn) retryBtn.addEventListener("click", loadDataset);
  }

  async function loadDataset() {
    const errBanner = document.getElementById("dataset-error-banner");
    const errMsg = document.getElementById("dataset-error-msg");
    if (errBanner) errBanner.hidden = true;

    try {
      const res = await fetch("data/analyst_dataset.json");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      DATASET = await res.json();
      renderOverviewTab();
      renderExplorerTab();
      renderComparisonTab();
      renderHistoricalTreasurySection();
      renderEventsTab();
    } catch (err) {
      console.error("Failed to load analyst_dataset.json:", err);
      if (errMsg) errMsg.textContent = `Could not load analyst_dataset.json (${err.message}). Verify the local server is running.`;
      if (errBanner) errBanner.hidden = false;
    }
  }

  function init() {
    bindEvents();
    loadDataset();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
