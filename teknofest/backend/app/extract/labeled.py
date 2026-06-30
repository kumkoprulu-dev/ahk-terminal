"""Etiket-değer (div-tabanlı) oran ayrıştırma.

Bazı bankalar (ör. Vakıf Katılım) oranları HTML tablosu yerine div/span
içinde "Brüt Oran %32,33", "Net Oran %26,67" gibi etiket-değer çiftleriyle
sunar. Bu modül bu kalıpları yakalar — grounding ile (eşleşen ibare alıntı olur).
"""
from __future__ import annotations

import re

from .schema import Grounded

# Etiket → alan eşlemesi. Sıra önemli: daha spesifik (net) önce gelir.
_LABELS_NET = ("net oran", "net kâr payı", "net kar payı", "net kar payi", "net getiri")
_LABELS_BRUT = ("brüt oran", "brut oran", "brüt kâr payı", "brut kar payi",
                "yıllık brüt", "yillik brut", "brüt getiri", "kâr payı oranı",
                "kar payı oranı", "kar payi orani", "yıllık oran", "yillik oran")

# "%32,33" ya da "% 32,33" ya da "%32"
_PCT = r"%\s?(\d{1,3}(?:[.,]\d{1,2})?)"


def _find(text: str, labels: tuple[str, ...]) -> Grounded[float]:
    low = text.lower()
    for lbl in labels:
        # Etiketin hemen ardından (±40 karakter penceresi) ilk yüzdeyi yakala
        for m in re.finditer(re.escape(lbl), low):
            window = text[m.start(): m.end() + 40]
            pm = re.search(_PCT, window)
            if pm:
                try:
                    val = float(pm.group(1).replace(".", "").replace(",", "."))
                except ValueError:
                    continue
                if 0 < val <= 200:
                    quote = re.sub(r"\s+", " ", text[m.start(): m.end() + 20]).strip()
                    return Grounded(value=val, source_quote=quote, confidence=0.88)
    return Grounded()


def extract_labeled_rates(text: str) -> dict[str, Grounded]:
    """Metinden brüt/net oranı etiket-değer kalıbıyla çıkar."""
    out: dict[str, Grounded] = {}
    brut = _find(text, _LABELS_BRUT)
    if brut.value is not None:
        out["kar_payi_orani"] = brut
    net = _find(text, _LABELS_NET)
    if net.value is not None:
        out["kar_payi_orani_net"] = net
    return out
