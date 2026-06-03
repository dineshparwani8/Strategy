/* ═══════════════════════════════════════════════════════════
   ENGULF-BOT  —  Dashboard JavaScript
   Polls the FastAPI backend every 30 s for live data.
   ═══════════════════════════════════════════════════════════ */

const API = "";          // empty = same origin (FastAPI serves frontend)
const POLL_MS   = 30_000;
const PRICE_MS  = 15_000;

/* ── State ──────────────────────────────────────────────── */
let equityChart  = null;
let allTrades    = [];
let lastPrices   = {};
let filterSym    = "";
let filterResult = "";

/* ── DOM helpers ────────────────────────────────────────── */
const $  = id => document.getElementById(id);
const fmt  = (n, d=2) => Number(n).toLocaleString("en-US", {minimumFractionDigits:d, maximumFractionDigits:d});
const fmtP = n => (n >= 0 ? "+" : "") + fmt(n, 2);
const pct  = n => (n >= 0 ? "+" : "") + fmt(n, 2) + "%";
const ts   = s => {
  if (!s) return "—";
  const d = new Date(s);
  return d.toLocaleDateString("en-GB", {day:"2-digit",month:"short"}) + " " +
         d.toLocaleTimeString("en-GB", {hour:"2-digit",minute:"2-digit"});
};

function flash(el) {
  el.classList.remove("flashing");
  void el.offsetWidth;
  el.classList.add("flashing");
}

