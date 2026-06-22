// Dashboard / Panel modülü
(function () {
  const MODULES = [
    ["chart", "📈", "Grafik", "Mum grafik + 44 gösterge, Ichimoku bulutu"],
    ["scanner", "🔍", "Tarayıcı", "Kural tabanlı piyasa taraması (DSL)"],
    ["strategy", "🧪", "Strateji", "Backtest: metrikler, equity, işlemler"],
    ["optimize", "⚙️", "Optimize", "Grid / Random / Bayesian parametre"],
    ["walkforward", "🔁", "Walk-Forward", "Out-of-sample aşırı uyum testi"],
    ["portfolio", "💼", "Portföy", "Markowitz + Kuantum + Monte Carlo"],
    ["sentiment", "🧠", "Sentiment", "AI haber duyarlılığı (Google+Yahoo)"],
    ["fundamentals", "📑", "Temel", "Değer/kârlılık/büyüme/sağlık skoru"],
    ["fusion", "🎯", "Füzyon", "Teknik + Haber + Temel birleşik sinyal"],
  ];
  const QUICK_SCANS = [
    ["Aşırı satım", "RSI(14) < 30 AND Volume > SMA(Volume, 20)"],
    ["Trend + güç", "EMA(20) > EMA(50) AND ADX(14) > 25"],
    ["MACD kesişim", "MACD Cross Up AND RSI(14) > 50"],
  ];

  function go(view) { document.querySelector(`.tab[data-view="${view}"]`).click(); }

  async function init() {
    document.getElementById("dash-modules").innerHTML = MODULES.map(([v, i, t, d]) =>
      `<div class="mod-card" data-go="${v}"><div class="ico">${i}</div><h4>${t}</h4><p>${d}</p></div>`).join("");
    document.querySelectorAll(".mod-card").forEach((c) => c.addEventListener("click", () => go(c.dataset.go)));

    try {
      const u = await API.get("/api/universes");
      document.getElementById("dash-group").innerHTML = u.universes.map((g) =>
        `<option value="${g.id}">${g.label}</option>`).join("");
    } catch (e) {}
    document.getElementById("dash-group").addEventListener("change", loadMovers);

    document.getElementById("dash-quick-scans").innerHTML = QUICK_SCANS.map((q, i) =>
      `<button class="ghost example" data-i="${i}">${q[0]}<small>${q[1]}</small></button>`).join("");
    document.querySelectorAll("#dash-quick-scans .example").forEach((b) =>
      b.addEventListener("click", () => runQuickScan(QUICK_SCANS[b.dataset.i][1])));

    const openSym = () => { const v = document.getElementById("dash-sym").value.trim(); if (v) { go("chart"); window.Chart.load(v); } };
    document.getElementById("dash-sym-btn").addEventListener("click", openSym);
    document.getElementById("dash-sym").addEventListener("keydown", (e) => { if (e.key === "Enter") openSym(); });
    document.getElementById("dash-sent-btn").addEventListener("click", loadSentimentPulse);
    window.Live.onQuote(liveUpdate);

    loadMovers();
  }

  function runQuickScan(rule) {
    go("scanner");
    const ta = document.getElementById("scan-rule");
    ta.value = rule;
    ta.dispatchEvent(new Event("input"));
    setTimeout(() => document.getElementById("scan-run").click(), 200);
  }

  function spark(arr, up) {
    if (!arr || arr.length < 2) return "";
    const W = 80, H = 22, min = Math.min(...arr), max = Math.max(...arr), rng = max - min || 1;
    const pts = arr.map((v, i) => `${(i / (arr.length - 1) * W).toFixed(1)},${(H - (v - min) / rng * H).toFixed(1)}`).join(" ");
    return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="${up ? "#26a69a" : "#ef5350"}" stroke-width="1.5"/></svg>`;
  }

  function moverRow(m) {
    const up = m.change >= 0;
    return `<div class="mv" data-sym="${m.symbol}"><span class="mvs">${m.symbol.replace(".IS", "").replace("-USD", "").replace("=F", "")}</span>
      ${spark(m.spark, up)}
      <span class="mvc ${up ? "pos" : "neg"}">${up ? "+" : ""}${fmt(m.change)}%</span></div>`;
  }

  function liveUpdate(data) {
    Object.values(data).forEach((q) => {
      document.querySelectorAll(`.mv[data-sym="${q.symbol}"] .mvc`).forEach((cell) => {
        const up = q.change >= 0;
        cell.textContent = `${up ? "+" : ""}${fmt(q.change)}%`;
        cell.className = "mvc " + (up ? "pos" : "neg");
        cell.style.transition = "none"; cell.style.opacity = "0.4";
        setTimeout(() => { cell.style.transition = "opacity .6s"; cell.style.opacity = "1"; }, 50);
      });
    });
  }

  async function loadMovers() {
    const group = document.getElementById("dash-group").value || "bist30";
    const breadth = document.getElementById("dash-breadth");
    breadth.textContent = "Piyasa verisi çekiliyor…";
    document.getElementById("dash-gainers").innerHTML = `<div class="spinner" style="padding:8px">⏳</div>`;
    document.getElementById("dash-losers").innerHTML = "";
    try {
      const r = await API.get(`/api/market/movers?group=${group}&limit=5`);
      breadth.innerHTML = `${r.count} sembol · <span class="pos">▲ ${r.advancers}</span> / <span class="neg">▼ ${r.decliners}</span>`;
      document.getElementById("dash-gainers").innerHTML = r.gainers.map(moverRow).join("");
      document.getElementById("dash-losers").innerHTML = r.losers.map(moverRow).join("");
      window.Live.subscribe("dash", [...r.gainers, ...r.losers].map((x) => x.symbol));
    } catch (e) {
      breadth.innerHTML = `<span class="neg">Hata: ${e.message}</span>`;
      document.getElementById("dash-gainers").innerHTML = "";
    }
  }

  function sentColor(s) {
    const t = Math.max(-1, Math.min(1, s));
    const r = t < 0 ? 239 : Math.round(210 - 172 * t);
    const g = t < 0 ? Math.round(83 + 127 * (t + 1)) : 166;
    const b = t < 0 ? 80 : Math.round(80 + 74 * t);
    return `rgb(${r},${g},${b})`;
  }

  async function loadSentimentPulse() {
    const group = document.getElementById("dash-group").value || "bist30";
    const box = document.getElementById("dash-sentiment");
    box.innerHTML = `<div class="spinner" style="padding:8px">⏳ Haberler analiz ediliyor… (biraz sürebilir)</div>`;
    try {
      const r = await API.post("/api/sentiment/group", { group, limit: 3 });
      const top = r.results.slice(0, 4), bottom = r.results.slice(-4).reverse();
      const pill = (m) => `<span class="sent-pill" style="background:${sentColor(m.score)}">${m.symbol.replace(".IS", "").replace("-USD", "").replace("=F", "")} ${m.score >= 0 ? "+" : ""}${fmt(m.score)}</span>`;
      box.innerHTML = `<div class="muted" style="font-size:11px;margin:4px 0">En pozitif</div><div class="sent-pulse">${top.map(pill).join("")}</div>
        <div class="muted" style="font-size:11px;margin:8px 0 4px">En negatif</div><div class="sent-pulse">${bottom.map(pill).join("")}</div>`;
    } catch (e) {
      box.innerHTML = `<span class="neg">Hata: ${e.message}</span>`;
    }
  }

  window.Dashboard = { init };
})();
