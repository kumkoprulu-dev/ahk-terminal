"""İki dilli (TR + EN) finansal duyarlılık sözlüğü ve hızlı skorlayıcı.

FinBERT gibi ağır bir model gerektirmeden, finans haber başlıklarını anında skorlar.
Kök (stem) eşleşmesi kullanılır: 'yüksel' → 'yükseldi/yükseliş/yükselişte' hepsini yakalar.
"""
from __future__ import annotations

import re

POSITIVE = [
    # Türkçe kökler
    "yüksel", "rekor", "kâr", "kar artı", "büyü", "artış", "artt", "kazanç", "kazandı",
    "anlaşma", "ihale kazan", "teşvik", "onay", "güçlü", "ralli", "zirve", "temettü",
    "geri alım", "yatırım", "ihracat", "sözleşme", "başarı", "prim yaptı", "tavan",
    "olumlu", "destek", "büyüme", "yükseliş", "atağı", "uçtu", "fırladı", "sıçradı",
    # English stems
    "surge", "soar", "rally", "gain", "profit", "beat", "upgrade", "growth", "record",
    "strong", "jump", "rise", "bullish", "outperform", "dividend", "buyback", "expand",
    "deal", "win", "approve", "partnership", "breakthrough", "boost", "rebound", "high",
]

NEGATIVE = [
    # Türkçe kökler
    "düş", "zarar", "iflas", "kriz", "ceza", "soruşturma", "dava", "gerile", "kayıp",
    "borç", "temerrüt", "satış baskı", "uyarı", "düşür", "zayıf", "çöküş", "kapan",
    "işten çıkar", "dolandırıcılık", "hile", "dip", "taban", "olumsuz", "endişe",
    "panik", "sert düşüş", "geriledi", "eridi", "çakıldı", "küçül", "tahkikat", "haciz",
    # English stems
    "plunge", "slump", "fall", "drop", "loss", "miss", "downgrade", "weak", "crash",
    "bearish", "fraud", "lawsuit", "probe", "fine", "bankrupt", "default", "cut",
    "decline", "warning", "layoff", "sink", "tumble", "selloff", "plummet", "low", "fear",
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def score_headline(title: str) -> float:
    """Tek başlık için [-1, 1] aralığında duyarlılık skoru."""
    t = _norm(title)
    pos = sum(1 for w in POSITIVE if w in t)
    neg = sum(1 for w in NEGATIVE if w in t)
    if pos == 0 and neg == 0:
        return 0.0
    return (pos - neg) / (pos + neg)


def label_for(score: float) -> str:
    if score > 0.15:
        return "pozitif"
    if score < -0.15:
        return "negatif"
    return "nötr"
