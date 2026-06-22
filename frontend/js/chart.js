// Grafik modülü: Lightweight Charts v4 (CDN global: LightweightCharts)
(function () {
  const COLORS = ["#2f81f7", "#d29922", "#a371f7", "#3fb950", "#db61a2", "#e3b341", "#56d4dd", "#f0883e"];
  const baseLayout = {
    layout: { background: { color: "#161b22" }, textColor: "#8b949e" },
    grid: { vertLines: { color: "#1c2430" }, horzLines: { color: "#1c2430" } },
    rightPriceScale: { borderColor: "#2a3340" },
    timeScale: { borderColor: "#2a3340", timeVisible: false },
    crosshair: { mode: 0 },
  };

  // Çok çıktılı göstergelerde her çizgiye anlamlı renk
  const OUTPUT_COLORS = {
    Ichimoku: { Tenkan: "#2f81f7", Kijun: "#ef5350", SpanA: "#26a69a", SpanB: "#f0883e" },
    BollingerBands: { Upper: "#56d4dd", Middle: "#d29922", Lower: "#56d4dd" },
    Donchian: { Upper: "#56d4dd", Middle: "#d29922", Lower: "#56d4dd" },
    KeltnerChannel: { Upper: "#a371f7", Middle: "#d29922", Lower: "#a371f7" },
    SuperTrend: { SuperTrend: "#26a69a", Direction: "#8b949e" },
    MACD: { MACD: "#2f81f7", Signal: "#f0883e", Hist: "#8b949e" },
    Stochastic: { K: "#2f81f7", D: "#f0883e" },
    StochRSI: { K: "#2f81f7", D: "#f0883e" },
    ADX: { ADX: "#e3b341", PlusDI: "#26a69a", MinusDI: "#ef5350" },
    Aroon: { AroonUp: "#26a69a", AroonDown: "#ef5350", AroonOsc: "#a371f7" },
  };
  function lineColor(inst, out, k, total) {
    const m = OUTPUT_COLORS[inst.name];
    if (m && m[out]) return m[out];
    if (total <= 1) return inst.color;            // tek çizgi: örnek bazlı renk
    return COLORS[(inst.cbase + k) % COLORS.length];
  }

  // ---- Ichimoku bulut (kumo) dolgusu: SpanA/SpanB arası, v4 series primitive ----
  class CloudRenderer {
    constructor(data) { this._data = data; }
    draw(target) {
      const data = this._data;
      if (!data || data.length < 2) return;
      target.useBitmapCoordinateSpace((scope) => {
        const ctx = scope.context;
        const hr = scope.horizontalPixelRatio, vr = scope.verticalPixelRatio;
        for (let i = 0; i < data.length - 1; i++) {
          const p0 = data[i], p1 = data[i + 1];
          ctx.beginPath();
          ctx.moveTo(p0.x * hr, p0.ya * vr);
          ctx.lineTo(p1.x * hr, p1.ya * vr);
          ctx.lineTo(p1.x * hr, p1.yb * vr);
          ctx.lineTo(p0.x * hr, p0.yb * vr);
          ctx.closePath();
          ctx.fillStyle = p0.up ? "rgba(38,166,154,0.18)" : "rgba(239,83,80,0.18)";
          ctx.fill();
        }
      });
    }
  }
  class CloudPaneView {
    constructor(source) { this._source = source; this._data = []; }
    update() {
      const s = this._source;
      if (!s._series || !s._chart) { this._data = []; return; }
      const ts = s._chart.timeScale();
      this._data = s._points.map((p) => {
        const x = ts.timeToCoordinate(p.time);
        const ya = s._series.priceToCoordinate(p.spanA);
        const yb = s._series.priceToCoordinate(p.spanB);
        if (x == null || ya == null || yb == null) return null;
        return { x, ya, yb, up: p.spanA >= p.spanB };
      }).filter(Boolean);
    }
    renderer() { return new CloudRenderer(this._data); }
    zOrder() { return "bottom"; }
  }
  class CloudPrimitive {
    constructor(points) { this._points = points; this._chart = null; this._series = null; this._paneView = new CloudPaneView(this); }
    attached(p) { this._chart = p.chart; this._series = p.series; this._requestUpdate = p.requestUpdate; }
    detached() { this._chart = null; this._series = null; }
    updateAllViews() { this._paneView.update(); }
    paneViews() { return [this._paneView]; }
  }
  function attachCloud(inst, spanA, spanB) {
    const aMap = new Map(spanA.map((p) => [p.time, p.value]));
    const pts = [];
    for (const p of spanB) if (aMap.has(p.time)) pts.push({ time: p.time, spanA: aMap.get(p.time), spanB: p.value });
    if (pts.length < 2 || !inst.series[0] || !inst.series[0].attachPrimitive) return;
    try { inst.series[0].attachPrimitive(new CloudPrimitive(pts)); } catch (e) {}
  }

  let mainChart, candleSeries, volumeSeries;
  let active = [];       // {id, name, params, overlay, outputs, series:[], chart, container}
  let colorIdx = 0;
  let lastCandles = [];

  function init() {
    const el = document.getElementById("chart-main");
    mainChart = LightweightCharts.createChart(el, { ...baseLayout, width: el.clientWidth, height: 460 });
    candleSeries = mainChart.addCandlestickSeries({
      upColor: "#26a69a", downColor: "#ef5350", borderVisible: false,
      wickUpColor: "#26a69a", wickDownColor: "#ef5350",
    });
    volumeSeries = mainChart.addHistogramSeries({
      priceFormat: { type: "volume" }, priceScaleId: "",
    });
    volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });

    new ResizeObserver(() => mainChart.applyOptions({ width: el.clientWidth })).observe(el);
    syncFromMain();
    bindToolbar();
    window.Live.onQuote((data) => {
      const q = data[State.symbol];
      if (q) liveTitle(q);
    });
  }

  function liveTitle(q) {
    const el = document.getElementById("chart-title");
    if (!el) return;
    el.innerHTML = `${State.symbol} · ${fmt(q.price)} <span class="${q.change >= 0 ? "pos" : "neg"}">${q.change >= 0 ? "+" : ""}${fmt(q.change)}%</span> <span style="font-size:10px;color:#26a69a" title="canlı">●</span>`;
    el.style.transition = "none";
    el.style.color = q.change >= 0 ? "#26a69a" : "#ef5350";
    setTimeout(() => { el.style.transition = "color .7s"; el.style.color = ""; }, 60);
  }

  function resize() {
    const el = document.getElementById("chart-main");
    if (mainChart) mainChart.applyOptions({ width: el.clientWidth });
  }

  // --- toolbar: arama, interval, range ---
  function bindToolbar() {
    const input = document.getElementById("symbol-search");
    const box = document.getElementById("search-results");
    let t;
    input.addEventListener("input", () => {
      clearTimeout(t);
      const q = input.value.trim();
      if (!q) { box.classList.remove("show"); return; }
      t = setTimeout(async () => {
        try {
          const r = await API.get("/api/symbols/search?q=" + encodeURIComponent(q));
          box.innerHTML = r.results.map((s) =>
            `<div class="search-item" data-sym="${s.symbol}"><span>${s.symbol}</span><span class="name">${s.name || ""}</span></div>`
          ).join("");
          box.classList.add("show");
          box.querySelectorAll(".search-item").forEach((it) =>
            it.addEventListener("click", () => {
              box.classList.remove("show");
              input.value = "";
              load(it.dataset.sym);
            }));
        } catch (e) {}
      }, 250);
    });
    document.addEventListener("click", (e) => {
      if (!e.target.closest(".search-wrap")) box.classList.remove("show");
    });

    document.querySelectorAll("#interval-seg button").forEach((b) =>
      b.addEventListener("click", () => {
        document.querySelectorAll("#interval-seg button").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        State.interval = b.dataset.v;
        load(State.symbol);
      }));
    document.querySelectorAll("#range-seg button").forEach((b) =>
      b.addEventListener("click", () => {
        document.querySelectorAll("#range-seg button").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        State.range = b.dataset.v;
        load(State.symbol);
      }));
  }

  // --- veri yükle ---
  async function load(symbol) {
    State.symbol = symbol;
    document.getElementById("chart-title").textContent = "yükleniyor…";
    try {
      const r = await API.get(`/api/ohlcv?symbol=${encodeURIComponent(symbol)}&interval=${State.interval}&range=${State.range}`);
      lastCandles = r.candles;
      candleSeries.setData(r.candles.map((c) => ({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close })));
      volumeSeries.setData(r.candles.map((c) => ({ time: c.time, value: c.volume, color: c.close >= c.open ? "rgba(38,166,154,.5)" : "rgba(239,83,80,.5)" })));
      mainChart.timeScale().fitContent();
      const last = r.candles[r.candles.length - 1];
      const prev = r.candles[r.candles.length - 2] || last;
      const chg = prev ? ((last.close - prev.close) / prev.close * 100) : 0;
      document.getElementById("chart-title").innerHTML =
        `${symbol} · ${fmt(last.close)} <span class="${chg >= 0 ? "pos" : "neg"}">${chg >= 0 ? "+" : ""}${fmt(chg)}%</span>`;
      window.Live.subscribe("chart", [symbol]);
      await refreshIndicators();
    } catch (e) {
      document.getElementById("chart-title").innerHTML = `<span class="neg">${symbol}: ${e.message}</span>`;
    }
  }

  // --- gösterge seçici ---
  function initIndicatorPicker() {
    const sel = document.getElementById("indic-select");
    const byGroup = {};
    State.indicators.forEach((i) => { (byGroup[i.group] = byGroup[i.group] || []).push(i); });
    sel.innerHTML = Object.keys(byGroup).sort().map((g) =>
      `<optgroup label="${g}">` + byGroup[g].map((i) => `<option value="${i.name}">${i.name}</option>`).join("") + `</optgroup>`
    ).join("");
    sel.addEventListener("change", renderParams);
    renderParams();
    document.getElementById("indic-add-btn").addEventListener("click", addCurrent);
  }

  function renderParams() {
    const name = document.getElementById("indic-select").value;
    const meta = State.indicatorsByName[name];
    const box = document.getElementById("indic-params");
    if (!meta) { box.innerHTML = ""; return; }
    box.innerHTML = meta.params.filter((p) => p.type !== "source").map((p) =>
      `<div class="param-row"><label>${p.name}</label><input data-p="${p.name}" type="number" step="${p.step}" value="${p.default}" /></div>`
    ).join("");
  }

  function addCurrent() {
    const name = document.getElementById("indic-select").value;
    const meta = State.indicatorsByName[name];
    const params = {};
    document.querySelectorAll("#indic-params input").forEach((i) => (params[i.dataset.p] = parseFloat(i.value)));
    const cbase = colorIdx;
    const inst = {
      id: "i" + Date.now(),
      name, params, overlay: meta.overlay, outputs: meta.outputs,
      color: COLORS[colorIdx % COLORS.length], cbase, series: [], chart: null, container: null,
    };
    colorIdx++;
    active.push(inst);
    renderChips();
    drawIndicator(inst);
  }

  function renderChips() {
    document.getElementById("active-indics").innerHTML = active.map((a) => {
      const p = Object.values(a.params).join(",");
      return `<div class="chip"><span><span class="dot" style="background:${a.color}"></span>${a.name}(${p})</span><button data-id="${a.id}">✕</button></div>`;
    }).join("");
    document.querySelectorAll(".active-indics .chip button").forEach((b) =>
      b.addEventListener("click", () => removeIndicator(b.dataset.id)));
  }

  function removeIndicator(id) {
    const idx = active.findIndex((a) => a.id === id);
    if (idx < 0) return;
    const inst = active[idx];
    if (inst.overlay) inst.series.forEach((s) => mainChart.removeSeries(s));
    else if (inst.container) inst.container.remove();
    active.splice(idx, 1);
    renderChips();
  }

  async function refreshIndicators() {
    for (const inst of active) {
      if (inst.overlay) inst.series.forEach((s) => mainChart.removeSeries(s));
      else if (inst.container) inst.container.remove();
      inst.series = []; inst.chart = null; inst.container = null;
      await drawIndicator(inst);
    }
  }

  async function drawIndicator(inst) {
    let res;
    try {
      res = await API.post("/api/indicators/compute", {
        symbol: State.symbol, indicator: inst.name, params: inst.params,
        interval: State.interval, range: State.range,
      });
    } catch (e) { return; }

    const outs = Object.entries(res.series);
    if (inst.overlay) {
      outs.forEach(([out, pts], k) => {
        const s = mainChart.addLineSeries({ color: lineColor(inst, out, k, outs.length), lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
        s.setData(pts);
        inst.series.push(s);
      });
      if (inst.name === "Ichimoku" && res.series.SpanA && res.series.SpanB) {
        attachCloud(inst, res.series.SpanA, res.series.SpanB);
      }
    } else {
      const wrap = document.createElement("div");
      wrap.className = "subchart";
      wrap.innerHTML = `<div class="label">${inst.name}(${Object.values(inst.params).join(",")})</div><button class="rm" data-id="${inst.id}">✕</button>`;
      document.getElementById("subcharts").appendChild(wrap);
      wrap.querySelector(".rm").addEventListener("click", () => removeIndicator(inst.id));
      const ch = LightweightCharts.createChart(wrap, { ...baseLayout, width: wrap.clientWidth, height: 150 });
      new ResizeObserver(() => ch.applyOptions({ width: wrap.clientWidth })).observe(wrap);
      outs.forEach(([out, pts], k) => {
        const col = lineColor(inst, out, k, outs.length);
        if (/hist/i.test(out)) {
          const s = ch.addHistogramSeries({ color: col });
          s.setData(pts.map((p) => ({ time: p.time, value: p.value, color: p.value >= 0 ? "rgba(38,166,154,.6)" : "rgba(239,83,80,.6)" })));
        } else {
          const s = ch.addLineSeries({ color: col, lineWidth: 1.5, lastValueVisible: true });
          s.setData(pts);
        }
      });
      ch.timeScale().fitContent();
      inst.chart = ch; inst.container = wrap;
      linkChart(ch);
    }
  }

  // --- zaman ekseni senkronu ---
  let linked = [];
  function linkChart(ch) {
    linked.push(ch);
    ch.timeScale().subscribeVisibleLogicalRangeChange((r) => {
      if (!r) return;
      mainChart.timeScale().setVisibleLogicalRange(r);
    });
  }
  function syncFromMain() {
    mainChart.timeScale().subscribeVisibleLogicalRangeChange((r) => {
      if (!r) return;
      linked.forEach((c) => c.timeScale().setVisibleLogicalRange(r));
    });
  }

  window.Chart = { init, load, resize, initIndicatorPicker };
})();
