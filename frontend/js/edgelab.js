// Edge Lab / Kantitatif — sistematik kombo arama (combo_search) UI'dan
(function () {
  async function init() {
    document.getElementById("el-run").addEventListener("click", run);
  }

  const short = (s) => s.replace(".IS", "").replace("-USDT-SWAP", "").replace("-USD", "");

  async function run() {
    const level = document.getElementById("el-level").value;
    const universe = document.getElementById("el-universe").value;
    const top = parseInt(document.getElementById("el-top").value) || 20;
    const basket_size = parseInt(document.getElementById("el-basket").value) || 6;
    const meta = document.getElementById("el-meta");
    meta.textContent = "Taranıyor… (sepet çekiliyor, kombolar backtest ediliyor — 15–40 sn sürebilir)";
    document.getElementById("el-results").innerHTML = `<div class="spinner">⏳ Kombolar taranıyor…</div>`;
    const btn = document.getElementById("el-run");
    btn.disabled = true;
    try {
      const r = await API.post("/api/portfolio/edge/search", { level, universe, top, basket_size });
      meta.innerHTML = `<b>${level === "singles" ? "Tekli gösterge" : "İkili kombo"}</b> · sepet ${r.n_basket} (${r.basket.map(short).join(", ")}) · in-sample triage`;
      renderTable(r.results);
    } catch (e) {
      meta.innerHTML = `<span class="neg">Hata: ${e.message}</span>`;
      document.getElementById("el-results").innerHTML = "";
    } finally {
      btn.disabled = false;
    }
  }

  function renderTable(rows) {
    if (!rows || !rows.length) { document.getElementById("el-results").innerHTML = `<div class="muted">Sonuç yok.</div>`; return; }
    const body = rows.map((x, i) => `<tr>
      <td class="muted">${i + 1}</td>
      <td><b>${x.name}</b></td>
      <td class="${x.sharpe >= 1 ? "pos" : ""}"><b>${fmt(x.sharpe, 2)}</b></td>
      <td class="${x.total_return >= 0 ? "pos" : "neg"}">${fmt(x.total_return, 0)}%</td>
      <td class="neg">${fmt(x.max_drawdown, 0)}%</td>
      <td class="muted">${fmt(x.num_trades, 0)}</td>
      <td>${x.prof_pct}%</td>
      <td>${x.beat_bh}%</td>
      <td class="muted">${fmt(x.score, 2)}</td></tr>`).join("");
    document.getElementById("el-results").innerHTML = `<table><thead><tr>
      <th>#</th><th>kombo</th><th>Sharpe</th><th>getiri</th><th>DD</th><th>işlem</th>
      <th title="kârlı sembol %">kârlı</th><th title="Al&Tut'u geçen sembol %">&gt;B&amp;H</th><th>skor</th>
      </tr></thead><tbody>${body}</tbody></table>
      <div class="muted" style="font-size:11px;margin-top:6px">Skor = semboller-arası ort. Sharpe (az-işlem cezalı). ⚠ in-sample triage — kalıcı seçim için walk-forward (Sonuçlar / scriptler).</div>`;
  }

  window.EdgeLab = { init };
})();
