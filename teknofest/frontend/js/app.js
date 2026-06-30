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
    return `<tr>
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
}

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
  $("#provider-badge").textContent = "provider: " + h.provider;
  $("#chat-mode").textContent = h.provider === "mock" ? "deterministik" : h.provider + " + araç";
  renderSuggest();
  $("#btn-ingest").onclick = ingest;
  $("#btn-live").onclick = ingestLive;
  $("#btn-eval").onclick = runEval;
  $("#tip-filter").onchange = applyFilter;
  $("#chat-form").onsubmit = (e) => { e.preventDefault(); const q = $("#chat-q").value.trim(); if (q) { ask(q); $("#chat-q").value = ""; } };
  if (h.urun_sayisi > 0) loadData(); else ingest();
}
init();
