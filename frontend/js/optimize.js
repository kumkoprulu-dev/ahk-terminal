// Parametre Optimizasyonu modülü
(function () {
  const OBJ_LABELS = {
    sharpe: "Sharpe", sortino: "Sortino", total_return: "Toplam Getiri",
    calmar: "Calmar", profit_factor: "Profit Factor", win_rate: "Kazanma %",
    max_drawdown: "Min. Düşüş",
  };
  let examples = [];

  async function init() {
    try {
      const r = await API.get("/api/optimize/examples");
      examples = r.examples;
      document.getElementById("opt-objective").innerHTML = r.objectives.map((o) =>
        `<option value="${o}" ${o === "sharpe" ? "selected" : ""}>${OBJ_LABELS[o] || o}</option>`).join("");
      document.getElementById("opt-examples").innerHTML = examples.map((e, i) =>
        `<button class="ghost example" data-i="${i}">${e.name}<small>↳ ${e.entry}</small></button>`).join("");
      document.querySelectorAll("#opt-examples .example").forEach((b) =>
        b.addEventListener("click", () => loadExample(examples[b.dataset.i])));
    } catch (e) {}

    ["opt-entry", "opt-exit"].forEach((id) =>
      document.getElementById(id).addEventListener("input", () => detectParams()));
    document.getElementById("opt-run").addEventListener("click", run);
    detectParams();
  }

  function loadExample(e) {
    document.getElementById("opt-entry").value = e.entry;
    document.getElementById("opt-exit").value = e.exit || "";
    const preset = {};
    (e.params || []).forEach((p) => (preset[p.name] = p));
    detectParams(preset);
  }

  function currentParamValues() {
    const map = {};
    document.querySelectorAll("#opt-params .opt-param").forEach((row) => {
      map[row.dataset.name] = {
        min: row.querySelector(".pmin").value,
        max: row.querySelector(".pmax").value,
        step: row.querySelector(".pstep").value,
      };
    });
    return map;
  }

  function detectParams(preset) {
    const text = document.getElementById("opt-entry").value + " " + document.getElementById("opt-exit").value;
    const names = [...new Set([...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]))];
    const existing = { ...currentParamValues(), ...(preset || {}) };
    const box = document.getElementById("opt-params");
    if (!names.length) {
      box.innerHTML = `<div class="muted" style="font-size:12px">Şablona <code>{ad}</code> yazınca otomatik belirir.</div>`;
      updateCombos();
      return;
    }
    box.innerHTML = names.map((n) => {
      const p = existing[n] || {};
      return `<div class="opt-param" data-name="${n}">
        <span class="pname">{${n}}</span>
        <input class="pmin" type="number" placeholder="min" value="${p.min ?? 5}" />
        <input class="pmax" type="number" placeholder="max" value="${p.max ?? 50}" />
        <input class="pstep" type="number" placeholder="adım" value="${p.step ?? 5}" /></div>`;
    }).join("");
    box.querySelectorAll("input").forEach((i) => i.addEventListener("input", updateCombos));
    updateCombos();
  }

  function gatherParams() {
    return [...document.querySelectorAll("#opt-params .opt-param")].map((row) => ({
      name: row.dataset.name,
      min: parseInt(row.querySelector(".pmin").value),
      max: parseInt(row.querySelector(".pmax").value),
      step: Math.max(parseInt(row.querySelector(".pstep").value) || 1, 1),
    }));
  }

  function updateCombos() {
    const params = gatherParams();
    let combos = params.length ? 1 : 0;
    params.forEach((p) => {
      const cnt = Math.max(Math.floor((p.max - p.min) / p.step) + 1, 1);
      combos *= cnt;
    });
    const el = document.getElementById("opt-validate");
    el.className = "validate-msg";
    el.textContent = combos ? `≈ ${combos.toLocaleString("tr-TR")} kombinasyon` : "";
  }

  const num = (id) => { const v = parseFloat(document.getElementById(id).value); return isNaN(v) ? null : v; };

  async function run() {
    const params = gatherParams();
    if (!params.length) {
      const el = document.getElementById("opt-validate");
      el.textContent = "✕ En az bir {param} ve aralığı gerekli"; el.className = "validate-msg err"; return;
    }
    const body = {
      symbol: document.getElementById("opt-symbol").value.trim(),
      entry_template: document.getElementById("opt-entry").value.trim(),
      exit_template: document.getElementById("opt-exit").value.trim() || null,
      params,
      interval: document.getElementById("opt-interval").value,
      range: document.getElementById("opt-range").value,
      direction: document.getElementById("opt-direction").value,
      method: document.getElementById("opt-method").value,
      objective: document.getElementById("opt-objective").value,
      n_trials: parseInt(document.getElementById("opt-trials").value) || 150,
      fee_bps: (num("opt-fee") || 0) * 100,
    };
    const meta = document.getElementById("opt-meta");
    meta.textContent = "Optimizasyon çalışıyor… (binlerce kombinasyon test ediliyor)";
    document.getElementById("opt-best").innerHTML = "";
    document.getElementById("opt-results").innerHTML = `<div class="spinner">⏳ Hesaplanıyor…</div>`;
    try {
      const r = await API.post("/api/optimize", body);
      meta.innerHTML = `<b>${r.symbol}</b> · ${r.method.toUpperCase()} · ${OBJ_LABELS[r.objective] || r.objective} · ${r.evaluated}/${r.total_combos.toLocaleString("tr-TR")} kombinasyon test edildi`;
      renderBest(r);
      renderResults(r);
    } catch (e) {
      meta.innerHTML = `<span class="neg">Hata: ${e.message}</span>`;
      document.getElementById("opt-results").innerHTML = "";
    }
  }

  function subst(tpl, params) {
    let out = tpl || "";
    Object.entries(params).forEach(([k, v]) => (out = out.replaceAll("{" + k + "}", v)));
    return out;
  }

  function renderBest(r) {
    if (!r.best) { document.getElementById("opt-best").innerHTML = `<div class="muted">Geçerli sonuç yok (işlem üreten kombinasyon bulunamadı).</div>`; return; }
    const b = r.best, m = b.metrics;
    const pstr = Object.entries(b.params).map(([k, v]) => `${k}=${v}`).join(", ");
    document.getElementById("opt-best").innerHTML = `<div class="best-card">
      <div class="bp">🏆 En iyi: ${pstr}</div>
      <div class="metrics-grid">
        <div class="metric"><div class="k">Getiri</div><div class="v ${m.total_return>=0?'pos':'neg'}">${fmt(m.total_return)}%</div></div>
        <div class="metric"><div class="k">Sharpe</div><div class="v">${fmt(m.sharpe)}</div></div>
        <div class="metric"><div class="k">Min. Düşüş</div><div class="v neg">${fmt(m.max_drawdown)}%</div></div>
        <div class="metric"><div class="k">İşlem</div><div class="v">${m.num_trades}</div></div>
        <div class="metric"><div class="k">Kazanma</div><div class="v">${fmt(m.win_rate)}%</div></div>
      </div>
      <button class="primary" id="opt-send" style="margin-top:10px">Strateji sekmesinde aç →</button></div>`;
    document.getElementById("opt-send").addEventListener("click", () => sendToStrategy(r, r.best.params));
  }

  function sendToStrategy(r, params) {
    document.getElementById("bt-symbol").value = document.getElementById("opt-symbol").value;
    document.getElementById("bt-entry").value = subst(r.entry_template, params);
    document.getElementById("bt-exit").value = subst(r.exit_template, params);
    document.getElementById("bt-range").value = document.getElementById("opt-range").value;
    document.getElementById("bt-direction").value = document.getElementById("opt-direction").value;
    document.querySelector('.tab[data-view="strategy"]').click();
    document.getElementById("bt-run").click();
  }

  function renderResults(r) {
    const el = document.getElementById("opt-results");
    if (!r.results.length) { el.innerHTML = ""; return; }
    const pnames = Object.keys(r.results[0].params);
    const head = `<tr>${pnames.map((p) => `<th>${p}</th>`).join("")}
      <th>Getiri%</th><th>Sharpe</th><th>MaxDD%</th><th>İşlem</th><th>Kazanma%</th><th>Skor</th></tr>`;
    const rows = r.results.map((res, i) => {
      const m = res.metrics;
      return `<tr class="${i === 0 ? "best" : ""}" data-i="${i}">
        ${pnames.map((p) => `<td>${res.params[p]}</td>`).join("")}
        <td class="${m.total_return>=0?'pos':'neg'}">${fmt(m.total_return)}</td>
        <td>${fmt(m.sharpe)}</td><td class="neg">${fmt(m.max_drawdown)}</td>
        <td class="muted">${m.num_trades}</td><td>${fmt(m.win_rate)}</td>
        <td><b>${res.score ?? "—"}</b></td></tr>`;
    }).join("");
    el.innerHTML = `<table><thead>${head}</thead><tbody>${rows}</tbody></table>`;
    el.querySelectorAll("tbody tr").forEach((tr) =>
      tr.addEventListener("click", () => sendToStrategy(r, r.results[tr.dataset.i].params)));
  }

  window.Optimize = { init };
})();