/* ── Toast ──────────────────────────────────────────────── */
function toast(msg, type = "info") {
  const icons = { success:"✅", error:"❌", info:"ℹ️" };
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${icons[type]}</span><span>${msg}</span>`;
  $("toastContainer").appendChild(el);
  setTimeout(() => {
    el.classList.add("toast-fade");
    setTimeout(() => el.remove(), 350);
  }, 3500);
}

/* ── Clock ──────────────────────────────────────────────── */
function updateClock() {
  $("clock").textContent = new Date().toUTCString().slice(17, 25) + " UTC";
}
setInterval(updateClock, 1000);
updateClock();

/* ══════════════════════════════════════════════════════════
   PRICES
══════════════════════════════════════════════════════════ */
async function fetchPrices() {
  try {
    const data = await fetch(`${API}/api/prices`).then(r => r.json());
    lastPrices = data;
    renderPrices(data);
  } catch (e) {
    console.warn("Price fetch failed", e);
  }
}

function renderPrices(data) {
  const btc = data["BTC/USDT"];
  const eth = data["ETH/USDT"];

  if (btc?.price) {
    $("btcPrice").textContent = "$" + fmt(btc.price, 0);
    const chgEl = $("btcChg");
    chgEl.textContent  = pct(btc.change_pct);
    chgEl.className    = "price-chg " + (btc.change_pct >= 0 ? "up" : "down");
  }
  if (eth?.price) {
    $("ethPrice").textContent = "$" + fmt(eth.price, 0);
    const chgEl = $("ethChg");
    chgEl.textContent  = pct(eth.change_pct);
    chgEl.className    = "price-chg " + (eth.change_pct >= 0 ? "up" : "down");
  }
}

/* ══════════════════════════════════════════════════════════
   STATUS  (open positions)
══════════════════════════════════════════════════════════ */
async function fetchStatus() {
  const data = await fetch(`${API}/api/status`).then(r => r.json());
  renderPositions(data.symbols);
}

function renderPositions(symbols) {
  const container = $("positionCards");
  const cards = [];
  let openCount = 0;

  for (const [sym, s] of Object.entries(symbols)) {
    // Status chips on sym breakdown
    const shortSym = sym.split("/")[0].toLowerCase();
    const statusEl = $(shortSym + "Status");
    if (statusEl) {
      statusEl.textContent  = s.status === "IN_TRADE" ? "IN TRADE" : "IDLE";
      statusEl.className    = "sym-status" + (s.status === "IN_TRADE" ? " in-trade" : "");
    }
    // Capital
    const capEl = $(shortSym + "Capital");
    if (capEl) {
      capEl.textContent = "$" + fmt(s.capital, 2);
      flash(capEl);
    }

    if (s.status === "IN_TRADE") {
      openCount++;
      const price = lastPrices[sym]?.price || 0;
      // Progress between SL and TP
      let progress = 50;
      if (price && s.stop_price && s.target_price) {
        const range = Math.abs(s.target_price - s.stop_price);
        if (range > 0) {
          const dist = s.trade_type === "LONG"
            ? (price - s.stop_price)
            : (s.stop_price - price);
          progress = Math.max(0, Math.min(100, (dist / range) * 100));
        }
      }

      const isBTC = sym.includes("BTC");
      cards.push(`
        <div class="pos-card">
          <div class="pos-card-header">
            <span class="pos-sym">${sym}</span>
            <span class="pos-type ${s.trade_type === "LONG" ? "long" : "short"}">${s.trade_type}</span>
          </div>
          <div class="pos-grid">
            <div class="pos-item">
              <div class="pos-item-label">Entry</div>
              <div class="pos-item-val mono">$${fmt(s.entry_price, 2)}</div>
            </div>
            <div class="pos-item">
              <div class="pos-item-label">Stop</div>
              <div class="pos-item-val mono sl">$${fmt(s.stop_price, 2)}</div>
            </div>
            <div class="pos-item">
              <div class="pos-item-label">Target</div>
              <div class="pos-item-val mono tp">$${fmt(s.target_price, 2)}</div>
            </div>
            <div class="pos-item">
              <div class="pos-item-label">Size</div>
              <div class="pos-item-val mono">${fmt(s.position_size, 4)}</div>
            </div>
            <div class="pos-item">
              <div class="pos-item-label">Live Price</div>
              <div class="pos-item-val mono">${price ? "$" + fmt(price, 2) : "—"}</div>
            </div>
            <div class="pos-item">
              <div class="pos-item-label">Since</div>
              <div class="pos-item-val" style="font-size:11px">${ts(s.entry_time)}</div>
            </div>
          </div>
          <div class="pos-bar-row">
            <div class="pos-bar-track">
              <div class="pos-bar-fill ${isBTC ? "btc-bar" : "eth-bar"}" style="width:${progress.toFixed(0)}%"></div>
            </div>
          </div>
        </div>`
      );
    }
  }

  container.innerHTML = cards.join("") || "";

  // Update open count badge
  const badge = $("posCount");
  badge.textContent = openCount;
  badge.className   = "panel-badge" + (openCount > 0 ? " active" : "");
}

/* ══════════════════════════════════════════════════════════
   STATS
══════════════════════════════════════════════════════════ */
async function fetchStats() {
  const data = await fetch(`${API}/api/stats`).then(r => r.json());
  renderStats(data);
}

function renderStats(data) {
  // Total capital = sum of both symbols
  const totalCap = Object.values(data.per_symbol).reduce((a, s) => a + s.capital, 0);
  const totalInit = data.initial_capital * Object.keys(data.per_symbol).length;
  const totalRet  = (totalCap / totalInit - 1) * 100;

  const capEl = $("statCapitalVal");
  capEl.textContent = "$" + fmt(totalCap, 2);
  flash(capEl);

  $("statCapitalRet").innerHTML =
    `<span class="${totalRet >= 0 ? "pnl-pos" : "pnl-neg"}">${pct(totalRet)}</span> vs $${fmt(totalInit, 0)} start`;

  $("statTrades").textContent = data.total_trades;
  $("statTradesSub").textContent = `${data.wins}W / ${data.losses}L`;

  const wrEl = $("statWinRate");
  wrEl.textContent = data.total_trades ? fmt(data.win_rate, 1) + "%" : "—";
  $("statWinRateSub").textContent = data.total_trades ? "over " + data.total_trades + " trades" : "No trades yet";

  const pnlEl = $("statPnl");
  pnlEl.textContent = data.total_trades ? "$" + fmtP(data.total_pnl) : "—";
  pnlEl.className   = "stat-value mono " + (data.total_pnl >= 0 ? "pnl-pos" : "pnl-neg");
  $("statPnlSub").textContent = data.total_trades ? "across all symbols" : "No trades yet";

  // Per-symbol breakdown
  for (const [sym, s] of Object.entries(data.per_symbol)) {
    const short = sym.split("/")[0].toLowerCase();
    const retEl = $(short + "Ret");
    if (retEl) {
      retEl.innerHTML = `<span class="${s.return_pct >= 0 ? "pnl-pos" : "pnl-neg"}">${pct(s.return_pct)}</span>`;
    }
    const pnlEl2 = $(short + "Pnl");
    if (pnlEl2) pnlEl2.innerHTML = `<span class="${s.pnl >= 0 ? "pnl-pos" : "pnl-neg"}">${fmtP(s.pnl)}</span>`;
    const wrEl2 = $(short + "Wr");
    if (wrEl2) wrEl2.textContent = s.trades ? fmt(s.win_rate, 1) + "%" : "—";
    const trEl = $(short + "Trades");
    if (trEl) trEl.textContent = s.trades;

    // Bar: capital relative to initial
    const barEl = $(short + "Bar");
    if (barEl) {
      const pct_w = Math.max(0, Math.min(200, (s.capital / data.initial_capital) * 50));
      barEl.style.width = pct_w + "%";
    }
  }

  // Equity curve
  renderEquityChart(data.equity_curve);
}

/* ══════════════════════════════════════════════════════════
   EQUITY CHART (Chart.js)
══════════════════════════════════════════════════════════ */
function renderEquityChart(points) {
  const emptyEl = $("chartEmpty");
  if (!points || points.length === 0) {
    emptyEl.classList.remove("hidden");
    return;
  }
  emptyEl.classList.add("hidden");

  // Split into per-symbol series, sorted by time
  const btcPts = points.filter(p => p.symbol === "BTC/USDT").sort((a, b) => a.time < b.time ? -1 : 1);
  const ethPts = points.filter(p => p.symbol === "ETH/USDT").sort((a, b) => a.time < b.time ? -1 : 1);

  // Add initial capital as first point
  const INIT = 10000;
  const mkDataset = (pts, color) => {
    const d = pts.map(p => ({ x: new Date(p.time), y: p.capital }));
    if (d.length) d.unshift({ x: new Date(d[0].x.getTime() - 900_000), y: INIT });
    return { data: d, borderColor: color, backgroundColor: color + "18",
             fill: true, tension: 0.35, pointRadius: 3, pointHoverRadius: 5,
             borderWidth: 2 };
  };

  const datasets = [];
  if (btcPts.length) datasets.push({ label: "BTC/USDT", ...mkDataset(btcPts, "#f7931a") });
  if (ethPts.length) datasets.push({ label: "ETH/USDT", ...mkDataset(ethPts, "#627eea") });

  if (equityChart) {
    equityChart.data.datasets = datasets;
    equityChart.update("none");
    return;
  }

  const ctx = $("equityChart").getContext("2d");
  equityChart = new Chart(ctx, {
    type: "line",
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          type: "time",
          time: { unit: "hour", displayFormats: { hour: "MMM d HH:mm" } },
          grid:  { color: "rgba(255,255,255,0.05)" },
          ticks: { color: "#8888aa", font: { family: "'JetBrains Mono'" } },
        },
        y: {
          grid:  { color: "rgba(255,255,255,0.05)" },
          ticks: {
            color: "#8888aa",
            font:  { family: "'JetBrains Mono'" },
            callback: v => "$" + Number(v).toLocaleString(),
          },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#111126",
          borderColor: "rgba(255,255,255,0.1)",
          borderWidth: 1,
          titleColor: "#e4e4f0",
          bodyColor: "#8888aa",
          padding: 12,
          callbacks: {
            label: ctx => ` ${ctx.dataset.label}: $${fmt(ctx.parsed.y, 2)}`,
          },
        },
      },
    },
  });
}

/* ══════════════════════════════════════════════════════════
   TRADES TABLE
══════════════════════════════════════════════════════════ */
async function fetchTrades() {
  const data = await fetch(`${API}/api/trades?limit=200`).then(r => r.json());
  allTrades = data.trades || [];
  renderTrades();
}

function renderTrades() {
  const sym    = $("filterSym").value;
  const result = $("filterResult").value;

  let trades = allTrades.filter(t =>
    (!sym    || t.symbol === sym) &&
    (!result || t.result === result)
  );

  const tbody = $("tradeBody");
  if (trades.length === 0) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="14">
      <div class="empty-msg">No trades match the current filter.</div></td></tr>`;
    $("tableFooter").textContent = "";
    return;
  }

  tbody.innerHTML = trades.map((t, i) => {
    const isBtc  = t.symbol.includes("BTC");
    const isWin  = t.result === "WIN";
    const pnlCls = t.pnl >= 0 ? "pnl-pos" : "pnl-neg";

    return `<tr>
      <td class="mono" style="color:var(--text2)">${trades.length - i}</td>
      <td><span class="badge-sym ${isBtc ? "btc" : "eth"}">${t.symbol.split("/")[0]}</span></td>
      <td><span class="badge-type ${t.trade_type.toLowerCase()}">${t.trade_type}</span></td>
      <td class="mono">$${fmt(t.entry_price)}</td>
      <td class="mono">$${fmt(t.exit_price)}</td>
      <td class="mono" style="color:var(--red)">$${fmt(t.stop_price)}</td>
      <td class="mono" style="color:var(--green)">$${fmt(t.target_price)}</td>
      <td class="mono" style="color:var(--text2)">${fmt(t.position_size, 4)}</td>
      <td class="mono ${pnlCls}">${fmtP(t.pnl)}</td>
      <td class="mono">$${fmt(t.capital_after)}</td>
      <td><span class="badge-result ${isWin ? "win" : "loss"}">${isWin ? "✓ WIN" : "✗ LOSS"}</span></td>
      <td><span class="badge-reason">${t.exit_reason}</span></td>
      <td style="color:var(--text2);font-size:11px">${ts(t.entry_time)}</td>
      <td style="color:var(--text2);font-size:11px">${ts(t.exit_time)}</td>
    </tr>`;
  }).join("");

  $("tableFooter").textContent = `Showing ${trades.length} trade${trades.length !== 1 ? "s" : ""}`;
}

