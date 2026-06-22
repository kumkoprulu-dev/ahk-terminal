// Canlı fiyat akışı (WebSocket istemcisi)
(function () {
  let ws = null;
  const subs = {};       // key -> symbols[]  (birleşik küme gönderilir)
  let symbols = [];
  const cbs = [];
  let retry = null;

  function setDot(on) {
    const d = document.getElementById("live-dot");
    if (!d) return;
    d.style.color = on ? "#26a69a" : "#8b949e";
    d.title = on ? "Canlı bağlı (~gecikmeli)" : "Canlı bağlanıyor…";
  }

  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    try { ws = new WebSocket(`${proto}://${location.host}/ws/prices`); }
    catch (e) { scheduleRetry(); return; }
    ws.onopen = () => { setDot(true); if (symbols.length) send(); };
    ws.onmessage = (e) => {
      try { const m = JSON.parse(e.data); if (m.type === "quotes") cbs.forEach((cb) => cb(m.data)); }
      catch (err) {}
    };
    ws.onclose = () => { setDot(false); scheduleRetry(); };
    ws.onerror = () => { try { ws.close(); } catch (e) {} };
  }

  function scheduleRetry() {
    if (retry) return;
    retry = setTimeout(() => { retry = null; connect(); }, 4000);
  }

  function send() {
    if (ws && ws.readyState === 1) ws.send(JSON.stringify({ symbols }));
  }

  // subscribe(symbols) veya subscribe(key, symbols) — çoklu tüketici için birleşir
  function subscribe(a, b) {
    if (Array.isArray(a) && b === undefined) { subs["_default"] = a; }
    else { subs[a] = b || []; }
    const merged = new Set();
    Object.values(subs).forEach((arr) => (arr || []).forEach((s) => s && merged.add(s)));
    symbols = [...merged].slice(0, 60);
    send();
  }

  function onQuote(cb) { cbs.push(cb); }

  window.Live = { connect, subscribe, onQuote };
})();
