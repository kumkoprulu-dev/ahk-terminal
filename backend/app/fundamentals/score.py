"""Temel analiz skorlaması — oranları 0-100 birleşik skora çevirir.

Dört kova: Değer, Kârlılık, Büyüme, Finansal Sağlık. Eksik veriler atlanır;
skor yalnız mevcut metriklerden hesaplanır.
"""
from __future__ import annotations

INF = float("inf")

# (eşik, skor) merdivenleri
_HIGH = {  # yüksek = iyi
    "roe": [(25, 100), (15, 82), (8, 62), (3, 42), (-INF, 15)],
    "roa": [(15, 100), (8, 80), (3, 55), (0, 35), (-INF, 15)],
    "net_margin": [(20, 100), (10, 80), (3, 55), (0, 35), (-INF, 15)],
    "revenue_growth": [(25, 100), (12, 80), (3, 55), (-5, 30), (-INF, 10)],
    "earnings_growth": [(25, 100), (12, 80), (3, 55), (-10, 30), (-INF, 10)],
    "current_ratio": [(2.5, 100), (1.5, 82), (1, 60), (0.7, 40), (-INF, 20)],
    "dividend_yield": [(5, 100), (3, 82), (1, 62), (0.01, 45), (-INF, 30)],
}
_LOW = {  # düşük = iyi
    "pe": [(10, 100), (15, 85), (25, 65), (35, 45), (60, 25), (INF, 10)],
    "pb": [(1, 100), (2, 85), (4, 65), (7, 40), (INF, 20)],
    "ps": [(1, 100), (3, 80), (6, 55), (10, 35), (INF, 20)],
    "debt_to_equity": [(0.3, 100), (0.7, 82), (1.2, 60), (2, 40), (INF, 20)],
}

_BUCKETS = {
    "Değer": ["pe", "pb", "ps"],
    "Kârlılık": ["roe", "roa", "net_margin"],
    "Büyüme": ["revenue_growth", "earnings_growth"],
    "Sağlık": ["debt_to_equity", "current_ratio"],
}
_WEIGHTS = {"Değer": 0.25, "Kârlılık": 0.30, "Büyüme": 0.25, "Sağlık": 0.20}


def _metric_score(key: str, value) -> float | None:
    if value is None or not isinstance(value, (int, float)):
        return None
    if key in _HIGH:
        for cut, sc in _HIGH[key]:
            if value >= cut:
                return float(sc)
        return float(_HIGH[key][-1][1])
    if key in _LOW:
        # negatif PE/PB = zarar/anormal → düşük skor
        if key in ("pe", "pb", "ps") and value <= 0:
            return 15.0
        for cut, sc in _LOW[key]:
            if value <= cut:
                return float(sc)
        return float(_LOW[key][-1][1])
    return None


def label_for(score: float) -> str:
    if score >= 75:
        return "çok güçlü"
    if score >= 60:
        return "güçlü"
    if score >= 45:
        return "orta"
    if score >= 30:
        return "zayıf"
    return "çok zayıf"


def fundamental_score(fund: dict) -> dict:
    """Fundamentals dict → {score, label, buckets, details}."""
    details: dict[str, float] = {}
    buckets: dict[str, float] = {}
    for bucket, keys in _BUCKETS.items():
        scores = []
        for k in keys:
            s = _metric_score(k, fund.get(k))
            if s is not None:
                details[k] = round(s, 1)
                scores.append(s)
        if scores:
            buckets[bucket] = round(sum(scores) / len(scores), 1)

    if not buckets:
        return {"score": None, "label": "veri yok", "buckets": {}, "details": {}}

    total_w = sum(_WEIGHTS[b] for b in buckets)
    composite = sum(buckets[b] * _WEIGHTS[b] for b in buckets) / total_w
    composite = round(composite, 1)
    return {"score": composite, "label": label_for(composite),
            "buckets": buckets, "details": details}
