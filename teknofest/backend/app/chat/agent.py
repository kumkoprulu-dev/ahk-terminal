"""Agentic chatbot — niyet çözümleme → araç çağırma → kaynak-temelli yanıt.

Tasarım: HİBRİT.
  * Niyet ve hangi aracın çağrılacağı: mock modda kural/regex router; LLM modda
    LLM bir araç planı önerir (gelecekte genişletilebilir). Her hâlde araçlar
    deterministik kod çalıştırır.
  * Doğal dil cevap: sayısal sonuç koddan gelir; LLM yalnız bu sonucu Türkçe
    cümleye döker (varsa). Böylece oran/tutar ASLA uydurulamaz.

Yanıt her zaman "kaynaklar" listesiyle döner (grounding): hangi banka/üründen,
hangi alıntıyla geldiği gösterilir.
"""
from __future__ import annotations

import re

from ..llm import get_provider
from . import tools


def _niyet_coz(soru: str) -> dict:
    low = soru.lower()
    # ürün tipi
    tip = None
    for t, keys in tools.TIP_KEYS.items():
        if any(k in low for k in keys):
            tip = t
            break
    pb = None
    for p, keys in tools.PB_KEYS.items():
        if any(k in low for k in keys):
            pb = p
            break

    # getiri hesabı: "100000 tl ... 32 gün"
    tutar_m = re.search(r"(\d[\d.\s]{2,})\s*(tl|usd|eur|lira)", low)
    vade_m = re.search(r"(\d{1,4})\s*g[üu]n", low)
    if tutar_m and ("kazan" in low or "getiri" in low or "ne kadar" in low or "hesap" in low):
        return {"niyet": "getiri", "tip": tip, "pb": pb,
                "tutar": float(tutar_m.group(1).replace(".", "").replace(" ", "")),
                "vade": int(vade_m.group(1)) if vade_m else None}

    if any(w in low for w in ["en yüksek", "en iyi", "en fazla", "en çok", "en yuksek", "hangisi daha"]):
        return {"niyet": "en_iyi", "tip": tip, "pb": pb}
    if any(w in low for w in ["karşılaştır", "karsilastir", "kıyasla", "kiyasla", "tablo"]):
        return {"niyet": "karsilastir", "tip": tip, "pb": pb}
    if "kampanya" in low:
        return {"niyet": "kampanya", "tip": tip, "pb": pb}
    if any(w in low for w in ["kaç", "kac", "özet", "ozet", "toplam", "hangi banka"]):
        return {"niyet": "ozet", "tip": tip, "pb": pb}
    # varsayılan: filtrele/listele
    return {"niyet": "filtrele", "tip": tip, "pb": pb}


def _fmt_urun(r: dict) -> str:
    parts = [f"**{r['banka']} – {r['urun_adi']}**"]
    if r.get("kar_payi_orani") is not None:
        parts.append(f"kâr payı %{r['kar_payi_orani']}")
    if r.get("paylasim_orani"):
        parts.append(f"paylaşım {r['paylasim_orani']}")
    if r.get("vade_gun"):
        parts.append(f"{r['vade_gun']} gün")
    if r.get("para_birimi"):
        parts.append(r["para_birimi"])
    return " · ".join(parts)


def _kaynaklar_for(rows: list[dict]) -> list[dict]:
    """Ürün satırları için kaynak alıntıları topla."""
    from .. import store
    from ..extract.schema import KatilimUrunu

    by_key = {(u["banka"], u["urun_adi"]): u for u in store.list_urunler()}
    out = []
    for r in rows or []:
        key = (r.get("banka"), r.get("urun_adi"))
        p = by_key.get(key)
        if not p:
            continue
        u = KatilimUrunu.model_validate(p)
        q = u.kar_payi_orani.source_quote or u.vade_gun.source_quote
        out.append({"banka": u.banka, "urun": u.urun_adi, "url": u.kaynak_url, "alinti": q})
    return out


