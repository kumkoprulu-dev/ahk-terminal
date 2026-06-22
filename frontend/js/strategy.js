// Strateji / Backtest modülü
(function () {
  let equityChart, equitySeries;

  async function init() {
    try {
      const ex = await API.get("/api/backtest/examples");
      document.getElementById("bt-examples").innerHTML = ex.examples.map((e, i) =>
        `<button class="ghost example" data-i="${i}">${e.name}<small>↳ ${e.entry}${e.exit ? " · ⤴ " + e.exit : ""}</small></button>`
      ).join("");
      document.querySelectorAll("#bt-examples .example").forEach((b) =>
        b.addEventListener("click", () => {
          const e = ex.examples[b.dataset.i];
          document.getElementById("bt-entry").value = e.entry;
          document.getElementById("bt-exit").value = e.exit || "";
          validate();
        }));
    } catch (e) {}

    let vt;
    ["bt-entry", "bt-exit"].forEach((id) =>
      document.getElementById(id).addEventListener("input", () => { clearTimeout(vt); vt = setTimeout(validate, 400); }));
    document.getElementById("bt-run").addEventListener("click", run);

    async function nlBuild() {
      const text = document.getElementById("bt-nl").value.trim();
      if (!text) return;
      try {
        const r = await API.post("/api/formula", { text });
        document.getElementById("bt-entry").value = r.rule || "";
        await validate();
        if (!r.valid && r.error) { const el = document.getElementById("bt-validate"); el.textContent = "⚠ " + r.error; el.className = "validate-msg err"; }
      } catch (e) {}
    }
    document.getElementById("bt-nl-btn").addEventListener("click", nlBuild);
    document.getElementById("bt-nl").addEventListener("keydown", (e) => { if (e.key === "Enter") nlBuild(); });

    const g = (id) => document.getElementById(id).value;
    const s = (id, v) => { if (v != null) document.getElementById(id).value = v; };
    window.Auth.bindSaved({
      saveBtn: "bt-save", loadSel: "bt-load", delBtn: "bt-del", kind: "strategy",
      getData: () => ({ symbol: g("bt-symbol"), entry: g("bt-entry"), exit: g("bt-exit"),
        interval: g("bt-interval"), range: g("bt-range"), direction: g("bt-direction"),
        cash: g("bt-cash"), fee: g("bt-fee"), stop: g("bt-stop"), target: g("bt-target") }),
      setData: (d) => { ["symbol", "entry", "exit", "interval", "range", "direction", "cash", "fee", "stop", "target"]
        .forEach((k) => s("bt-" + k, d[k])); validate(); },
    });
  }

  async function validate() {
    const el = document.getElementById("bt-validate");
    const entry = document.getElementById("bt-entry").value.trim();
    const exit = document.getElementById("bt-exit").value.trim();
    if (!entry) { el.textContent = ""; return false; }
    try {
      for (const [label, rule] of [["Giriş", entry], ["Çıkış", exit]]) {
        if (!rule) continue;
        const r = await API.post("/api/scan/validate", { rule });
        if (!r.valid) { el.textContent = `✕ ${label}: ${r.error}`; el.className = "validate-msg err"; return false; }
      }
      el.textContent = "✓ Kurallar geçerli"; el.className = "validate-msg ok"; return true;
    } catch (e) { el.textContent = "✕ " + e.message; el.className = "validate-msg err"; return false; }
  }

  const num = (id) => { const v = parseFloat(document.getElementById(id).value); return isNaN(v) ? null : v; };

  async function run() {
    if (!(await validate())) return;
    const body = {
      symbol: document.getElementById("bt-symbol").value.trim(),
      entry_rule: document.getElementById("bt-entry").value.trim(),
      exit_rule: document.getElementById("bt-exit").value.trim() || null,
      interval: document.getElementById("bt-interval").value,
      range: document.getElementById("bt-range").value,
      direction: document.getElementById("bt-direction").value,
      initial_cash: num("bt-cash") || 10000,
      fee_bps: (num("bt-fee") || 0) * 100, // yüzde -> baz puan (%0.1 = 10 bps)
      stop_loss: num("bt-stop"),
      take_profit: num("bt-target"),
    };
    const meta = document.getElementById("bt-meta");
    meta.textContent = "Backtest çalışıyor…";
    document.getElementById("bt-metrics").innerHTML = "";
    document.getElementById("bt-trades").innerHTML = "";
    try {
      const r = await API.post("/api/backtest", body);
      renderMetrics(r.metrics);
      renderEquity(r.equity);
      renderTrades(r.trades);
      meta.innerHTML = `<b>${body.symbol}</b> · ${r.metrics.num_trades} işlem · ${body.range} · ${body.direction.toUpperCase()}`;
    } catch (e) {
      meta.innerHTML = `<span class="neg">Hata: ${e.message}</span>`;
    }
  }

  function renderMetrics(m) {
    const signed = (v) => (v >= 0 ? "pos" : "neg");
    const cards = [
      ["Toplam Getiri", m.total_return + "%", signed(m.total_return)],
      ["Al-Tut", m.buy_hold_return + "%", signed(m.buy_hold_return)],
      ["CAGR", m.cagr + "%", signed(m.cagr)],
      ["Sharpe", m.sharpe, signed(m.sharpe)],
      ["Sortino", m.sortino, signed(m.sortino)],
      ["Maks. Düşüş", m.max_drawdown + "%", "neg"],
      ["Calmar", m.calmar, signed(m.calmar)],
      ["Kazanma", m.win_rate + "%", ""],
      ["Profit Factor", m.profit_factor, signed(m.profit_factor - 1)],
      ["İşlem", m.num_trades, ""],
      ["Ort. Kazanç", m.avg_win + "%", "pos"],
      ["Ort. Kayıp", m.avg_loss + "%", "neg"],
      ["Piyasada", m.exposure + "%", ""],
      ["Son Bakiye", fmt(m.final_equity), ""],
    ];
    document.getElementById("bt-metrics").innerHTML = cards.map(([k, v, cls]) =>
      `<div class="metric"><div class="k">${k}</div><div class="v ${cls}">${v}</div></div>`
    ).join("");
  }

  function renderEquity(equity) {
    const el = document.getElementById("bt-equity");
    el.style.display = "block";
    if (!equityChart) {
      equityChart = LightweightCharts.createChart(el, {
        layout: { background: { color: "#161b22" }, textColor: "#8b949e" },
        grid: { vertLines: { color: "#1c2430" }, horzLines: { color: "#1c2430" } },
        rightPriceScale: { borderColor: "#2a3340" },
        timeScale: { borderColor: "#2a3340" },
        width: el.clientWidth, height: 280,
      });
      equitySeries = equityChart.addAreaSeries({
        lineColor: "#2f81f7", topColor: "rgba(47,129,247,.3)", bottomColor: "rgba(47,129,247,0)", lineWidth: 2,
      });
      new ResizeObserver(() => equityChart.applyOptions({ width: el.clientWidth })).observe(el);
    }
    equitySeries.setData(equity.map((p) => ({ time: p.time, value: p.value })));
    equityChart.timeScale().fitContent();
  }

  function renderTrades(trades) {
    const el = document.getElementById("bt-trades");
    if (!trades.length) { el.innerHTML = `<div class="spinner">İşlem yok.</div>`; return; }
    const rows = trades.slice().reverse().map((t) => `<tr>
      <td>${t.entry_date}</td><td>${t.exit_date}</td>
      <td>${fmt(t.entry_price)}</td><td>${fmt(t.exit_price)}</td>
      <td class="${t.return_pct >= 0 ? "pos" : "neg"}">${t.return_pct >= 0 ? "+" : ""}${fmt(t.return_pct)}%</td>
      <td class="muted">${t.bars}</td>
      <td><span class="reason ${t.reason}">${t.reason}</span></td></tr>`).join("");
    el.innerHTML = `<table><thead><tr>
      <th>Giriş</th><th>Çıkış</th><th>Giriş F.</th><th>Çıkış F.</th><th>Getiri</th><th>Bar</th><th>Sebep</th>
      </tr></thead><tbody>${rows}</tbody></table>`;
  }

  window.Strategy = { init };
})();
