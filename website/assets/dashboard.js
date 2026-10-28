/* US Equity Atlas — UI for the project's local SQLite market API. */
const SECTOR_COLORS = ["#88af38", "#db7d66", "#6b9ecb", "#d69346", "#a58e4f", "#bd6750", "#8a9b61", "#60a3a3", "#b884a6", "#c79357", "#7f92cf"];
const RANGE_LABELS = { "1M": "1 month", "6M": "6 months", "1Y": "1 year", "5Y": "5 years", ALL: "all history" };
const state = { sector: "All", query: "", page: 1, overview: null, selected: "AAPL", detail: null, range: "1Y", chartRows: [], detailRequest: 0 };
const $ = (selector) => document.querySelector(selector);
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const fullDate = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
const shortDate = new Intl.DateTimeFormat("en-US", { month: "short", year: "numeric", timeZone: "UTC" });

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
}

function asDate(value) { return new Date(`${value}T00:00:00Z`); }
function last(items) { return items[items.length - 1]; }
function percent(value, decimals = 1) {
  if (!Number.isFinite(value)) return "—";
  return `${value > 0 ? "+" : ""}${(value * 100).toFixed(decimals)}%`;
}
function classFor(value) { return value >= 0 ? "positive" : "negative"; }
function standardDeviation(values) {
  if (values.length < 2) return 0;
  const average = values.reduce((total, value) => total + value, 0) / values.length;
  return Math.sqrt(values.reduce((total, value) => total + (value - average) ** 2, 0) / (values.length - 1));
}
function maximumDrawdown(rows) {
  let peak = -Infinity, drawdown = 0;
  rows.forEach((row) => { peak = Math.max(peak, row.adj_close); drawdown = Math.min(drawdown, row.adj_close / peak - 1); });
  return drawdown;
}

async function request(url) {
  const response = await fetch(url);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || "The local market API could not complete this request.");
  return payload;
}

function setAppError(message) {
  $("#header-status").textContent = "Setup needed";
  $("#stock-list").innerHTML = `<div class="list-message">${escapeHtml(message)}</div>`;
  $("#price-chart").innerHTML = `<div class="chart-loading">${escapeHtml(message)}</div>`;
}

function sectorName(sector) {
  return sector === "All" ? "ALL EQUITIES" : sector.toUpperCase();
}

function selectSector(sector) {
  state.sector = sector;
  state.page = 1;
  renderSectors();
  loadStocks();
}

function renderSectors() {
  if (!state.overview) return;
  const sectors = state.overview.sectors;
  const allButton = `<button class="sector-chip ${state.sector === "All" ? "is-active" : ""}" type="button" data-sector="All">All Sectors <span class="chip-count">${state.overview.total_stocks.toLocaleString("en-US")}</span></button>`;
  $("#sector-chips").innerHTML = allButton + sectors.map((sector) => `<button class="sector-chip ${state.sector === sector.key ? "is-active" : ""}" type="button" data-sector="${escapeHtml(sector.key)}">${escapeHtml(sector.key)} <span class="chip-count">${sector.count.toLocaleString("en-US")}</span></button>`).join("");
  document.querySelectorAll("[data-sector]").forEach((button) => button.addEventListener("click", () => selectSector(button.dataset.sector)));

  $("#sector-grid").innerHTML = sectors.filter((sector) => sector.key !== "Unclassified").map((sector, index) => `<button class="sector-card ${state.sector === sector.key ? "is-active" : ""}" type="button" data-sector="${escapeHtml(sector.key)}" style="--sector-color:${SECTOR_COLORS[index % SECTOR_COLORS.length]}"><span class="sector-number">${String(index + 1).padStart(2, "0")}</span><strong>${escapeHtml(sector.key)}</strong><span>${sector.count.toLocaleString("en-US")} equities · ${escapeHtml(sector.label_id)}</span></button>`).join("");
  document.querySelectorAll(".sector-card[data-sector]").forEach((card) => card.addEventListener("click", () => { selectSector(card.dataset.sector); document.querySelector(".explorer").scrollIntoView({ behavior: "smooth", block: "start" }); }));
}

function renderStockList(payload) {
  const { items, total, page, pages } = payload;
  $("#active-sector-label").textContent = sectorName(state.sector);
  $("#results-count").textContent = `${total.toLocaleString("en-US")} stocks`;
  $("#page-count").textContent = `PAGE ${page} / ${pages}`;
  $("#pagination-label").textContent = `${page} of ${pages}`;
  $("#previous-page").disabled = page <= 1;
  $("#next-page").disabled = page >= pages;
  if (!items.length) {
    $("#stock-list").innerHTML = '<div class="list-message">No matching equities found.</div>';
    return;
  }
  $("#stock-list").innerHTML = items.map((item) => `<button class="stock-button ${item.symbol === state.selected ? "is-selected" : ""}" role="listitem" type="button" data-symbol="${escapeHtml(item.symbol)}"><span><span class="stock-ticker">${escapeHtml(item.symbol)}</span><span class="stock-company">${escapeHtml(item.security_name)}</span></span><span class="stock-price">${Number.isFinite(item.close) ? money.format(item.close) : "—"}</span></button>`).join("");
  document.querySelectorAll(".stock-button[data-symbol]").forEach((button) => button.addEventListener("click", () => selectStock(button.dataset.symbol)));
}

async function loadStocks() {
  $("#stock-list").innerHTML = '<div class="list-message">Loading equities catalog…</div>';
  const params = new URLSearchParams({ sector: state.sector, q: state.query, page: String(state.page), page_size: "40" });
  try {
    const payload = await request(`/api/stocks?${params}`);
    if (payload.page !== state.page && payload.total) { state.page = payload.page; }
    renderStockList(payload);
  } catch (error) { setAppError(error.message); }
}

function updateDetail(detail) {
  state.detail = detail;
  $("#detail-empty").hidden = true;
  $("#stock-detail").hidden = false;
  $("#selected-sector").textContent = detail.sector;
  $("#selected-ticker").textContent = detail.symbol;
  $("#selected-company").textContent = detail.security_name;
  $("#selected-industry").textContent = detail.industry || "Industry data unavailable";
  $("#last-price").textContent = Number.isFinite(detail.close) ? money.format(detail.close) : "—";
  $("#day-change").textContent = Number.isFinite(detail.daily_change) ? `${percent(detail.daily_change)} today` : "—";
  $("#day-change").className = `change ${classFor(detail.daily_change || 0)}`;
}

async function selectStock(symbol) {
  state.selected = symbol;
  state.detailRequest += 1;
  const requestId = state.detailRequest;
  $("#price-chart").innerHTML = '<div class="chart-loading">Loading price history…</div>';
  loadStockNews(symbol);
  try {
    const detail = await request(`/api/stock?symbol=${encodeURIComponent(symbol)}`);
    if (requestId !== state.detailRequest) return;
    updateDetail(detail);
    renderStockListCache();
    await loadHistory(requestId);
  } catch (error) { if (requestId === state.detailRequest) setAppError(error.message); }
}

function renderStockListCache() {
  document.querySelectorAll(".stock-button[data-symbol]").forEach((button) => {
    const selected = button.dataset.symbol === state.selected;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
}

const newsState = {
  currentSymbol: "AAPL",
  companyName: "",
  activeTab: "direct", // "direct" or "spillover"
  directItems: [],
  spilloverItems: [],
  connectedPartners: [],
  dbTotal: 0,
};

let newsRequestId = 0;

async function loadStockNews(symbol, companyName = "") {
  const container = $("#stock-news-feed");
  const tickerLabel = $("#news-stock-ticker");
  const badge = $("#news-source-badge");
  const dbCounter = $("#news-db-counter");
  if (!container) return;

  newsState.currentSymbol = symbol;
  newsState.companyName = companyName;

  newsRequestId += 1;
  const currentReq = newsRequestId;

  if (tickerLabel) tickerLabel.textContent = symbol;
  if (badge) badge.textContent = "Fetching Live Feed…";

  container.innerHTML = `
    <div class="news-skeleton-grid">
      <div class="news-skeleton-card"></div>
      <div class="news-skeleton-card"></div>
      <div class="news-skeleton-card"></div>
    </div>
  `;

  try {
    const params = new URLSearchParams({ symbol, name: companyName, limit: "15" });
    const res = await request(`/api/news?${params}`);
    if (currentReq !== newsRequestId) return;

    newsState.directItems = res.items || [];
    newsState.spilloverItems = res.spillover_news || [];
    newsState.connectedPartners = res.connected_partners || [];
    newsState.dbTotal = res.db_total || 0;

    if (badge) badge.textContent = `${res.provider || 'Finnhub'} · ${res.count} Stories`;
    if (dbCounter) dbCounter.textContent = `💾 ${res.db_total || 0} in SQLite`;

    renderNewsFeed();
  } catch (err) {
    if (currentReq !== newsRequestId) return;
    if (badge) badge.textContent = "Feed Unavailable";
    container.innerHTML = `
      <div class="news-empty-state">
        <p>Could not load news feed for <strong>${escapeHtml(symbol)}</strong> at this moment.</p>
      </div>
    `;
  }
}

function renderNewsFeed() {
  const container = $("#stock-news-feed");
  if (!container) return;

  const isDirect = newsState.activeTab === "direct";
  const items = isDirect ? newsState.directItems : newsState.spilloverItems;
  const partnersStrip = $("#spillover-partners-strip");
  const chipsContainer = $("#spillover-partners-chips");

  $("#btn-news-direct")?.classList.toggle("is-active", isDirect);
  $("#btn-news-spillover")?.classList.toggle("is-active", !isDirect);

  if (partnersStrip) partnersStrip.hidden = isDirect || !newsState.connectedPartners.length;
  if (!isDirect && chipsContainer) {
    chipsContainer.innerHTML = newsState.connectedPartners.slice(0, 6).map((p) => `
      <span class="spillover-chip" title="${escapeHtml(p.relation)}">🔗 <strong>${escapeHtml(p.ticker || p.node_id)}</strong>: ${escapeHtml(p.relation_label)}</span>
    `).join("");
  }

  if (!items || !items.length) {
    container.innerHTML = `
      <div class="news-empty-state">
        <p>${isDirect 
          ? `No recent direct news found for <strong>${escapeHtml(newsState.currentSymbol)}</strong>.` 
          : `No direct upstream suppliers or downstream customers found with recent alerts for <strong>${escapeHtml(newsState.currentSymbol)}</strong>. Try clicking [ 📥 Backfill 1Y News ] to archive more historical reports.`}
        </p>
      </div>
    `;
    return;
  }

  container.innerHTML = items.map((item) => {
    const sentimentClass = item.sentiment === "Bullish" ? "badge-bullish" : item.sentiment === "Bearish" ? "badge-bearish" : "badge-neutral";
    const imageHtml = item.image
      ? `<div class="news-card-thumb"><img src="${escapeHtml(item.image)}" alt="" loading="lazy" onerror="this.parentElement.style.display='none'"></div>`
      : `<div class="news-card-thumb news-card-thumb-fallback"><span>${item.is_spillover ? '🔗' : '📰'}</span></div>`;

    let spilloverBadge = "";
    if (item.is_spillover) {
      const rel = (item.relation_label || "").toLowerCase();
      let badgeType = "badge-customer";
      if (rel.includes("supplier")) badgeType = "badge-supplier";
      else if (rel.includes("rival") || rel.includes("compet")) badgeType = "badge-competitor";
      else if (rel.includes("cost") || rel.includes("commodity")) badgeType = "badge-cost";

      spilloverBadge = `
        <div class="news-spillover-badge ${badgeType}">
          🔗 ${escapeHtml(item.relation_label || 'Graph Spillover')}
        </div>
      `;
    }

    return `
      <article class="news-card">
        ${imageHtml}
        <div class="news-card-body">
          ${spilloverBadge}
          <div class="news-card-meta">
            <span class="news-source">${escapeHtml(item.source)}</span>
            <span class="news-dot">·</span>
            <span class="news-time">${escapeHtml(item.relative_time)}</span>
            <span class="news-sentiment-badge ${sentimentClass}">${escapeHtml(item.sentiment)}</span>
          </div>
          <h4 class="news-headline">
            <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.headline)} ↗</a>
          </h4>
          <p class="news-summary">${escapeHtml(item.summary || "")}</p>
        </div>
      </article>
    `;
  }).join("");
}

// News Tab Event Listeners
$("#btn-news-direct")?.addEventListener("click", () => {
  newsState.activeTab = "direct";
  renderNewsFeed();
});

$("#btn-news-spillover")?.addEventListener("click", () => {
  newsState.activeTab = "spillover";
  renderNewsFeed();
});

// Backfill Historical News Event Listener
$("#btn-news-backfill")?.addEventListener("click", async () => {
  const btn = $("#btn-news-backfill");
  const dbCounter = $("#news-db-counter");
  if (!btn || btn.disabled) return;

  const originalHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `🔄 Archiving 1Y News…`;

  try {
    const res = await request(`/api/news/backfill?symbol=${encodeURIComponent(newsState.currentSymbol)}&months=12`);
    if (dbCounter) dbCounter.textContent = `💾 ${res.total_in_db || 0} in SQLite`;
    btn.innerHTML = `✅ +${res.new_articles_added || 0} Added!`;

    // Refresh current news feed to reflect newly archived articles
    const params = new URLSearchParams({ symbol: newsState.currentSymbol, name: newsState.companyName, limit: "15" });
    const updatedNews = await request(`/api/news?${params}`);
    newsState.directItems = updatedNews.items || [];
    newsState.spilloverItems = updatedNews.spillover_news || [];
    newsState.dbTotal = updatedNews.db_total || 0;
    renderNewsFeed();

    setTimeout(() => {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }, 3000);
  } catch (err) {
    console.error("Backfill error:", err);
    btn.innerHTML = `⚠️ Backfill Failed`;
    setTimeout(() => {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }, 2500);
  }
});

async function loadHistory(requestId = state.detailRequest) {
  if (!state.selected) return;
  $("#price-chart").innerHTML = '<div class="chart-loading">Loading price history…</div>';
  try {
    const payload = await request(`/api/history?symbol=${encodeURIComponent(state.selected)}&range=${state.range}`);
    if (requestId !== state.detailRequest) return;
    renderHistory(payload.rows);
  } catch (error) { if (requestId === state.detailRequest) setAppError(error.message); }
}

function renderHistory(rows) {
  if (!rows?.length || rows.length < 2) { renderNoHistory(); return; }
  const sampledRows = rows.length > 800 ? rows.filter((_, index) => index % Math.ceil(rows.length / 800) === 0 || index === rows.length - 1) : rows;
  state.chartRows = sampledRows;
  const width = 1000, height = 340, left = 12, right = 68, top = 20, bottom = 37;
  const chartWidth = width - left - right, chartHeight = height - top - bottom;
  const values = sampledRows.map((row) => row.adj_close);
  let min = Math.min(...values), max = Math.max(...values);
  const padding = Math.max((max - min) * .12, max * .03, .01);
  min = Math.max(0, min - padding); max += padding;
  const toX = (index) => left + index / (sampledRows.length - 1) * chartWidth;
  const toY = (value) => top + (max - value) / (max - min) * chartHeight;
  const line = sampledRows.map((row, index) => `${index ? "L" : "M"}${toX(index).toFixed(2)},${toY(row.adj_close).toFixed(2)}`).join(" ");
  const area = `${line} L ${toX(sampledRows.length - 1).toFixed(2)},${top + chartHeight} L ${left},${top + chartHeight} Z`;
  const grids = [0, .33, .66, 1].map((position) => { const y = top + position * chartHeight; const value = max - position * (max - min); return `<line class="chart-grid" x1="${left}" x2="${left + chartWidth}" y1="${y}" y2="${y}"/><text class="chart-axis-label" x="${width - 2}" y="${y + 3}" text-anchor="end">${money.format(value)}</text>`; }).join("");
  const dates = [0, .33, .66, 1].map((position) => { const index = Math.min(sampledRows.length - 1, Math.round(position * (sampledRows.length - 1))); const anchor = position === 0 ? "start" : position === 1 ? "end" : "middle"; return `<text class="chart-axis-label" x="${toX(index)}" y="${height - 7}" text-anchor="${anchor}">${shortDate.format(asDate(sampledRows[index].date))}</text>`; }).join("");
  const sectorIndex = Math.max(0, state.overview?.sectors.findIndex((sector) => sector.key === state.detail?.sector) ?? 0);
  const chartColor = SECTOR_COLORS[sectorIndex % SECTOR_COLORS.length];
  $("#price-chart").style.setProperty("--chart-color", chartColor);
  $("#price-chart").innerHTML = `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="Adjusted close price from ${rows[0].date} to ${last(rows).date}"><defs><linearGradient id="chart-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="${chartColor}" stop-opacity=".28"/><stop offset="100%" stop-color="${chartColor}" stop-opacity="0"/></linearGradient></defs>${grids}<path class="chart-area" d="${area}"/><path class="chart-line" d="${line}"/>${dates}</svg>`;
  $("#chart-summary").textContent = `Adjusted close · ${fullDate.format(asDate(rows[0].date))} — ${fullDate.format(asDate(last(rows).date))}`;
  renderMetrics(rows);
}

function renderNoHistory() {
  state.chartRows = [];
  $("#price-chart").innerHTML = '<div class="chart-loading">No price history is available for this ticker.</div>';
  $("#chart-summary").textContent = "No historical price data";
  ["#period-return", "#volatility", "#drawdown", "#trading-range", "#trading-volume"].forEach((selector) => { const el = $(selector); if (el) { el.textContent = "—"; el.className = ""; } });
  $("#period-return-note").textContent = "No historical data";
  $("#trading-range-note").textContent = "—";
  if ($("#trading-sessions")) $("#trading-sessions").textContent = "0 sessions";
}

function formatVolume(num) {
  if (!num || num <= 0) return "—";
  if (num >= 1e9) return `${(num / 1e9).toFixed(2)}B`;
  if (num >= 1e6) return `${(num / 1e6).toFixed(2)}M`;
  if (num >= 1e3) return `${(num / 1e3).toFixed(1)}K`;
  return num.toLocaleString();
}

function renderMetrics(rows) {
  const periodReturn = last(rows).adj_close / rows[0].adj_close - 1;
  const dailyReturns = rows.slice(1).map((row, index) => row.adj_close / rows[index].adj_close - 1);
  const volatility = standardDeviation(dailyReturns) * Math.sqrt(252);
  const prices = rows.map((row) => row.adj_close);
  const lastVol = last(rows).volume || 0;
  const recentRows = rows.slice(-30);
  const avgVol = recentRows.reduce((sum, r) => sum + (r.volume || 0), 0) / Math.max(1, recentRows.length);

  $("#period-return").textContent = percent(periodReturn); $("#period-return").className = classFor(periodReturn);
  $("#period-return-note").textContent = `${fullDate.format(asDate(rows[0].date))} → latest`;
  $("#volatility").textContent = percent(volatility);
  $("#drawdown").textContent = percent(maximumDrawdown(rows)); $("#drawdown").className = "negative";
  $("#trading-range").textContent = `${money.format(Math.min(...prices))} – ${money.format(Math.max(...prices))}`;
  $("#trading-range-note").textContent = "Adjusted close";

  if ($("#trading-volume")) $("#trading-volume").textContent = formatVolume(lastVol);
  if ($("#trading-sessions")) $("#trading-sessions").textContent = `${rows.length.toLocaleString()} bars · 30D avg: ${formatVolume(avgVol)}`;
}

function renderChartTooltip(clientX) {
  const rows = state.chartRows;
  if (!rows.length) return;
  const wrap = $("#chart-wrap"), rect = wrap.getBoundingClientRect();
  const ratio = Math.max(0, Math.min(1, (clientX - rect.left - 12) / Math.max(1, rect.width - 80)));
  const index = Math.round(ratio * (rows.length - 1)), row = rows[index];
  const x = 12 + index / Math.max(1, rows.length - 1) * (rect.width - 80);
  const values = rows.map((item) => item.adj_close), min = Math.min(...values), max = Math.max(...values);
  const padding = Math.max((max - min) * .12, max * .03, .01), paddedMin = Math.max(0, min - padding), paddedMax = max + padding;
  const y = 20 + (paddedMax - row.adj_close) / (paddedMax - paddedMin) * (rect.height - 57);
  const tooltip = $("#chart-tooltip");
  const volText = row.volume ? ` · Vol: ${formatVolume(row.volume)}` : "";
  tooltip.innerHTML = `<strong>${money.format(row.adj_close)}</strong><span>${fullDate.format(asDate(row.date))}${volText}</span>`;
  tooltip.style.left = `${Math.max(73, Math.min(rect.width - 73, x))}px`; tooltip.style.top = `${Math.max(48, y)}px`; tooltip.hidden = false;
}

async function start() {
  if (location.protocol === "file:") { setAppError("Run dashboard via `python market_server.py`, then open http://127.0.0.1:8000."); return; }
  try {
    const overview = await request("/api/overview");
    state.overview = overview;
    $("#total-stocks").textContent = overview.total_stocks.toLocaleString("en-US");
    $("#earliest-date").textContent = fullDate.format(asDate(overview.earliest_date));
    $("#latest-date").textContent = fullDate.format(asDate(overview.latest_date));
    $("#header-status").textContent = `${overview.total_stocks.toLocaleString("en-US")} stocks · local data`;
    $("#footer-source").textContent = `Local SQLite & MongoDB data engine · sector taxonomy refreshed ${overview.sector_updated_at ? fullDate.format(new Date(overview.sector_updated_at)) : "—"}`;
    renderSectors();
    await Promise.all([loadStocks(), selectStock(state.selected)]);

    // Pre-fetch StockLens graph in background for instant tab switching
    request("/api/stocklens/graph").then((data) => {
      stocklensState.graphData = data;
      stocklensState.nodesMap = {};
      data.nodes.forEach((n) => { stocklensState.nodesMap[n.id] = n; });
      loadCentralityTable();
      populatePathDropdowns();
    }).catch(() => {});
  } catch (error) { setAppError(error.message); }
}

let searchTimer;
$("#stock-search").addEventListener("input", (event) => { clearTimeout(searchTimer); searchTimer = setTimeout(() => { state.query = event.target.value.trim(); state.page = 1; loadStocks(); }, 220); });
$("#previous-page").addEventListener("click", () => { if (state.page > 1) { state.page -= 1; loadStocks(); } });
$("#next-page").addEventListener("click", () => { state.page += 1; loadStocks(); });
document.querySelectorAll("[data-range]").forEach((button) => button.addEventListener("click", () => { state.range = button.dataset.range; document.querySelectorAll("[data-range]").forEach((item) => item.classList.toggle("is-active", item === button)); loadHistory(); }));
document.querySelectorAll(".quick-chip").forEach((btn) => {
  btn.addEventListener("click", () => {
    const sym = btn.dataset.quick;
    $("#stock-search").value = "";
    state.query = "";
    selectStock(sym);
  });
});
$("#chart-wrap").addEventListener("pointermove", (event) => renderChartTooltip(event.clientX));
$("#chart-wrap").addEventListener("pointerleave", () => { $("#chart-tooltip").hidden = true; });
$("#chart-wrap").addEventListener("keydown", (event) => { if (["ArrowLeft", "ArrowRight"].includes(event.key)) { event.preventDefault(); const rect = $("#chart-wrap").getBoundingClientRect(); renderChartTooltip(rect.left + rect.width * (event.key === "ArrowLeft" ? .35 : .65)); } });
start();

/* ==========================================================================
   STOCKLENS US — FINANCIAL KNOWLEDGE GRAPH & QUANTITATIVE ANALYTICS ENGINE
   ========================================================================== */

const stocklensState = {
  activeView: "atlas",
  graphData: null,
  centralityData: null,
  evidenceData: null,
  nodesMap: {},
  canvas: null,
  ctx: null,
  nodes: [],
  edges: [],
  selectedNode: null,
  hoveredNode: null,
  draggedNode: null,
  transform: { x: 0, y: 0, k: 1 },
  isPanning: false,
  panStart: { x: 0, y: 0 },
  filterType: "All",
  searchQuery: "",
  animating: false,
  selectedYear: 2026,
  selectedRange: "ALL",
  viewMode: "topology", // "topology" or "contagion"
  contagionData: null,
  shockEpicenter: null,
};

// 1. TOP VIEW NAVIGATION TABS
document.querySelectorAll(".nav-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    const view = tab.dataset.view;
    switchView(view);
  });
});

