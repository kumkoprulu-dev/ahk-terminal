"""Değerlendirme harness'ı — çıkarım doğruluğu (precision / recall / F1).

Alan bazında karşılaştırır:
  * TP: gold'da değer var, model doğru çıkardı.
  * FP: model değer üretti ama gold None ya da yanlış (halüsinasyon/hatalı).
  * FN: gold'da değer var, model None bıraktı (kaçırma).
None==None doğru-negatif sayılır (skora dahil edilmez).
"""
from __future__ import annotations

from ..extract import extract_one
from ..ingest import get_sample_sources
from ..llm import get_provider
from .gold import ALANLAR, GOLD


def _esit(alan: str, beklenen, gercek) -> bool:
    if beklenen is None and gercek is None:
        return True
    if beklenen is None or gercek is None:
        return False
    if isinstance(beklenen, float) or isinstance(gercek, (int, float)):
        try:
            return abs(float(beklenen) - float(gercek)) < 0.011
        except (TypeError, ValueError):
            return False
    return str(beklenen) == str(gercek)


def _flat_field(u, alan):
    f = u.to_flat()
    return f.get(alan)


def degerlendir(provider_name: str | None = None) -> dict:
    prov = get_provider(provider_name)
    tp = fp = fn = tn = 0
    detay = []
    for s in get_sample_sources():
        gold = GOLD.get(s.banka, {})
        u = extract_one(s.banka, s.sample_text, url=s.url, provider=prov)
        satir = {"banka": s.banka, "alanlar": {}}
        for alan in ALANLAR:
            beklenen = gold.get(alan)
            gercek = _flat_field(u, alan)
            dogru = _esit(alan, beklenen, gercek)
            if beklenen is not None and gercek is not None and dogru:
                tp += 1; durum = "TP"
            elif beklenen is not None and gercek is not None and not dogru:
                fp += 1; durum = "FP"  # yanlış değer
            elif beklenen is None and gercek is not None:
                fp += 1; durum = "FP"  # halüsinasyon
            elif beklenen is not None and gercek is None:
                fn += 1; durum = "FN"
            else:
                tn += 1; durum = "TN"
            satir["alanlar"][alan] = {"beklenen": beklenen, "gercek": gercek, "durum": durum}
        detay.append(satir)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    toplam = tp + fp + fn + tn
    return {
        "provider": prov.name,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round((tp + tn) / toplam, 4) if toplam else 0.0,
        "detay": detay,
    }
