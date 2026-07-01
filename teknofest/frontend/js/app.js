// KatılımLens — TEKNOFEST Senaryo 2 dashboard
const API = "/api";
const $ = (s) => document.querySelector(s);

const TIP_AD = {
  katilma_hesabi: "Katılma Hesabı", altin_hesabi: "Altın Hesabı",
  doviz_katilma: "Döviz Katılma", finansman: "Finansman",
  kart_kampanya: "Kart Kampanya", katilim_sigorta: "Katılım Sigortası", diger: "Diğer",
};
const PB_AD = { TRY: "₺ TL", USD: "$ USD", EUR: "€ EUR", XAU: "Altın" };

let DETAY = []; // grounding alıntıları için tam kayıtlar

async function api(path, opts) {
  const r = await fetch(API + path, opts);
  return r.json();
}

// ---- Özet kartları --------------------------------------------------------
function renderCards(ozet, evalF1) {
  const f1 = evalF1 != null ? (evalF1 * 100).toFixed(1) + "%" : "—";
  $("#cards").innerHTML = `
    <div class="card accent"><div class="k">Ürün</div><div class="v">${ozet.urun_sayisi||0}</div></div>
    <div class="card"><div class="k">Banka</div><div class="v">${ozet.banka_sayisi||0}</div></div>
    <div class="card good"><div class="k">Kaynaklı Alan</div><div class="v">${ozet.toplam_grounded_alan||0}</div></div>
    <div class="card gold"><div class="k">Ort. Güven</div><div class="v">${Math.round((ozet.ort_guven||0)*100)}<small>%</small></div></div>
    <div class="card good"><div class="k">Çıkarım F1</div><div class="v">${f1}</div></div>`;
}

// ---- Karşılaştırma tablosu ------------------------------------------------
function quoteFor(banka, urun) {
  const d = DETAY.find((x) => x.banka === banka && x.urun_adi === urun);
  if (!d) return "";
  return (d.kar_payi_orani && d.kar_payi_orani.source_quote) || "";
}