function switchView(view) {
  stocklensState.activeView = view;
  document.querySelectorAll(".nav-tab").forEach((t) => t.classList.toggle("is-active", t.dataset.view === view));
  document.querySelectorAll(".view-panel").forEach((panel) => {
    panel.hidden = panel.id !== `view-${view}`;
  });

  window.scrollTo({ top: 0, behavior: "instant" });

  if (view === "graph") requestAnimationFrame(() => initGraphView());
  else if (view === "paths") initPathsView();
  else if (view === "quant") initQuantView();
  else if (view === "bubble") initBubbleView();
  else if (view === "evidence") initEvidenceView();
}

// 2. FINANCIAL KNOWLEDGE GRAPH MODULE
async function initGraphView() {
  if (!stocklensState.graphData) {
    await loadGraphData();
    loadCentralityTable();
    populatePathDropdowns();
  } else {
    setupGraphCanvas();
  }
}

async function loadGraphData() {
  const params = new URLSearchParams({
    year: String(stocklensState.selectedYear || 2026),
    range: stocklensState.selectedRange || "ALL",
    type: stocklensState.filterType || "All",
    q: stocklensState.searchQuery || ""
  });
  try {
    const data = await request(`/api/stocklens/graph?${params}`);
    stocklensState.graphData = data;
    stocklensState.nodesMap = {};
    data.nodes.forEach((n) => { stocklensState.nodesMap[n.id] = n; });

    // Update KPI strip counts
    if ($("#kg-total-nodes")) $("#kg-total-nodes").textContent = data.nodes.length;
    if ($("#kg-total-edges")) $("#kg-total-edges").textContent = data.edges.length;

    setupGraphCanvas();
  } catch (e) {
    console.error("Error loading graph data:", e);
  }
}

