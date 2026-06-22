// Temel Analiz modülü
(function () {
  const METRIC_LABELS = {
    pe: "F/K (PE)", forward_pe: "İleri F/K", pb: "PD/DD (PB)", ps: "PD/Satış (PS)",
    roe: "ROE %", roa: "ROA %", net_margin: "Net Marj %", operating_margin: "Faaliyet Marj %",
    gross_margin: "Brüt Marj %", revenue_growth: "Gelir Büyüme %", earnings_growth: "Kâr Büyüme %",
    dividend_yield: "Temettü %", current_ratio: "Cari Oran", debt_to_equity: "Borç/Özsermaye",
    market_cap: "Piyasa Değeri (M)", beta: "Beta", eps: "HBK (EPS)",
  };

  async function init() {
    try {
      const u = await API.get("/api/universes");
      document.getElementById("fd-group").innerHTML = u.universes.map((g) =>
        `<option value="${g.id}">${g.label} (${g.count})</option>`).join("");
    } catch (e) {}
    document.getElementById("fd-run").addEventListener("click", runGroup);
    document.getElementById("fd-symbol-btn").addEventListener("click", runSymbol);
    document.getElementById("fd-symbol").addEventListener("keydown", (e) => { if (e.key === "Enter") runSymbol(); });
  }

  function scoreColor(s) {
    if (s == null) return "#3a4655";
    const t = Math.max(0, Math.min(100, s)) / 100;
    const r = t < 0.5 ? 239 : Math.round(239 - (239 - 38) * (t - 0.5) * 2);
    const g = t < 0.5 ? Math.round(83 + (166 - 83) * t * 2) : 166;
    return `rgb(${r},${g},90)`;
  }

  function bucketBar(name, score) {
    return `<div class="wbar"><span class="wsym">${name}</span>
      <span class="track"><span class="fill" style="width:${score || 0}%;background:${scoreColor(score)}"></span></span>
      <span class="wval">${score == null ? "—" : fmt(score, 0)}</span></div>`;
  }

  async function runGroup() {
    const group = document.getElementById("fd-group").value;
    const meta = document.getElementById("fd-meta");
    meta.textContent = "Temel veriler çekiliyor…";
    document.getElementById("fd-results").innerHTML = `<div class="spinner">⏳ Analiz ediliyor…</div>`;
    document.getElementById("fd-detail-panel").style.display = "none";
    try {
      const r = await API.post("/api/fundamentals/group", { group });
      const withData = r.results.filter((x) => x.score != null).length;
      meta.innerHTML = `<b>${withData}</b>/${r.count} sembolde veri`;
      renderTable(r.results);
    } catch (e) {
      meta.innerHTML = `<span class="neg">Hata: ${e.message}</span>`;
      document.getElementById("fd-results").innerHTML = "";
    }
  }

  function renderTable(rows) {
    const body = rows.map((r) => {
      const b = r.buckets || {};
      return `<tr data-sym="${r.symbol}">
        <td>${r.symbol.replace(".IS", "")}</td>
        <td class="muted">${(r.name || "").slice(0, 22)}</td>
        <td><b style="color:${scoreColor(r.score)}">${r.score == null ? "—" : fmt(r.score, 0)}</b></td>
        <td>${r.label}</td>
        <td class="muted" style="font-size:11px">D${fmt(b["Değer"] || 0, 0)} K${fmt(b["Kârlılık"] || 0, 0)} B${fmt(b["Büyüme"] || 0, 0)} S${fmt(b["Sağlık"] || 0, 0)}</td></tr>`;
    }).join("");
    document.getElementById("fd-results").innerHTML = `<table><thead><tr>
      <th>Sembol</th><th>Ad</th><th>Skor</th><th>Durum</th>
      <th title="Değer / Kârlılık / Büyüme / Finansal Sağlık (her biri 0-100)">D/K/B/S ⓘ</th></tr></thead><tbody>${body}</tbody></table>
      <div class="muted" style="font-size:11px;margin-top:6px"><b>D</b>=Değer (ucuzluk) · <b>K</b>=Kârlılık · <b>B</b>=Büyüme · <b>S</b>=Finansal Sağlık — her biri 0-100</div>`;
    document.querySelectorAll("#fd-results tbody tr").forEach((tr) =>
      tr.addEventListener("click", () => loadDetail(tr.dataset.sym)));
  }

  async function runSymbol() {
    const s = document.getElementById("fd-symbol").value.trim();
    if (s) await loadDetail(s, true);
  }

  async function loadDetail(symbol, scroll) {
    const panel = document.getElementById("fd-detail-panel");
    const det = document.getElementById("fd-detail");
    panel.style.display = "block";
    document.getElementById("fd-detail-title").textContent = symbol;
    det.innerHTML = `<div class="spinner">⏳</div>`;
    try {
      const d = await API.get("/api/fundamentals?symbol=" + encodeURIComponent(symbol));
      if (d.score == null) { det.innerHTML = `<div class="muted">Bu sembol için temel veri bulunamadı (kaynak: ${d.source || "yok"}).</div>`; return; }
      document.getElementById("fd-detail-title").innerHTML =
        `${d.name} <span class="se-score" style="background:${scoreColor(d.score)}">${fmt(d.score, 0)} ${d.label}</span> <span class="muted" style="font-size:11px">${d.source}</span>`;
      const buckets = ["Değer", "Kârlılık", "Büyüme", "Sağlık"].map((k) => bucketBar(k, d.buckets[k])).join("");
      const m = d.metrics;
      const rows = Object.keys(METRIC_LABELS).filter((k) => m[k] != null).map((k) =>
        `<tr><td>${METRIC_LABELS[k]}</td><td style="text-align:right">${fmt(m[k], k === "market_cap" ? 0 : 2)}</td></tr>`).join("");
      det.innerHTML = `<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div><div class="muted" style="font-size:11px;margin-bottom:6px">Kovalar</div>${buckets}</div>
        <div><div class="muted" style="font-size:11px;margin-bottom:6px">Oranlar</div><table>${rows}</table></div></div>`;
      if (scroll) panel.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      det.innerHTML = `<span class="neg">Hata: ${e.message}</span>`;
    }
  }

  window.Fundamentals = { init };
})();