function renderTable(rows) {
  const tb = $("#compare-table tbody");
  if (!rows.length) { tb.innerHTML = `<tr><td colspan="10" class="empty">Veri yok.</td></tr>`; return; }
  const best = Math.max(...rows.map((r) => r.kar_payi_orani || -1));
  tb.innerHTML = rows.map((r) => {
    const q = quoteFor(r.banka, r.urun_adi).replace(/"/g, "&quot;");
    const isBest = r.kar_payi_orani === best && best > 0;
    const rateMain = r.kar_payi_orani != null
      ? `<span class="rate ${isBest ? "best" : ""}" title="📌 Kaynak: ${q}">%${r.kar_payi_orani}${isBest ? " 🏆" : ""}</span>` : "—";
    const pay = r.paylasim_orani
      ? `<div class="paylasim" title="Kâr paylaşım oranı (müşteri-banka)">📊 ${r.paylasim_orani}</div>` : "";
    const rate = rateMain + pay;
    const conf = Math.round((r.guven || 0) * 100);
    const canli = r.kaynak_url && !/\/ornek\//.test(r.kaynak_url);
    const srcBadge = `<span class="srcbadge ${canli ? "canli" : "ornek"}">${canli ? "CANLI" : "örnek"}</span>`;
    return `<tr class="clickable" data-banka="${r.banka.replace(/"/g, "&quot;")}" data-urun="${(r.urun_adi||"").replace(/"/g, "&quot;")}">
      <td data-label="Banka"><b>${r.banka}</b> ${srcBadge}</td>
      <td data-label="Ürün">${r.urun_adi}</td>
      <td data-label="Tip"><span class="tag">${TIP_AD[r.urun_tipi] || r.urun_tipi}</span></td>
      <td class="num" data-label="Kâr Payı">${rate}</td>
      <td class="num" data-label="Net">${r.kar_payi_orani_net != null ? "%" + r.kar_payi_orani_net : "—"}</td>
      <td class="num" data-label="Vade">${r.vade_gun != null ? r.vade_gun + " gün" : "—"}</td>
      <td data-label="Birim">${PB_AD[r.para_birimi] || "—"}</td>
      <td class="num" data-label="Min">${r.min_tutar != null ? r.min_tutar.toLocaleString("tr-TR") : "—"}</td>
      <td class="num conf" data-label="Güven"><span class="bar"><i style="width:${conf}%"></i></span> ${conf}%</td>
      <td data-label="Kaynak">${r.kaynak_url ? `<a class="src-link" href="${r.kaynak_url}" target="_blank">bağlantı ↗</a>` : "—"}</td>
    </tr>`;
  }).join("");
}

async function loadData() {
  const [flat, detay, ozet] = await Promise.all([
    api("/urunler"), api("/urunler/detay"), api("/ozet"),
  ]);
  DETAY = detay.urunler || [];
  window._ROWS = flat.urunler || [];
  applyFilter();
  renderCards(ozet, window._lastF1);
  renderSkor();
}

// ---- Karşılaştırma Skoru (şartname 5.7) -----------------------------------
const SKOR_ETIKET = {
  en_yuksek_kar_payi_mevduat: ["📈 En yüksek kâr payı (mevduat)", (r) => "%" + r.kar_payi_orani],
  en_dusuk_kar_payi_finansman: ["📉 En düşük kâr payı (finansman)", (r) => "%" + r.kar_payi_orani],
  en_uzun_vade: ["⏳ En uzun vade", (r) => r.vade_gun + " gün"],
  en_dusuk_asgari_tutar: ["💰 En düşük asgari tutar", (r) => (r.min_tutar || 0).toLocaleString("tr-TR")],
  en_avantajli_kampanya: ["⭐ En avantajlı", (r) => (r.avantajlar || []).length + " avantaj"],
};
async function renderSkor() {
  const s = await api("/skor");
  const cards = Object.entries(SKOR_ETIKET).map(([k, [lbl, fmt]]) => {
    const r = s[k];
    if (!r) return "";
    return `<div class="skor-card">
      <div class="sk-label">${lbl}</div>
      <div class="sk-bank">${r.banka}</div>
      <div class="sk-val">${fmt(r)}</div>
      <div class="sk-urun">${r.urun_adi}</div>
    </div>`;
  }).join("");
  $("#skor").innerHTML = cards || "<p class='hint'>Skor için veri yok.</p>";
}

// ---- Ürün Detay Modalı (kaynak + JSON) ------------------------------------
const ALAN_ETIKET = {
  kar_payi_orani: "Kâr payı oranı (brüt %)", kar_payi_orani_net: "Net kâr payı (%)",
  paylasim_orani: "Kâr paylaşım oranı", vade_gun: "Vade (gün)", para_birimi: "Para birimi",
  min_tutar: "Asgari tutar", max_tutar: "Azami tutar",
  finansman_tutari: "Finansman tutarı", taksit_sayisi: "Taksit sayısı",
  tahsis_ucreti: "Tahsis ücreti", odul_miktari: "Ödül miktarı",
  indirim_orani: "İndirim oranı (%)", alisveris_puani: "Alışveriş puanı",
  kampanya_bitis: "Kampanya bitişi",
};
async function openDetay(banka, urun) {
  const p = await api(`/urun/detay?banka=${encodeURIComponent(banka)}&urun_adi=${encodeURIComponent(urun)}`);
  $("#detay-baslik").textContent = `${p.banka} – ${p.urun_adi}`;
  // Kaynak/alanlar görünümü
  const rows = Object.entries(ALAN_ETIKET).map(([key, lbl]) => {
    const f = p[key]; if (!f || f.value == null) return "";
    const conf = Math.round((f.confidence || 0) * 100);
    return `<div class="alan">
      <div class="alan-ust"><span class="alan-ad">${lbl}</span>
        <span class="alan-deg">${f.value}</span>
        <span class="alan-guv">%${conf}</span></div>
      ${f.source_quote ? `<div class="alan-alinti">📌 "${f.source_quote}"</div>` : ""}
    </div>`;
  }).join("");
  const av = (p.avantajlar || []).map((a) => `<span class="tag">${a}</span>`).join(" ");
  const ks = (p.kosullar || []).map((a) => `<span class="tag">${a}</span>`).join(" ");
  const hk = (p.hedef_kitle || []).map((a) => `<span class="tag">${a}</span>`).join(" ");
  // Sınıflandırma alanları (grounding'siz skaler/liste)
  const meta = [];
  if (p.kampanya_turu && p.kampanya_turu !== "—") meta.push(["Kampanya türü", p.kampanya_turu]);
  if (p.masrafsiz) meta.push(["Masrafsız", "✓ Evet"]);
  const metaHtml = meta.map(([k, v]) =>
    `<div class="alan"><div class="alan-ust"><span class="alan-ad">${k}</span><span class="alan-deg">${v}</span></div></div>`).join("");
  $("#detay-kaynak").innerHTML = `
    <div class="kaynak-banner">📄 Kaynak: <a href="${p.kaynak_url}" target="_blank">${p.kaynak_url || "—"}</a>
      <span class="mini">çekildi: ${p.cekildigi_tarih || "—"}</span></div>
    ${rows}
    ${metaHtml}
    ${hk ? `<div class="alan"><div class="alan-ad">Hedef kitle</div>${hk}</div>` : ""}
    ${av ? `<div class="alan"><div class="alan-ad">Avantajlar</div>${av}</div>` : ""}
    ${ks ? `<div class="alan"><div class="alan-ad">Koşullar</div>${ks}</div>` : ""}`;
  $("#detay-json").textContent = JSON.stringify(p, null, 2);
  $("#detay-modal").style.display = "flex";
}
function closeDetay() { $("#detay-modal").style.display = "none"; }

function applyFilter() {
  const t = $("#tip-filter").value;
  const rows = (window._ROWS || []).filter((r) => !t || r.urun_tipi === t);
  renderTable(rows);
}

// ---- Chat -----------------------------------------------------------------
function addMsg(text, who, sources) {
  const div = document.createElement("div");
  div.className = "msg " + who;
  div.innerHTML = text.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\n/g, "<br>");
  if (sources && sources.length) {
    const s = sources.filter((x) => x.alinti).slice(0, 3)
      .map((x) => `<b>${x.banka}</b>: "${x.alinti}"`).join("<br>");
    if (s) { const sd = document.createElement("div"); sd.className = "src"; sd.innerHTML = "📌 Kaynak:<br>" + s; div.appendChild(sd); }
  }
  $("#chat-log").appendChild(div);
  $("#chat-log").scrollTop = $("#chat-log").scrollHeight;
}