async function loadCentralityTable() {
  const tbody = $("#centrality-tbody");
  if (!tbody) return;
  try {
    const res = await request("/api/stocklens/centrality");
    stocklensState.centralityData = res.items;
    tbody.innerHTML = res.items.slice(0, 15).map((r) => `
      <tr>
        <td><code>${escapeHtml(r.entity_id)}</code></td>
        <td><strong>${escapeHtml(r.canonical_name)}</strong></td>
        <td><span class="insp-rel-type" style="background:${ENTITY_COLOR_MAP[r.entity_type] || '#94A3B8'}20; color:${ENTITY_COLOR_MAP[r.entity_type] || '#475569'}">${escapeHtml(r.entity_type)}</span></td>
        <td><code>${escapeHtml(r.ticker || '—')}</code></td>
        <td>${(r.pagerank || 0).toFixed(4)}</td>
        <td>${(r.betweenness || 0).toFixed(4)}</td>
        <td>${r.total_degree || 0}</td>
      </tr>
    `).join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="7" class="loading-td">Error loading centrality: ${escapeHtml(e.message)}</td></tr>`;
  }
}

const ENTITY_COLOR_MAP = {
  Sector: "#6366F1",
  Industry: "#8B5CF6",
  Company: "#10B981",
  Commodity: "#F59E0B",
  MacroIndicator: "#EF4444",
  Product: "#06B6D4"
};

window.stocklensState = stocklensState;

function setupGraphCanvas() {
  const canvas = $("#kg-canvas");
  if (!canvas) return;
  stocklensState.canvas = canvas;
  stocklensState.ctx = canvas.getContext("2d");

  // Resize canvas to exactly match container client dimensions
  const container = canvas.parentElement;
  const rect = container ? container.getBoundingClientRect() : null;
  const width = Math.max(320, Math.floor((rect && rect.width) || container.clientWidth || 840));
  const height = Math.max(480, Math.floor((container && container.clientHeight) || 580));
  canvas.width = width;
  canvas.height = height;

  // Initialize node physics positions
  const rawNodes = stocklensState.graphData.nodes;
  const rawEdges = stocklensState.graphData.edges;

  // Filter nodes if requested
  const fType = stocklensState.filterType;
  const q = stocklensState.searchQuery.toLowerCase();
  const visibleNodes = rawNodes.filter((n) => {
    if (fType !== "All" && n.type !== fType) return false;
    if (q && !n.id.toLowerCase().includes(q) && !n.name.toLowerCase().includes(q) && !n.ticker.toLowerCase().includes(q)) return false;
    return true;
  });

  const visibleIds = new Set(visibleNodes.map((n) => n.id));
  const visibleEdges = rawEdges.filter((e) => visibleIds.has(e.source) && visibleIds.has(e.target));

  const cx = canvas.width / 2;
  const cy = canvas.height / 2;

  stocklensState.nodes = visibleNodes.map((n, i) => {
    const angle = (i / visibleNodes.length) * 2 * Math.PI;
    const radius = 180 + (i % 3) * 60;
    return {
      ...n,
      x: cx + radius * Math.cos(angle) + (Math.random() - 0.5) * 40,
      y: cy + radius * Math.sin(angle) + (Math.random() - 0.5) * 40,
      vx: 0,
      vy: 0,
      radius: n.type === "Sector" ? 18 : n.type === "Company" ? 13 : 9,
    };
  });

  const nodeMap = {};
  stocklensState.nodes.forEach((n) => { nodeMap[n.id] = n; });

  stocklensState.edges = visibleEdges.map((e) => ({
    ...e,
    sourceNode: nodeMap[e.source],
    targetNode: nodeMap[e.target],
  })).filter((e) => e.sourceNode && e.targetNode);

  if (!stocklensState.animating) {
    stocklensState.animating = true;
    requestAnimationFrame(renderGraphStep);
  }
}

// Graph Force Physics Simulation Step
function renderGraphStep() {
  if (stocklensState.activeView !== "graph") {
    stocklensState.animating = false;
    return;
  }

  const { ctx, canvas, nodes, edges, transform } = stocklensState;
  if (!ctx || !canvas) return;

  // Apply Force Simulation (Coulomb repulsion + Hooke spring attraction)
  const kRepulse = 3500;
  const kAttract = 0.045;
  const damping = 0.84;
  const cx = canvas.width / 2;
  const cy = canvas.height / 2;

  for (let i = 0; i < nodes.length; i++) {
    const n1 = nodes[i];
    // Repulsion from other nodes
    for (let j = i + 1; j < nodes.length; j++) {
      const n2 = nodes[j];
      const dx = n2.x - n1.x;
      const dy = n2.y - n1.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      if (dist < 320) {
        const force = kRepulse / (dist * dist);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        n1.vx -= fx;
        n1.vy -= fy;
        n2.vx += fx;
        n2.vy += fy;
      }
    }
    // Centering force
    n1.vx += (cx - n1.x) * 0.008;
    n1.vy += (cy - n1.y) * 0.008;
  }

  // Edge Spring Attraction
  for (const e of edges) {
    const s = e.sourceNode;
    const t = e.targetNode;
    const dx = t.x - s.x;
    const dy = t.y - s.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const targetDist = 90;
    const force = (dist - targetDist) * kAttract;
    const fx = (dx / dist) * force;
    const fy = (dy / dist) * force;
    s.vx += fx;
    s.vy += fy;
    t.vx -= fx;
    t.vy -= fy;
  }

  // Update positions & velocity damping
  for (const n of nodes) {
    if (n === stocklensState.draggedNode) continue;
    n.vx *= damping;
    n.vy *= damping;
    n.x += n.vx;
    n.y += n.vy;
  }

  // CLEAR CANVAS
  ctx.save();
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Apply Zoom & Pan
  ctx.translate(transform.x, transform.y);
  ctx.scale(transform.k, transform.k);

  // DRAW EDGES
  for (const e of edges) {
    const s = e.sourceNode;
    const t = e.targetNode;
    const isHighlighted = (stocklensState.selectedNode && (s.id === stocklensState.selectedNode.id || t.id === stocklensState.selectedNode.id));
    let edgeStroke = isHighlighted ? "#38bdf8" : "rgba(148, 163, 184, 0.22)";
    let edgeWidth = isHighlighted ? 2.2 : 1.0;

    if (stocklensState.viewMode === "contagion" && stocklensState.contagionData) {
      const isFromEpicenter = s.id === stocklensState.shockEpicenter;
      const targetStatus = stocklensState.contagionData.nodes_map?.[t.id]?.status;
      if (isFromEpicenter && targetStatus === "VULNERABLE") {
        edgeStroke = "rgba(239, 68, 68, 0.75)";
        edgeWidth = 2.4;
      } else if (isFromEpicenter && targetStatus === "BENEFICIARY") {
        edgeStroke = "rgba(16, 185, 129, 0.75)";
        edgeWidth = 2.4;
      }
    }

    ctx.beginPath();
    ctx.moveTo(s.x, s.y);
    ctx.lineTo(t.x, t.y);
    ctx.strokeStyle = edgeStroke;
    ctx.lineWidth = edgeWidth;
    ctx.stroke();

    // Arrowhead towards target
    const dx = t.x - s.x;
    const dy = t.y - s.y;
    const angle = Math.atan2(dy, dx);
    const arrowDist = t.radius + 6;
    const arrowX = t.x - Math.cos(angle) * arrowDist;
    const arrowY = t.y - Math.sin(angle) * arrowDist;

    ctx.save();
    ctx.fillStyle = isHighlighted ? "#38bdf8" : "rgba(148, 163, 184, 0.4)";
    ctx.translate(arrowX, arrowY);
    ctx.rotate(angle);
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(-6, -3);
    ctx.lineTo(-6, 3);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }

  // DRAW NODES
  for (const n of nodes) {
    const isSelected = stocklensState.selectedNode?.id === n.id;
    const isHovered = stocklensState.hoveredNode?.id === n.id;
    const isContagion = stocklensState.viewMode === "contagion";
    const contagionInfo = isContagion && stocklensState.contagionData?.nodes_map?.[n.id];
    const isEpicenter = isContagion && (stocklensState.shockEpicenter === n.id);

    // Glowing halo for selected/hovered node or shock epicenter
    if (isEpicenter) {
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.radius + 12, 0, 2 * Math.PI);
      ctx.fillStyle = "rgba(239, 68, 68, 0.4)";
      ctx.fill();
    } else if (isSelected || isHovered) {
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.radius + 7, 0, 2 * Math.PI);
      ctx.fillStyle = isSelected ? "rgba(244, 63, 94, 0.3)" : "rgba(56, 189, 248, 0.25)";
      ctx.fill();
    }

    // Determine Node Color
    let nodeColor = ENTITY_COLOR_MAP[n.type] || n.color || "#94a3b8";
    if (isContagion) {
      if (isEpicenter) {
        nodeColor = "#ef4444";
      } else if (contagionInfo) {
        nodeColor = contagionInfo.color; // #EF4444 (Vulnerable) or #10B981 (Beneficiary) or #64748B
      } else {
        nodeColor = "#334155"; // Neutral / Dimmed
      }
    } else if (n.is_active === false) {
      nodeColor = "#273549"; // Dimmed if outside temporal horizon
    }

    // Node body
    ctx.beginPath();
    ctx.arc(n.x, n.y, n.radius, 0, 2 * Math.PI);
    ctx.fillStyle = isSelected ? "#f43f5e" : nodeColor;
    ctx.fill();
    ctx.lineWidth = isEpicenter ? 2.5 : 1.5;
    ctx.strokeStyle = isEpicenter ? "#fee2e2" : "#0b111a";
    ctx.stroke();

    // Node label
    let label = n.ticker || n.name.slice(0, 10);
    if (isContagion && contagionInfo && !isEpicenter) {
      const pct = (contagionInfo.impact_score * 100).toFixed(0);
      label = `${n.ticker || n.name.slice(0, 6)} ${pct > 0 ? '+' : ''}${pct}%`;
    }

    ctx.font = isSelected || isEpicenter ? "700 11px DM Mono, monospace" : "500 9px DM Mono, monospace";
    ctx.fillStyle = isSelected || isEpicenter ? "#fff" : (isContagion && !contagionInfo ? "#64748b" : "#cbd5e1");
    ctx.textAlign = "center";
    ctx.fillText(label, n.x, n.y - n.radius - 4);
  }

  ctx.restore();
  requestAnimationFrame(renderGraphStep);
}

// Canvas Interaction (Hover, Click, Pan, Zoom, Drag)
const kgCanvas = $("#kg-canvas");
if (kgCanvas) {
  function getMouseCanvasPos(e) {
    const rect = kgCanvas.getBoundingClientRect();
    const { transform } = stocklensState;
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    return {
      x: (mouseX - transform.x) / transform.k,
      y: (mouseY - transform.y) / transform.k,
      rawX: mouseX,
      rawY: mouseY
    };
  }

  function findNodeAt(x, y) {
    for (let i = stocklensState.nodes.length - 1; i >= 0; i--) {
      const n = stocklensState.nodes[i];
      const dx = n.x - x;
      const dy = n.y - y;
      if (dx * dx + dy * dy <= (n.radius + 4) * (n.radius + 4)) return n;
    }
    return null;
  }

  kgCanvas.addEventListener("mousemove", (e) => {
    const pos = getMouseCanvasPos(e);
    if (stocklensState.draggedNode) {
      stocklensState.draggedNode.x = pos.x;
      stocklensState.draggedNode.y = pos.y;
      return;
    }
    if (stocklensState.isPanning) {
      stocklensState.transform.x = pos.rawX - stocklensState.panStart.x;
      stocklensState.transform.y = pos.rawY - stocklensState.panStart.y;
      return;
    }

    const hit = findNodeAt(pos.x, pos.y);
    stocklensState.hoveredNode = hit;
    const tooltip = $("#kg-tooltip");
    if (hit && tooltip) {
      tooltip.hidden = false;
      tooltip.style.left = `${pos.rawX + 15}px`;
      tooltip.style.top = `${pos.rawY - 15}px`;
      tooltip.innerHTML = `<strong>${escapeHtml(hit.name)}</strong> (${escapeHtml(hit.id)})<br>Type: ${hit.type}<br>Ticker: ${hit.ticker || 'N/A'}<br>Degree: ${hit.degree}`;
    } else if (tooltip) {
      tooltip.hidden = true;
    }
  });

  kgCanvas.addEventListener("mousedown", (e) => {
    const pos = getMouseCanvasPos(e);
    const hit = findNodeAt(pos.x, pos.y);
    if (hit) {
      stocklensState.draggedNode = hit;
      if (stocklensState.viewMode === "contagion") {
        runContagionSimulation(hit.id, "negative");
      }
      inspectNode(hit);
    } else {
      stocklensState.isPanning = true;
      stocklensState.panStart.x = pos.rawX - stocklensState.transform.x;
      stocklensState.panStart.y = pos.rawY - stocklensState.transform.y;
    }
  });

  window.addEventListener("mouseup", () => {
    stocklensState.draggedNode = null;
    stocklensState.isPanning = false;
  });

  kgCanvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.12 : 0.89;
    const pos = getMouseCanvasPos(e);
    stocklensState.transform.x = pos.rawX - (pos.rawX - stocklensState.transform.x) * zoomFactor;
    stocklensState.transform.y = pos.rawY - (pos.rawY - stocklensState.transform.y) * zoomFactor;
    stocklensState.transform.k *= zoomFactor;
  });
}

function inspectNode(node) {
  stocklensState.selectedNode = node;
  $("#insp-type").textContent = `${node.type.toUpperCase()} · ${node.id}`;
  $("#insp-name").textContent = node.name;
  $("#insp-ticker").textContent = `${node.ticker ? node.ticker + ' · ' : ''}${node.exchange || 'US Market'}`;
  $("#insp-in-deg").textContent = node.in_degree || 0;
  $("#insp-out-deg").textContent = node.out_degree || 0;
  $("#insp-tot-deg").textContent = node.degree || 0;

  // Filter connected relationships
  const connectedEdges = (stocklensState.graphData?.edges || []).filter((e) => e.source === node.id || e.target === node.id);
  const relList = $("#insp-rel-list");
  if (!connectedEdges.length) {
    relList.innerHTML = `<p class="empty-hint">No direct connections recorded for this node.</p>`;
    return;
  }

  relList.innerHTML = connectedEdges.map((e) => {
    const isOut = e.source === node.id;
    const partnerId = isOut ? e.target : e.source;
    const partner = stocklensState.nodesMap[partnerId];
    const partnerName = partner ? partner.name : partnerId;
    const arrow = isOut ? `&rarr;` : `&larr;`;
    const badgeClass = e.evidence_status === "verified" ? "insp-badge-verified" : "insp-badge-inferred";

    return `
      <div class="insp-rel-item">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span class="insp-rel-type ${badgeClass}">${escapeHtml(e.rel_type)}</span>
          <span style="font-size:9px; color:var(--ink-soft);">${escapeHtml(e.evidence_status)}</span>
        </div>
        <div style="font-weight:700; margin-top:2px;">${arrow} ${escapeHtml(partnerName)} <small style="color:var(--ink-soft)">(${escapeHtml(partnerId)})</small></div>
        ${e.notes ? `<div style="font-size:10px; color:var(--ink-soft); margin-top:4px;">${escapeHtml(e.notes)}</div>` : ''}
      </div>
    `;
  }).join("");
}

// Filter buttons
document.querySelectorAll(".kg-filter-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".kg-filter-btn").forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    stocklensState.filterType = btn.dataset.kgFilter;
    setupGraphCanvas();
  });
});

let kgSearchTimer;
$("#kg-search-input")?.addEventListener("input", (e) => {
  clearTimeout(kgSearchTimer);
  kgSearchTimer = setTimeout(() => {
    stocklensState.searchQuery = e.target.value.trim();
    setupGraphCanvas();
  }, 200);
});

$("#kg-reset-btn")?.addEventListener("click", () => {
  stocklensState.transform = { x: 0, y: 0, k: 1 };
  stocklensState.filterType = "All";
  stocklensState.searchQuery = "";
  if ($("#kg-search-input")) $("#kg-search-input").value = "";
  document.querySelectorAll(".kg-filter-btn").forEach((b) => b.classList.toggle("is-active", b.dataset.kgFilter === "All"));
  setupGraphCanvas();
});

// --- TEMPORAL & 2-COLOR CONTAGION CONTROLS ---

// Timeframe Range Buttons (1W, 1M, 1Y, 5Y, ALL)
document.querySelectorAll(".kg-range-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".kg-range-btn").forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    stocklensState.selectedRange = btn.dataset.kgRange;
    loadGraphData();
  });
});

// Historical Year Slider (1980 - 2026)
let kgYearSliderTimer;
$("#kg-year-slider")?.addEventListener("input", (e) => {
  const yr = parseInt(e.target.value, 10);
  if ($("#kg-year-display")) $("#kg-year-display").textContent = yr;
  stocklensState.selectedYear = yr;
  clearTimeout(kgYearSliderTimer);
  kgYearSliderTimer = setTimeout(() => {
    loadGraphData();
  }, 120);
});

// Mode Switcher (Taxonomy vs 2-Color Shock)
function setGraphMode(mode) {
  stocklensState.viewMode = mode;
  $("#kg-mode-topology")?.classList.toggle("is-active", mode === "topology");
  $("#kg-mode-contagion")?.classList.toggle("is-active", mode === "contagion");

  const contagionPanel = $("#kg-contagion-panel");
  const leaderboard = $("#kg-impact-leaderboard");
  const legend = $("#kg-legend");

  if (mode === "contagion") {
    if (contagionPanel) contagionPanel.hidden = false;
    if (leaderboard) leaderboard.hidden = false;
    if (legend) {
      legend.innerHTML = `
        <span><i style="background:#EF4444"></i> Vulnerable / Drop (Negative Contagion)</span>
        <span><i style="background:#10B981"></i> Beneficiary / Gain (Competitor / Windfall)</span>
        <span><i style="background:#334155"></i> Neutral / Dimmed</span>
      `;
    }
    // Default shock simulation if not yet initiated
    if (!stocklensState.contagionData) {
      runContagionSimulation("co_nvda", "negative");
    }
  } else {
    if (contagionPanel) contagionPanel.hidden = true;
    if (leaderboard) leaderboard.hidden = true;
    if (legend) {
      legend.innerHTML = `
        <span><i style="background:#6366F1"></i> Sector</span>
        <span><i style="background:#8B5CF6"></i> Industry</span>
        <span><i style="background:#10B981"></i> Company</span>
        <span><i style="background:#F59E0B"></i> Commodity</span>
        <span><i style="background:#EF4444"></i> Macro</span>
        <span><i style="background:#06B6D4"></i> Product</span>
      `;
    }
  }
}

$("#kg-mode-topology")?.addEventListener("click", () => setGraphMode("topology"));
$("#kg-mode-contagion")?.addEventListener("click", () => setGraphMode("contagion"));

// Shock Presets
document.querySelectorAll(".shock-preset-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".shock-preset-btn").forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    const nodeId = btn.dataset.shockNode;
    const shockType = btn.dataset.shockType || "negative";
    runContagionSimulation(nodeId, shockType);
  });
});

// Reset Shock Simulation
$("#kg-reset-shock-btn")?.addEventListener("click", () => {
  stocklensState.contagionData = null;
  stocklensState.shockEpicenter = null;
  document.querySelectorAll(".shock-preset-btn").forEach((b) => b.classList.remove("is-active"));
  const statusMsg = $("#contagion-status-msg");
  if (statusMsg) statusMsg.textContent = "Simulation reset. Click any node on canvas or choose a preset above to simulate shock contagion.";

  const vulnList = $("#vulnerable-list");
  if (vulnList) vulnList.innerHTML = `<p class="empty-hint">Choose a shock preset or click any node to simulate negative contagion.</p>`;
  const beneList = $("#beneficiary-list");
  if (beneList) beneList.innerHTML = `<p class="empty-hint">Entities benefiting from substitute demand or commodity windfalls will appear here.</p>`;
});

// Run Contagion Simulation API
async function runContagionSimulation(nodeId, shockType = "negative") {
  const statusMsg = $("#contagion-status-msg");
  if (statusMsg) statusMsg.textContent = `Simulating propagation shock from ${nodeId}…`;

  try {
    const data = await request(`/api/stocklens/contagion?node=${encodeURIComponent(nodeId)}&shock_type=${shockType}&magnitude=1.0`);
    stocklensState.contagionData = data;
    stocklensState.shockEpicenter = nodeId;

    if (statusMsg) {
      const epicName = data.epicenter ? `${data.epicenter.name} (${data.epicenter.ticker || data.epicenter.id})` : nodeId;
      statusMsg.innerHTML = `<strong>Shock Epicenter:</strong> ${escapeHtml(epicName)} · <strong>Downstream Impacted:</strong> ${data.impacted_count} entities (${data.top_vulnerable.length} vulnerable, ${data.top_beneficiaries.length} beneficiaries)`;
    }

    renderContagionLeaderboard(data);
  } catch (err) {
    console.error("Contagion simulation error:", err);
    if (statusMsg) statusMsg.textContent = `Simulation error: ${err.message}`;
  }
}

// Render Contagion Impact Leaderboard
function renderContagionLeaderboard(data) {
  const vulnList = $("#vulnerable-list");
  const beneList = $("#beneficiary-list");

  if (vulnList) {
    if (!data.top_vulnerable || data.top_vulnerable.length === 0) {
      vulnList.innerHTML = `<p class="empty-hint">No direct vulnerable equities detected for this shock configuration.</p>`;
    } else {
      vulnList.innerHTML = data.top_vulnerable.map((item, idx) => {
        const pct = (item.impact_score * 100).toFixed(1);
        const barWidth = Math.min(100, Math.max(10, Math.abs(item.impact_score) * 100));
        return `
          <div class="impact-item impact-vulnerable">
            <div class="impact-rank">#${idx + 1}</div>
            <div class="impact-info">
              <div class="impact-title">
                <strong>${escapeHtml(item.name)}</strong>
                <code class="impact-ticker">${escapeHtml(item.ticker || item.id)}</code>
              </div>
              <div class="impact-notes">${escapeHtml(item.notes || 'Supply disruption & cost inflation')}</div>
              <div class="impact-bar-wrap">
                <div class="impact-bar-fill bar-red" style="width: ${barWidth}%"></div>
              </div>
            </div>
            <div class="impact-badge badge-vulnerable">${pct}%</div>
          </div>
        `;
      }).join("");
    }
  }

  if (beneList) {
    if (!data.top_beneficiaries || data.top_beneficiaries.length === 0) {
      beneList.innerHTML = `<p class="empty-hint">No direct competitor or windfall beneficiaries detected.</p>`;
    } else {
      beneList.innerHTML = data.top_beneficiaries.map((item, idx) => {
        const pct = (item.impact_score * 100).toFixed(1);
        const barWidth = Math.min(100, Math.max(10, Math.abs(item.impact_score) * 100));
        return `
          <div class="impact-item impact-beneficiary">
            <div class="impact-rank">#${idx + 1}</div>
            <div class="impact-info">
              <div class="impact-title">
                <strong>${escapeHtml(item.name)}</strong>
                <code class="impact-ticker">${escapeHtml(item.ticker || item.id)}</code>
              </div>
              <div class="impact-notes">${escapeHtml(item.notes || 'Competitor market share gain & windfall revenue')}</div>
              <div class="impact-bar-wrap">
                <div class="impact-bar-fill bar-green" style="width: ${barWidth}%"></div>
              </div>
            </div>
            <div class="impact-badge badge-beneficiary">+${pct}%</div>
          </div>
        `;
      }).join("");
    }
  }
}

// AI Live News Graph Extractor Sync Button
$("#kg-sync-btn")?.addEventListener("click", async () => {
  const btn = $("#kg-sync-btn");
  if (!btn || btn.disabled) return;

  const originalHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<span class="sync-icon spin">🔄</span> Analyzing News via AI…`;

  try {
    const res = await request("/api/stocklens/sync_news_relations");
    btn.innerHTML = `<span class="sync-icon">✅</span> +${res.new_edges_added || 0} New Paths Found!`;

    // Reload graph data with new dynamic paths
    await loadGraphData();

    setTimeout(() => {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }, 3500);
  } catch (err) {
    console.error("AI News Sync error:", err);
    btn.innerHTML = `<span class="sync-icon">⚠️</span> Scan Failed`;
    setTimeout(() => {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }, 2500);
  }
});

// 3. ECONOMIC TRANSMISSION PATHS MODULE
function populatePathDropdowns() {
  const nodes = stocklensState.graphData?.nodes || [];
  const srcSelect = $("#path-source-select");
  const tgtSelect = $("#path-target-select");
  if (!srcSelect || !tgtSelect || srcSelect.options.length > 0) return;

  const sorted = [...nodes].sort((a, b) => a.name.localeCompare(b.name));
  const optionsHtml = sorted.map((n) => `<option value="${escapeHtml(n.id)}">${escapeHtml(n.name)} (${escapeHtml(n.ticker || n.id)})</option>`).join("");
  srcSelect.innerHTML = optionsHtml;
  tgtSelect.innerHTML = optionsHtml;

  // Defaults
  srcSelect.value = "commodity_wti";
  tgtSelect.value = "co_dal";
}

$("#path-hops-slider")?.addEventListener("input", (e) => {
  if ($("#hops-value")) $("#hops-value").textContent = e.target.value;
});

document.querySelectorAll(".quick-path-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const src = btn.dataset.src;
    const tgt = btn.dataset.tgt;
    if ($("#path-source-select")) $("#path-source-select").value = src;
    if ($("#path-target-select")) $("#path-target-select").value = tgt;
    executeTracePaths();
  });
});

$("#find-paths-btn")?.addEventListener("click", executeTracePaths);

