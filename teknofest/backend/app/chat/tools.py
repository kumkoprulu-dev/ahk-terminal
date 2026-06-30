"""Chatbot araçları — hepsi DETERMİNİSTİK ve store verisine dayanır.

Ajan bu araçları çağırır; sayısal cevaplar koddan gelir, LLM'den DEĞİL.
Bu, "sıfır halüsinasyon" garantisinin chatbot tarafındaki temelidir:
oranlar/tutarlar daima yapılandırılmış veriden ve kaynak alıntıyla döner.
"""
from __future__ import annotations

import re

from .. import compare, store
from ..extract.schema import KatilimUrunu


def _load() -> list[KatilimUrunu]:
    return [KatilimUrunu.model_validate(p) for p in store.list_urunler()]


def tool_en_iyi(urun_tipi=None, para_birimi=None) -> dict:
    best = compare.en_iyi_oran(_load(), urun_tipi=urun_tipi, para_birimi=para_birimi)
    return {"araç": "en_iyi_oran", "sonuç": best}


def tool_karsilastir(urun_tipi=None) -> dict:
    return {"araç": "karsilastir", "sonuç": compare.karsilastir(_load(), urun_tipi=urun_tipi)}


def tool_filtrele(**kw) -> dict:
    rows = [u.to_flat() for u in compare.filtrele(_load(), **kw)]
    return {"araç": "filtrele", "sonuç": rows}


def tool_getiri(anapara: float, yillik_oran: float, vade_gun: int) -> dict:
    return {"araç": "getiri_hesapla",
            "sonuç": compare.getiri_hesapla(anapara, yillik_oran, vade_gun)}


def tool_ozet() -> dict:
    return {"araç": "ozet", "sonuç": compare.ozet(_load())}


def rag_ara(soru: str, k: int = 3) -> list[dict]:
    """Kaynak metinlerde basit kelime-örtüşmesi tabanlı RAG getirimi."""
    sorgu = set(re.findall(r"\w+", soru.lower()))
    skorlu = []
    for kyn in store.get_kaynaklar():
        kelimeler = set(re.findall(r"\w+", kyn["metin"].lower()))
        skor = len(sorgu & kelimeler)
        if skor:
            skorlu.append((skor, kyn))
    skorlu.sort(key=lambda x: x[0], reverse=True)
    return [k_[1] for k_ in skorlu[:k]]


# Para birimi / tip anahtar sözlükleri (niyet çözümleme için)
TIP_KEYS = {
    "altin_hesabi": ["altın", "altin", "gram"],
    "doviz_katilma": ["dolar", "usd", "euro", "eur", "döviz", "doviz"],
    "finansman": ["konut", "ev", "taşıt", "tasit", "kredi", "finansman"],
    "katilma_hesabi": ["katılma", "katilma", "vadeli", "mevduat", "tl hesab", "birikim"],
    "kart_kampanya": ["kart", "harcama"],
}
PB_KEYS = {
    "XAU": ["altın", "altin", "gram"],
    "USD": ["dolar", "usd"],
    "EUR": ["euro", "eur"],
    "TRY": ["tl", "lira", "türk lira"],
}