async function ask(q) {
  addMsg(q, "user");
  const typing = document.createElement("div");
  typing.className = "msg bot"; typing.innerHTML = "<span class='spin'>◌</span> düşünüyor…";
  $("#chat-log").appendChild(typing);
  try {
    const r = await api("/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ soru: q, use_llm: true }),
    });
    typing.remove();
    addMsg(r.cevap || "—", "bot", r.kaynaklar);
  } catch (e) { typing.remove(); addMsg("Hata: " + e, "bot"); }
}

const SUGGEST = [
  "En yüksek kâr payı hangi bankada?",
  "Altın hesaplarını karşılaştır",
  "100000 TL 32 gün ne kazandırır?",
  "Aktif kampanyalar neler?",
];
function renderSuggest() {
  $("#suggest").innerHTML = SUGGEST.map((s) => `<span class="chip">${s}</span>`).join("");
  $("#suggest").querySelectorAll(".chip").forEach((c) =>
    c.onclick = () => { $("#chat-q").value = c.textContent; ask(c.textContent); });
}

// ---- Eval -----------------------------------------------------------------
async function runEval() {
  $("#eval-box").innerHTML = "<p class='hint'><span class='spin'>◌</span> ölçülüyor…</p>";
  const r = await api("/eval");
  window._lastF1 = r.f1;
  $("#eval-box").innerHTML = `
    <div class="eval-metrics">
      <div class="metric"><div class="mv">${(r.precision*100).toFixed(0)}%</div><div class="ml">Precision</div></div>
      <div class="metric"><div class="mv">${(r.recall*100).toFixed(0)}%</div><div class="ml">Recall</div></div>
      <div class="metric"><div class="mv">${(r.f1*100).toFixed(1)}%</div><div class="ml">F1</div></div>
      <div class="metric"><div class="mv">${(r.accuracy*100).toFixed(0)}%</div><div class="ml">Accuracy</div></div>
    </div>
    <div class="confusion">
      <span>TP ${r.tp}</span><span>FP ${r.fp}</span><span>FN ${r.fn}</span><span>TN ${r.tn}</span>
      <span style="margin-left:auto">provider: <b style="color:var(--accent)">${r.provider}</b></span>
    </div>
    <p class="hint">Gold-set'e karşı ${r.tp+r.fp+r.fn+r.tn} alan değerlendirildi. FP=0 → sıfır halüsinasyon.</p>`;
  const oz = await api("/ozet");
  renderCards(oz, r.f1);
}

