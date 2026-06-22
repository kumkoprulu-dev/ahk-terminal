// Hesap / kayıt modülü
(function () {
  const KEY = "ahk_token";
  let token = localStorage.getItem(KEY) || null;
  let username = null;
  let mode = "login";
  const bindings = [];

  function setToken(t, u) {
    token = t; username = u;
    if (t) localStorage.setItem(KEY, t); else localStorage.removeItem(KEY);
    renderWidget();
    bindings.forEach(refreshBinding);
    if (window.Alarms) window.Alarms.refresh();
  }

  async function init() {
    renderWidget();
    bindModal();
    if (token) {
      try { const me = await API.get("/api/auth/me"); username = me.username; renderWidget(); }
      catch (e) { setToken(null, null); }
    }
  }

  function renderWidget() {
    const w = document.getElementById("auth-widget");
    if (!w) return;
    if (token && username) {
      w.innerHTML = `<span class="uname">👤 ${username}</span><button class="tab" id="auth-logout">Çıkış</button>`;
      document.getElementById("auth-logout").addEventListener("click", logout);
    } else {
      w.innerHTML = `<button class="tab" id="auth-open">Giriş / Kayıt</button>`;
      document.getElementById("auth-open").addEventListener("click", () => openModal("login"));
    }
  }

  function openModal(m) {
    mode = m;
    document.getElementById("auth-title").textContent = m === "login" ? "Giriş Yap" : "Kayıt Ol";
    document.getElementById("auth-submit").textContent = m === "login" ? "Giriş" : "Kayıt Ol";
    document.getElementById("auth-toggle").textContent = m === "login" ? "Kayıt ol" : "Girişe dön";
    document.getElementById("auth-msg").textContent = "";
    document.getElementById("auth-modal").style.display = "flex";
    document.getElementById("auth-username").focus();
  }
  function closeModal() { document.getElementById("auth-modal").style.display = "none"; }

  function bindModal() {
    document.getElementById("auth-close").addEventListener("click", closeModal);
    document.getElementById("auth-toggle").addEventListener("click", () => openModal(mode === "login" ? "register" : "login"));
    document.getElementById("auth-submit").addEventListener("click", submit);
    document.getElementById("auth-password").addEventListener("keydown", (e) => { if (e.key === "Enter") submit(); });
  }

  async function submit() {
    const u = document.getElementById("auth-username").value.trim();
    const p = document.getElementById("auth-password").value;
    const msg = document.getElementById("auth-msg");
    msg.className = "validate-msg"; msg.textContent = "…";
    try {
      const r = await API.post("/api/auth/" + (mode === "login" ? "login" : "register"), { username: u, password: p });
      setToken(r.token, r.username);
      closeModal();
    } catch (e) {
      msg.className = "validate-msg err"; msg.textContent = "✕ " + e.message;
    }
  }

  async function logout() {
    try { await API.post("/api/auth/logout", {}); } catch (e) {}
    setToken(null, null);
  }

  // ---- kaydet / yükle bağlama ----
  function bindSaved(cfg) {
    bindings.push(cfg);
    document.getElementById(cfg.saveBtn).addEventListener("click", () => doSave(cfg));
    document.getElementById(cfg.delBtn).addEventListener("click", () => doDel(cfg));
    document.getElementById(cfg.loadSel).addEventListener("change", (e) => {
      const item = (cfg._items || []).find((x) => String(x.id) === e.target.value);
      if (item) cfg.setData(item.data);
    });
    refreshBinding(cfg);
  }

  async function refreshBinding(cfg) {
    const sel = document.getElementById(cfg.loadSel);
    if (!token) { sel.innerHTML = `<option value="">📂 (giriş yapın)</option>`; cfg._items = []; return; }
    try {
      const r = await API.get("/api/saved?kind=" + cfg.kind);
      cfg._items = r.items;
      sel.innerHTML = `<option value="">📂 Yükle… (${r.items.length})</option>` +
        r.items.map((i) => `<option value="${i.id}">${i.name}</option>`).join("");
    } catch (e) { cfg._items = []; }
  }

  async function doSave(cfg) {
    if (!token) { openModal("login"); return; }
    const name = prompt("Kayıt adı:");
    if (!name) return;
    try { await API.post("/api/saved", { kind: cfg.kind, name, data: cfg.getData() }); await refreshBinding(cfg); }
    catch (e) { alert("Kaydedilemedi: " + e.message); }
  }

  async function doDel(cfg) {
    const sel = document.getElementById(cfg.loadSel);
    const id = sel.value;
    if (!id) return;
    if (!confirm("Seçili kaydı sil?")) return;
    try { await API.del("/api/saved/" + id); await refreshBinding(cfg); }
    catch (e) { alert("Silinemedi: " + e.message); }
  }

  window.Auth = { init, token: () => token, isLoggedIn: () => !!token, openModal, bindSaved };
})();