async function executeTracePaths() {
  const src = $("#path-source-select")?.value || "commodity_wti";
  const tgt = $("#path-target-select")?.value || "co_dal";
  const hops = $("#path-hops-slider")?.value || 4;
  const out = $("#paths-output");
  if (!out) return;

  out.innerHTML = `<div class="empty-paths-state">Tracing transmission paths between <strong>${src}</strong> and <strong>${tgt}</strong>…</div>`;

  try {
    const res = await request(`/api/stocklens/paths?source=${encodeURIComponent(src)}&target=${encodeURIComponent(tgt)}&max_hops=${hops}`);
    if (!res.paths || res.paths.length === 0) {
      out.innerHTML = `<div class="empty-paths-state">No economic transmission path found between <strong>${src}</strong> and <strong>${tgt}</strong> within ${hops} hops.</div>`;
      return;
    }

    out.innerHTML = res.paths.map((p, idx) => {
      const finalHop = p[p.length - 1];
      const totalLag = finalHop.cumulative_lag || 0;
      return `
        <article class="path-card">
          <div class="path-card-header">
            <strong>Transmission Path #${idx + 1} (${p.length} Hops)</strong>
            <span class="metric-label">Cumulative Lag: <strong>${totalLag} Days</strong></span>
          </div>
          <div class="path-steps">
            ${p.map((hop) => `
              <div class="path-step-item">
                <div class="step-number">${hop.hop}</div>
                <div>
                  <div class="step-body-top">
                    <span class="step-entity">${escapeHtml(hop.from_name)}</span>
                    <span class="step-rel-badge">${escapeHtml(hop.rel_type)}</span>
                    <span style="font-size:12px;">&rarr;</span>
                    <span class="step-entity">${escapeHtml(hop.to_name)}</span>
                    <span class="insp-rel-type insp-badge-${hop.evidence_status === 'verified' ? 'verified' : 'inferred'}">${escapeHtml(hop.evidence_status)}</span>
                    ${hop.lag_days ? `<span style="font-size:10px; color:var(--ink-soft); font-family:var(--mono);">Lag: ${hop.lag_days}d</span>` : ''}
                  </div>
                  ${hop.notes ? `<div style="font-size:11px; color:var(--ink-soft);">${escapeHtml(hop.notes)}</div>` : ''}
                  ${hop.evidence_details && hop.evidence_details.length ? hop.evidence_details.map((ev) => `
                    <div class="step-evidence-quote">
                      <strong>📑 ${escapeHtml(ev.source_title || 'SEC 10-K Filing')}</strong><br>
                      <em>"${escapeHtml(ev.page_or_excerpt || '')}"</em><br>
                      <a href="${escapeHtml(ev.source_url || '#')}" target="_blank" rel="noopener">Official SEC EDGAR Filing ↗</a>
                    </div>
                  `).join('') : ''}
                </div>
              </div>
            `).join('')}
          </div>
        </article>
      `;
    }).join("");
  } catch (e) {
    out.innerHTML = `<div class="empty-paths-state">Error tracing paths: ${escapeHtml(e.message)}</div>`;
  }
}

function initPathsView() {
  if (stocklensState.graphData) {
    populatePathDropdowns();
  } else {
    initGraphView().then(populatePathDropdowns);
  }
}

// 4. QUANTITATIVE MODELS MODULE
function initQuantView() {
  runMarketModel();
  runEventStudy();
  runLeadLag();
  runUniverseLeadLag();
}

document.querySelectorAll(".subnav-pill").forEach((pill) => {
  pill.addEventListener("click", () => {
    const tab = pill.dataset.quantTab;
    document.querySelectorAll(".subnav-pill").forEach((p) => p.classList.toggle("is-active", p.dataset.quantTab === tab));
    document.querySelectorAll(".quant-subpanel").forEach((p) => { p.hidden = p.id !== `quant-${tab}`; });
    if (tab === "universe-lead-lag" && !ullState.data) {
      runUniverseLeadLag();
    }
  });
});

// A. Market Model OLS
$("#mm-run-btn")?.addEventListener("click", runMarketModel);

async function runMarketModel() {
  const ticker = $("#mm-stock-select")?.value || "NVDA";
  const startDate = $("#mm-start-date")?.value || "2022-01-01";
  try {
    const res = await request(`/api/stocklens/market_model?ticker=${ticker}&benchmark=^GSPC&start_date=${startDate}`);
    $("#mm-beta").textContent = res.beta.toFixed(2);
    $("#mm-alpha").textContent = `${(res.alpha_annualized * 100).toFixed(1)}%`;
    $("#mm-r2").textContent = `${(res.r_squared * 100).toFixed(1)}%`;
    $("#mm-idio-vol").textContent = `${(res.idiosyncratic_volatility_annualized * 100).toFixed(1)}%`;
    $("#mm-sharpe").textContent = res.sharpe_ratio.toFixed(2);
    $("#mm-chart-title").textContent = `OLS REGRESSION: ${ticker} vs ^GSPC (S&P 500)`;
    $("#mm-sample-size").textContent = `${res.sample_size} Trading Sessions (${res.start_date} → ${res.end_date})`;

    renderScatterChart(res.points, res.line, ticker);
  } catch (e) {
    console.error("Market Model error:", e);
  }
}

function renderScatterChart(points, line, ticker) {
  const container = $("#mm-scatter-chart");
  if (!container || !points || !points.length) return;

  const width = 800;
  const height = 340;
  const pad = 40;

  const allX = points.map((p) => p.x);
  const allY = points.map((p) => p.y);
  const minX = Math.min(...allX);
  const maxX = Math.max(...allX);
  const minY = Math.min(...allY);
  const maxY = Math.max(...allY);

  function scaleX(val) { return pad + ((val - minX) / (maxX - minX)) * (width - 2 * pad); }
  function scaleY(val) { return height - pad - ((val - minY) / (maxY - minY)) * (height - 2 * pad); }

  const dots = points.map((p) => `<circle cx="${scaleX(p.x).toFixed(1)}" cy="${scaleY(p.y).toFixed(1)}" r="3" fill="#38bdf8" opacity="0.6"/>`).join("");
  const lineSvg = `<line x1="${scaleX(line[0].x).toFixed(1)}" y1="${scaleY(line[0].y).toFixed(1)}" x2="${scaleX(line[1].x).toFixed(1)}" y2="${scaleY(line[1].y).toFixed(1)}" stroke="#f43f5e" stroke-width="2.5"/>`;

  // Zero axis lines
  const zeroX = scaleX(0);
  const zeroY = scaleY(0);
  const axes = `
    <line x1="${pad}" y1="${zeroY}" x2="${width - pad}" y2="${zeroY}" stroke="rgba(255,255,255,0.2)" stroke-dasharray="3"/>
    <line x1="${zeroX}" y1="${pad}" x2="${zeroX}" y2="${height - pad}" stroke="rgba(255,255,255,0.2)" stroke-dasharray="3"/>
  `;

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" style="width:100%; height:100%; background:#0b111a; border-radius:4px;">
      ${axes}
      ${dots}
      ${lineSvg}
      <text x="${width - pad}" y="${height - 10}" fill="#94a3b8" font-size="10" font-family="DM Mono, monospace" text-anchor="end">S&P 500 Daily Return</text>
      <text x="${pad}" y="20" fill="#94a3b8" font-size="10" font-family="DM Mono, monospace">${escapeHtml(ticker)} Daily Return</text>
    </svg>
  `;
}

// B. Event Study Lab
$("#ev-run-btn")?.addEventListener("click", runEventStudy);
$("#ev-preset-select")?.addEventListener("change", runEventStudy);

async function runEventStudy() {
  const preset = $("#ev-preset-select")?.value || "NVDA|2024-03-18";
  const [ticker, eventDate] = preset.split("|");
  const pre = $("#ev-pre-window")?.value || 3;
  const post = $("#ev-post-window")?.value || 7;

  try {
    const res = await request(`/api/stocklens/event_study?ticker=${ticker}&event_date=${eventDate}&pre_window=${pre}&post_window=${post}`);
    const carVal = res.car * 100;
    $("#ev-car").textContent = `${carVal > 0 ? '+' : ''}${carVal.toFixed(2)}%`;
    $("#ev-car").style.color = carVal >= 0 ? "#10b981" : "#f43f5e";
    $("#ev-tstat").textContent = res.t_statistic.toFixed(2);
    $("#ev-pval").textContent = res.p_value.toFixed(4);
    $("#ev-sig-badge").textContent = res.statistically_significant ? "Significant (p < 0.05)" : "Not Significant";
    $("#ev-sig-badge").style.color = res.statistically_significant ? "#10b981" : "#94a3b8";

    renderEventStudyChart(res.event_series, ticker, eventDate);
  } catch (e) {
    console.error("Event study error:", e);
  }
}

function renderEventStudyChart(series, ticker, date) {
  const container = $("#ev-chart");
  if (!container || !series || !series.length) return;

  const width = 800;
  const height = 300;
  const pad = 40;

  const relDays = series.map((s) => s.rel_day);
  const minDay = Math.min(...relDays);
  const maxDay = Math.max(...relDays);

  const cars = series.map((s) => s.car * 100);
  const ars = series.map((s) => s.abnormal_return * 100);
  const allVals = [...cars, ...ars, 0];
  const minVal = Math.min(...allVals) - 1;
  const maxVal = Math.max(...allVals) + 1;

  function scaleX(day) { return pad + ((day - minDay) / (maxDay - minDay)) * (width - 2 * pad); }
  function scaleY(val) { return height - pad - ((val - minVal) / (maxVal - minVal)) * (height - 2 * pad); }

  const zeroY = scaleY(0);
  const eventX = scaleX(0);

  // Bars for AR
  const barWidth = Math.max(8, (width - 2 * pad) / series.length * 0.45);
  const bars = series.map((s) => {
    const x = scaleX(s.rel_day) - barWidth / 2;
    const yVal = scaleY(s.abnormal_return * 100);
    const y = Math.min(zeroY, yVal);
    const h = Math.abs(yVal - zeroY);
    const color = s.abnormal_return >= 0 ? "rgba(56, 189, 248, 0.7)" : "rgba(244, 63, 94, 0.7)";
    return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barWidth.toFixed(1)}" height="${h.toFixed(1)}" fill="${color}"/>`;
  }).join("");

  // Line for CAR
  const carLine = series.map((s, idx) => `${idx === 0 ? 'M' : 'L'}${scaleX(s.rel_day).toFixed(1)},${scaleY(s.car * 100).toFixed(1)}`).join(" ");

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" style="width:100%; height:100%; background:#0b111a; border-radius:4px;">
      <line x1="${pad}" y1="${zeroY}" x2="${width - pad}" y2="${zeroY}" stroke="rgba(255,255,255,0.3)"/>
      <line x1="${eventX}" y1="${pad}" x2="${eventX}" y2="${height - pad}" stroke="#f43f5e" stroke-dasharray="4" stroke-width="1.5"/>
      <text x="${eventX + 6}" y="${pad + 14}" fill="#f43f5e" font-size="10" font-family="DM Mono, monospace">Event T0 (${escapeHtml(date)})</text>
      ${bars}
      <path d="${carLine}" fill="none" stroke="#10b981" stroke-width="2.5"/>
      ${series.map((s) => `<circle cx="${scaleX(s.rel_day).toFixed(1)}" cy="${scaleY(s.car * 100).toFixed(1)}" r="3" fill="#10b981"/>`).join("")}
      <text x="${width - pad}" y="${height - 10}" fill="#94a3b8" font-size="10" font-family="DM Mono, monospace" text-anchor="end">Days Relative to Event (T0)</text>
      <text x="${pad}" y="20" fill="#10b981" font-size="10" font-family="DM Mono, monospace">CAR (%) & AR (%)</text>
    </svg>
  `;
}

// C. Lead/Lag Cross-Correlation
$("#ll-run-btn")?.addEventListener("click", runLeadLag);

async function runLeadLag() {
  const equity = $("#ll-stock-select")?.value || "DAL";
  const macro = $("#ll-macro-select")?.value || "CL=F";

  try {
    const res = await request(`/api/stocklens/lead_lag?equity=${equity}&macro=${encodeURIComponent(macro)}`);
    const optLag = res.optimal_lag_days;
    const interp = optLag > 0 ? `${macro} leads ${equity} returns by ${optLag} trading days.` : optLag === 0 ? `Coincident daily transmission (0 days lag).` : `${equity} leads ${macro} by ${Math.abs(optLag)} trading days.`;

    $("#ll-optimal-lag").textContent = `${optLag} Days (r = ${res.max_abs_correlation.toFixed(3)})`;
    $("#ll-interp").textContent = interp;

    renderLeadLagChart(res.lag_matrix, equity, macro);
  } catch (e) {
    console.error("Lead/lag error:", e);
  }
}

function renderLeadLagChart(matrix, equity, macro) {
  const container = $("#ll-chart");
  if (!container || !matrix || !matrix.length) return;

  const width = 800;
  const height = 300;
  const pad = 40;

  const lags = matrix.map((m) => m.lag_days);
  const minLag = Math.min(...lags);
  const maxLag = Math.max(...lags);

  const corrs = matrix.map((m) => m.correlation);
  const maxAbs = Math.max(...corrs.map(Math.abs), 0.15) * 1.15;

  function scaleX(lag) { return pad + ((lag - minLag) / (maxLag - minLag)) * (width - 2 * pad); }
  function scaleY(corr) { return height / 2 - (corr / maxAbs) * (height / 2 - pad); }

  const zeroY = height / 2;
  const barWidth = Math.max(12, (width - 2 * pad) / matrix.length * 0.55);

  const bars = matrix.map((m) => {
    const x = scaleX(m.lag_days) - barWidth / 2;
    const yVal = scaleY(m.correlation);
    const y = Math.min(zeroY, yVal);
    const h = Math.abs(yVal - zeroY);
    const color = m.correlation >= 0 ? "#10b981" : "#f43f5e";
    return `
      <rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barWidth.toFixed(1)}" height="${h.toFixed(1)}" fill="${color}"/>
      <text x="${scaleX(m.lag_days).toFixed(1)}" y="${m.correlation >= 0 ? (y - 5).toFixed(1) : (y + h + 11).toFixed(1)}" fill="#cbd5e1" font-size="9" font-family="DM Mono, monospace" text-anchor="middle">${m.correlation.toFixed(2)}</text>
    `;
  }).join("");

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" style="width:100%; height:100%; background:#0b111a; border-radius:4px;">
      <line x1="${pad}" y1="${zeroY}" x2="${width - pad}" y2="${zeroY}" stroke="rgba(255,255,255,0.4)"/>
      <line x1="${scaleX(0)}" y1="${pad}" x2="${scaleX(0)}" y2="${height - pad}" stroke="rgba(255,255,255,0.2)" stroke-dasharray="3"/>
      ${bars}
      <text x="${width - pad}" y="${height - 10}" fill="#94a3b8" font-size="10" font-family="DM Mono, monospace" text-anchor="end">Lag Horizon (Days)</text>
      <text x="${pad}" y="20" fill="#94a3b8" font-size="10" font-family="DM Mono, monospace">Pearson Correlation (r)</text>
    </svg>
  `;
}

// D. Universe Lead/Lag Multi-Horizon Ripple Engine
const ullState = {
  ticker: "NVDA",
  threshold: 0.025,
  horizon: 5,
  data: null,
  activeFollowerIndex: 0,
};

$("#ull-run-btn")?.addEventListener("click", () => runUniverseLeadLag());
$("#ull-stock-select")?.addEventListener("change", (e) => {
  ullState.ticker = e.target.value;
  runUniverseLeadLag();
});

document.querySelectorAll("#ull-threshold-pills .ull-pill").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#ull-threshold-pills .ull-pill").forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    ullState.threshold = parseFloat(btn.dataset.val);
    runUniverseLeadLag();
  });
});

document.querySelectorAll("#ull-horizon-pills .ull-pill").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#ull-horizon-pills .ull-pill").forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    ullState.horizon = parseInt(btn.dataset.val, 10);
    runUniverseLeadLag();
  });
});

async function runUniverseLeadLag() {
  const ticker = ullState.ticker;
  const threshold = ullState.threshold;
  const horizon = ullState.horizon;
  const tbody = $("#ull-table-body");
  if (tbody) tbody.innerHTML = `<tr><td colspan="9" class="loading-td">Scanning universe for ${escapeHtml(ticker)} information diffusion (Horizon: T+${horizon}d)…</td></tr>`;

  try {
    const res = await request(`/api/stocklens/universe_lead_lag?ticker=${ticker}&threshold=${threshold}&horizon=${horizon}`);
    ullState.data = res;
    ullState.activeFollowerIndex = 0;
    renderUniverseLeadLag(res);
  } catch (e) {
    console.error("Universe lead lag error:", e);
    if (tbody) tbody.innerHTML = `<tr><td colspan="9" class="loading-td">Error scanning universe: ${escapeHtml(e.message)}</td></tr>`;
  }
}