// ---- Init -----------------------------------------------------------------
async function ingest() {
  const btn = $("#btn-ingest");
  btn.disabled = true; btn.innerHTML = "<span class='spin'>◌</span> analiz ediliyor…";
  await api("/ingest/samples", { method: "POST" });
  await loadData();
  btn.disabled = false; btn.innerHTML = "↻ Örnek veri";
}

async function ingestLive() {
  const btn = $("#btn-live");
  btn.disabled = true; btn.innerHTML = "<span class='spin'>◌</span> bankalardan çekiliyor…";
  try {
    const r = await api("/ingest/live", { method: "POST" });
    await loadData();
    const live = r.canli, fb = r.fallback, fail = r.basarisiz;
    addMsg(
      `🌐 **Canlı kazıma tamamlandı.** ${r.kaynak_sayisi} kaynaktan ${live} tanesi gerçek banka ` +
      `sitesinden canlı çekildi${fb ? `, ${fb} tanesi örnek-fallback (JS-SPA)` : ""}` +
      `${fail ? `, ${fail} başarısız` : ""}. ` +
      `Çıkarılan oranlar kaynak alıntısıyla doğrulanmıştır.`,
      "bot");
  } catch (e) {
    addMsg("Canlı kazıma hatası: " + e, "bot");
  }
  btn.disabled = false; btn.innerHTML = "🌐 Canlı çek (gerçek bankalar)";
}

async function init() {
  const h = await api("/health");
  const badge = $("#provider-badge");
  if (h.onprem && !h.harici_servis_kullaniliyor) {
    badge.innerHTML = `🔒 On-Prem · ${h.provider}`;
    badge.classList.add("onprem");
    badge.title = "Kurum içi çalışır — dış servise bağımlı değil, müşteri verisi kurum dışına çıkmaz (şartname 5.9)";
  } else {
    badge.textContent = "provider: " + h.provider;
  }
  $("#chat-mode").textContent = h.provider === "mock" ? "deterministik" : h.provider + " + araç";
  renderSuggest();
  $("#btn-ingest").onclick = ingest;
  $("#btn-live").onclick = ingestLive;
  $("#btn-eval").onclick = runEval;
  // Satır tıklama → detay modalı (event delegation; kaynak linkine tıklama hariç)
  $("#compare-table").addEventListener("click", (e) => {
    if (e.target.closest("a")) return;
    const tr = e.target.closest("tr.clickable");
    if (tr) openDetay(tr.dataset.banka, tr.dataset.urun);
  });
  $("#detay-kapat").onclick = closeDetay;
  $("#detay-modal").addEventListener("click", (e) => { if (e.target.id === "detay-modal") closeDetay(); });
  document.querySelectorAll(".modal-tabs .tab").forEach((t) => t.onclick = () => {
    document.querySelectorAll(".modal-tabs .tab").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    const isJson = t.dataset.tab === "json";
    $("#detay-kaynak").style.display = isJson ? "none" : "block";
    $("#detay-json").style.display = isJson ? "block" : "none";
  });
  $("#tip-filter").onchange = applyFilter;
  $("#chat-form").onsubmit = (e) => { e.preventDefault(); const q = $("#chat-q").value.trim(); if (q) { ask(q); $("#chat-q").value = ""; } };
  if (h.urun_sayisi > 0) loadData(); else ingest();
}
init();