def cevapla(soru: str, *, use_llm: bool = True) -> dict:
    """Ana giriş — soruyu yanıtla. Dönüş: {cevap, arac, veri, kaynaklar}."""
    niyet = _niyet_coz(soru)
    n = niyet["niyet"]
    arac_sonuc = None
    rows_for_src: list[dict] = []
    cevap = ""

    if n == "getiri":
        # önce uygun ürünü bul (oranı oradan al → grounding)
        best = tools.tool_en_iyi(niyet.get("tip"), niyet.get("pb"))["sonuç"]
        if not best:
            return {"cevap": "Bu kritere uygun ürün bulunamadı.", "arac": "getiri",
                    "veri": None, "kaynaklar": []}
        vade = niyet.get("vade") or best.get("vade_gun") or 32
        oran = best.get("kar_payi_orani") or 0
        h = tools.tool_getiri(niyet["tutar"], oran, vade)["sonuç"]
        arac_sonuc = h
        rows_for_src = [best]
        cevap = (
            f"{_fmt_urun(best)} ürününde **{h['anapara']:,.0f} {best.get('para_birimi') or 'TL'}** "
            f"{vade} gün vadede tahmini **net {h['net_kar_payi']:,.2f}** kâr payı kazandırır "
            f"(brüt {h['brut_kar_payi']:,.2f}, vade sonu toplam {h['vade_sonu_toplam']:,.2f})."
        )

    elif n == "en_iyi":
        res = tools.tool_en_iyi(niyet.get("tip"), niyet.get("pb"))
        best = res["sonuç"]
        arac_sonuc = best
        if best:
            rows_for_src = [best]
            cevap = f"En yüksek kâr payı: {_fmt_urun(best)}."
        else:
            cevap = "Bu kritere uygun ürün bulunamadı."

    elif n == "karsilastir":
        res = tools.tool_karsilastir(niyet.get("tip"))["sonuç"]
        arac_sonuc = res
        rows_for_src = res["satirlar"]
        if res["satirlar"]:
            sat = "\n".join(f"- {_fmt_urun(r)}" for r in res["satirlar"][:6])
            cevap = (f"{res['adet']} ürün karşılaştırıldı (ort. %{res['ortalama_oran']}):\n{sat}")
        else:
            cevap = "Karşılaştırılacak ürün bulunamadı."

    elif n == "kampanya":
        res = tools.tool_filtrele(sadece_kampanya=True, urun_tipi=niyet.get("tip"))["sonuç"]
        arac_sonuc = res
        rows_for_src = res
        cevap = (f"{len(res)} aktif kampanya:\n" + "\n".join(f"- {_fmt_urun(r)}" for r in res)) if res \
            else "Aktif kampanya bulunamadı."

    elif n == "ozet":
        res = tools.tool_ozet()["sonuç"]
        arac_sonuc = res
        cevap = (f"Sistemde {res['urun_sayisi']} ürün, {res['banka_sayisi']} banka var "
                 f"({', '.join(res['bankalar'])}). Ortalama güven %{res['ort_guven']*100:.0f}.")

    else:  # filtrele
        res = tools.tool_filtrele(urun_tipi=niyet.get("tip"), para_birimi=niyet.get("pb"))["sonuç"]
        arac_sonuc = res
        rows_for_src = res
        cevap = ("\n".join(f"- {_fmt_urun(r)}" for r in res)) if res else "Uygun ürün bulunamadı."

    kaynaklar = _kaynaklar_for(rows_for_src)

    # Opsiyonel: LLM ile doğal dil cilası (sayısal veri sabit kalır)
    if use_llm:
        prov = get_provider()
        if prov.name != "mock" and prov.available:
            try:
                sys = ("Aşağıdaki YAPILANDIRILMIŞ sonucu, sayıları DEĞİŞTİRMEDEN, kısa ve "
                       "akıcı Türkçe ile kullanıcıya açıkla. Katılım bankacılığı dili kullan "
                       "(faiz değil kâr payı). Veride olmayan bilgi ekleme.")
                usr = f"Soru: {soru}\n\nSonuç verisi: {arac_sonuc}\n\nTaslak cevap: {cevap}"
                out = prov.complete(sys, usr, max_tokens=400)
                if out.text.strip():
                    cevap = out.text.strip()
            except Exception:
                pass

    return {"cevap": cevap, "arac": n, "niyet": niyet, "veri": arac_sonuc, "kaynaklar": kaynaklar}