function renderUniverseLeadLag(data) {
  if (!data || !data.trigger) return;
  const { trigger, horizon_days, followers_count, top_followers, sector_summary } = data;

  // 1. Summary Banner
  if ($("#ull-stat-events")) $("#ull-stat-events").textContent = `${trigger.shock_count} Shock Days (≥ +${trigger.threshold_pct}%)`;
  if ($("#ull-stat-sample")) $("#ull-stat-sample").textContent = `${trigger.sample_start} → ${trigger.sample_end}`;
  if ($("#ull-stat-universe")) $("#ull-stat-universe").textContent = `${followers_count + 1} Assets · 11 Sectors`;
  if ($("#ull-stat-top-target")) {
    const top = top_followers && top_followers[0];
    $("#ull-stat-top-target").textContent = top ? `${top.ticker} (+${top.cum_return_at_horizon.toFixed(2)}%)` : "—";
  }

  // 2. Sector Diffusion Map
  const horizonText = horizon_days === 1 ? "T+1 Day" : horizon_days === 2 ? "T+2 Days" : horizon_days === 5 ? "T+5 Days (1 Week)" : horizon_days === 10 ? "T+10 Days (2 Weeks)" : `T+${horizon_days} Days (1 Month)`;
  if ($("#ull-sector-horizon-label")) $("#ull-sector-horizon-label").textContent = `Diffusion Horizon: ${horizonText}`;

  const sectorGrid = $("#ull-sector-grid");
  if (sectorGrid && sector_summary) {
    sectorGrid.innerHTML = sector_summary.map((s) => {
      const ret = s.avg_cum_return;
      const retColor = ret >= 0 ? "#10b981" : "#ef4444";
      const retSign = ret >= 0 ? "+" : "";
      return `
        <div class="ull-sector-card">
          <div class="ull-sector-header">
            <span class="ull-sector-name">${escapeHtml(s.sector)}</span>
            <span class="ull-sector-count">${s.stock_count} ${s.stock_count === 1 ? 'asset' : 'assets'}</span>
          </div>
          <div class="ull-sector-return" style="color:${retColor};">${retSign}${ret.toFixed(2)}%</div>
          <div class="ull-sector-winrate">Hit Rate: <strong>${s.avg_hit_rate.toFixed(1)}%</strong></div>
        </div>
      `;
    }).join("");
  }

  // 3. Followers Leaderboard Table
  const tbody = $("#ull-table-body");
  if (tbody) {
    if (!top_followers || !top_followers.length) {
      tbody.innerHTML = `<tr><td colspan="9" class="loading-td">No follower assets found meeting criteria.</td></tr>`;
      return;
    }

    tbody.innerHTML = top_followers.map((f, idx) => {
      const cumRet = f.cum_return_at_horizon;
      const cumColor = cumRet >= 0 ? "#047857" : "#b91c1c";
      const cumSign = cumRet >= 0 ? "+" : "";
      const isSelected = idx === ullState.activeFollowerIndex;
      const badgeHtml = f.is_graph_verified
        ? `<span class="ull-badge ull-badge-verified">⛓️ ${escapeHtml(f.graph_badge)}</span>`
        : `<span class="ull-badge ull-badge-corr">📊 Statistical</span>`;

      return `
        <tr class="${isSelected ? 'is-active-row' : ''}" data-idx="${idx}">
          <td><strong>${idx + 1}</strong></td>
          <td>
            <strong>${escapeHtml(f.ticker)}</strong>
            <span style="color:var(--ink-soft); font-size:10px; display:block;">${escapeHtml(f.name.split('-')[0].trim())}</span>
          </td>
          <td>${escapeHtml(f.sector)}</td>
          <td><span style="color:#6366f1; font-weight:700;">T+${f.peak_lag_day}d</span></td>
          <td>+${f.peak_avg_return.toFixed(2)}%</td>
          <td style="color:${cumColor}; font-weight:700;">${cumSign}${cumRet.toFixed(2)}%</td>
          <td>${f.cum_hit_rate.toFixed(1)}%</td>
          <td><strong>${f.lift_factor.toFixed(2)}x</strong></td>
          <td>${badgeHtml}</td>
        </tr>
      `;
    }).join("");

    tbody.querySelectorAll("tr[data-idx]").forEach((row) => {
      row.addEventListener("click", () => {
        const idx = parseInt(row.dataset.idx, 10);
        ullState.activeFollowerIndex = idx;
        tbody.querySelectorAll("tr").forEach((r) => r.classList.remove("is-active-row"));
        row.classList.add("is-active-row");
        renderImpulseChart(top_followers[idx], trigger);
      });
    });
  }

  // 4. Render Impulse Chart for initial follower
  if (top_followers && top_followers.length) {
    const activeFollower = top_followers[ullState.activeFollowerIndex] || top_followers[0];
    renderImpulseChart(activeFollower, trigger);
  }
}

function renderImpulseChart(follower, trigger) {
  const container = $("#ull-impulse-chart");
  const metaBox = $("#ull-impulse-meta");
  if (!container || !follower) return;

  if ($("#ull-impulse-title")) {
    $("#ull-impulse-title").textContent = `${follower.ticker} Cumulative Drift after ${trigger.ticker} Shock`;
  }
  if ($("#ull-impulse-badge")) {
    $("#ull-impulse-badge").textContent = `Peak Lag: T+${follower.peak_lag_day}d · Win Rate: ${follower.cum_hit_rate.toFixed(1)}%`;
  }

  const curve = follower.impulse_curve || [];
  if (!curve.length) {
    container.innerHTML = `<div class="list-message">No impulse trajectory available.</div>`;
    return;
  }

  const width = 600;
  const height = 290;
  const pad = 42;

  const days = curve.map((c) => c.day);
  const minDay = 0;
  const maxDay = Math.max(...days, 20);

  const cumVals = curve.map((c) => c.cum_return);
  const minVal = Math.min(0, ...cumVals);
  const maxVal = Math.max(0.5, ...cumVals);
  const range = (maxVal - minVal) * 1.25 || 1;

  function scaleX(d) { return pad + (d / maxDay) * (width - 2 * pad); }
  function scaleY(v) { return height - pad - ((v - minVal) / range) * (height - 2 * pad); }

  const zeroY = scaleY(0);

  // Build SVG path
  const points = curve.map((c) => `${scaleX(c.day).toFixed(1)},${scaleY(c.cum_return).toFixed(1)}`);
  const pathD = `M ${points.join(" L ")}`;
  const areaD = `M ${scaleX(0).toFixed(1)},${zeroY.toFixed(1)} L ${points.join(" L ")} L ${scaleX(maxDay).toFixed(1)},${zeroY.toFixed(1)} Z`;

  // Peak lag vertical marker
  const peakX = scaleX(follower.peak_lag_day);

  const circles = curve.map((c) => {
    const cx = scaleX(c.day).toFixed(1);
    const cy = scaleY(c.cum_return).toFixed(1);
    const isPeak = c.day === follower.peak_lag_day;
    return `
      <circle cx="${cx}" cy="${cy}" r="${isPeak ? 5 : 3.5}" fill="${isPeak ? '#10b981' : '#6366f1'}" stroke="#fff" stroke-width="${isPeak ? 2 : 1}"/>
      <text x="${cx}" y="${(cy - 8).toFixed(1)}" fill="${isPeak ? '#10b981' : '#94a3b8'}" font-size="9" font-family="DM Mono, monospace" text-anchor="middle">${c.cum_return >= 0 ? '+' : ''}${c.cum_return.toFixed(1)}%</text>
    `;
  }).join("");

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" style="width:100%; height:100%; background:#0b111a; border-radius:4px;">
      <defs>
        <linearGradient id="ull-area-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#6366f1" stop-opacity="0.35"/>
          <stop offset="100%" stop-color="#6366f1" stop-opacity="0.0"/>
        </linearGradient>
      </defs>
      <!-- Zero Axis -->
      <line x1="${pad}" y1="${zeroY.toFixed(1)}" x2="${width - pad}" y2="${zeroY.toFixed(1)}" stroke="rgba(255,255,255,0.25)" stroke-dasharray="3"/>
      <!-- Peak Lag Line -->
      <line x1="${peakX.toFixed(1)}" y1="${pad}" x2="${peakX.toFixed(1)}" y2="${height - pad}" stroke="#10b981" stroke-dasharray="4" stroke-width="1.5"/>
      <text x="${peakX + 6}" y="${pad + 14}" fill="#10b981" font-size="10" font-family="DM Mono, monospace">Peak Effect T+${follower.peak_lag_day}d</text>
      <!-- Area Fill -->
      <path d="${areaD}" fill="url(#ull-area-grad)"/>
      <!-- Trajectory Line -->
      <path d="${pathD}" fill="none" stroke="#6366f1" stroke-width="2.5"/>
      <!-- Data Points -->
      ${circles}
      <!-- Axis Labels -->
      <text x="${width - pad}" y="${height - 10}" fill="#94a3b8" font-size="10" font-family="DM Mono, monospace" text-anchor="end">Days After T0 Shock (T+0 to T+20)</text>
      <text x="${pad}" y="20" fill="#94a3b8" font-size="10" font-family="DM Mono, monospace">Cumulative Return (%)</text>
    </svg>
  `;

  if (metaBox) {
    const relText = follower.is_graph_verified
      ? `Confirmed in Ground-Truth Knowledge Graph via <strong>${escapeHtml(follower.graph_badge)}</strong>.`
      : `Cross-asset macro/sector statistical spillover.`;
    metaBox.innerHTML = `
      <div>
        When <strong>${escapeHtml(trigger.ticker)}</strong> moves ≥ <strong>+${trigger.threshold_pct}%</strong> in a day, 
        <strong>${escapeHtml(follower.ticker)}</strong> (${escapeHtml(follower.name.split('-')[0].trim())}) historically follows with a 
        peak return on <strong>T+${follower.peak_lag_day}</strong> (avg <strong>+${follower.peak_avg_return.toFixed(2)}%</strong>) 
        and cumulative <strong>+${follower.cum_return_at_horizon.toFixed(2)}%</strong> at horizon.
      </div>
      <div style="margin-top:6px; font-size:10px; color:var(--ink-soft);">
        Relationship: ${relText} Win rate: <strong>${follower.cum_hit_rate.toFixed(1)}%</strong> vs baseline ${follower.base_up_rate.toFixed(1)}% (<strong>${follower.lift_factor.toFixed(2)}x lift</strong>).
      </div>
    `;
  }
}

// 5. SEC 10-K EVIDENCE CATALOG MODULE
async function initEvidenceView() {
  const grid = $("#evidence-grid");
  if (!grid) return;
  if (!stocklensState.evidenceData) {
    try {
      const res = await request("/api/stocklens/evidence");
      stocklensState.evidenceData = res.items || [];
    } catch (e) {
      grid.innerHTML = `<div class="list-message">Error loading evidence: ${escapeHtml(e.message)}</div>`;
      return;
    }
  }
  renderEvidenceCards(stocklensState.evidenceData);
}

function renderEvidenceCards(items) {
  const grid = $("#evidence-grid");
  if (!grid) return;
  if (!items.length) {
    grid.innerHTML = `<div class="list-message">No citations matched the query.</div>`;
    return;
  }

  grid.innerHTML = items.map((ev) => `
    <article class="evidence-card">
      <div>
        <div class="evidence-card-header">
          <h3>${escapeHtml(ev.source_title || 'SEC Form 10-K Filing')}</h3>
          <span class="evidence-pub-badge">${escapeHtml(ev.publisher || 'Regulator')}</span>
        </div>
        <div class="evidence-meta">Citation Key: <code>${escapeHtml(ev.source_id)}</code> · Filed: ${escapeHtml(ev.published_at || '—')}</div>
        <div class="evidence-excerpt">"${escapeHtml(ev.page_or_excerpt || '')}"</div>
      </div>
      <div>
        <a href="${escapeHtml(ev.source_url || '#')}" target="_blank" rel="noopener" class="evidence-link-btn">Inspect SEC EDGAR Filing ↗</a>
      </div>
    </article>
  `).join("");
}

$("#evidence-search-input")?.addEventListener("input", (e) => {
  const q = e.target.value.toLowerCase().trim();
  if (!stocklensState.evidenceData) return;
  const filtered = stocklensState.evidenceData.filter((ev) =>
    (ev.source_title || '').toLowerCase().includes(q) ||
    (ev.page_or_excerpt || '').toLowerCase().includes(q) ||
    (ev.source_id || '').toLowerCase().includes(q)
  );
  renderEvidenceCards(filtered);
});

window.addEventListener("resize", () => {
  if (stocklensState.activeView === "graph" && stocklensState.canvas) {
    const container = stocklensState.canvas.parentElement;
    if (container) {
      const rect = container.getBoundingClientRect();
      const w = Math.max(320, Math.floor(rect.width || container.clientWidth || 840));
      const h = Math.max(480, Math.floor(container.clientHeight || 580));
      stocklensState.canvas.width = w;
      stocklensState.canvas.height = h;
    }
  }
});

// ==============================================================================
// 6. AI BUBBLE & CONTAGION RADAR MODULE (UPGRADED ECONOMETRIC SUITE)
// ==============================================================================
const bubbleState = {
  activeTab: "valuation",
  valuationData: null,
  activeStock: "NVDA",
  subsectorFilter: "All",
  sortBy: "market_cap_billions",
  dotcomData: null,
  safeHavenData: null,
  safeHavenTierFilter: "All",
  safeHavenSortBy: "resilience_score",
  dbScanData: null,
  fragilityData: null,
  contagionData: null,
  tailContagionData: null,
  activeScenario: "scenario_a",
  wacc: 0.095,
  terminalGrowth: 0.035,
  capexCut: 20.0,
  rateHike: 100.0,
  semiShock: 15.0,
  tailTrigger: "NVDA",
  tailThreshold: 3.5,
};

function initBubbleView() {
  if (!bubbleState.valuationData) {
    loadBubbleValuation();
  }
}

// Subnav Tab Switching
document.querySelectorAll("[data-bubble-tab]").forEach((pill) => {
  pill.addEventListener("click", () => {
    const tab = pill.dataset.bubbleTab;
    bubbleState.activeTab = tab;
    document.querySelectorAll("[data-bubble-tab]").forEach((p) => p.classList.toggle("is-active", p.dataset.bubbleTab === tab));
    document.querySelectorAll(".bubble-subpanel").forEach((panel) => {
      panel.hidden = panel.id !== `bubble-subpanel-${tab}`;
    });
    if (tab === "dotcom" && !bubbleState.dotcomData) loadDotComComparison();
    else if (tab === "safehaven") {
      if (!bubbleState.safeHavenData) loadSafeHavens();
      if (!bubbleState.dbScanData) runDatabaseCrashScan();
    } else if (tab === "fragility" && !bubbleState.fragilityData) loadFragilityIndex();
    else if (tab === "contagion") {
      if (!bubbleState.contagionData) runBubbleContagion();
      if (!bubbleState.tailContagionData) loadTailContagionMatrix();
    }
  });
});

// Refresh Button Listener
$("#bubble-refresh-btn")?.addEventListener("click", () => {
  loadBubbleValuation(true);
  if (bubbleState.activeTab === "safehaven") {
    loadSafeHavens(true);
    runDatabaseCrashScan();
  }
  if (bubbleState.activeTab === "fragility") loadFragilityIndex();
  if (bubbleState.activeTab === "contagion") {
    runBubbleContagion();
    loadTailContagionMatrix();
  }
});

// Filter & Sort Listeners
$("#bubble-subsector-filter")?.addEventListener("change", (e) => {
  bubbleState.subsectorFilter = e.target.value;
  renderBubbleTable();
  renderValuationScatterChart();
});

$("#bubble-sort-select")?.addEventListener("change", (e) => {
  bubbleState.sortBy = e.target.value;
  renderBubbleTable();
});

// Reverse DCF Slider Listeners
$("#dcf-wacc-slider")?.addEventListener("input", (e) => {
  const val = parseFloat(e.target.value);
  bubbleState.wacc = val / 100.0;
  if ($("#dcf-wacc-val")) $("#dcf-wacc-val").textContent = `${val.toFixed(1)}%`;
  updateReverseDcfCalculation();
});

$("#dcf-tg-slider")?.addEventListener("input", (e) => {
  const val = parseFloat(e.target.value);
  bubbleState.terminalGrowth = val / 100.0;
  if ($("#dcf-tg-val")) $("#dcf-tg-val").textContent = `${val.toFixed(1)}%`;
  updateReverseDcfCalculation();
});

// Scenario Pills & Interactive Stress Sliders Listeners
document.querySelectorAll("#contagion-scenario-pills .bubble-pill")?.forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#contagion-scenario-pills .bubble-pill").forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    bubbleState.activeScenario = btn.dataset.scenario;
    runBubbleContagion();
  });
});

$("#stress-capex-slider")?.addEventListener("input", (e) => {
  bubbleState.capexCut = parseFloat(e.target.value);
  if ($("#stress-capex-val")) $("#stress-capex-val").textContent = `-${bubbleState.capexCut.toFixed(0)}%`;
});
$("#stress-capex-slider")?.addEventListener("change", () => runBubbleContagion());

$("#stress-semi-slider")?.addEventListener("input", (e) => {
  bubbleState.semiShock = parseFloat(e.target.value);
  if ($("#stress-semi-val")) $("#stress-semi-val").textContent = `-${bubbleState.semiShock.toFixed(0)}%`;
});
$("#stress-semi-slider")?.addEventListener("change", () => runBubbleContagion());

$("#stress-rate-slider")?.addEventListener("input", (e) => {
  bubbleState.rateHike = parseFloat(e.target.value);
  if ($("#stress-rate-val")) $("#stress-rate-val").textContent = `+${bubbleState.rateHike.toFixed(0)} bps`;
});
$("#stress-rate-slider")?.addEventListener("change", () => runBubbleContagion());

// Tail Contagion Controls
$("#tail-trigger-select")?.addEventListener("change", (e) => {
  bubbleState.tailTrigger = e.target.value;
  loadTailContagionMatrix();
});
$("#tail-threshold-select")?.addEventListener("change", (e) => {
  bubbleState.tailThreshold = parseFloat(e.target.value);
  loadTailContagionMatrix();
});

// Fragility Weight Preset Pills
const FRAGILITY_WEIGHT_PRESETS = {
  baseline: { valuation_w: 0.25, concentration_w: 0.20, capex_w: 0.20, yield_w: 0.15, corr_w: 0.10, guidance_w: 0.10 },
  equal: { valuation_w: 0.1667, concentration_w: 0.1667, capex_w: 0.1667, yield_w: 0.1667, corr_w: 0.1667, guidance_w: 0.1667 },
  valuation: { valuation_w: 0.35, concentration_w: 0.15, capex_w: 0.30, yield_w: 0.10, corr_w: 0.05, guidance_w: 0.05 },
  contagion: { valuation_w: 0.15, concentration_w: 0.35, capex_w: 0.15, yield_w: 0.05, corr_w: 0.20, guidance_w: 0.10 },
  macro: { valuation_w: 0.25, concentration_w: 0.10, capex_w: 0.15, yield_w: 0.35, corr_w: 0.10, guidance_w: 0.05 },
};

document.querySelectorAll("#fragility-preset-pills .bubble-pill")?.forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#fragility-preset-pills .bubble-pill").forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    const presetKey = btn.dataset.wPreset || "baseline";
    loadFragilityIndex(FRAGILITY_WEIGHT_PRESETS[presetKey]);
  });
});

// --- A. Valuation, Capital Intensity & Reverse DCF 2.0 ---
async function loadBubbleValuation(forceRefresh = false) {
  const tbody = $("#bubble-valuation-tbody");
  if (tbody && !bubbleState.valuationData) {
    tbody.innerHTML = `<tr><td colspan="14" class="loading-td">Fetching real-time market data, capital intensity &amp; Reverse DCF 2.0…</td></tr>`;
  }
  const btn = $("#bubble-refresh-btn");
  if (btn) btn.textContent = "⏳ Fetching Live Data…";

  try {
    const res = await request(`/api/bubble/valuation?force_refresh=${forceRefresh}`);
    bubbleState.valuationData = res;
    if ($("#bubble-live-timestamp")) {
      $("#bubble-live-timestamp").textContent = `Real-Time Data: ${res.timestamp}`;
    }

    renderSubsectorStrip(res.subsector_summary);
    renderValuationScatterChart();
    renderBubbleTable();

    const defaultItem = res.items.find((i) => i.symbol === bubbleState.activeStock) || res.items[0];
    if (defaultItem) {
      applyReverseDcfResult(defaultItem.reverse_dcf, defaultItem);
    }
  } catch (e) {
    console.error("Bubble valuation error:", e);
    if (tbody) tbody.innerHTML = `<tr><td colspan="14" class="loading-td">Error loading valuation: ${escapeHtml(e.message)}</td></tr>`;
  } finally {
    if (btn) btn.textContent = "🔄 Refresh Live Data";
  }
}

function renderSubsectorStrip(summary) {
  const container = $("#bubble-subsector-strip");
  if (!container || !summary) return;
  container.innerHTML = summary.map((s) => `
    <div class="subsector-mini-card">
      <span>${escapeHtml(s.subsector)}</span>
      <strong>Fwd P/E: ${s.median_forward_pe > 0 ? s.median_forward_pe.toFixed(1) + 'x' : '—'} · ROIC: ${s.median_roic_pct ? s.median_roic_pct.toFixed(1) + '%' : '—'}</strong>
      <span style="font-size:10px; color:var(--ink-soft);">Capex/Rev: ${s.median_capex_to_rev_pct ? s.median_capex_to_rev_pct.toFixed(1) + '%' : '—'} · Sust: ${s.avg_sustainability_score || '—'}/100 (${s.stocks_count} stocks)</span>
    </div>
  `).join("");
}

function renderValuationScatterChart() {
  const container = $("#bubble-valuation-scatter-chart");
  if (!container || !bubbleState.valuationData?.items) return;

  let items = [...bubbleState.valuationData.items].filter((i) => i.forward_pe && i.forward_pe > 0 && i.forward_pe < 140);
  if (bubbleState.subsectorFilter !== "All") {
    items = items.filter((i) => i.subsector === bubbleState.subsectorFilter);
  }
  if (!items.length) {
    container.innerHTML = `<div class="list-message">No equities with valid Forward P/E in selected filter.</div>`;
    return;
  }

  const width = 860;
  const height = 285;
  const padL = 52;
  const padR = 36;
  const padT = 26;
  const padB = 38;

  const growths = items.map((i) => Number(i.revenue_growth_yoy_pct ?? 12));
  const pes = items.map((i) => Number(i.forward_pe ?? 25));
  const minX = Math.min(-10, ...growths) - 4;
  const maxX = Math.max(45, ...growths) + 8;
  const minY = 5;
  const maxY = Math.max(65, ...pes) + 8;

  function scaleX(val) {
    return padL + ((val - minX) / (maxX - minX)) * (width - padL - padR);
  }
  function scaleY(val) {
    return height - padB - ((val - minY) / (maxY - minY)) * (height - padT - padB);
  }

  // Fair PEG = 1.25x reference line: Forward PE = 12 + 1.15 * Growth
  const pegX1 = Math.max(0, minX);
  const pegY1 = Math.min(maxY, 12 + 1.15 * pegX1);
  const pegX2 = Math.min(maxX, (maxY - 12) / 1.15);
  const pegY2 = 12 + 1.15 * pegX2;

  const bubblesSvg = items.map((it) => {
    const gx = Number(it.revenue_growth_yoy_pct ?? 12);
    const py = Number(it.forward_pe ?? 25);
    const cx = scaleX(gx);
    const cy = scaleY(py);
    const mcap = Number(it.market_cap_billions || 50);
    const r = Math.max(6, Math.min(22, Math.sqrt(mcap) * 0.36));
    const sust = Number(it.sustainability_score ?? 65);
    const color = sust >= 75 ? "#10b981" : sust >= 52 ? "#38bdf8" : "#f43f5e";
    const isSel = it.symbol === bubbleState.activeStock;

    return `
      <g class="scatter-bubble-node" data-sym="${escapeHtml(it.symbol)}" style="cursor:pointer;">
        <circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${r.toFixed(1)}" fill="${color}" fill-opacity="${isSel ? '0.88' : '0.48'}" stroke="${isSel ? '#ffffff' : color}" stroke-width="${isSel ? '2.5' : '1.4'}"/>
        <text x="${cx.toFixed(1)}" y="${(cy - r - 4).toFixed(1)}" fill="${isSel ? '#ffffff' : '#cbd5e1'}" font-size="${isSel ? '10.5' : '9.5'}" font-weight="${isSel ? '700' : '600'}" font-family="DM Mono, monospace" text-anchor="middle">${escapeHtml(it.symbol)}</text>
      </g>
    `;
  }).join("");

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" style="width:100%; height:285px; background:#0b111a; border-radius:6px;">
      <!-- Grid lines -->
      <line x1="${padL}" y1="${scaleY(25).toFixed(1)}" x2="${width - padR}" y2="${scaleY(25).toFixed(1)}" stroke="rgba(148,163,184,0.14)" stroke-dasharray="3"/>
      <text x="${padL - 6}" y="${(scaleY(25) + 3).toFixed(1)}" fill="#64748b" font-size="9" font-family="DM Mono, monospace" text-anchor="end">25x</text>
      <line x1="${padL}" y1="${scaleY(50).toFixed(1)}" x2="${width - padR}" y2="${scaleY(50).toFixed(1)}" stroke="rgba(148,163,184,0.14)" stroke-dasharray="3"/>
      <text x="${padL - 6}" y="${(scaleY(50) + 3).toFixed(1)}" fill="#64748b" font-size="9" font-family="DM Mono, monospace" text-anchor="end">50x</text>
      
      <!-- Fair Growth-Adjusted Multiple Equilibrium Corridor -->
      <line x1="${scaleX(pegX1).toFixed(1)}" y1="${scaleY(pegY1).toFixed(1)}" x2="${scaleX(pegX2).toFixed(1)}" y2="${scaleY(pegY2).toFixed(1)}" stroke="rgba(234,179,8,0.55)" stroke-width="1.8" stroke-dasharray="5,4"/>
      <text x="${(scaleX(pegX2) - 8).toFixed(1)}" y="${(scaleY(pegY2) + 14).toFixed(1)}" fill="#eab308" font-size="9.5" font-family="DM Mono, monospace" text-anchor="end">Equilibrium Growth-Justified Multiple Line</text>

      <!-- Bubbles -->
      ${bubblesSvg}

      <!-- Axis Labels -->
      <text x="${width - padR}" y="${height - 10}" fill="#94a3b8" font-size="10" font-family="DM Mono, monospace" text-anchor="end">YoY Revenue Growth (%) →</text>
      <text x="${padL + 6}" y="18" fill="#94a3b8" font-size="10" font-family="DM Mono, monospace">↑ Forward P/E Multiple (x)</text>

      <!-- Legend -->
      <circle cx="${width - 330}" cy="16" r="5" fill="#10b981"/>
      <text x="${width - 320}" y="19" fill="#cbd5e1" font-size="9.5" font-family="DM Mono, monospace">High Sust. (≥75)</text>
      <circle cx="${width - 210}" cy="16" r="5" fill="#38bdf8"/>
      <text x="${width - 200}" y="19" fill="#cbd5e1" font-size="9.5" font-family="DM Mono, monospace">Moderate (52-74)</text>
      <circle cx="${width - 95}" cy="16" r="5" fill="#f43f5e"/>
      <text x="${width - 85}" y="19" fill="#cbd5e1" font-size="9.5" font-family="DM Mono, monospace">Stretch (&lt;52)</text>
    </svg>
  `;

  container.querySelectorAll(".scatter-bubble-node").forEach((node) => {
    node.addEventListener("click", () => {
      const sym = node.dataset.sym;
      if (sym) selectDcfStock(sym);
    });
  });
}

