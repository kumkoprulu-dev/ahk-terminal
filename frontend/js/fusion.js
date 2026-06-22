// 3'lü Füzyon modülü (Teknik + Haber + Temel)
(function () {
  const SIG_CLASS = {
    "GÜÇLÜ AL": "sig-strong-buy", "AL": "sig-buy", "NÖTR": "sig-neutral",
    "SAT": "sig-sell", "GÜÇLÜ SAT": "sig-strong-sell",
  };

  async function init() {
    try {
      const u = await API.get("/api/universes");
      document.getElementById("fz-group").innerHTML = u.universes.map((g) =>
        `<option value="${g.id}">${g.label} (${g.count})</option>`).join("");
    } catch (e) {}
    document.getElementById("fz-run").addEventListener("click", run);
  }

  // skor 0-100 -> renk (kırmızı→sarı→yeşil)
  function scoreColor(s) {
    if (s == null) return "#3a4655";
    const t = Math.max(0, Math.min(100, s)) / 100;
    const r = t < 0.5 ? 239 : Math.round(239 - (239 - 38) * (t - 0.5) * 2);
    const g = t < 0.5 ? Math.round(83 + (166 - 83) * t * 2) : 166;
    return `rgb(${r},${g},90)`;
  }

  function bar(score) {
    if (score == null) return `<span class="axis"><span class="muted" style="font-size:11px">—</span></span>`;
    return `<span class="axis"><span style="font-size:11px;text-align:right">${fmt(score, 0)}</span>
      <span class="track"><span class="fill" style="width:${score}%;background:${scoreColor(score)}"></span></span></span>`;
  }

  async function run() {
    const group = document.getElementById("fz-group").value;
    const num = (id) => parseFloat(document.getElementById(id).value) || 0;
    const body = {
      group,
      weights: { technical: num("fz-wt"), sentiment: num("fz-ws"), fundamental: num("fz-wf") },
      with_sentiment: document.getElementById("fz-sent").checked,
    };
    const meta = document.getElementById("fz-meta");
    meta.textContent = "Füzyon hesaplanıyor… (teknik + haber + temel — biraz sürebilir)";
    document.getElementById("fz-results").innerHTML = `<div class="spinner">⏳ 3 eksen analiz ediliyor…</div>`;
    try {
      const r = await API.post("/api/fusion/group", body);
      meta.innerHTML = `<b>${r.count}</b> sembol · ağırlık T${body.weights.technical}/H${body.weights.sentiment}/F${body.weights.fundamental}${r.with_sentiment ? "" : " · haber kapalı"}`;
      renderTable(r.results);
    } catch (e) {
      meta.innerHTML = `<span class="neg">Hata: ${e.message}</span>`;
      document.getElementById("fz-results").innerHTML = "";
    }
  }

  function renderTable(rows) {
    if (!rows.length) { document.getElementById("fz-results").innerHTML = `<div class="spinner">Sonuç yok.</div>`; return; }
    const body = rows.map((r) => {
      const sentScore = r.sentiment == null ? null : 50 + 50 * r.sentiment;
      return `<tr data-sym="${r.symbol}">
        <td>${r.symbol.replace(".IS", "").replace("-USD", "").replace("=F", "")}</td>
        <td><span class="sig ${SIG_CLASS[r.signal] || "sig-neutral"}">${r.signal}</span></td>
        <td><b style="color:${scoreColor(r.composite)}">${r.composite == null ? "—" : fmt(r.composite, 0)}</b></td>
        <td>${bar(r.technical)}</td>
        <td>${bar(sentScore)}</td>
        <td>${bar(r.fundamental)}</td>
        <td class="flag-cell">${r.flag || ""}</td></tr>`;
    }).join("");
    document.getElementById("fz-results").innerHTML = `<table><thead><tr>
      <th>Sembol</th><th>Sinyal</th><th>Bileşik</th><th>Teknik</th><th>Haber</th><th>Temel</th><th>Not</th>
      </tr></thead><tbody>${body}</tbody></table>`;
    document.querySelectorAll("#fz-results tbody tr").forEach((tr) =>
      tr.addEventListener("click", () => { document.querySelector('.tab[data-view="chart"]').click(); window.Chart.load(tr.dataset.sym); }));
  }

  window.Fusion = { init };
})();
