// Tarayıcı modülü
(function () {
  let sortKey = "change", sortDir = -1;
  let lastMatches = [];

  async function init() {
    // universe listesi
    try {
      const u = await API.get("/api/universes");
      const sel = document.getElementById("scan-universe");
      sel.innerHTML = u.universes.map((x) => `<option value="${x.id}">${x.label} (${x.count})</option>`).join("");
    } catch (e) {}

    // örnek kurallar
    try {
      const ex = await API.get("/api/scan/examples");
      document.getElementById("scan-examples").innerHTML = ex.examples.map((e) =>
        `<button class="ghost example" data-rule="${e.rule.replace(/"/g, "&quot;")}">${e.name}<small>${e.rule}</small></button>`
      ).join("");
      document.querySelectorAll(".example").forEach((b) =>
        b.addEventListener("click", () => {
          document.getElementById("scan-rule").value = b.dataset.rule;
          validate();
        }));
    } catch (e) {}

    const rule = document.getElementById("scan-rule");
    let vt;
    rule.addEventListener("input", () => { clearTimeout(vt); vt = setTimeout(validate, 400); });
    document.getElementById("scan-run").addEventListener("click", run);

    async function nlBuild() {
      const text = document.getElementById("scan-nl").value.trim();
      if (!text) return;
      try {
        const r = await API.post("/api/formula", { text });
        document.getElementById("scan-rule").value = r.rule || "";
        await validate();
        if (!r.valid && r.error) { const el = document.getElementById("scan-validate"); el.textContent = "⚠ " + r.error; el.className = "validate-msg err"; }
      } catch (e) {}
    }
    document.getElementById("scan-nl-btn").addEventListener("click", nlBuild);
    document.getElementById("scan-nl").addEventListener("keydown", (e) => { if (e.key === "Enter") nlBuild(); });
  }

  async function validate() {
    const rule = document.getElementById("scan-rule").value.trim();
    const el = document.getElementById("scan-validate");
    if (!rule) { el.textContent = ""; return true; }
    try {
      const r = await API.post("/api/scan/validate", { rule });
      if (r.valid) { el.textContent = "✓ Kural geçerli"; el.className = "validate-msg ok"; return true; }
      el.textContent = "✕ " + r.error; el.className = "validate-msg err"; return false;
    } catch (e) { el.textContent = "✕ " + e.message; el.className = "validate-msg err"; return false; }
  }

  async function run() {
    const rule = document.getElementById("scan-rule").value.trim();
    if (!rule) return;
    if (!(await validate())) return;
    const universe = document.getElementById("scan-universe").value;
    const range = document.getElementById("scan-range").value;
    const meta = document.getElementById("scan-meta");
    const res = document.getElementById("scan-results");
    meta.textContent = `${universe} taranıyor…`;
    res.innerHTML = `<div class="spinner">⏳ Hesaplanıyor, lütfen bekleyin…</div>`;
    try {
      const r = await API.post("/api/scan", { universe, rule, range });
      lastMatches = r.matches;
      meta.innerHTML = `<b>${r.match_count}</b> eşleşme · ${r.scanned} sembol tarandı${r.errors ? ` · ${r.errors} hata` : ""}`;
      renderTable();
    } catch (e) {
      meta.innerHTML = `<span class="neg">Hata: ${e.message}</span>`;
      res.innerHTML = "";
    }
  }

  function renderTable() {
    const res = document.getElementById("scan-results");
    if (!lastMatches.length) { res.innerHTML = `<div class="spinner">Eşleşme yok. Kuralı gevşetmeyi deneyin.</div>`; return; }
    const sorted = [...lastMatches].sort((a, b) => (a[sortKey] > b[sortKey] ? 1 : -1) * sortDir);
    const head = `<tr>
      <th data-k="symbol">Sembol</th>
      <th data-k="price">Fiyat</th>
      <th data-k="change">Değişim %</th>
      <th data-k="rsi">RSI</th>
      <th data-k="volume">Hacim</th></tr>`;
    const rows = sorted.map((m) => `<tr data-sym="${m.symbol}">
      <td>${m.symbol}</td>
      <td>${fmt(m.price)}</td>
      <td class="${m.change >= 0 ? "pos" : "neg"}">${m.change >= 0 ? "+" : ""}${fmt(m.change)}</td>
      <td>${m.rsi == null ? "—" : fmt(m.rsi, 1)}</td>
      <td class="muted">${(m.volume || 0).toLocaleString("tr-TR")}</td></tr>`).join("");
    res.innerHTML = `<table><thead>${head}</thead><tbody>${rows}</tbody></table>`;
    res.querySelectorAll("th").forEach((th) =>
      th.addEventListener("click", () => {
        const k = th.dataset.k;
        if (k === sortKey) sortDir *= -1; else { sortKey = k; sortDir = -1; }
        renderTable();
      }));
    res.querySelectorAll("tbody tr").forEach((tr) =>
      tr.addEventListener("click", () => switchToChart(tr.dataset.sym)));
  }

  window.Scanner = { init };
})();
