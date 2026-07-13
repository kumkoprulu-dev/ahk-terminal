// NNFX Yuva Arama — DaviddTech/StrategyFactory kalıbını panelden üret + OOS test.
// Ağır arama arka-plan job olarak koşar (POST /api/nnfx/search → GET /search/{id} poll).
(function () {
  let polling = null;

  async function init() {
    const btn = document.getElementById("nx-run");
    if (btn) btn.addEventListener("click", run);
  }

  function stopPolling() {
    if (polling) { clearInterval(polling); polling = null; }
  }

  async function run() {
    stopPolling();
    const interval = document.getElementById("nx-interval").value;
    const use_confirm2 = document.getElementById("nx-c2").checked;
    const top = parseInt(document.getElementById("nx-top").value) || 30;
    const meta = document.getElementById("nx-meta");
    const btn = document.getElementById("nx-run");
    document.getElementById("nx-noise").innerHTML = "";
    document.getElementById("nx-results").innerHTML =
      `<div class="spinner">⏳ NNFX kombolar üretiliyor + OOS test ediliyor…</div>`;
    btn.disabled = true;
    try {
      const { job_id } = await API.post("/api/nnfx/search", { interval, use_confirm2, top });
      const started = Date.now();
      polling = setInterval(async () => {
        try {
          const s = await API.get(`/api/nnfx/search/${job_id}`);
          const el = Math.round((Date.now() - started) / 1000);
          meta.innerHTML = `Job <code>${job_id}</code> · <b>${s.status}</b> · ${s.elapsed_s || el}s`;
          if (s.status === "done") {
            stopPolling(); btn.disabled = false;
            render(s.result);
          } else if (s.status === "error") {
            stopPolling(); btn.disabled = false;
            meta.innerHTML = `<span class="neg">Hata: ${s.error || "bilinmeyen"}</span>`;
            document.getElementById("nx-results").innerHTML = "";
          }
        } catch (e) {
          stopPolling(); btn.disabled = false;
          meta.innerHTML = `<span class="neg">Poll hatası: ${e.message}</span>`;
        }
      }, 4000);
    } catch (e) {
      btn.disabled = false;
      meta.innerHTML = `<span class="neg">Başlatılamadı: ${e.message}</span>`;
      document.getElementById("nx-results").innerHTML = "";
    }
  }

  function render(r) {
    const meta = document.getElementById("nx-meta");
    if (!r || !r.ok) {
      meta.innerHTML = `<span class="neg">${(r && r.error) || "Sonuç yok."}</span>`;
      return;
    }
    meta.innerHTML = `<b>${r.n_combos}</b> strateji · sepet ${r.symbols.length} · ${r.slots} · OOS-sıralı · run #${r.run_id}`;

    // Noise kapısı ortalama katkısı (NNFX'in en öğretici bulgusu)
    const na = r.noise_avg || {};
    const best = Object.entries(na).sort((a, b) => b[1] - a[1])[0];
    document.getElementById("nx-noise").innerHTML =
      `<div class="muted" style="font-size:12px">Noise kapısı ort OOS Sharpe: ` +
      Object.entries(na).map(([k, v]) =>
        `<b class="${v >= 0 ? "pos" : "neg"}">${k} ${v.toFixed(3)}</b>`).join(" · ") +
      (best ? ` — en iyi <b>${best[0]}</b>` : "") + `</div>`;

    const rows = (r.results || []).map((x, i) => `<tr>
      <td class="muted">${x.rank || i + 1}</td>
      <td><b>${x.name}</b></td>
      <td class="muted">${x.noise}</td>
      <td class="muted">${x.is_sharpe != null ? Number(x.is_sharpe).toFixed(2) : "—"}</td>
      <td class="${x.oos_sharpe >= 0.2 ? "pos" : x.oos_sharpe < 0 ? "neg" : ""}"><b>${Number(x.oos_sharpe).toFixed(3)}</b></td>
      <td class="${x.total_return >= 0 ? "pos" : "neg"}">${Number(x.total_return).toFixed(0)}%</td>
      <td class="neg">${Number(x.max_drawdown).toFixed(0)}%</td>
      <td class="muted">${Number(x.num_trades).toFixed(0)}</td>
      <td>${x.prof_pct}%</td>
      <td>${x.beat_bh}%</td>
    </tr>`).join("");
    document.getElementById("nx-results").innerHTML = `
      <table class="tbl">
        <thead><tr><th>#</th><th>Strateji (yuvalar)</th><th>Noise</th><th>IS</th><th>OOS Sh</th>
          <th>Getiri</th><th>DD</th><th>İşlem</th><th>Kâr%</th><th>&gt;B&amp;H</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <div class="muted" style="font-size:11px;margin-top:6px">In-sample (IS) → OOS düşüşü overfit payını gösterir. Bu bir araştırma/triage aracıdır; çıkan kombolar canlıya OTOMATİK bağlanmaz.</div>`;
  }

  window.Nnfx = { init };
})();
