// Ortak durum, API yardımcıları ve sekme yönetimi
function authHeaders(extra) {
  const h = { ...(extra || {}) };
  const t = window.Auth && window.Auth.token();
  if (t) h["Authorization"] = "Bearer " + t;
  return h;
}
const API = {
  async get(path) {
    const r = await fetch(path, { headers: authHeaders() });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(path, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
    return r.json();
  },
  async del(path) {
    const r = await fetch(path, { method: "DELETE", headers: authHeaders() });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
    return r.json();
  },
};

const State = {
  symbol: "ASELS.IS",
  interval: "1d",
  range: "1y",
  indicators: [],      // gösterge metadata (registry)
  indicatorsByName: {},
};

const fmt = (n, d = 2) => (n == null ? "—" : Number(n).toLocaleString("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d }));

// Sekme geçişi
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("view-" + btn.dataset.view).classList.add("active");
    if (btn.dataset.view === "chart" && window.Chart) window.Chart.resize();
  });
});

function switchToChart(symbol) {
  State.symbol = symbol;
  document.querySelector('.tab[data-view="chart"]').click();
  window.Chart.load(symbol);
}

// Başlangıç: sağlık + gösterge metadata
(async function init() {
  window.Auth.init();
  window.Live.connect();
  try {
    const h = await API.get("/health");
    document.getElementById("status").innerHTML =
      `<b>●</b> ${h.indicators} gösterge · veri: ${h.finnhub ? "Finnhub+yfinance" : "yfinance"}`;
  } catch (e) {
    document.getElementById("status").textContent = "API erişilemiyor";
  }
  try {
    const data = await API.get("/api/indicators");
    State.indicators = data.indicators;
    data.indicators.forEach((i) => (State.indicatorsByName[i.name] = i));
    window.Chart.initIndicatorPicker();
  } catch (e) { console.error(e); }

  window.Chart.init();
  window.Scanner.init();
  window.Strategy.init();
  window.Optimize.init();
  window.WalkForward.init();
  window.Portfolio.init();
  window.Sentiment.init();
  window.Fundamentals.init();
  window.Fusion.init();
  window.Dashboard.init();
  window.Alarms.init();
  window.Chart.load(State.symbol);
})();