/* ══════════════════════════════════════════════════════════
   MASTER REFRESH
══════════════════════════════════════════════════════════ */
async function refresh() {
  const dot   = $("statusDot");
  const label = $("statusLabel");

  try {
    await Promise.all([fetchStatus(), fetchStats(), fetchTrades()]);
    dot.className     = "status-dot online";
    label.textContent = "Live";
  } catch (err) {
    console.error("Refresh failed:", err);
    dot.className     = "status-dot error";
    label.textContent = "Disconnected";
    toast("Cannot reach backend — is main.py running?", "error");
  }
}

/* ── Trigger-check button ───────────────────────────────── */
$("btnTrigger").addEventListener("click", async () => {
  const btn = $("btnTrigger");
  btn.disabled    = true;
  btn.textContent = "Running…";
  try {
    await fetch(`${API}/api/trigger-check`, { method: "POST" });
    toast("Strategy check complete", "success");
    await refresh();
  } catch (e) {
    toast("Check failed — backend unreachable", "error");
  } finally {
    btn.disabled    = false;
    btn.textContent = "⟳ Run Check";
  }
});

/* ── Filter listeners ───────────────────────────────────── */
$("filterSym").addEventListener("change",    e => { filterSym    = e.target.value; renderTrades(); });
$("filterResult").addEventListener("change", e => { filterResult = e.target.value; renderTrades(); });

/* ══════════════════════════════════════════════════════════
   BOOT
══════════════════════════════════════════════════════════ */
(async () => {
  await fetchPrices();   // prices first (needed for pos cards)
  await refresh();       // full data load

  setInterval(fetchPrices, PRICE_MS);   // prices every 15 s
  setInterval(refresh,     POLL_MS);    // full refresh every 30 s
})();
