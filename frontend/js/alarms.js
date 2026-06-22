// Alarmlar modülü (dashboard)
(function () {
  const val = (id) => document.getElementById(id).value.trim();
  let notified = new Set();

  async function init() {
    document.getElementById("alarm-add").addEventListener("click", add);
    document.getElementById("alarm-rule").addEventListener("keydown", (e) => { if (e.key === "Enter") add(); });
    await refresh();
    setTimeout(check, 3500);
    setInterval(check, 45000);
  }

  async function add() {
    const msg = document.getElementById("alarm-msg");
    if (!window.Auth.isLoggedIn()) { window.Auth.openModal("login"); return; }
    const symbol = val("alarm-symbol"), name = val("alarm-name");
    let rule = val("alarm-rule");
    if (!symbol || !rule || !name) { msg.className = "validate-msg err"; msg.textContent = "✕ Sembol, kural ve ad gerekli"; return; }
    msg.className = "validate-msg"; msg.textContent = "…";
    try {
      await API.post("/api/alarms", { name, symbol, rule });
    } catch (e) {
      try {  // kural geçersizse metinden formüle çevirmeyi dene
        const f = await API.post("/api/formula", { text: rule });
        if (!f.valid) throw e;
        await API.post("/api/alarms", { name, symbol, rule: f.rule });
      } catch (e2) { msg.className = "validate-msg err"; msg.textContent = "✕ " + (e2.message || e.message); return; }
    }
    document.getElementById("alarm-rule").value = "";
    document.getElementById("alarm-name").value = "";
    msg.className = "validate-msg ok"; msg.textContent = "✓ Eklendi";
    await refresh(); check();
  }

  async function refresh() {
    const box = document.getElementById("alarm-list");
    if (!box) return;
    if (!window.Auth.isLoggedIn()) { box.innerHTML = `<div class="muted" style="font-size:12px">Alarm kurmak için giriş yapın.</div>`; return; }
    try {
      const r = await API.get("/api/alarms");
      if (!r.alarms.length) { box.innerHTML = `<div class="muted" style="font-size:12px">Henüz alarm yok.</div>`; return; }
      box.innerHTML = r.alarms.map((a) =>
        `<div class="mv" data-id="${a.id}" style="grid-template-columns:1fr auto">
          <span><b>${a.name}</b> <span class="muted" style="font-size:11px">${a.data.symbol} · ${a.data.rule}</span></span>
          <button class="ghost" data-del="${a.id}">🗑</button></div>`).join("");
      box.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", () => del(b.dataset.del)));
    } catch (e) {}
  }

  async function del(id) { try { await API.del("/api/alarms/" + id); await refresh(); } catch (e) {} }

  async function check() {
    if (!window.Auth.isLoggedIn()) return;
    try {
      const r = await API.get("/api/alarms/check");
      const badge = document.getElementById("alarm-badge");
      if (r.triggered.length) {
        badge.innerHTML = `<span class="neg">🔴 ${r.triggered.length} tetiklendi: ${r.triggered.map((t) => t.symbol.replace(".IS", "")).join(", ")}</span>`;
        notify(r.triggered);
      } else { badge.textContent = r.count ? `(${r.count} aktif)` : ""; }
      document.querySelectorAll("#alarm-list .mv").forEach((el) => (el.style.background = ""));
      r.triggered.forEach((t) => { const el = document.querySelector(`#alarm-list .mv[data-id="${t.id}"]`); if (el) el.style.background = "rgba(239,83,80,.12)"; });
    } catch (e) {}
  }

  function notify(triggered) {
    if (!("Notification" in window)) return;
    if (Notification.permission === "default") Notification.requestPermission();
    if (Notification.permission !== "granted") return;
    triggered.forEach((t) => {
      const key = t.id + ":" + t.price;
      if (notified.has(key)) return;
      notified.add(key);
      new Notification("🔔 Alarm: " + t.name, { body: `${t.symbol} · ${t.rule} · ${t.price}` });
    });
  }

  window.Alarms = { init, refresh };
})();