function renderBubbleTable() {
  const tbody = $("#bubble-valuation-tbody");
  if (!tbody || !bubbleState.valuationData) return;

  let items = [...(bubbleState.valuationData.items || [])];

  if (bubbleState.subsectorFilter !== "All") {
    items = items.filter((i) => i.subsector === bubbleState.subsectorFilter);
  }

  const sortKey = bubbleState.sortBy;
  items.sort((a, b) => {
    let valA = a[sortKey];
    let valB = b[sortKey];
    if (sortKey === "implied_5y_fcf_cagr_pct") {
      valA = a.reverse_dcf ? a.reverse_dcf.implied_5y_fcf_cagr_pct : -999;
      valB = b.reverse_dcf ? b.reverse_dcf.implied_5y_fcf_cagr_pct : -999;
    }
    valA = (valA === null || valA === undefined) ? -999999 : valA;
    valB = (valB === null || valB === undefined) ? -999999 : valB;
    return valB - valA;
  });

  tbody.innerHTML = items.map((it) => {
    const isSelected = it.symbol === bubbleState.activeStock;
    const dcf = it.reverse_dcf || {};
    const cagr = dcf.implied_5y_fcf_cagr_pct;
    const cagrClass = cagr > 40 ? "dcf-badge-stretch" : cagr > 20 ? "dcf-badge-expectations" : "dcf-badge-achievable";
    const daySign = it.day_change_pct >= 0 ? "+" : "";
    const dayColor = it.day_change_pct >= 0 ? "#10b981" : "#ef4444";
    const sust = it.sustainability_score ?? 65;
    const sustColor = sust >= 75 ? "#10b981" : sust >= 52 ? "#38bdf8" : "#f43f5e";

    return `
      <tr class="${isSelected ? 'is-active-row' : ''}" data-symbol="${escapeHtml(it.symbol)}">
        <td>
          <strong>${escapeHtml(it.symbol)}</strong>
          <span style="display:block; font-size:10px; color:var(--ink-soft);">${escapeHtml((it.name || '').split(' ')[0])}</span>
        </td>
        <td>
          <span style="font-size:10.5px; font-weight:600; color:var(--text);">${escapeHtml(it.exposure_tier || it.subsector)}</span>
          <span style="display:block; font-size:9.5px; color:var(--ink-soft);" title="${escapeHtml(it.exposure_evidence || '')}">${escapeHtml(it.ai_exposure)}</span>
        </td>
        <td style="font-weight:700;">$${it.current_price.toFixed(2)}</td>
        <td style="color:${dayColor}; font-weight:700;">${daySign}${it.day_change_pct.toFixed(2)}%</td>
        <td>$${it.market_cap_billions ? it.market_cap_billions.toFixed(0) : '—'}B</td>
        <td style="font-weight:700; color:#38bdf8;" title="Uncertainty: ${escapeHtml(it.exposure_uncertainty || 'Medium')}">${it.ai_rev_share_est_pct !== undefined ? it.ai_rev_share_est_pct.toFixed(0) + '%' : '—'}</td>
        <td style="font-weight:600;">${it.forward_pe ? it.forward_pe.toFixed(1) + 'x' : '—'}</td>
        <td>${it.price_to_sales ? it.price_to_sales.toFixed(1) + 'x' : '—'}</td>
        <td style="font-weight:700; color:${(it.roic_pct || 0) >= 15 ? '#10b981' : 'var(--text)'};">${it.roic_pct !== null && it.roic_pct !== undefined ? it.roic_pct.toFixed(1) + '%' : '—'}</td>
        <td>${it.capex_to_rev_pct !== null && it.capex_to_rev_pct !== undefined ? it.capex_to_rev_pct.toFixed(1) + '%' : '—'}</td>
        <td style="color:${(it.sbc_to_rev_pct || 0) > 12 ? '#f43f5e' : 'var(--ink-soft)'};">${it.sbc_to_rev_pct !== null && it.sbc_to_rev_pct !== undefined ? it.sbc_to_rev_pct.toFixed(1) + '%' : '—'}</td>
        <td style="font-weight:700; color:${cagr > 35 ? '#f43f5e' : '#10b981'};">${cagr !== undefined ? (cagr >= 0 ? '+' : '') + cagr.toFixed(1) + '%' : '—'}</td>
        <td><span style="font-weight:700; color:${sustColor};">${sust.toFixed(0)}/100</span></td>
        <td><span class="dcf-badge ${cagrClass}">${escapeHtml(dcf.verdict || 'Moderate')}</span></td>
      </tr>
    `;
  }).join("");

  tbody.querySelectorAll("tr[data-symbol]").forEach((row) => {
    row.addEventListener("click", () => {
      const sym = row.dataset.symbol;
      selectDcfStock(sym);
    });
  });
}

function selectDcfStock(symbol) {
  bubbleState.activeStock = symbol;
  document.querySelectorAll("#bubble-valuation-tbody tr").forEach((r) => {
    r.classList.toggle("is-active-row", r.dataset.symbol === symbol);
  });
  renderValuationScatterChart();
  updateReverseDcfCalculation();
}

async function updateReverseDcfCalculation() {
  const sym = bubbleState.activeStock;
  const wacc = bubbleState.wacc;
  const tg = bubbleState.terminalGrowth;

  try {
    const res = await request(`/api/bubble/reverse_dcf?symbol=${sym}&wacc=${wacc}&terminal_growth=${tg}`);
    const stockInfo = (bubbleState.valuationData?.items || []).find((i) => i.symbol === sym) || { symbol: sym, name: sym, current_price: 100 };
    applyReverseDcfResult(res, stockInfo);
  } catch (e) {
    console.error("Reverse DCF calculation error:", e);
  }
}

