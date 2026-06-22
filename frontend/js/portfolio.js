// Portföy Optimizasyonu modülü
(function () {
  let symbols = [];
  let groups = [];

  async function init() {
    try {
      const u = await API.get("/api/universes");
      groups = u.universes;
      document.getElementById("pf-group").innerHTML = groups.map((g) =>
        `<option value="${g.id}">${g.label} (${g.count})</option>`).join("");
      const m = await API.get("/api/portfolio/methods");
      document.getElementById("pf-method").innerHTML = m.methods.map((x) =>
        `<option value="${x.id}" ${x.id === "max_sharpe" ? "selected" : ""}>${x.label}</option>`).join("");
    } catch (e) {}

    document.getElementById("pf-group").addEventListener("change", loadGroup);
    document.getElementById("pf-add-btn").addEventListener("click", addSymbol);
    document.getElementById("pf-add").addEventListener("keydown", (e) => { if (e.key === "Enter") addSymbol(); });
    document.getElementById("pf-run").addEventListener("click", run);

    window.Auth.bindSaved({
      saveBtn: "pf-save", loadSel: "pf-load", delBtn: "pf-del", kind: "portfolio",
      getData: () => ({ symbols: [...symbols],
        method: document.getElementById("pf-method").value,
        range: document.getElementById("pf-range").value,
        risk: document.getElementById("pf-risk").value,
        mc: document.getElementById("pf-mc").value,
        minfund: document.getElementById("pf-minfund").value,
        tilt: document.getElementById("pf-tilt").checked }),
      setData: (d) => {
        if (Array.isArray(d.symbols)) { symbols = d.symbols.slice(); renderChips(); }
        const set = (id, v) => { if (v != null) document.getElementById(id).value = v; };
        set("pf-method", d.method); set("pf-range", d.range); set("pf-risk", d.risk);
        set("pf-mc", d.mc); set("pf-minfund", d.minfund);
        if (d.tilt != null) document.getElementById("pf-tilt").checked = d.tilt;
      },
    });
    await loadGroup();
  }

  async function loadGroup() {
    const id = document.getElementById("pf-group").value;
    try {
      const r = await API.get("/api/universes/" + id);
      symbols = r.symbols.map((s) => s.symbol);
      renderChips();
    } catch (e) {}
  }

  function addSymbol() {
    const inp = document.getElementById("pf-add");
    const v = inp.value.trim().toUpperCase();
    if (v && !symbols.includes(v)) { symbols.push(v); renderChips(); }
    inp.value = "";
  }

  function renderChips() {
    document.getElementById("pf-symbols").innerHTML = symbols.map((s) =>
      `<span class="pf-chip">${s}<button data-s="${s}">✕</button></span>`).join("");
    document.querySelectorAll("#pf-symbols .pf-chip button").forEach((b) =>
      b.addEventListener("click", () => { symbols = symbols.filter((x) => x !== b.dataset.s); renderChips(); }));
  }

  const num = (id) => { const v = parseFloat(document.getElementById(id).value); return isNaN(v) ? null : v; };

  async function run() {
    if (symbols.length < 2) {
      const el = document.getElementById("pf-validate");
      el.textContent = "✕ En az 2 sembol gerekli"; el.className = "validate-msg err"; return;
    }
    document.getElementById("pf-validate").textContent = "";
    const body = {
      symbols, method: document.getElementById("pf-method").value,
      range: document.getElementById("pf-range").value,
      risk_tolerance: num("pf-risk") || 0.5,
      mc_horizon: parseInt(document.getElementById("pf-mc").value) || 21,
      min_fundamental: num("pf-minfund") || 0,
      fusion_tilt: document.getElementById("pf-tilt").checked,
    };
    const meta = document.getElementById("pf-meta");
    meta.textContent = "Optimize ediliyor… (veri çekiliyor, etkin sınır hesaplanıyor)";
    ["pf-metrics", "pf-weights", "pf-frontier", "pf-mc-cards", "pf-mc-hist", "pf-compare"].forEach((id) => document.getElementById(id).innerHTML = "");
    try {
      const r = await API.post("/api/portfolio/optimize", body);
      meta.innerHTML = `<b>${r.method_label}</b> · ${r.n_assets_total} sembol → ${r.metrics.n_holdings} pozisyon`;
      renderMetrics(r.metrics);
      renderWeights(r.weights);
      renderFrontier(r);
      renderMC(r.montecarlo);
      renderCompare(r.comparison, r.method);
    } catch (e) {
      meta.innerHTML = `<span class="neg">Hata: ${e.message}</span>`;
    }
  }

  function renderMetrics(m) {
    const cards = [
      ["Beklenen Getiri", fmt(m.exp_return) + "%", m.exp_return >= 0 ? "pos" : "neg"],
      ["Volatilite", fmt(m.volatility) + "%", ""],
      ["Sharpe", fmt(m.sharpe, 3), m.sharpe >= 1 ? "pos" : ""],
      ["Pozisyon", m.n_holdings, ""],
    ];
    document.getElementById("pf-metrics").innerHTML = cards.map(([k, v, c]) =>
      `<div class="metric"><div class="k">${k}</div><div class="v ${c}">${v}</div></div>`).join("");
  }

  function renderWeights(weights) {
    const max = Math.max(...weights.map((w) => w.weight), 1);
    document.getElementById("pf-weights").innerHTML = weights.map((w) =>
      `<div class="wbar"><span class="wsym">${w.symbol.replace(".IS", "").replace("-USD", "").replace("=F", "")}</span>
        <span class="track"><span class="fill" style="width:${(w.weight / max * 100).toFixed(1)}%"></span></span>
        <span class="wval">${fmt(w.weight)}%</span></div>`).join("");
  }

  function renderCompare(comp, current) {
    const rows = comp.map((c) => `<tr class="${c.method === current ? "best" : ""}">
      <td>${c.label}</td>
      <td class="${c.return >= 0 ? "pos" : "neg"}">${fmt(c.return)}%</td>
      <td>${fmt(c.risk)}%</td>
      <td><b>${fmt(c.sharpe, 3)}</b></td>
      <td class="muted">${c.n_assets}</td></tr>`).join("");
    document.getElementById("pf-compare").innerHTML = `<table><thead><tr>
      <th>Yöntem</th><th>Getiri</th><th>Risk</th><th>Sharpe</th><th>Hisse</th></tr></thead><tbody>${rows}</tbody></table>`;
  }

  // --- Etkin sınır SVG scatter (x=risk, y=getiri) ---
  function renderFrontier(r) {
    const W = 380, H = 240, pad = 34;
    const all = [...(r.cloud || []), ...(r.frontier || []), r.point];
    if (!all.length) { document.getElementById("pf-frontier").innerHTML = ""; return; }
    const xs = all.map((p) => p.risk), ys = all.map((p) => p.return);
    const xmin = Math.min(...xs), xmax = Math.max(...xs), ymin = Math.min(...ys), ymax = Math.max(...ys);
    const sx = (v) => pad + (v - xmin) / (xmax - xmin || 1) * (W - pad - 10);
    const sy = (v) => H - pad - (v - ymin) / (ymax - ymin || 1) * (H - pad - 10);

    const cloud = (r.cloud || []).map((p) => `<circle cx="${sx(p.risk).toFixed(1)}" cy="${sy(p.return).toFixed(1)}" r="1.6" fill="#3a4655" opacity="0.5"/>`).join("");
    const fr = (r.frontier || []);
    const frLine = fr.length ? `<polyline points="${fr.map((p) => `${sx(p.risk).toFixed(1)},${sy(p.return).toFixed(1)}`).join(" ")}" fill="none" stroke="#3fb950" stroke-width="2"/>` : "";
    const pt = r.point;
    const ptDot = `<circle cx="${sx(pt.risk).toFixed(1)}" cy="${sy(pt.return).toFixed(1)}" r="6" fill="#2f81f7" stroke="#fff" stroke-width="1.5"/>`;
    const axes = `<line x1="${pad}" y1="${H - pad}" x2="${W - 10}" y2="${H - pad}" stroke="#2a3340"/>
      <line x1="${pad}" y1="10" x2="${pad}" y2="${H - pad}" stroke="#2a3340"/>
      <text x="${W / 2}" y="${H - 6}" fill="#8b949e" font-size="10" text-anchor="middle">Risk (volatilite %)</text>
      <text x="10" y="${H / 2}" fill="#8b949e" font-size="10" text-anchor="middle" transform="rotate(-90 10 ${H / 2})">Getiri %</text>`;
    document.getElementById("pf-frontier").innerHTML =
      `<svg viewBox="0 0 ${W} ${H}" width="100%" style="display:block">${axes}${cloud}${frLine}${ptDot}</svg>
       <div class="muted" style="font-size:11px">🔵 Seçilen portföy · 🟢 etkin sınır · ⚪ rastgele portföyler</div>`;
  }

  // --- Monte Carlo: kartlar + histogram ---
  function renderMC(mc) {
    document.getElementById("pf-mc-h").textContent = mc.horizon_days;
    const cards = [
      [`VaR (%${mc.confidence})`, "-" + fmt(mc.var) + "%", "neg"],
      ["CVaR", "-" + fmt(mc.cvar) + "%", "neg"],
      ["Kâr Olasılığı", fmt(mc.prob_positive) + "%", "pos"],
      ["Beklenen", fmt(mc.expected) + "%", mc.expected >= 0 ? "pos" : "neg"],
    ];
    document.getElementById("pf-mc-cards").innerHTML = cards.map(([k, v, c]) =>
      `<div class="metric"><div class="k">${k}</div><div class="v ${c}">${v}</div></div>`).join("");

    const h = mc.hist || [];
    if (!h.length) { document.getElementById("pf-mc-hist").innerHTML = ""; return; }
    const W = 700, H = 120, n = h.length, bw = W / n;
    const maxN = Math.max(...h.map((b) => b.n), 1);
    const bars = h.map((b, i) =>
      `<rect x="${(i * bw).toFixed(1)}" y="${(H - b.n / maxN * H).toFixed(1)}" width="${(bw - 1).toFixed(1)}" height="${(b.n / maxN * H).toFixed(1)}" fill="${b.x < -mc.var ? "#ef5350" : "#2f81f7"}" opacity="0.8"/>`).join("");
    document.getElementById("pf-mc-hist").innerHTML =
      `<svg viewBox="0 0 ${W} ${H}" width="100%" style="display:block">${bars}</svg>
       <div class="muted" style="font-size:11px">Ufuk getiri dağılımı (10.000 senaryo) · kırmızı = VaR kuyruğu</div>`;
  }

  window.Portfolio = { init };
})();
