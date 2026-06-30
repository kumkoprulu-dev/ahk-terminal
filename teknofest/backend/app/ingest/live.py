"""Canlı kazıma orkestratörü — gerçek banka sayfalarından uçtan uca.

Her LiveSource için:
  1. Sayfayı çek (fetch_page) — başlık + temiz ana metin.
  2. İçerik ince/boşsa (JS-SPA) paketli örnek metne düş (varsa) ve işaretle.
  3. Çıkarım yap (LLM varsa o, yoksa kural temeli) — sayfa başlığı ürün adı olur.
  4. Para birimi ipucu (url/başlıktan) uygula; metinden gelen yanlış değeri düzelt.
  5. Kaydet ve kaynak-başına durum döndür.
"""
from __future__ import annotations

from ..extract import extract_one, extract_page
from ..extract.schema import Grounded
from ..llm import LLMProvider, get_provider
from .live_sources import LiveSource, get_live_sources
from .scraper import fetch_page
from .sources import SAMPLE_SOURCES

# Banka adına göre paketli örnek (SPA fallback için)
_SAMPLE_BY_BANK = {s.banka: s for s in SAMPLE_SOURCES}

MIN_USABLE_LEN = 300  # bu uzunluğun altı "ince/SPA" sayılır


def _apply_currency_hint(urun, ipucu: str | None):
    """Metinden gelen para birimi güvenilmezse (canlı sayfada menü gürültüsü)
    url/başlık ipucuyla düzelt."""
    if not ipucu:
        return
    pb = urun.para_birimi
    # İpucu TRY iken metin XAU/USD yakalamışsa ve güven düşükse düzelt
    if pb.value != ipucu and (pb.confidence < 0.85 or pb.value in (None, "XAU")):
        urun.para_birimi = Grounded(value=ipucu, source_quote=pb.source_quote,
                                    confidence=0.6)


def ingest_live(provider: LLMProvider | None = None, sources: list[LiveSource] | None = None) -> dict:
    provider = provider or get_provider()
    sources = sources or get_live_sources()
    from .. import store

    sonuc = []
    urunler = []
    from .scraper import render_page

    for s in sources:
        page = fetch_page(s.url)
        # httpx ince/boş döndüyse ve sayfa JS-SPA ise Playwright ile RENDER dene
        if (not page.ok or len(page.text) < MIN_USABLE_LEN) and s.render_required:
            rendered = render_page(s.url)
            if rendered.ok and len(rendered.text) >= MIN_USABLE_LEN:
                page = rendered
        kaynak = "canli-render" if (s.render_required and page.ok and len(page.text) >= MIN_USABLE_LEN) else "canli"
        metin = page.text
        title = page.title or s.urun_adi

        # SPA / ince içerik → örneğe düş (tablo yok, düz metin çıkarımı)
        if not page.ok or len(metin) < MIN_USABLE_LEN:
            sample = _SAMPLE_BY_BANK.get(s.banka)
            if sample is None:
                sonuc.append({"banka": s.banka, "urun": s.urun_adi, "url": s.url,
                              "kaynak": "basarisiz", "status": page.status, "len": len(page.text)})
                continue
            kaynak = "ornek-fallback" if s.render_required else "ince-fallback"
            metin = sample.sample_text
            urun = extract_one(s.banka, metin, url=s.url, urun_adi=s.urun_adi, provider=provider)
        else:
            # Canlı sayfa → tablo-farkındalıklı çıkarım (oran/paylaşım tabloları)
            urun = extract_page(s.banka, page, provider=provider)

        _apply_currency_hint(urun, s.para_birimi_ipucu)
        store.save_kaynak(s.banka, s.url, metin)
        store.save_urun(urun)
        urunler.append(urun)
        f = urun.to_flat()
        sonuc.append({
            "banka": s.banka, "urun": urun.urun_adi, "url": s.url, "kaynak": kaynak,
            "status": page.status, "len": len(page.text), "tablo": len(page.tables),
            "kar_payi": f["kar_payi_orani"], "paylasim": f.get("paylasim_orani"),
            "vade_gun": f["vade_gun"], "grounded": urun.grounded_field_count(), "guven": f["guven"],
        })

    from .. import compare
    return {
        "provider": provider.name,
        "kaynak_sayisi": len(sources),
        "canli": sum(1 for r in sonuc if r["kaynak"] == "canli"),
        "fallback": sum(1 for r in sonuc if r["kaynak"].endswith("fallback")),
        "basarisiz": sum(1 for r in sonuc if r["kaynak"] == "basarisiz"),
        "sonuclar": sonuc,
        "ozet": compare.ozet(urunler) if urunler else {},
    }