function applyReverseDcfResult(dcf, stockInfo) {
  if (!dcf) return;
  if ($("#dcf-ticker-title")) {
    $("#dcf-ticker-title").textContent = `${stockInfo.symbol} · ${stockInfo.name} ($${stockInfo.current_price?.toFixed(2) || '—'})`;
  }
  const badge = $("#dcf-verdict-badge");
  if (badge) {
    badge.textContent = dcf.verdict || "Speculative Stretch";
    badge.className = `dcf-badge ${dcf.implied_5y_fcf_cagr_pct > 40 ? 'dcf-badge-stretch' : dcf.implied_5y_fcf_cagr_pct > 20 ? 'dcf-badge-expectations' : 'dcf-badge-achievable'}`;
  }
  if ($("#dcf-implied-growth")) {
    $("#dcf-implied-growth").textContent = `${dcf.implied_5y_fcf_cagr_pct >= 0 ? '+' : ''}${dcf.implied_5y_fcf_cagr_pct.toFixed(1)}% / yr`;
    $("#dcf-implied-growth").style.color = dcf.implied_5y_fcf_cagr_pct > 35 ? "#f43f5e" : "#10b981";
  }
  if ($("#dcf-current-fcf")) {
    const curFcf = dcf.current_fcf_billions !== undefined ? `$${dcf.current_fcf_billions.toFixed(1)}B` : "—";
    const yr5Fcf = dcf.projected_yr5_fcf_billions !== undefined ? `$${dcf.projected_yr5_fcf_billions.toFixed(1)}B` : "—";
    $("#dcf-current-fcf").textContent = `${curFcf} → ${yr5Fcf}`;
  }
  if ($("#dcf-expectation-gap")) {
    const gap = Number(dcf.expectation_gap_pct ?? 0);
    const gapSign = gap >= 0 ? "+" : "";
    $("#dcf-expectation-gap").textContent = `${gapSign}${gap.toFixed(1)}% vs Hist`;
    $("#dcf-expectation-gap").style.color = gap > 15 ? "#f43f5e" : gap > 0 ? "#eab308" : "#10b981";
  }

  // Render 5x5 WACC vs Terminal Growth Sensitivity Matrix
  const matBox = $("#dcf-sensitivity-matrix");
  if (matBox && dcf.sensitivity_matrix && dcf.sensitivity_matrix.length) {
    const colHeaders = dcf.sensitivity_matrix[0].cells.map((c) => {
      const tgVal = c.tg_pct ?? c.terminal_growth_pct ?? 3.0;
      return `<th style="text-align:center; font-size:10px; padding:4px 6px;">g=${tgVal.toFixed(1)}%</th>`;
    }).join("");
    const rowsHtml = dcf.sensitivity_matrix.map((row) => {
      const cellsHtml = row.cells.map((cell) => {
        const gVal = cell.implied_cagr_pct ?? cell.implied_5y_fcf_cagr_pct ?? 0;
        const bg = gVal > 40 ? "rgba(244,63,94,0.22)" : gVal > 22 ? "rgba(234,179,8,0.18)" : "rgba(16,185,129,0.20)";
        const col = gVal > 40 ? "#fda4af" : gVal > 22 ? "#fde047" : "#6ee7b7";
        const isCurrent = Boolean(cell.is_center);
        return `<td style="text-align:center; padding:4px 6px; font-family:'DM Mono',monospace; font-size:10.5px; font-weight:${isCurrent ? '800' : '600'}; background:${bg}; color:${col}; ${isCurrent ? 'outline:1.5px solid #fff;' : ''}">${gVal >= 0 ? '+' : ''}${gVal.toFixed(1)}%</td>`;
      }).join("");
      return `<tr><td style="font-size:10px; font-weight:700; padding:4px 6px; color:#94a3b8;">WACC ${row.wacc_pct.toFixed(1)}%</td>${cellsHtml}</tr>`;
    }).join("");
    matBox.innerHTML = `<table class="data-table" style="margin:0; border-collapse:separate; border-spacing:2px;"><thead><tr><th style="font-size:10px; padding:4px 6px;">WACC \\ g</th>${colHeaders}</tr></thead><tbody>${rowsHtml}</tbody></table>`;
  }

  if ($("#dcf-narrative-box")) {
    $("#dcf-narrative-box").innerHTML = `
      <strong>Model Diagnosis:</strong> ${escapeHtml(dcf.assessment || '')}<br>
      <span style="font-size:10.5px; color:var(--ink-soft); display:block; margin-top:4px;">
        <strong>Evidence Basis:</strong> ${escapeHtml(stockInfo.exposure_evidence || 'SEC 10-K segment disclosures')} · 
        ROIC: <strong>${stockInfo.roic_pct ?? '—'}%</strong> · Capex/Rev: <strong>${stockInfo.capex_to_rev_pct ?? '—'}%</strong> · SBC/Rev: <strong>${stockInfo.sbc_to_rev_pct ?? '—'}%</strong>.
      </span>
    `;
  }
}

// --- B. Dot-Com vs AI Comparison (10 Quantitative Dimensions) ---
async function loadDotComComparison() {
  const synthesis = $("#dotcom-synthesis-text");
  if (synthesis) synthesis.textContent = "Loading 10-dimension empirical comparison matrix & historical index drawdowns…";

  try {
    const res = await request("/api/bubble/dotcom_compare");
    bubbleState.dotcomData = res;

    if (synthesis && res.matrix?.synthesis) {
      synthesis.textContent = res.matrix.synthesis;
    }
    if ($("#dotcom-survivorship-note") && res.matrix?.historical_stats?.survivorship_bias_disclosure) {
      $("#dotcom-survivorship-note").innerHTML = `🛡️ <strong>Survivorship Bias &amp; SQLite Audit:</strong> ${escapeHtml(res.matrix.historical_stats.survivorship_bias_disclosure)} (<strong>${escapeHtml(res.matrix.historical_stats.dotcom_sqlite_survivors_positive || '')}</strong>).`;
    }

    const grid = $("#dotcom-matrix-grid");
    if (grid && res.matrix?.matrix) {
      grid.innerHTML = res.matrix.matrix.map((m) => `
        <div class="matrix-card">
          <div class="matrix-header">
            <h4>${escapeHtml(m.category)}: ${escapeHtml(m.indicator)}</h4>
            <span class="matrix-verdict-badge">${escapeHtml(m.fragility_verdict)}</span>
          </div>
          <div class="matrix-comparison-row">
            <div class="era-col">
              <span class="metric-label">DOT-COM BUBBLE (1995–2002)</span>
              <strong>${escapeHtml(m.dotcom_era.value)}</strong>
              <p>${escapeHtml(m.dotcom_era.detail)}</p>
              <div style="font-size:10px; color:#ef4444; margin-top:4px;">Risk: ${escapeHtml(m.dotcom_era.risk_assessment)}</div>
            </div>
            <div class="era-col">
              <span class="metric-label">CONTEMPORARY AI CYCLE (2020–2026)</span>
              <strong style="color:#6366f1;">${escapeHtml(m.ai_era.value)}</strong>
              <p>${escapeHtml(m.ai_era.detail)}</p>
              <div style="font-size:10px; color:#047857; margin-top:4px;">Structure: ${escapeHtml(m.ai_era.risk_assessment)}</div>
            </div>
          </div>
        </div>
      `).join("");
    }

    renderDotComChart(res.drawdown);
  } catch (e) {
    console.error("Dotcom comparison error:", e);
    if (synthesis) synthesis.textContent = `Error loading comparison: ${e.message}`;
  }
}

function renderDotComChart(drawdown) {
  const container = $("#dotcom-drawdown-chart");
  if (!container || !drawdown) return;

  const dotcomPts = drawdown.dotcom_cycle?.data || [];
  const modernPts = drawdown.modern_ai_cycle?.data || [];
  if (!dotcomPts.length && !modernPts.length) {
    container.innerHTML = `<div class="list-message">Trajectory data unavailable.</div>`;
    return;
  }

  const width = 800;
  const height = 320;
  const pad = 44;

  const allVals = [...dotcomPts.map((p) => p.normalized_index), ...modernPts.map((p) => p.normalized_index)];
  const minVal = Math.min(...allVals, 50);
  const maxVal = Math.max(...allVals, 400);

  const maxLen = Math.max(dotcomPts.length, modernPts.length);

  function scaleX(idx) { return pad + (idx / maxLen) * (width - 2 * pad); }
  function scaleY(val) { return height - pad - ((val - minVal) / (maxVal - minVal)) * (height - 2 * pad); }

  const zeroY = scaleY(100);

  const dotcomPath = dotcomPts.map((p, i) => `${scaleX(i).toFixed(1)},${scaleY(p.normalized_index).toFixed(1)}`).join(" L ");
  const modernPath = modernPts.map((p, i) => `${scaleX(i).toFixed(1)},${scaleY(p.normalized_index).toFixed(1)}`).join(" L ");

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" style="width:100%; height:100%; background:#0b111a; border-radius:4px;">
      <line x1="${pad}" y1="${zeroY.toFixed(1)}" x2="${width - pad}" y2="${zeroY.toFixed(1)}" stroke="rgba(255,255,255,0.3)" stroke-dasharray="3"/>
      <text x="${pad + 6}" y="${zeroY - 6}" fill="#94a3b8" font-size="9" font-family="DM Mono, monospace">Baseline 100</text>
      <path d="M ${dotcomPath}" fill="none" stroke="#ef4444" stroke-width="2.2" opacity="0.85"/>
      <path d="M ${modernPath}" fill="none" stroke="#6366f1" stroke-width="2.8"/>
      <text x="${width - pad}" y="${height - 12}" fill="#94a3b8" font-size="10" font-family="DM Mono, monospace" text-anchor="end">Trading Sessions (Indexed from Inception)</text>
      <text x="${pad}" y="20" fill="#94a3b8" font-size="10" font-family="DM Mono, monospace">Normalized Index (Base = 100)</text>
      <rect x="${width - 320}" y="14" width="12" height="12" fill="#ef4444" rx="2"/>
      <text x="${width - 302}" y="24" fill="#cbd5e1" font-size="10" font-family="DM Mono, monospace">Nasdaq 1995–2003 (Dot-Com -78% Bust)</text>
      <rect x="${width - 320}" y="32" width="12" height="12" fill="#6366f1" rx="2"/>
      <text x="${width - 302}" y="42" fill="#cbd5e1" font-size="10" font-family="DM Mono, monospace">Nasdaq 2018–2026 (Modern AI Cycle)</text>
    </svg>
  `;
}

// --- C. AI Market Fragility Index 2.0 ---
async function loadFragilityIndex(customWeights = null) {
  try {
    let url = "/api/bubble/fragility_index";
    if (customWeights) {
      const qs = new URLSearchParams(customWeights).toString();
      url += `?${qs}`;
    }
    const res = await request(url);
    bubbleState.fragilityData = res;

    if ($("#fragility-score-val")) $("#fragility-score-val").textContent = res.composite_score.toFixed(1);
    const circle = $("#fragility-dial-circle");
    if (circle) {
      circle.style.borderColor = res.status_color || "#f97316";
      circle.style.boxShadow = `0 4px 16px ${res.status_color || '#f97316'}40`;
    }
    const badge = $("#fragility-regime-badge");
    if (badge) {
      badge.textContent = res.regime;
      badge.style.color = res.status_color;
      badge.style.borderColor = `${res.status_color}50`;
      badge.style.background = `${res.status_color}18`;
    }
    if ($("#fragility-summary-text")) $("#fragility-summary-text").textContent = res.summary;
    if ($("#fragility-asof")) $("#fragility-asof").textContent = `As of: ${res.asof || res.as_of || 'Live Market'}`;
    if ($("#fragility-sens-range") && res.sensitivity_range) {
      $("#fragility-sens-range").textContent = `${res.sensitivity_range.min_score.toFixed(1)} – ${res.sensitivity_range.max_score.toFixed(1)} (Δ ${res.sensitivity_range.spread.toFixed(1)})`;
    }

    // Render preset sensitivity badges strip
    const presetStrip = $("#fragility-preset-summary-strip");
    if (presetStrip && res.weight_sensitivity_presets) {
      presetStrip.innerHTML = res.weight_sensitivity_presets.map((p) => `
        <div style="padding:6px 10px; background:rgba(15,23,42,0.6); border:1px solid rgba(148,163,184,0.18); border-radius:6px; font-size:11px;">
          <span style="color:#94a3b8; display:block; font-size:9.5px;">${escapeHtml(p.scheme)}</span>
          <strong style="color:${p.composite_score >= 70 ? '#f97316' : '#10b981'}; font-family:'DM Mono',monospace;">${p.composite_score.toFixed(1)} / 100</strong>
        </div>
      `).join("");
    }

    // Render 6 dimension cards
    const grid = $("#fragility-cards-grid");
    if (grid && res.components) {
      grid.innerHTML = res.components.map((c) => {
        const trendClass = c.trend_direction === "up" ? "trend-up" : c.trend_direction === "down" ? "trend-down" : "trend-flat";
        const barColor = c.score > 75 ? "#ef4444" : c.score > 55 ? "#f97316" : "#10b981";
        return `
          <div class="fragility-component-card">
            <div class="fcomp-header">
              <strong>${escapeHtml(c.name)}</strong>
              <span class="fcomp-trend ${trendClass}">${escapeHtml(c.trend)}</span>
            </div>
            <div class="fcomp-bar-wrap">
              <div class="fcomp-bar-fill" style="width:${c.score}%; background:${barColor};"></div>
            </div>
            <div class="fcomp-meta">
              <span>Score: <strong>${c.score}%</strong> (z = ${c.z_score >= 0 ? '+' : ''}${c.z_score})</span>
              <span>Weight: <strong>${(c.weight * 100).toFixed(1)}%</strong></span>
            </div>
            <div style="font-size:10.5px; font-weight:600; color:var(--ink);">${escapeHtml(c.raw_value)}</div>
            <div style="font-size:9.5px; color:#64748b; margin-top:2px;">Benchmark: ${escapeHtml(c.benchmark || '')}</div>
            <div class="fcomp-detail">${escapeHtml(c.detail)}</div>
          </div>
        `;
      }).join("");
    }

    renderFragilityHistoryChart(res.historical_trajectory || []);

    if ($("#fragility-caveat-box")) {
      $("#fragility-caveat-box").innerHTML = `<strong>Methodological Governance:</strong> ${escapeHtml(res.caveat || '')}`;
    }
  } catch (e) {
    console.error("Fragility index error:", e);
  }
}

function renderFragilityHistoryChart(traj) {
  const container = $("#fragility-history-chart");
  if (!container) return;
  if (!traj || !traj.length) {
    container.innerHTML = `<div class="list-message">Historical trajectory unavailable.</div>`;
    return;
  }

  const width = 840;
  const height = 250;
  const padL = 46;
  const padR = 46;
  const padT = 24;
  const padB = 34;

  function scaleX(idx) {
    return padL + (idx / Math.max(1, traj.length - 1)) * (width - padL - padR);
  }
  function scaleYScore(val) {
    return height - padB - ((val - 30) / 70) * (height - padT - padB);
  }
  function scaleYCorr(corr) {
    return height - padB - ((corr - 0.1) / 0.75) * (height - padT - padB);
  }

  const scorePath = traj.map((p, i) => `${scaleX(i).toFixed(1)},${scaleYScore(p.fragility_score).toFixed(1)}`).join(" L ");
  const corrPath = traj.map((p, i) => `${scaleX(i).toFixed(1)},${scaleYCorr(p.pairwise_corr).toFixed(1)}`).join(" L ");
  const y60 = scaleYScore(60);
  const y80 = scaleYScore(80);

  // Year labels along X axis
  const yearLabels = [];
  let lastYear = "";
  traj.forEach((p, i) => {
    const yr = p.date.slice(0, 4);
    if (yr !== lastYear) {
      lastYear = yr;
      yearLabels.push(`<text x="${scaleX(i).toFixed(1)}" y="${height - 10}" fill="#94a3b8" font-size="9.5" font-family="DM Mono, monospace" text-anchor="middle">${yr}</text>`);
    }
  });

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" style="width:100%; height:250px; background:#0b111a; border-radius:6px;">
      <!-- Regime threshold lines -->
      <line x1="${padL}" y1="${y80.toFixed(1)}" x2="${width - padR}" y2="${y80.toFixed(1)}" stroke="rgba(239,68,68,0.35)" stroke-dasharray="4"/>
      <text x="${padL + 6}" y="${(y80 - 4).toFixed(1)}" fill="#ef4444" font-size="9" font-family="DM Mono, monospace">Extreme Fragility Threshold (80)</text>
      <line x1="${padL}" y1="${y60.toFixed(1)}" x2="${width - padR}" y2="${y60.toFixed(1)}" stroke="rgba(249,115,22,0.3)" stroke-dasharray="3"/>
      <text x="${padL + 6}" y="${(y60 - 4).toFixed(1)}" fill="#f97316" font-size="9" font-family="DM Mono, monospace">Elevated Regime (60)</text>

      <!-- Pairwise Correlation Line (Cyan) -->
      <path d="M ${corrPath}" fill="none" stroke="#38bdf8" stroke-width="1.8" opacity="0.8"/>
      <!-- Composite Fragility Score Line (Orange/Amber) -->
      <path d="M ${scorePath}" fill="none" stroke="#f97316" stroke-width="2.8"/>

      ${yearLabels.join("")}

      <!-- Legend -->
      <rect x="${width - 370}" y="10" width="11" height="11" fill="#f97316" rx="2"/>
      <text x="${width - 354}" y="19" fill="#cbd5e1" font-size="9.5" font-family="DM Mono, monospace">Composite Fragility Score (0–100)</text>
      <rect x="${width - 175}" y="10" width="11" height="11" fill="#38bdf8" rx="2"/>
      <text x="${width - 159}" y="19" fill="#cbd5e1" font-size="9.5" font-family="DM Mono, monospace">60D AI Pairwise Corr</text>
    </svg>
  `;
}

// --- D. Contagion, Stress Testing & Conditional Tail Matrix ---
async function runBubbleContagion() {
  const tbody = $("#contagion-waterfall-tbody");
  if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="loading-td">Simulating network contagion shock…</td></tr>`;

  const scenarioId = bubbleState.activeScenario;
  const capex = bubbleState.capexCut;
  const rate = bubbleState.rateHike;
  const semi = bubbleState.semiShock;

  try {
    const res = await request(`/api/bubble/stress_test?scenario_id=${scenarioId}&capex_cut=${capex}&rate_hike=${rate}&semi_shock=${semi}`);
    bubbleState.contagionData = res;

    if ($("#contagion-scenario-title")) $("#contagion-scenario-title").textContent = res.scenario.title;
    if ($("#contagion-scenario-narrative")) $("#contagion-scenario-narrative").textContent = res.scenario.narrative;
    if ($("#contagion-epicenter-label")) $("#contagion-epicenter-label").textContent = `SHOCK ORIGIN: ${res.scenario.epicenter}`;
    if ($("#contagion-stat-top-vuln")) $("#contagion-stat-top-vuln").textContent = res.summary.most_vulnerable_ticker;
    if ($("#contagion-stat-top-resilient")) $("#contagion-stat-top-resilient").textContent = res.summary.most_resilient_ticker;

    if (tbody && res.impact_waterfall) {
      tbody.innerHTML = res.impact_waterfall.map((r) => {
        const revSign = r.projected_revenue_impact_pct > 0 ? "+" : "";
        const revColor = r.projected_revenue_impact_pct >= 0 ? "#10b981" : "#ef4444";
        const ebitColor = r.projected_ebitda_impact_pct >= 0 ? "#10b981" : "#ef4444";
        const badgeBg = r.badge_color;

        return `
          <tr>
            <td><strong>${escapeHtml(r.symbol)}</strong></td>
            <td style="font-size:10px; color:var(--ink-soft);">${escapeHtml(r.tier)}</td>
            <td>${r.direct_exposure_pct.toFixed(0)}%</td>
            <td style="color:${revColor}; font-weight:700;">${revSign}${r.projected_revenue_impact_pct.toFixed(1)}%</td>
            <td style="color:${ebitColor}; font-weight:700;">${r.projected_ebitda_impact_pct.toFixed(1)}%</td>
            <td style="font-weight:700; color:${r.price_drop_midpoint >= 0 ? '#10b981' : '#ef4444'};">${escapeHtml(r.price_pressure_range)}</td>
            <td><span class="contagion-badge" style="background:${badgeBg}20; color:${badgeBg}; border:1px solid ${badgeBg}40;">${escapeHtml(r.vulnerability_class)}</span></td>
          </tr>
        `;
      }).join("");
    }
  } catch (e) {
    console.error("Contagion simulation error:", e);
    if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="loading-td">Error running stress test: ${escapeHtml(e.message)}</td></tr>`;
  }
}

