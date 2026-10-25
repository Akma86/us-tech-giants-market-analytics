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
