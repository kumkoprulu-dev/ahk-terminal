// Haber Duyarlılığı (Sentiment) modülü
(function () {
  async function init() {
    try {
      const u = await API.get("/api/universes");
      document.getElementById("se-group").innerHTML = u.universes.map((g) =>
        `<option value="${g.id}">${g.label} (${g.count})</option>`).join("");
      const b = await API.get("/api/sentiment/backends");
      document.getElementById("se-backend").innerHTML = b.backends.map((x) =>
        `<option value="${x}">${x === "finbert" ? "FinBERT (derin model)" : "Sözlük (hızlı)"}</option>`).join("");
    } catch (e) {}
    document.getElementById("se-run").addEventListener("click", runGroup);
    document.getElementById("se-symbol-btn").addEventListener("click", runSymbol);
    document.getElementById("se-symbol").addEventListener("keydown", (e) => { if (e.key === "Enter") runSymbol(); });
  }

  // skor [-1,1] -> kırmızı→sarı→yeşil renk
  function scoreColor(s) {
    const t = Math.max(-1, Math.min(1, s));
    let r, g;
    if (t < 0) { r = 239; g = Math.round(83 + (210 - 83) * (t + 1)); } // kırmızı→sarı
    else { r = Math.round(210 - (210 - 38) * t); g = Math.round(166 + (166 - 166) * t); } // sarı→yeşil
    const b = t < 0 ? 80 : Math.round(80 + (154 - 80) * t);
    return `rgb(${r},${g},${b})`;
  }

  const backend = () => document.getElementById("se-backend").value || "lexicon";

  async function runGroup() {
    const group = document.getElementById("se-group").value;
    const meta = document.getElementById("se-meta");
    meta.textContent = "Haberler çekiliyor ve analiz ediliyor…";
    document.getElementById("se-results").innerHTML = `<div class="spinner">⏳ Google News taranıyor…</div>`;
    document.getElementById("se-detail-panel").style.display = "none";
    try {
      const r = await API.post("/api/sentiment/group", { group, backend: backend(), limit: 4 });
      meta.innerHTML = `<b>${r.count}</b> sembol · model: ${r.backend === "finbert" ? "FinBERT" : "Sözlük"}`;
      renderTable(r.results);
    } catch (e) {
      meta.innerHTML = `<span class="neg">Hata: ${e.message}</span>`;
      document.getElementById("se-results").innerHTML = "";
    }
  }

  function renderTable(rows) {
    if (!rows.length) { document.getElementById("se-results").innerHTML = `<div class="spinner">Sonuç yok.</div>`; return; }
    const body = rows.map((r) => `<tr data-sym="${r.symbol}">
      <td>${r.symbol.replace(".IS", "").replace("-USD", "").replace("=F", "")}</td>
      <td class="muted">${r.name}</td>
      <td><span class="se-score" style="background:${scoreColor(r.score)}">${r.score >= 0 ? "+" : ""}${fmt(r.score)}</span></td>
      <td>${r.label}</td>
      <td class="muted">${r.n_news}</td></tr>`).join("");
    document.getElementById("se-results").innerHTML = `<table><thead><tr>
      <th>Sembol</th><th>Ad</th><th>Skor</th><th>Durum</th><th>Haber</th></tr></thead><tbody>${body}</tbody></table>`;
    document.querySelectorAll("#se-results tbody tr").forEach((tr) =>
      tr.addEventListener("click", () => loadDetail(tr.dataset.sym)));
  }

  async function runSymbol() {
    const sym = document.getElementById("se-symbol").value.trim();
    if (sym) await loadDetail(sym, true);
  }

  async function loadDetail(symbol, scroll) {
    const panel = document.getElementById("se-detail-panel");
    const det = document.getElementById("se-detail");
    document.getElementById("se-detail-title").innerHTML = `Haber Başlıkları — ${symbol}`;
    panel.style.display = "block";
    det.innerHTML = `<div class="spinner">⏳ Haberler yükleniyor…</div>`;
    try {
      const r = await API.get(`/api/sentiment?symbol=${encodeURIComponent(symbol)}&backend=${backend()}&limit=8`);
      if (!r.headlines.length) { det.innerHTML = `<div class="muted">Haber bulunamadı.</div>`; return; }
      document.getElementById("se-detail-title").innerHTML =
        `${r.name} <span class="se-score" style="background:${scoreColor(r.score)}">${r.score >= 0 ? "+" : ""}${fmt(r.score)} ${r.label}</span>`;
      det.innerHTML = r.headlines.map((h) => `<div class="headline">
        <span class="se-score" style="background:${scoreColor(h.score)}">${h.score >= 0 ? "+" : ""}${fmt(h.score)}</span>
        <div><a href="${h.link}" target="_blank" rel="noopener noreferrer">${h.title}</a>
          <div class="meta">${h.source || ""}${h.published ? " · " + h.published : ""}</div></div></div>`).join("");
      if (scroll) panel.scrollIntoView({ behavior: "smooth" });
    } catch (e) {
      det.innerHTML = `<span class="neg">Hata: ${e.message}</span>`;
    }
  }

  window.Sentiment = { init };
})();