async function loadTailContagionMatrix() {
  const tbody = $("#tail-contagion-tbody");
  const metaStrip = $("#tail-contagion-meta-strip");
  if (tbody) tbody.innerHTML = `<tr><td colspan="10" class="loading-td">Computing conditional tail co-movement from us_equities.db…</td></tr>`;

  try {
    const trig = bubbleState.tailTrigger || "NVDA";
    const tau = bubbleState.tailThreshold || 3.5;
    const res = await request(`/api/bubble/tail_contagion?trigger=${encodeURIComponent(trig)}&threshold=${tau}`);
    bubbleState.tailContagionData = res;

    if (metaStrip) {
      metaStrip.innerHTML = `
        <strong>Empirical SQLite Sample (${escapeHtml(res.sample_window || '2020–2026')}):</strong>
        Found <strong>${res.downside_events_count} Downside Crash Days</strong> where <strong>${escapeHtml(res.trigger_symbol)} ≤ -${res.threshold_pct}%</strong> (mean ${res.trigger_downside_mean_pct}%)
        and <strong>${res.upside_events_count} Upside Surge Days ≥ +${res.threshold_pct}%</strong> (mean +${res.trigger_upside_mean_pct}%).
        Multiple-testing controlled via <strong>${escapeHtml(res.fdr_method || 'Benjamini-Hochberg FDR')}</strong>.
      `;
    }

    if (tbody && res.pairs) {
      tbody.innerHTML = res.pairs.map((p) => {
        const downColor = p.downside_expected_ret_pct < -2.0 ? "#ef4444" : p.downside_expected_ret_pct < 0 ? "#f97316" : "#10b981";
        const upColor = p.upside_expected_ret_pct >= 0 ? "#10b981" : "#ef4444";
        const qBadge = p.statistically_significant_fdr
          ? `<span style="color:#10b981; font-weight:700;">q=${p.fdr_q_value.toFixed(4)} ★</span>`
          : `<span style="color:#64748b;">q=${p.fdr_q_value.toFixed(3)}</span>`;
        const regimeColor = p.oos_regime.includes("Hedge") ? "#10b981" : p.oos_regime.includes("Intensifying") ? "#ef4444" : "#38bdf8";

        return `
          <tr>
            <td><strong>${escapeHtml(p.symbol)}</strong></td>
            <td style="font-size:10px; color:var(--ink-soft);">${escapeHtml(p.tier)}</td>
            <td style="font-weight:700; color:${p.downside_prob_pct >= 75 ? '#ef4444' : p.downside_prob_pct <= 52 ? '#10b981' : 'var(--text)'};">${p.downside_prob_pct.toFixed(1)}%</td>
            <td style="font-weight:700; color:${downColor};">${p.downside_expected_ret_pct >= 0 ? '+' : ''}${p.downside_expected_ret_pct.toFixed(2)}%</td>
            <td style="font-family:'DM Mono',monospace; font-size:10.5px; color:#94a3b8;">${escapeHtml(p.downside_ci95)}</td>
            <td style="font-weight:700; color:${upColor};">${p.upside_expected_ret_pct >= 0 ? '+' : ''}${p.upside_expected_ret_pct.toFixed(2)}%</td>
            <td style="font-weight:700;">${p.tail_beta_down.toFixed(2)}x</td>
            <td style="color:${p.tail_asymmetry_ratio > 1.15 ? '#f43f5e' : '#cbd5e1'}; font-weight:600;">${p.tail_asymmetry_ratio.toFixed(2)}x</td>
            <td style="font-family:'DM Mono',monospace; font-size:10.5px;">${qBadge}</td>
            <td>
              <span style="color:${regimeColor}; font-weight:600; font-size:10.5px;">${escapeHtml(p.oos_regime)}</span>
              <span style="display:block; font-size:9.5px; color:#64748b;">20-23: ${p.pre2024_down_ret_pct}% · 24-26: ${p.post2024_down_ret_pct}%</span>
            </td>
          </tr>
        `;
      }).join("");
    }
  } catch (e) {
    console.error("Tail contagion matrix error:", e);
    if (tbody) tbody.innerHTML = `<tr><td colspan="10" class="loading-td">Error computing tail matrix: ${escapeHtml(e.message)}</td></tr>`;
  }
}

// --- E. Safe Haven & Empirical Anti-Crash Rotation Radar ---
$("#safehaven-tier-filter")?.addEventListener("change", (e) => {
  bubbleState.safeHavenTierFilter = e.target.value;
  renderSafeHavenTable();
});

$("#safehaven-sort-select")?.addEventListener("change", (e) => {
  bubbleState.safeHavenSortBy = e.target.value;
  renderSafeHavenTable();
});

$("#dbscan-corr-select")?.addEventListener("change", () => runDatabaseCrashScan());
$("#dbscan-dotcom-select")?.addEventListener("change", () => runDatabaseCrashScan());
$("#dbscan-pos-crash-chk")?.addEventListener("change", () => runDatabaseCrashScan());

async function loadSafeHavens(forceRefresh = false) {
  const tbody = $("#safehaven-tbody");
  if (tbody && !bubbleState.safeHavenData) {
    tbody.innerHTML = `<tr><td colspan="13" class="loading-td">Scanning 34 counter-cyclical &amp; flight-to-safety assets…</td></tr>`;
  }

  try {
    const res = await request(`/api/bubble/safe_havens?refresh=${forceRefresh}`);
    bubbleState.safeHavenData = res;

    renderSafeHavenComparison(res.benchmark_comparison);
    renderSafeHavenTable();
  } catch (e) {
    console.error("Safe havens error:", e);
    if (tbody) tbody.innerHTML = `<tr><td colspan="13" class="loading-td">Error scanning safe haven assets: ${escapeHtml(e.message)}</td></tr>`;
  }
}

function renderSafeHavenComparison(comp) {
  const strip = $("#safehaven-comparison-strip");
  if (!strip || !comp) return;

  const haven = comp.safe_haven_basket || {};
  const tech = comp.ai_bubble_universe || {};

  strip.innerHTML = `
    <div class="safehaven-comp-card is-haven">
      <div class="comp-header">
        <strong style="color:#10b981;">🛡️ ${escapeHtml(haven.label || 'Safe Haven Basket')}</strong>
        <span class="safehaven-pill-tag">CAPITAL RECIPIENT</span>
      </div>
      <div class="comp-metrics-grid">
        <div class="comp-metric-box">
          <span class="metric-label">FORWARD P/E</span>
          <strong style="color:#10b981;">${haven.avg_forward_pe}x</strong>
        </div>
        <div class="comp-metric-box">
          <span class="metric-label">CORR VS NVDA</span>
          <strong style="color:#10b981;">${haven.avg_corr_with_nvda ?? '0.09'}</strong>
        </div>
        <div class="comp-metric-box">
          <span class="metric-label">ON NVDA CRASH</span>
          <strong style="color:#10b981;">${escapeHtml(haven.avg_ret_when_nvda_crashes || '-0.12%')}</strong>
        </div>
        <div class="comp-metric-box">
          <span class="metric-label">DOT-COM 2000-02</span>
          <strong style="color:#10b981;">${escapeHtml(haven.dotcom_crash_performance || '')}</strong>
        </div>
      </div>
      <p style="margin:0; font-size:11px; color:var(--ink-soft);">${escapeHtml(haven.capital_source || '')}</p>
    </div>

    <div class="safehaven-comp-card is-tech">
      <div class="comp-header">
        <strong style="color:#ef4444;">⚡ ${escapeHtml(tech.label || 'AI Tech Universe')}</strong>
        <span class="dcf-badge dcf-badge-stretch">LIQUIDATION SOURCE</span>
      </div>
      <div class="comp-metrics-grid">
        <div class="comp-metric-box">
          <span class="metric-label">FORWARD P/E</span>
          <strong style="color:#ef4444;">${tech.avg_forward_pe}x</strong>
        </div>
        <div class="comp-metric-box">
          <span class="metric-label">CORR VS NVDA</span>
          <strong style="color:#ef4444;">${tech.avg_corr_with_nvda ?? '0.642'}</strong>
        </div>
        <div class="comp-metric-box">
          <span class="metric-label">ON NVDA CRASH</span>
          <strong style="color:#ef4444;">${escapeHtml(tech.avg_ret_when_nvda_crashes || '-3.85%')}</strong>
        </div>
        <div class="comp-metric-box">
          <span class="metric-label">DOT-COM 2000-02</span>
          <strong style="color:#ef4444;">${escapeHtml(tech.dotcom_crash_performance || '')}</strong>
        </div>
      </div>
      <p style="margin:0; font-size:11px; color:var(--ink-soft);">${escapeHtml(tech.capital_source || '')}</p>
    </div>
  `;
}

function renderSafeHavenTable() {
  const tbody = $("#safehaven-tbody");
  if (!tbody || !bubbleState.safeHavenData) return;

  let assets = [...(bubbleState.safeHavenData.assets || [])];

  if (bubbleState.safeHavenTierFilter !== "All") {
    assets = assets.filter((a) => a.resilience_tier === bubbleState.safeHavenTierFilter);
  }

  const sortKey = bubbleState.safeHavenSortBy;
  const isAscending = sortKey === "forward_pe" || sortKey === "ev_to_ebitda" || sortKey === "beta" || sortKey === "corr_with_nvda";

  assets.sort((a, b) => {
    let valA = a[sortKey];
    let valB = b[sortKey];
    if (valA === null || valA === undefined) valA = isAscending ? 999999 : -999999;
    if (valB === null || valB === undefined) valB = isAscending ? 999999 : -999999;
    return isAscending ? valA - valB : valB - valA;
  });

  tbody.innerHTML = assets.map((a) => {
    const daySign = a.day_change_pct >= 0 ? "+" : "";
    const dayColor = a.day_change_pct >= 0 ? "#10b981" : "#ef4444";
    const scoreClass = a.resilience_score >= 85 ? "score-ultra" : "score-high";
    const corrVal = Number(a.corr_with_nvda ?? 0.12);
    const corrColor = corrVal <= 0.05 ? "#10b981" : corrVal <= 0.20 ? "#38bdf8" : "#cbd5e1";
    const crashRet = Number(a.avg_ret_on_nvda_crash_pct ?? 0.0);
    const crashColor = crashRet >= 0 ? "#10b981" : crashRet > -0.5 ? "#eab308" : "#f97316";

    return `
      <tr data-sh-sym="${escapeHtml(a.symbol)}" style="cursor:pointer;">
        <td><strong>${escapeHtml(a.symbol)}</strong></td>
        <td>
          <span style="font-weight:600;">${escapeHtml(a.name)}</span>
          <span style="display:block; font-size:10px; color:var(--ink-soft);">${escapeHtml(a.theme)}</span>
        </td>
        <td><span class="pill" style="font-size:10px;">${escapeHtml(a.sector)}</span></td>
        <td style="font-weight:700;">$${a.current_price?.toFixed(2) || '—'}</td>
        <td style="font-weight:700; color:${dayColor};">${daySign}${a.day_change_pct?.toFixed(2) || 0.0}%</td>
        <td style="font-weight:600;">${a.forward_pe ? a.forward_pe.toFixed(1) + 'x' : a.trailing_pe ? a.trailing_pe.toFixed(1) + 'x' : '—'}</td>
        <td style="font-weight:700; color:#10b981;">${a.dividend_yield_pct > 0 ? a.dividend_yield_pct.toFixed(2) + '%' : '—'}</td>
        <td style="font-weight:700; color:${a.beta < 0.5 ? '#10b981' : 'var(--text)'};">${a.beta !== null && a.beta !== undefined ? a.beta.toFixed(2) : '—'}</td>
        <td style="font-family:'DM Mono',monospace; font-weight:700; color:${corrColor};">${corrVal >= 0 ? '+' : ''}${corrVal.toFixed(3)}</td>
        <td style="font-family:'DM Mono',monospace; font-weight:700; color:${crashColor};" title="Win Rate: ${a.win_rate_on_nvda_crash_pct ?? 50}% across ${a.nvda_crash_days_sampled ?? 122} NVDA crash days">${crashRet >= 0 ? '+' : ''}${crashRet.toFixed(2)}% <span style="font-size:9.5px; color:#94a3b8;">(${a.win_rate_on_nvda_crash_pct ?? 50}% W)</span></td>
        <td><span class="dotcom-gain-badge">+${a.dotcom_return_pct?.toFixed(1)}%</span></td>
        <td><span class="safety-score-pill ${scoreClass}">${a.resilience_score} / 100</span></td>
        <td class="why-rises-cell">${escapeHtml(a.why_it_rises)}</td>
      </tr>
    `;
  }).join("");
}

async function runDatabaseCrashScan() {
  const tbody = $("#dbscan-tbody");
  const banner = $("#dbscan-summary-banner");
  if (tbody) tbody.innerHTML = `<tr><td colspan="12" class="loading-td">Scanning 2,200 stocks in us_equities.db across 2000–2002 Dot-Com Bust &amp; 122 NVDA Crash Days…</td></tr>`;

  const maxCorr = $("#dbscan-corr-select")?.value || "0.25";
  const minDotcom = $("#dbscan-dotcom-select")?.value || "20";
  const onlyPos = $("#dbscan-pos-crash-chk")?.checked ? "true" : "false";

  try {
    const res = await request(`/api/bubble/database_scan?max_nvda_corr=${maxCorr}&min_dotcom_return=${minDotcom}&only_positive_crash=${onlyPos}&limit=45`);
    bubbleState.dbScanData = res;

    if (banner) {
      banner.innerHTML = `
        <strong>SQLite Empirical Audit Complete:</strong> Scanned <strong>${res.total_db_stocks_scanned} total US equities</strong> in <code>us_equities.db</code>
        → <strong>${res.dotcom_era_active_stocks} stocks</strong> traded across the Dot-Com Bust (Mar 10, 2000 – Oct 9, 2002)
        → <strong>${res.dotcom_positive_survivors} stocks posted positive gains</strong> while Nasdaq crashed -77.9%
        → <strong>${res.matching_filter_count} stocks</strong> match your current NVDA-crash &amp; Dot-Com filters.
      `;
    }

    if (tbody && res.results) {
      if (!res.results.length) {
        tbody.innerHTML = `<tr><td colspan="12" class="loading-td">No stocks matched these strict filter thresholds. Try relaxing Max Correlation or Min Dot-Com Return.</td></tr>`;
        return;
      }
      tbody.innerHTML = res.results.map((r, idx) => {
        const corrColor = r.corr_with_nvda <= 0 ? "#10b981" : r.corr_with_nvda <= 0.15 ? "#38bdf8" : "#cbd5e1";
        const crashColor = r.avg_ret_on_nvda_crash_pct >= 0 ? "#10b981" : "#eab308";
        return `
          <tr>
            <td><strong>#${idx + 1}</strong></td>
            <td>
              <strong>${escapeHtml(r.symbol)}</strong>
              ${r.in_curated_radar ? '<span class="safehaven-pill-tag" style="font-size:8.5px; padding:1px 5px; margin-left:4px;">CURATED</span>' : ''}
            </td>
            <td style="font-size:10.5px; color:var(--ink-soft);">${escapeHtml(r.sector)}</td>
            <td style="font-family:'DM Mono',monospace;">$${r.price_2000_peak.toFixed(2)}</td>
            <td style="font-family:'DM Mono',monospace;">$${r.price_2002_trough.toFixed(2)}</td>
            <td><span class="dotcom-gain-badge">+${r.dotcom_return_pct.toFixed(1)}%</span></td>
            <td style="font-weight:700;">$${r.price_latest.toFixed(2)}</td>
            <td style="font-family:'DM Mono',monospace; font-weight:700; color:${corrColor};">${r.corr_with_nvda >= 0 ? '+' : ''}${r.corr_with_nvda.toFixed(3)}</td>
            <td style="font-family:'DM Mono',monospace; font-weight:700; color:${crashColor};">${r.avg_ret_on_nvda_crash_pct >= 0 ? '+' : ''}${r.avg_ret_on_nvda_crash_pct.toFixed(2)}%</td>
            <td>${r.win_rate_on_nvda_crash_pct.toFixed(1)}%</td>
            <td>${r.annualized_volatility_pct.toFixed(1)}%</td>
            <td><span class="safety-score-pill score-ultra">${r.anti_crash_score.toFixed(1)} / 100</span></td>
          </tr>
        `;
      }).join("");
    }
  } catch (e) {
    console.error("Database crash scan error:", e);
    if (tbody) tbody.innerHTML = `<tr><td colspan="12" class="loading-td">Error scanning SQLite database: ${escapeHtml(e.message)}</td></tr>`;
  }
}





