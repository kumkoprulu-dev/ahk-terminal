"""Çıkarım orkestratörü — LLM + kural temeli + grounding doğrulaması.

Akış:
  1. LLM mevcutsa (claude/ollama) şema-kısıtlı çıkarım yap.
  2. LLM yoksa veya başarısızsa kural-tabanlı çıkarıma düş.
  3. Her iki durumda da GROUNDING DOĞRULAMASI uygula: bir değerin source_quote'u
     kaynak metinde gerçekten geçmiyorsa o değer "doğrulanmamış" sayılır ve
     (REQUIRE_GROUNDING açıksa) düşürülür. Bu, halüsinasyonu mekanik olarak keser.
"""
from __future__ import annotations

from datetime import date

from .. import config
from ..llm import LLMProvider, get_provider
from . import rules
from .prompts import SYSTEM, USER_TMPL
from .schema import ExtractionResult, Grounded, KatilimUrunu, UrunTipi


def _norm(s: str) -> str:
    return "".join(ch.lower() for ch in s if ch.isalnum())


def _verify_grounding(field: Grounded, source_text: str) -> Grounded:
    """source_quote kaynak metinde geçmiyorsa değeri düşür/işaretle."""
    if field.value is None:
        return field
    if not field.source_quote:
        if config.REQUIRE_GROUNDING:
            return Grounded(value=None, source_quote=None, confidence=0.0)
        return field
    # Birebir ya da normalize edilmiş eşleşme (boşluk/noktalama toleransı)
    if field.source_quote in source_text or _norm(field.source_quote)[:40] in _norm(source_text):
        return field
    # Alıntı uydurulmuş — değeri düşür
    if config.REQUIRE_GROUNDING:
        return Grounded(value=None, source_quote=None, confidence=0.0)
    field.confidence = min(field.confidence, 0.3)
    return field


def _from_llm_dict(d: dict, banka: str, url: str | None, source_text: str) -> KatilimUrunu:
    def g(key) -> Grounded:
        raw = d.get(key) or {}
        if not isinstance(raw, dict):
            raw = {"value": raw}
        return Grounded(
            value=raw.get("value"),
            source_quote=raw.get("source_quote"),
            confidence=float(raw.get("confidence", 0.0) or 0.0),
        )

    try:
        tip = UrunTipi(d.get("urun_tipi", "diger"))
    except ValueError:
        tip = UrunTipi.diger

    u = KatilimUrunu(
        banka=banka,
        urun_adi=d.get("urun_adi") or rules.guess_urun_adi(source_text),
        urun_tipi=tip,
        kar_payi_orani=_verify_grounding(g("kar_payi_orani"), source_text),
        kar_payi_orani_net=_verify_grounding(g("kar_payi_orani_net"), source_text),
        vade_gun=_verify_grounding(g("vade_gun"), source_text),
        para_birimi=_verify_grounding(g("para_birimi"), source_text),
        min_tutar=_verify_grounding(g("min_tutar"), source_text),
        max_tutar=_verify_grounding(g("max_tutar"), source_text),
        avantajlar=list(d.get("avantajlar") or []),
        kosullar=list(d.get("kosullar") or []),
        kampanya=bool(d.get("kampanya", False)),
        kampanya_bitis=_verify_grounding(g("kampanya_bitis"), source_text),
        kaynak_url=url,
        cekildigi_tarih=date.today().isoformat(),
    )
    return u


def extract_one(
    banka: str,
    text: str,
    *,
    url: str | None = None,
    urun_adi: str | None = None,
    provider: LLMProvider | None = None,
) -> KatilimUrunu:
    """Tek metinden tek ürün çıkar."""
    provider = provider or get_provider()
    if provider.name != "mock" and provider.available:
        try:
            res = provider.complete(
                SYSTEM,
                USER_TMPL.format(banka=banka, url=url or "-", text=text),
                force_json=True,
            )
            data = res.json()
            if isinstance(data, dict) and data.get("urunler"):
                return _from_llm_dict(data["urunler"][0], banka, url, text)
            if isinstance(data, dict):  # tek ürün düz dönmüş olabilir
                return _from_llm_dict(data, banka, url, text)
        except Exception:
            pass  # kurala düş
    # Kural-tabanlı temel
    u = rules.rule_extract(banka, urun_adi or rules.guess_urun_adi(text), text, url)
    # Kuralda da grounding zaten cümle-temelli; yine de doğrula
    u.kar_payi_orani = _verify_grounding(u.kar_payi_orani, text)
    return u


def extract_page(banka: str, page, *, provider: LLMProvider | None = None) -> KatilimUrunu:
    """Bir Page'den (metin + tablolar) zenginleştirilmiş çıkarım.

    1. Oran tablolarını markdown'a çevirip metnin başına ekler — hem LLM hem
       kural bu temiz yapıyı görür.
    2. extract_one ile temel çıkarımı yapar.
    3. Tablo-türevli yapısal alanlarla (paylaşım oranı, yıllık oran, asgari
       tutar) zenginleştirir — yapısal veri serbest metinden daha güvenilirdir.
    """
    from . import tables as tbl

    provider = provider or get_provider()
    md = tbl.tables_markdown(page.tables)
    # Tablo markdown'ı YALNIZ LLM'e verilir (LLM tabloyu iyi okur). Kural/mock
    # motoruna verilmez — aksi halde pipe'lı tablo metni gürültü/çirkin alıntı üretir.
    if md and provider.name not in ("mock",):
        combined = f"KÂR PAYI / ORAN TABLOLARI:\n{md}\n\n{page.text or ''}"
    else:
        combined = page.text or ""
    u = extract_one(banka, combined, url=page.url, urun_adi=page.title or None, provider=provider)

    # Ürün tipini BAŞLIKTAN önceliklendir: gövdedeki "Altın/Gümüş" kademe adları
    # bir TL katılma hesabını yanlışlıkla "altın hesabı" sınıflamasın.
    if page.title:
        from . import rules as _rules
        from .schema import UrunTipi
        tip_title = _rules.detect_urun_tipi(page.title)
        if tip_title != UrunTipi.diger:
            u.urun_tipi = tip_title

    tex = tbl.extract_from_tables(page.tables)
    pay = tex.get("paylasim_orani")
    if pay and pay.value:
        u.paylasim_orani = pay
    kpo = tex.get("kar_payi_orani")
    if kpo and kpo.value and not u.kar_payi_orani.grounded:
        u.kar_payi_orani = kpo
    mt = tex.get("min_tutar")
    if mt and mt.value and u.min_tutar.value is None:
        u.min_tutar = mt

    # Div-tabanlı etiket-değer oranları (tablo yoksa): "Brüt Oran %32,33" vb.
    from . import labeled
    lab = labeled.extract_labeled_rates(page.text or "")
    lbr = lab.get("kar_payi_orani")
    if lbr and lbr.value and not u.kar_payi_orani.grounded:
        u.kar_payi_orani = lbr
    lnet = lab.get("kar_payi_orani_net")
    if lnet and lnet.value and not u.kar_payi_orani_net.grounded:
        u.kar_payi_orani_net = lnet
    return u


def extract_sources(sources, *, provider: LLMProvider | None = None) -> ExtractionResult:
    """BankSource listesinden tüm ürünleri çıkar."""
    provider = provider or get_provider()
    out = ExtractionResult(provider=provider.name)
    for s in sources:
        try:
            u = extract_one(s.banka, s.sample_text, url=s.url, provider=provider)
            out.urunler.append(u)
        except Exception as e:  # pragma: no cover
            out.warnings.append(f"{s.banka}: {e}")
    return out
