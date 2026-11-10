/* =========================================================================
   US EQUITY ATLAS · EDITORIAL & QUANTITATIVE ENGINE (ANALYST SUITE)
   ========================================================================= */

(function () {
  "use strict";

  let DATASET = null;
  let activeRange = "ALL";

  const SERIES_COLORS = {
    NVDA: "#aff838", // Electric lime
    AAPL: "#38bdf8", // Sky cyan
    MSFT: "#60a5fa", // Electric blue
    GOOGL: "#fbbf24", // Amber gold
    AMZN: "#f97316", // Bright orange
    META: "#c084fc", // Neon violet
    TSLA: "#f43f5e", // Crimson rose
    AVGO: "#2dd4bf", // Mint teal
    AMD: "#f472b6", // Hot pink
    ORCL: "#818cf8", // Indigo
    "^GSPC": "#f1f5f9", // Crisp titanium white
    "^TNX": "#fb923c", // Warning amber
    "^VIX": "#e879f9", // Electric fuchsia
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

  function formatVol(n) {
    if (!n || n === 0) return "0";
    const num = Number(n);
    if (num >= 1e9) return (num / 1e9).toFixed(2) + "B";
    if (num >= 1e6) return (num / 1e6).toFixed(1) + "M";
    if (num >= 1e3) return (num / 1e3).toFixed(1) + "K";
    return num.toLocaleString();
  }

  function updatePriceHud(bar, ticker = "NVDA") {
    if (!bar) return;
    const dEl = document.getElementById("hud-val-date");
    const oEl = document.getElementById("hud-val-open");
    const hEl = document.getElementById("hud-val-high");
    const lEl = document.getElementById("hud-val-low");
    const cEl = document.getElementById("hud-val-close");
    const rEl = document.getElementById("hud-val-ret");
    const vEl = document.getElementById("hud-val-vol");

    const openVal = bar.o !== undefined ? bar.o : bar.c;
    const highVal = bar.h !== undefined ? bar.h : bar.c;
    const lowVal = bar.l !== undefined ? bar.l : bar.c;
    const closeVal = bar.c;

    if (dEl) dEl.textContent = bar.d;
    if (oEl) oEl.textContent = "$" + Number(openVal).toFixed(2);
    if (hEl) hEl.textContent = "$" + Number(highVal).toFixed(2);
    if (lEl) lEl.textContent = "$" + Number(lowVal).toFixed(2);
    if (cEl) cEl.textContent = "$" + Number(closeVal).toFixed(2);
    if (rEl) {
      const isPos = bar.ret >= 0;
      rEl.className = "hud-val hud-ret " + (isPos ? "pos" : "neg");
      rEl.textContent = (isPos ? "▲ +" : "▼ ") + Math.abs(Number(bar.ret)).toFixed(2) + "%";
    }
    if (vEl) vEl.textContent = formatVol(bar.v);
  }

  /* =======================================================================
     SKEUOMORPHIC SVG MULTI-LINE CHART ENGINE
     - Interactive Crosshair Hairline
     - Luminous Snapping Dots on Curves
     - High-Low Range Shadow Corridor
     - Rich Floating Tactile Tooltip with Open, High, Low, Close, Return & Volume
     - Real-Time Live HUD Telemetry Sync
     ======================================================================= */
  function renderMultiLineChart(containerId, seriesList, options = {}) {
    const el = document.getElementById(containerId);
    if (!el) return;

    const width = 640;
    const height = options.height || 270;
    const padL = 52;
    const padR = 24;
    const padT = 20;
    const padB = 32;
    const plotW = width - padL - padR;
    const plotH = height - padT - padB;

    const validSeries = seriesList.filter((s) => s.points && s.points.length > 1);
    if (!validSeries.length) {
      el.innerHTML = `<div style="padding:24px;color:rgba(255,255,255,0.4);font-family:var(--mono);">No time-series points available.</div>`;
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

    // Add 4% buffer so curves don't clip against border rails
    const spanRaw = maxY - minY;
    minY -= spanRaw * 0.03;
    maxY += spanRaw * 0.05;
    const ySpan = maxY - minY;

    const yTicks = 4;
    let gridHtml = "";

    for (let i = 0; i <= yTicks; i++) {
      const val = minY + (ySpan * i) / yTicks;
      const y = padT + plotH - (plotH * i) / yTicks;
      const label = options.yFormat ? options.yFormat(val) : val.toFixed(0);
      gridHtml += `
        <line x1="${padL}" y1="${y.toFixed(1)}" x2="${width - padR}" y2="${y.toFixed(1)}"
              stroke="rgba(255,255,255,0.06)" stroke-dasharray="2,3" />
        <text x="${padL - 10}" y="${(y + 3.5).toFixed(1)}" text-anchor="end"
              fill="rgba(255,255,255,0.45)" font-size="10" font-family="DM Mono, monospace">${label}</text>
      `;
    }

    if (options.baseline !== undefined && options.baseline >= minY && options.baseline <= maxY) {
      const by = padT + plotH - ((options.baseline - minY) / ySpan) * plotH;
      gridHtml += `
        <line x1="${padL}" y1="${by.toFixed(1)}" x2="${width - padR}" y2="${by.toFixed(1)}"
              stroke="rgba(175,248,56,0.35)" stroke-width="1.2" stroke-dasharray="4,4" />
      `;
    }

    const refPoints = validSeries[0].points;
    const dateStart = refPoints[0]?.d || "";
    const dateMid = refPoints[Math.floor(refPoints.length / 2)]?.d || "";
    const dateEnd = refPoints[refPoints.length - 1]?.d || "";

    const gradId = `grad-${containerId}`;
    const primaryColor = validSeries[0].color || "#aff838";
    let defsHtml = `
      <defs>
        <linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${primaryColor}" stop-opacity="0.28" />
          <stop offset="65%" stop-color="${primaryColor}" stop-opacity="0.06" />
          <stop offset="100%" stop-color="${primaryColor}" stop-opacity="0.0" />
        </linearGradient>
        <filter id="glow-${containerId}" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
    `;

    // 1. High-Low Range Corridor Envelope if options.ohlcData and showRange
    let rangeCorridorHtml = "";
    if (options.showRange && options.ohlcData && options.ohlcData.rawA) {
      const ohlcList = options.ohlcData.rawA;
      const baseA = options.ohlcData.baseLocalA || ohlcList[0]?.c || 100;
      const upperCoords = [];
      const lowerCoords = [];
      const n = ohlcList.length;

      for (let i = 0; i < n; i++) {
        const r = ohlcList[i];
        if (!r) continue;
        const x = padL + (i / Math.max(1, n - 1)) * plotW;
        const highVal = (r.h / baseA) * 100;
        const lowVal = (r.l / baseA) * 100;
        const yHigh = padT + plotH - ((highVal - minY) / ySpan) * plotH;
        const yLow = padT + plotH - ((lowVal - minY) / ySpan) * plotH;
        upperCoords.push(`${x.toFixed(1)},${yHigh.toFixed(1)}`);
        lowerCoords.unshift(`${x.toFixed(1)},${yLow.toFixed(1)}`);
      }
      if (upperCoords.length > 1) {
        const polyPoints = upperCoords.concat(lowerCoords).join(" ");
        rangeCorridorHtml = `
          <polygon points="${polyPoints}" fill="rgba(175, 248, 56, 0.07)" stroke="rgba(175, 248, 56, 0.22)" stroke-width="0.8" stroke-dasharray="2,2" />
        `;
      }
    }

    // 2. Multi-series lines and endpoint dots
    let pathsHtml = rangeCorridorHtml;
    validSeries.forEach((s, sIdx) => {
      const pts = s.points;
      const n = pts.length;
      const coords = [];
      let firstX = padL;
      let lastX = padL + plotW;
      let lastY = padT + plotH;

      for (let i = 0; i < n; i++) {
        const yv = pts[i].y;
        if (yv === null || yv === undefined || !Number.isFinite(yv)) continue;
        const x = padL + (i / Math.max(1, n - 1)) * plotW;
        const y = padT + plotH - ((yv - minY) / ySpan) * plotH;
        if (coords.length === 0) firstX = x;
        lastX = x;
        lastY = y;
        coords.push(`${x.toFixed(1)},${y.toFixed(1)}`);
      }
      if (coords.length > 1) {
        if (sIdx === 0) {
          const areaPts = `${firstX.toFixed(1)},${(padT + plotH).toFixed(1)} ${coords.join(" ")} ${lastX.toFixed(1)},${(padT + plotH).toFixed(1)}`;
          pathsHtml += `<polygon points="${areaPts}" fill="url(#${gradId})" />`;
        }
        pathsHtml += `
          <polyline fill="none" stroke="${s.color}" stroke-width="${s.width || 2.2}"
                    stroke-linecap="round" stroke-linejoin="round"
                    ${s.dashed ? 'stroke-dasharray="5,4"' : ""}
                    filter="url(#glow-${containerId})"
                    points="${coords.join(" ")}" />
          <circle cx="${lastX.toFixed(1)}" cy="${lastY.toFixed(1)}" r="3.8"
                  fill="${s.color}" stroke="#0a0e0c" stroke-width="1.8" />
        `;
      }
    });

    // 3. Crosshair Hairline & Tracking Beads
    let crosshairDotsHtml = validSeries
      .map(
        (s, idx) => `
        <circle class="crosshair-dot-${idx}" r="4.8" fill="${s.color}" stroke="#0a0e0c" stroke-width="2"
                style="display:none; pointer-events:none; filter:drop-shadow(0 0 6px ${s.color});" />
      `
      )
      .join("");

    const crosshairGroupHtml = `
      <g class="chart-crosshair-group" style="display:none; pointer-events:none;">
        <line class="chart-crosshair-v" y1="${padT}" y2="${padT + plotH}" stroke="rgba(175, 248, 56, 0.75)" stroke-width="1.2" stroke-dasharray="3,3" />
        ${crosshairDotsHtml}
      </g>
    `;

    // 4. Interactive Overlay
    const overlayHtml = `
      <rect class="chart-hover-overlay" x="${padL}" y="${padT}" width="${plotW}" height="${plotH}" fill="transparent" style="cursor:crosshair; pointer-events:all;" />
    `;

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
            <span>${s.label} <strong>${lastVal}</strong></span>
          </span>
        `;
      })
      .join("");

    el.innerHTML = `
      <svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}" class="skeuo-chart-svg">
        ${defsHtml}
        ${gridHtml}
        ${pathsHtml}
        ${crosshairGroupHtml}
        ${overlayHtml}
        <text x="${padL}" y="${height - 8}" fill="rgba(255,255,255,0.4)" font-size="10" font-family="DM Mono, monospace">${dateStart}</text>
        <text x="${padL + plotW / 2}" y="${height - 8}" text-anchor="middle" fill="rgba(255,255,255,0.4)" font-size="10" font-family="DM Mono, monospace">${dateMid}</text>
        <text x="${width - padR}" y="${height - 8}" text-anchor="end" fill="rgba(255,255,255,0.4)" font-size="10" font-family="DM Mono, monospace">${dateEnd}</text>
      </svg>
      <div class="skeuo-chart-tooltip" style="display:none; position:absolute; pointer-events:none; z-index:50;"></div>
      <div class="chart-legend">${legendHtml}</div>
    `;

    // 5. Attach Interactive Pointer Listeners
    const overlay = el.querySelector(".chart-hover-overlay");
    const crosshairGroup = el.querySelector(".chart-crosshair-group");
    const crosshairLine = el.querySelector(".chart-crosshair-v");
    const tooltipEl = el.querySelector(".skeuo-chart-tooltip");
    const svgEl = el.querySelector("svg");

    if (!overlay || !crosshairGroup || !tooltipEl || !svgEl) return;

    function handlePointerMove(e) {
      const rect = svgEl.getBoundingClientRect();
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      const clientY = e.touches ? e.touches[0].clientY : e.clientY;

      const svgX = ((clientX - rect.left) / rect.width) * width;
      if (svgX < padL || svgX > width - padR) {
        handlePointerLeave();
        return;
      }

      const relX = (svgX - padL) / plotW;
      const nPoints = refPoints.length;
      const idx = Math.max(0, Math.min(nPoints - 1, Math.round(relX * (nPoints - 1))));
      const pt = refPoints[idx];
      const snapX = padL + (idx / Math.max(1, nPoints - 1)) * plotW;

      // Position vertical hairline
      crosshairLine.setAttribute("x1", snapX.toFixed(1));
      crosshairLine.setAttribute("x2", snapX.toFixed(1));

      // Position tracking dots
      validSeries.forEach((s, sIdx) => {
        const dot = crosshairGroup.querySelector(`.crosshair-dot-${sIdx}`);
        if (!dot) return;
        const sPt = s.points[idx];
        if (sPt && sPt.y !== null && sPt.y !== undefined && Number.isFinite(sPt.y)) {
          const snapY = padT + plotH - ((sPt.y - minY) / ySpan) * plotH;
          dot.setAttribute("cx", snapX.toFixed(1));
          dot.setAttribute("cy", snapY.toFixed(1));
          dot.style.display = "block";
        } else {
          dot.style.display = "none";
        }
      });
      crosshairGroup.style.display = "block";

      // Render Tooltip Content
      if (options.ohlcData && options.ohlcData.rawA && options.ohlcData.rawA[idx]) {
        const barA = options.ohlcData.rawA[idx];
        const barB = options.ohlcData.rawB ? options.ohlcData.rawB[idx] : null;
        const dStr = barA.d || pt.d;

        let dayName = "";
        try {
          const dt = new Date(dStr + "T00:00:00Z");
          dayName = dt.toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" });
        } catch (_) {}

        const isPos = barA.ret >= 0;
        const chgSign = isPos ? "+" : "";
        const chgClass = isPos ? "pos" : "neg";
        const chgIcon = isPos ? "▲" : "▼";

        tooltipEl.innerHTML = `
          <div class="skeuo-tt-card">
            <div class="skeuo-tt-head">
              <div class="skeuo-tt-date-row">
                <span class="skeuo-tt-dot"></span>
                <span class="skeuo-tt-date">${dStr} ${dayName ? `· ${dayName}` : ""}</span>
              </div>
              <span class="skeuo-tt-badge">${options.ohlcData.ticker}</span>
            </div>
            <div class="skeuo-tt-ohlc-grid">
              <div class="skeuo-tt-cell">
                <span class="tt-tag">OPEN</span>
                <span class="tt-val">$${Number(barA.o).toFixed(2)}</span>
              </div>
              <div class="skeuo-tt-cell tt-high">
                <span class="tt-tag">HIGH</span>
                <span class="tt-val">$${Number(barA.h).toFixed(2)}</span>
              </div>
              <div class="skeuo-tt-cell tt-low">
                <span class="tt-tag">LOW</span>
                <span class="tt-val">$${Number(barA.l).toFixed(2)}</span>
              </div>
              <div class="skeuo-tt-cell tt-close">
                <span class="tt-tag">CLOSE</span>
                <span class="tt-val">$${Number(barA.c).toFixed(2)}</span>
              </div>
            </div>
            <div class="skeuo-tt-meta">
              <span class="skeuo-tt-chg ${chgClass}">
                ${chgIcon} ${chgSign}${Number(barA.ret).toFixed(2)}%
              </span>
              <span class="skeuo-tt-vol">Vol: <strong>${formatVol(barA.v)}</strong></span>
            </div>
            ${
              barB
                ? `
            <div class="skeuo-tt-comp">
              <span class="comp-name">${options.ohlcData.compareTicker}: $${Number(barB.c).toFixed(2)}</span>
              <span class="comp-ret ${barB.ret >= 0 ? "pos" : "neg"}">${barB.ret >= 0 ? "+" : ""}${Number(barB.ret).toFixed(2)}%</span>
            </div>`
                : ""
            }
          </div>
        `;

        // Update live HUD
        updatePriceHud(barA, options.ohlcData.ticker);
      } else {
        // Standard series tooltip
        const dStr = pt.d;
        tooltipEl.innerHTML = `
          <div class="skeuo-tt-card">
            <div class="skeuo-tt-head">
              <div class="skeuo-tt-date-row">
                <span class="skeuo-tt-dot"></span>
                <span class="skeuo-tt-date">${dStr}</span>
              </div>
            </div>
            <div class="skeuo-tt-list">
              ${validSeries
                .map((s) => {
                  const sPt = s.points[idx];
                  if (!sPt || sPt.y === undefined || Number.isNaN(sPt.y)) return "";
                  const fmtVal = options.yFormat ? options.yFormat(sPt.y) : sPt.y.toFixed(2);
                  return `
                  <div class="skeuo-tt-item">
                    <span class="swatch" style="background:${s.color}"></span>
                    <span class="name">${s.label}</span>
                    <strong class="val">${fmtVal}</strong>
                  </div>
                `;
                })
                .join("")}
            </div>
          </div>
        `;
      }

      // Position tooltip inside container
      const elRect = el.getBoundingClientRect();
      const ttWidth = 230;
      let posX = clientX - elRect.left + 16;
      let posY = clientY - elRect.top - 20;

      if (posX + ttWidth > elRect.width - 12) {
        posX = clientX - elRect.left - ttWidth - 16;
      }
      if (posY < 10) posY = 10;

      tooltipEl.style.left = `${Math.max(8, posX)}px`;
      tooltipEl.style.top = `${posY}px`;
      tooltipEl.style.display = "block";
    }

    function handlePointerLeave() {
      if (crosshairGroup) crosshairGroup.style.display = "none";
      if (tooltipEl) tooltipEl.style.display = "none";
      if (options.ohlcData && options.ohlcData.rawA) {
        const latest = options.ohlcData.rawA[options.ohlcData.rawA.length - 1];
        updatePriceHud(latest, options.ohlcData.ticker);
      }
    }

    overlay.addEventListener("pointerenter", handlePointerMove);
    overlay.addEventListener("pointermove", handlePointerMove);
    overlay.addEventListener("pointerleave", handlePointerLeave);
    overlay.addEventListener("touchstart", handlePointerMove, { passive: true });
    overlay.addEventListener("touchmove", handlePointerMove, { passive: true });
    overlay.addEventListener("touchend", handlePointerLeave);
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
        <div class="kpi-card" style="--kpi-glow:#76a721">
          <span class="kpi-label">#1 US GROWTH LEADER</span>
          <strong class="kpi-val pos">${topCagr ? topCagr.ticker : "NVDA"} · ${fmtPct(topCagr?.cagr_pct)}</strong>
          <span class="kpi-sub">Cumulative: ${fmtPct(topCagr?.total_return_pct)} · Sharpe ${fmtNum(topCagr?.sharpe_ratio)}</span>
        </div>
        <div class="kpi-card" style="--kpi-glow:#147b54">
          <span class="kpi-label">#2 US GROWTH LEADER</span>
          <strong class="kpi-val pos">${secondCagr ? secondCagr.ticker : "TSLA"} · ${fmtPct(secondCagr?.cagr_pct)}</strong>
          <span class="kpi-sub">Cumulative: ${fmtPct(secondCagr?.total_return_pct)} · Beta ${fmtNum(secondCagr?.beta)}</span>
        </div>
        <div class="kpi-card" style="--kpi-glow:#18201e">
          <span class="kpi-label">S&P 500 (^GSPC) BENCHMARK</span>
          <strong class="kpi-val ${clsSigned(sp500?.total_return_pct)}">${fmtPct(sp500?.total_return_pct)}</strong>
          <span class="kpi-sub">CAGR: ${fmtPct(sp500?.cagr_pct)} · Ann. Vol: ${fmtPct(sp500?.annualized_volatility_pct, 2, false)}</span>
        </div>
        <div class="kpi-card" style="--kpi-glow:#c54d3a">
          <span class="kpi-label">US 10Y TREASURY YIELD (^TNX)</span>
          <strong class="kpi-val mono">${fmtNum(macro.tnx_start)}% → ${fmtNum(macro.tnx_latest)}%</strong>
          <span class="kpi-sub">Cycle Range: ${fmtNum(macro.tnx_min)}% – ${fmtNum(macro.tnx_max)}% (${macro.yield_spike_days_count || 0} Spikes)</span>
        </div>
        <div class="kpi-card" style="--kpi-glow:#7c3aed">
          <span class="kpi-label">CBOE VOLATILITY INDEX (^VIX)</span>
          <strong class="kpi-val mono">${fmtNum(macro.vix_latest)} pts</strong>
          <span class="kpi-sub">Cycle Peak: ${fmtNum(macro.vix_max)} pts · ${macro.high_vix_days_count || 0} High-Fear Days</span>
        </div>
        <div class="kpi-card" style="--kpi-glow:#2563eb">
          <span class="kpi-label">TOP RISK-ADJUSTED SHARPE</span>
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
    const width = 560;
    const height = 260;
    const padL = 48;
    const padR = 32;
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
              stroke="rgba(255,255,255,0.06)" stroke-dasharray="2,3" />
        <text x="${padL - 8}" y="${(y + 3.5).toFixed(1)}" text-anchor="end"
              fill="rgba(255,255,255,0.45)" font-size="10" font-family="DM Mono, monospace">${yv.toFixed(0)}%</text>
      `;
    }

    for (let i = 0; i <= 4; i++) {
      const xv = minX + ((maxX - minX) * i) / 4;
      const x = padL + (plotW * i) / 4;
      grid += `
        <text x="${x.toFixed(1)}" y="${height - 6}" text-anchor="middle"
              fill="rgba(255,255,255,0.45)" font-size="10" font-family="DM Mono, monospace">${xv.toFixed(0)}% Vol</text>
      `;
    }

    const dots = items
      .map((s) => {
        const x = padL + ((s.annualized_volatility_pct - minX) / (maxX - minX)) * plotW;
        const y = padT + plotH - ((s.cagr_pct - minY) / (maxY - minY)) * plotH;
        const r = Math.max(7, Math.min(15, 7 + Math.max(0, s.sharpe_ratio) * 4.2));
        const col = s.role === "Benchmark" ? "#f1f5f9" : SERIES_COLORS[s.ticker] || "#aff838";
        return `
          <g class="scatter-point" style="cursor:pointer;">
            <title>${s.ticker} (${s.name})&#10;CAGR: ${s.cagr_pct}%&#10;Annualized Volatility: ${s.annualized_volatility_pct}%&#10;Sharpe Ratio: ${s.sharpe_ratio}&#10;Max Drawdown: ${s.max_drawdown_pct}%</title>
            <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${(r + 4).toFixed(1)}"
                    fill="${col}" fill-opacity="0.18" />
            <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r.toFixed(1)}"
                    fill="${col}" fill-opacity="0.92" stroke="#0a0e0c" stroke-width="1.8" />
            <text x="${(x + r + 5).toFixed(1)}" y="${(y + 3.5).toFixed(1)}"
                  fill="#f1f5f9" font-size="11" font-family="DM Mono, monospace" font-weight="700">${s.ticker}</text>
          </g>
        `;
      })
      .join("");

    el.innerHTML = `
      <svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}" class="skeuo-chart-svg">
        ${grid}
        ${dots}
      </svg>
      <div class="chart-legend">
        <span class="legend-item"><span class="legend-swatch" style="background:#aff838"></span>10 US Mega-Cap Equities (Bubble Radius = Sharpe Ratio)</span>
        <span class="legend-item"><span class="legend-swatch" style="background:#f1f5f9"></span>S&P 500 Benchmark (^GSPC)</span>
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
          <td class="mono"><strong>${Number(r.clean_trading_days).toLocaleString("en-US")}</strong> sessions</td>
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
        <div class="kpi-card" style="--kpi-glow:#76a721">
          <span class="kpi-label">${summary.ticker || ticker} LATEST CLOSE</span>
          <strong class="kpi-val">${fmtPrice(summary.latest_price, ticker)}</strong>
          <span class="kpi-sub">${summary.name || ""} · ${summary.sector || ""}</span>
        </div>
        <div class="kpi-card" style="--kpi-glow:#147b54">
          <span class="kpi-label">TOTAL RETURN (NOMINAL / EXCESS)</span>
          <strong class="kpi-val ${clsSigned(summary.total_return_pct)}">${fmtPct(summary.total_return_pct)}</strong>
          <span class="kpi-sub">Excess vs 10Y Treasury: ${fmtPct(summary.excess_return_pct)}</span>
        </div>
        <div class="kpi-card" style="--kpi-glow:#c54d3a">
          <span class="kpi-label">VOLATILITY & MAX DRAWDOWN</span>
          <strong class="kpi-val neg">${fmtPct(summary.max_drawdown_pct)} Max DD</strong>
          <span class="kpi-sub">Annualized Volatility: ${fmtPct(summary.annualized_volatility_pct, 2, false)}</span>
        </div>
        <div class="kpi-card" style="--kpi-glow:#2563eb">
          <span class="kpi-label">CAPM BETA & ANNUAL ALPHA</span>
          <strong class="kpi-val ${clsSigned(summary.alpha_annual_pct)}">α = ${fmtPct(summary.alpha_annual_pct)}</strong>
          <span class="kpi-sub">Beta (β) = ${fmtNum(summary.beta)} vs S&P 500 (^GSPC)</span>
        </div>
        <div class="kpi-card" style="--kpi-glow:#7c3aed">
          <span class="kpi-label">ANOMALY SPIKES DETECTED</span>
          <strong class="kpi-val mono">${summary.volume_anomalies_count || 0} Vol Spikes</strong>
          <span class="kpi-sub">${summary.return_3sigma_outliers || 0} Tail Shocks (>3σ)</span>
        </div>
      `;
    }

    const rawA = filterPointsByRange(DATASET.time_series[ticker] || [], activeRange);
    const rawB = filterPointsByRange(DATASET.time_series[compareTicker] || [], activeRange);

    const baseLocalA = rawA[0]?.c || 100;
    const baseExcA = rawA[0]?.exc_idx || 100;
    const baseLocalB = rawB[0]?.c || 100;

    renderMultiLineChart(
      "exp-price-chart",
      [
        {
          label: `${ticker} Nominal Index`,
          color: SERIES_COLORS[ticker] || "#aff838",
          width: 2.4,
          points: rawA.map((r) => ({ d: r.d, y: (r.c / baseLocalA) * 100 })),
        },
        {
          label: `${ticker} Rate-Adj Excess Index`,
          color: "#38bdf8",
          dashed: true,
          width: 2.0,
          points: rawA.map((r) => ({ d: r.d, y: (r.exc_idx / baseExcA) * 100 })),
        },
        {
          label: `${compareTicker} Benchmark/Peer`,
          color: SERIES_COLORS[compareTicker] || "#f43f5e",
          width: 2.0,
          points: rawB.map((r) => ({ d: r.d, y: (r.c / baseLocalB) * 100 })),
        },
      ],
      {
        baseline: 100,
        showRange: true,
        yFormat: (v) => v.toFixed(0),
        ohlcData: {
          ticker,
          rawA,
          compareTicker,
          rawB,
          baseLocalA,
        },
      }
    );

    // Initial HUD synchronization to latest observation
    if (rawA.length > 0) {
      updatePriceHud(rawA[rawA.length - 1], ticker);
    }

    renderMultiLineChart(
      "exp-vol-chart",
      [
        {
          label: `${ticker} 30D Annualized Volatility (%)`,
          color: SERIES_COLORS[ticker] || "#aff838",
          width: 2.2,
          points: rawA.map((r) => ({ d: r.d, y: r.vol30 })),
        },
        {
          label: `${ticker} Drawdown (%)`,
          color: "#f43f5e",
          width: 2.0,
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
          color: "#38bdf8",
          width: 2.1,
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
          (ev, idx) => `
          <div class="event-card">
            <div class="event-top">
              <div class="event-num-wrap">
                <span class="event-serif-num">${String(idx + 1).padStart(2, "0")}.</span>
                <span class="event-id-badge">${ev.matched_trading_date} · ${ev.ticker}</span>
              </div>
              <span class="tag-pill">${ev.category}</span>
            </div>
            <div class="event-title">${ev.title}</div>
            <p class="event-desc">${ev.explanation}</p>
            <div class="event-metrics">
              <div class="event-metric-item">
                <span>ACTUAL 1D RETURN</span>
                <strong class="${clsSigned(ev.actual_day_return_pct)}">${fmtPct(ev.actual_day_return_pct)}</strong>
              </div>
              <div class="event-metric-item">
                <span>ABNORMAL (T0)</span>
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
            <div class="event-source">
              <span>Filing / Source: ${ev.source}</span>
              <strong>$${fmtNum(ev.close_price)}</strong>
            </div>
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
    const secAnalyst = document.getElementById("section-analyst");
    const secDeep = document.getElementById("section-deepquant");
    const btnAnalyst = document.getElementById("btn-mode-analyst");
    const btnDeep = document.getElementById("btn-mode-deepquant");

    if (mode === "deepquant") {
      if (secAnalyst) secAnalyst.hidden = true;
      if (secDeep) secDeep.hidden = false;
      if (btnAnalyst) btnAnalyst.classList.remove("is-active");
      if (btnDeep) btnDeep.classList.add("is-active");
    } else {
      if (secAnalyst) secAnalyst.hidden = false;
      if (secDeep) secDeep.hidden = true;
      if (btnAnalyst) btnAnalyst.classList.add("is-active");
      if (btnDeep) btnDeep.classList.remove("is-active");
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function switchDashboardTab(tabId) {
    const tabs = ["overview", "explorer", "comparison", "events"];
    tabs.forEach((t) => {
      const panel = document.getElementById(`tab-${t}`);
      if (panel) panel.hidden = t !== tabId;
    });

    document.querySelectorAll(".analyst-nav-tab").forEach((btn) => {
      btn.classList.toggle("is-active", btn.getAttribute("data-tab") === tabId);
    });

    if (tabId === "overview") renderOverviewTab();
    if (tabId === "explorer") renderExplorerTab();
    if (tabId === "comparison") renderComparisonTab();
    if (tabId === "events") renderEventsTab();
  }

  function bindEvents() {
    const btnAnalyst = document.getElementById("btn-mode-analyst");
    const btnDeep = document.getElementById("btn-mode-deepquant");
    const btnBack = document.getElementById("btn-back-to-analyst");
    const btnToggleLive = document.getElementById("btn-toggle-deepquant-live");
    const brandHome = document.getElementById("brand-home-link");

    if (btnAnalyst) btnAnalyst.addEventListener("click", () => switchPlatformMode("analyst"));
    if (btnDeep) btnDeep.addEventListener("click", () => switchPlatformMode("deepquant"));
    if (btnBack) btnBack.addEventListener("click", () => switchPlatformMode("analyst"));
    if (btnToggleLive) {
      btnToggleLive.addEventListener("click", () => {
        const liveWs = document.getElementById("deepquant-live-workspace");
        if (!liveWs) return;
        const willShow = liveWs.hidden;
        liveWs.hidden = !willShow;
        btnToggleLive.textContent = willShow
          ? "✕ Hide Experimental Workspace"
          : "🧪 Launch Experimental Workspace (6 Modules)";
        if (willShow) {
          liveWs.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    }
    if (brandHome) {
      brandHome.addEventListener("click", (e) => {
        e.preventDefault();
        switchPlatformMode("analyst");
      });
    }

    document.querySelectorAll(".analyst-nav-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        const target = btn.getAttribute("data-tab");
        if (target) switchDashboardTab(target);
      });
    });

    // Interactive ticker pills in hero jump directly to Explorer for that stock
    document.querySelectorAll(".hero-ticker-pill[data-jump-ticker]").forEach((pill) => {
      pill.addEventListener("click", () => {
        const tk = pill.getAttribute("data-jump-ticker");
        const sel = document.getElementById("exp-ticker-select");
        if (sel && tk) {
          sel.value = tk;
          switchDashboardTab("explorer");
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
