// Canlı Runner Kontrolü — risk-paritesi başlat yardımcısı + canlı sleeve izleme
(function () {
  const SCRIPT_LABELS = {
    run_combo_portfolio: "Kripto Combo1", run_xsec: "Kripto cross-sectional",
    run_bist_combo: "BIST Combo1",
  };
  const cell = (v, d = 2) => (v == null ? '<td class="muted">—</td>' : `<td class="${v >= 0 ? "pos" : "neg"}">${fmt(v, d)}</td>`);
  let timer = null;

  async function init() {
    document.getElementById("cl-alloc-btn").addEventListener("click", allocate);
    document.querySelectorAll(".tab").forEach((t) =>
      t.addEventListener("click", () => {
        if (timer) { clearInterval(timer); timer = null; }
        if (t.dataset.view === "canli") { loadMonitor(); timer = setInterval(loadMonitor, 7000); }
      }));
  }

  async function allocate() {
    const crypto_total = parseFloat(document.getElementById("cl-crypto").value) || 3000;
    const bist_total = parseFloat(document.getElementById("cl-bist").value) || 300000;
    const el = document.getElementById("cl-alloc");
    el.innerHTML = `<div class="spinner">⏳ Risk paritesi hesaplanıyor (kripto + BIST verisi çekiliyor, ~30 sn)…</div>`;
    try {
      const r = await API.post("/api/portfolio/edge/allocate", { crypto_total, bist_total });
      renderAlloc(r);
    } catch (e) {
      el.innerHTML = `<span class="neg">Hata: ${e.message}</span>`;
    }
  }

  function cmdRow(cmd) {
    return `<div style="display:flex;gap:8px;align-items:center;margin:4px 0">
      <code style="flex:1;background:var(--bg2);padding:6px 9px;border-radius:6px;font-size:12px;overflow-x:auto;white-space:nowrap">${cmd}</code>
      <button class="ghost cl-copy" data-cmd="${cmd.replace(/"/g, "&quot;")}">kopyala</button></div>`;
  }

  function renderAlloc(r) {
    const rows = r.sleeves.map((s) => `<tr>
      <td>${s.sleeve}</td><td><b>${fmt(s.weight, 1)}%</b></td>
      <td>${fmt(s.capital, 0)} ${s.ccy}</td><td class="muted">:${s.port}</td></tr>`).join("");
    const cmds = r.sleeves.map((s) => cmdRow(s.command)).join("") +
      cmdRow(r.coordinator.split("  #")[0].trim());
    document.getElementById("cl-alloc").innerHTML = `
      <table><thead><tr><th>sleeve</th><th>ağırlık</th><th>sermaye</th><th>port</th></tr></thead><tbody>${rows}</tbody></table>
      <div class="muted" style="font-size:11px;margin:8px 0 4px">${r.note}</div>
      <div style="margin-top:6px"><b style="font-size:12px">Başlatma komutları</b>
        <span class="muted" style="font-size:11px">(platform venv python'u ile, <code>execution/zargan_quant</code> altında, ayrı pencerelerde)</span></div>
      ${cmds}`;
    document.querySelectorAll(".cl-copy").forEach((b) =>
      b.addEventListener("click", () => {
        navigator.clipboard.writeText(b.dataset.cmd);
        b.textContent = "✓"; setTimeout(() => (b.textContent = "kopyala"), 1200);
      }));
  }

  async function loadMonitor() {
    const el = document.getElementById("cl-monitor");
    const totEl = document.getElementById("cl-total");
    try {
      const r = await API.get("/api/results/live?limit=20");
      const sess = r.sessions || [];
      if (!sess.length) {
        totEl.textContent = "—";
        el.innerHTML = `<div class="muted" style="font-size:13px">Aktif canlı oturum yok. Yukarıdaki komutlarla başlatın (--save-every ile DB'ye yazar).</div>`;
        return;
      }
      const seen = new Set();
      const latest = sess.filter((s) => { if (seen.has(s.script)) return false; seen.add(s.script); return true; });
      const combined = latest.reduce((a, s) => a + (s.net_pnl || 0), 0);
      totEl.textContent = fmt(combined, 2);
      totEl.className = combined >= 0 ? "pos" : "neg";
      el.innerHTML = `<table><thead><tr>
        <th>sleeve</th><th>net PnL</th><th>realized</th><th>açık/sembol</th><th>snapshot</th><th>son</th>
        </tr></thead><tbody>${
        sess.map((s) => {
          const stale = latest.includes(s) ? "" : ' style="opacity:.5"';
          return `<tr${stale}><td>🟢 ${SCRIPT_LABELS[s.script] || s.script}</td>
            ${cell(s.net_pnl)}${cell(s.realized)}
            <td class="muted">${s.positions}/${s.symbols}</td>
            <td class="muted">${s.snaps}</td>
            <td class="muted" style="font-size:11px">${(s.last_ts || "").slice(11, 19)}</td></tr>`;
        }).join("")
      }</tbody></table>
      <div class="muted" style="font-size:11px;margin-top:6px">Birleşik = her script'in en son oturumu (soluk satır = eski oturum). Para birimleri ayrı (USDT/TRY).</div>`;
    } catch (e) {
      el.innerHTML = `<span class="neg">Hata: ${e.message}</span>`;
    }
  }

  window.Canli = { init };
})();
