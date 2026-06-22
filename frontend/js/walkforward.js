// Walk-Forward Analizi modülü
(function () {
  const OBJ_LABELS = {
    sharpe: "Sharpe", sortino: "Sortino", total_return: "Toplam Getiri",
    calmar: "Calmar", profit_factor: "Profit Factor", win_rate: "Kazanma %", max_drawdown: "Min. Düşüş",
  };
  let wfChart, wfSeries;

  async function init() {
    try {
      const r = await API.get("/api/optimize/examples");
      document.getElementById("wf-objective").innerHTML = r.objectives.map((o) =>
        `<option value="${o}" ${o === "sharpe" ? "selected" : ""}>${OBJ_LABELS[o] || o}</option>`).join("");
      // varsayılan örnek doldur
      const ex = r.examples[0];
      document.getElementById("wf-entry").value = ex.entry;
      document.getElementById("wf-exit").value = ex.exit || "";
      const preset = {}; (ex.params || []).forEach((p) => (preset[p.name] = p));
      detectParams(preset);
    } catch (e) {}
    ["wf-entry", "wf-exit"].forEach((id) =>
      document.getElementById(id).addEventListener("input", () => detectParams()));
    document.getElementById("wf-run").addEventListener("click", run);
  }

  function currentValues() {
    const map = {};
    document.querySelectorAll("#wf-params .opt-param").forEach((row) => {
      map[row.dataset.name] = { min: row.querySelector(".pmin").value, max: row.querySelector(".pmax").value, step: row.querySelector(".pstep").value };
    });
    return map;
  }

  function detectParams(preset) {
    const text = document.getElementById("wf-entry").value + " " + document.getElementById("wf-exit").value;
    const names = [...new Set([...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]))];
    const existing = { ...currentValues(), ...(preset || {}) };
    const box = document.getElementById("wf-params");
    if (!names.length) { box.innerHTML = `<div class="muted" style="font-size:12px">Şablona <code>{ad}</code> yazın.</div>`; return; }
    box.innerHTML = names.map((n) => {
      const p = existing[n] || {};
      return `<div class="opt-param" data-name="${n}"><span class="pname">{${n}}</span>
        <input class="pmin" type="number" placeholder="min" value="${p.min ?? 5}" />
        <input class="pmax" type="number" placeholder="max" value="${p.max ?? 50}" />
        <input class="pstep" type="number" placeholder="adım" value="${p.step ?? 5}" /></div>`;
    }).join("");
  }

  function gatherParams() {
    return [...document.querySelectorAll("#wf-params .opt-param")].map((row) => ({
      name: row.dataset.name,
      min: parseInt(row.querySelector(".pmin").value),
      max: parseInt(row.querySelector(".pmax").value),
      step: Math.max(parseInt(row.querySelector(".pstep").value) || 1, 1),
    }));
  }

  const num = (id) => { const v = parseFloat(document.getElementById(id).value); return isNaN(v) ? null : v; };

  async function run() {
    const params = gatherParams();
    const el = document.getElementById("wf-validate");
    if (!params.length) { el.textContent = "✕ En az bir {param} gerekli"; el.className = "validate-msg err"; return; }
    el.textContent = "";
    const body = {
      symbol: document.getElementById("wf-symbol").value.trim(),
      entry_template: document.getElementById("wf-entry").value.trim(),
      exit_template: document.getElementById("wf-exit").value.trim() || null,
      params,
      interval: document.getElementById("wf-interval").value,
      range: document.getElementById("wf-range").value,
      direction: document.getElementById("wf-direction").value,
      method: document.getElementById("wf-method").value,
      objective: document.getElementById("wf-objective").value,
      n_trials: parseInt(document.getElementById("wf-trials").value) || 60,
      train_bars: parseInt(document.getElementById("wf-train").value) || 252,
      test_bars: parseInt(document.getElementById("wf-test").value) || 63,
      fee_bps: (num("wf-fee") || 0) * 100,
    };
    const meta = document.getElementById("wf-meta");
    meta.textContent = "Walk-forward çalışıyor… (her pencerede optimizasyon + OOS test)";
    document.getElementById("wf-summary").innerHTML = "";
    document.getElementById("wf-folds").innerHTML = `<div class="spinner">⏳ Pencereler işleniyor…</div>`;
    try {
      const r = await API.post("/api/walkforward", body);
      const s = r.summary;
      meta.innerHTML = `<b>${r.symbol}</b> · ${r.method.toUpperCase()} · ${OBJ_LABELS[r.objective]} · ${s.folds} pencere · eğitim ${r.train_bars}/test ${r.test_bars} bar`;
      renderSummary(s);
      renderEquity(r.equity);
      renderFolds(r.folds);
    } catch (e) {
      meta.innerHTML = `<span class="neg">Hata: ${e.message}</span>`;
      document.getElementById("wf-folds").innerHTML = "";
    }
  }

  function renderSummary(s) {
    const sign = (v) => (v >= 0 ? "pos" : "neg");
    const overfit = s.avg_is_score > 0 && s.avg_oos_return <= 0;
    const cards = [
      ["OOS Getiri (birleşik)", fmt(s.oos_total_return) + "%", sign(s.oos_total_return)],
      ["OOS Sharpe", fmt(s.oos_sharpe), sign(s.oos_sharpe)],
      ["OOS Min. Düşüş", fmt(s.oos_max_drawdown) + "%", "neg"],
      ["Kârlı Pencere", s.profitable_folds + "/" + s.valid_folds + " (" + fmt(s.profitable_pct) + "%)", ""],
      ["Ort. OOS Getiri", fmt(s.avg_oos_return) + "%", sign(s.avg_oos_return)],
      ["Ort. IS Skor", fmt(s.avg_is_score, 3), ""],
      ["Son Bakiye", fmt(s.final_equity), ""],
      ["Aşırı Uyum?", overfit ? "⚠ Riskli" : "✓ Sağlıklı", overfit ? "neg" : "pos"],
    ];
    document.getElementById("wf-summary").innerHTML = cards.map(([k, v, c]) =>
      `<div class="metric"><div class="k">${k}</div><div class="v ${c}">${v}</div></div>`).join("");
  }

  function renderEquity(equity) {
    const el = document.getElementById("wf-equity");
    if (!equity || !equity.length) { el.style.display = "none"; return; }
    el.style.display = "block";
    if (!wfChart) {
      wfChart = LightweightCharts.createChart(el, {
        layout: { background: { color: "#161b22" }, textColor: "#8b949e" },
        grid: { vertLines: { color: "#1c2430" }, horzLines: { color: "#1c2430" } },
        rightPriceScale: { borderColor: "#2a3340" }, timeScale: { borderColor: "#2a3340" },
        width: el.clientWidth, height: 260,
      });
      wfSeries = wfChart.addAreaSeries({ lineColor: "#3fb950", topColor: "rgba(63,185,80,.3)", bottomColor: "rgba(63,185,80,0)", lineWidth: 2 });
      new ResizeObserver(() => wfChart.applyOptions({ width: el.clientWidth })).observe(el);
    }
    wfSeries.setData(equity.map((p) => ({ time: p.time, value: p.value })));
    wfChart.timeScale().fitContent();
  }

  function renderFolds(folds) {
    const el = document.getElementById("wf-folds");
    const rows = folds.map((f) => {
      const p = f.params ? Object.entries(f.params).map(([k, v]) => `${k}=${v}`).join(" ") : "—";
      const r = f.oos_return;
      return `<tr>
        <td>#${f.fold}</td>
        <td class="muted">${f.train_start}→${f.train_end}</td>
        <td class="muted">${f.test_start}→${f.test_end}</td>
        <td style="font-family:monospace;font-size:11px">${p}</td>
        <td>${f.is_score ?? "—"}</td>
        <td class="${r >= 0 ? "pos" : "neg"}">${r == null ? "—" : (r >= 0 ? "+" : "") + fmt(r)}%</td>
        <td>${f.oos_sharpe ?? "—"}</td>
        <td class="muted">${f.oos_trades}</td></tr>`;
    }).join("");
    el.innerHTML = `<table><thead><tr>
      <th>#</th><th>Eğitim</th><th>Test</th><th>En iyi param</th><th>IS skor</th><th>OOS Getiri</th><th>OOS Sharpe</th><th>İşlem</th>
      </tr></thead><tbody>${rows}</tbody></table>`;
  }

  window.WalkForward = { init };
})();
