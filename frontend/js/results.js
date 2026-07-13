// Kayıtlı Sonuçlar modülü — kalıcı results veritabanını (results.sqlite) görüntüler.
(function () {
  const KIND_LABELS = {
    grid: "Grid", grid_compare: "Grid karşılaştırma", walkforward: "Walk-forward",
    walkforward_matrix: "WF matris", portfolio: "Portföy", portfolio_stack: "Portföy yığın",
    combo_singles: "Kombo tekli", combo_pairs: "Kombo ikili", combo_triples: "Kombo üçlü",
    combo_structured: "Yapısal kombo", combo_validation: "Kombo doğrulama",
    combo1: "Combo1", trend: "Trend", head2head: "Kafa kafaya", ablation: "Ablasyon",
    accumulate: "Birikim", carry: "Carry",
  };
  const SCRIPT_LABELS = {
    run_combo_portfolio: "Kripto Combo1", run_xsec: "Kripto cross-sectional",
    run_bist_combo: "BIST Combo1", run_accumulate: "Birikim", run_crypto: "Piyasa yapıcı",
  };
  const scriptLabel = (s) => SCRIPT_LABELS[s] || s;
  let liveTimer = null;
  const kindLabel = (k) => KIND_LABELS[k] || k;
  const sign = (v) => (v == null ? "" : v >= 0 ? "pos" : "neg");
  const cell = (v, d = 2) => (v == null ? '<td class="muted">—</td>' : `<td class="${sign(v)}">${fmt(v, d)}</td>`);

  async function init() {
    document.getElementById("rs-refresh").addEventListener("click", refresh);
    document.getElementById("rs-metric").addEventListener("change", loadTop);
    document.getElementById("rs-kind").addEventListener("change", loadTop);
    // Sekmeye ilk geçişte yükle + canlı paneli otomatik tazele
    let loaded = false;
    document.querySelectorAll(".tab").forEach((t) =>
      t.addEventListener("click", () => {
        const isResults = t.dataset.view === "results";
        if (isResults && !loaded) { loaded = true; refresh(); }
        if (liveTimer) { clearInterval(liveTimer); liveTimer = null; }
        if (isResults) liveTimer = setInterval(loadLive, 7000);   // sadece sekme açıkken
      }));
  }

  async function refresh() {
    await Promise.all([loadRuns(), loadTop(), loadLive()]);
  }

  async function loadLive() {
    const el = document.getElementById("rs-live");
    const totalEl = document.getElementById("rs-live-total");
    try {
      const r = await API.get("/api/results/live?limit=20");
      const sess = r.sessions || [];
      if (!sess.length) {
        totalEl.textContent = "—";
        el.innerHTML = `<div class="muted" style="font-size:13px">Aktif canlı oturum yok. Bir runner'ı <code>--save-every</code> ile başlatın.</div>`;
        return;
      }
      // birleşik: her script'in EN SON oturumunu al (aynı script tekrarlıysa en yenisi)
      const seen = new Set();
      const latestPerScript = sess.filter((s) => {
        if (seen.has(s.script)) return false;
        seen.add(s.script); return true;
      });
      const combined = latestPerScript.reduce((a, s) => a + (s.net_pnl || 0), 0);
      totalEl.textContent = fmt(combined, 2);
      totalEl.className = combined >= 0 ? "pos" : "neg";
      el.innerHTML = `<table><thead><tr>
        <th>sleeve</th><th>script</th><th>net PnL</th><th>realized</th><th>açık/sembol</th><th>snapshot</th><th>son</th>
        </tr></thead><tbody>${
        sess.map((s) => {
          const stale = latestPerScript.includes(s) ? "" : ' style="opacity:.5"';
          return `<tr${stale}>
          <td>🟢 ${s.label || scriptLabel(s.script)}</td>
          <td class="muted">${scriptLabel(s.script)}</td>
          ${cell(s.net_pnl)}${cell(s.realized)}
          <td class="muted">${s.positions}/${s.symbols}</td>
          <td class="muted">${s.snaps}</td>
          <td class="muted" style="font-size:11px">${(s.last_ts || "").slice(11, 19)}</td></tr>`;
        }).join("")
      }</tbody></table>
      <div class="muted" style="font-size:11px;margin-top:6px">Birleşik = her script'in en son oturumu. Para birimleri ayrı (USDT/TRY) — yalın toplam.</div>`;
    } catch (e) {
      el.innerHTML = `<span class="neg">Hata: ${e.message}</span>`;
    }
  }

  async function loadRuns() {
    const el = document.getElementById("rs-runs");
    const status = document.getElementById("rs-status");
    el.innerHTML = `<div class="spinner">⏳ Yükleniyor…</div>`;
    try {
      const r = await API.get("/api/results/runs?limit=100");
      const runs = r.runs || [];
      status.textContent = `${runs.length} çalıştırma kayıtlı`;
      // tür filtresini doldur
      const kinds = [...new Set(runs.map((x) => x.kind))].sort();
      const sel = document.getElementById("rs-kind");
      const cur = sel.value;
      sel.innerHTML = `<option value="">tüm türler</option>` +
        kinds.map((k) => `<option value="${k}">${kindLabel(k)}</option>`).join("");
      sel.value = cur;
      if (!runs.length) {
        el.innerHTML = `<div class="muted" style="font-size:13px">Henüz kayıt yok. <code>backend/scripts</code> altından bir <code>run_*.py</code> çalıştırın; sonuçlar burada belirir.</div>`;
        return;
      }
      el.innerHTML = `<table><thead><tr><th>#</th><th>tarih</th><th>tür</th><th>etiket</th><th>sonuç</th></tr></thead><tbody>${
        runs.map((x) => `<tr class="rs-run-row" data-id="${x.run_id}" style="cursor:pointer">
          <td>${x.run_id}</td>
          <td class="muted" style="font-size:11px">${(x.created_at || "").slice(0, 16).replace("T", " ")}</td>
          <td>${kindLabel(x.kind)}</td>
          <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${(x.label || "").replace(/"/g, "&quot;")}">${x.label || "—"}</td>
          <td class="muted">${x.n_results}</td></tr>`).join("")
      }</tbody></table>`;
      el.querySelectorAll(".rs-run-row").forEach((row) =>
        row.addEventListener("click", () => {
          el.querySelectorAll(".rs-run-row").forEach((r2) => (r2.style.background = ""));
          row.style.background = "rgba(88,166,255,.12)";
          loadDetail(row.dataset.id, row.querySelector('td:nth-child(4)').title || row.querySelector('td:nth-child(4)').textContent);
        }));
    } catch (e) {
      el.innerHTML = `<span class="neg">Hata: ${e.message}</span>`;
    }
  }

  async function loadTop() {
    const el = document.getElementById("rs-top");
    const metric = document.getElementById("rs-metric").value;
    const kind = document.getElementById("rs-kind").value;
    el.innerHTML = `<div class="spinner">⏳ …</div>`;
    try {
      const q = `/api/results/top?metric=${metric}&limit=25${kind ? "&kind=" + encodeURIComponent(kind) : ""}`;
      const r = await API.get(q);
      const rows = r.results || [];
      if (!rows.length) { el.innerHTML = `<div class="muted" style="font-size:13px">Bu metrikte kayıtlı sonuç yok.</div>`; return; }
      el.innerHTML = `<table><thead><tr>
        <th>sembol / isim</th><th>itv</th><th>Sharpe</th><th>getiri%</th><th>DD%</th><th>işlem</th><th>tür</th><th>tarih</th>
        </tr></thead><tbody>${
        rows.map((x) => `<tr>
          <td>${x.name || x.symbol || "—"}</td>
          <td class="muted">${x.interval || ""}</td>
          ${cell(x.sharpe)}${cell(x.total_return, 1)}${cell(x.max_drawdown, 1)}
          <td class="muted">${x.num_trades == null ? "—" : fmt(x.num_trades, 0)}</td>
          <td>${kindLabel(x.kind)}</td>
          <td class="muted" style="font-size:11px">${(x.created_at || "").slice(0, 10)}</td></tr>`).join("")
      }</tbody></table>`;
    } catch (e) {
      el.innerHTML = `<span class="neg">Hata: ${e.message}</span>`;
    }
  }

  async function loadDetail(runId, label) {
    document.getElementById("rs-detail-title").textContent = `Çalıştırma #${runId}`;
    document.getElementById("rs-detail-meta").textContent = label || "";
    const el = document.getElementById("rs-detail");
    el.innerHTML = `<div class="spinner">⏳ Yükleniyor…</div>`;
    try {
      const r = await API.get(`/api/results/runs/${runId}?limit=500`);
      const rows = r.results || [];
      if (!rows.length) { el.innerHTML = `<div class="muted">Sonuç yok.</div>`; return; }
      el.innerHTML = `<div style="max-height:520px;overflow:auto"><table><thead><tr>
        <th>#</th><th>sembol / isim</th><th>itv</th><th>Sharpe</th><th>getiri%</th><th>DD%</th><th>işlem</th><th>skor</th>
        </tr></thead><tbody>${
        rows.map((x) => `<tr>
          <td class="muted">${x.rank == null ? "" : x.rank}</td>
          <td>${x.name || x.symbol || "—"}</td>
          <td class="muted">${x.interval || ""}</td>
          ${cell(x.sharpe)}${cell(x.total_return, 1)}${cell(x.max_drawdown, 1)}
          <td class="muted">${x.num_trades == null ? "—" : fmt(x.num_trades, 0)}</td>
          ${cell(x.score)}</tr>`).join("")
      }</tbody></table></div>`;
    } catch (e) {
      el.innerHTML = `<span class="neg">Hata: ${e.message}</span>`;
    }
  }

  window.Results = { init };
})();
