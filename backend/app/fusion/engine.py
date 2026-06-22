"""Füzyon motoru: Teknik + Haber (Sentiment) + Temel → birleşik sinyal.

Üç eksen 0-100'e normalize edilir, ağırlıklı birleştirilir. Eksik eksenin ağırlığı
diğerlerine dağıtılır. Özel kurallar (ör. negatif haber + olumlu teknik = uyarı) işlenir.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.data import service
from app.data.universe import get_universe
from app.fundamentals.service import analyze as fundamental_analyze
from app.fusion.technical import technical_score
from app.sentiment.engine import get_sentiment

DEFAULT_WEIGHTS = {"technical": 0.40, "sentiment": 0.25, "fundamental": 0.35}


def _signal(score: float) -> str:
    if score >= 70:
        return "GÜÇLÜ AL"
    if score >= 58:
        return "AL"
    if score >= 45:
        return "NÖTR"
    if score >= 32:
        return "SAT"
    return "GÜÇLÜ SAT"


def fuse(symbol: str, weights: dict | None = None, with_sentiment: bool = True,
         interval: str = "1d", range_: str = "1y") -> dict:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}

    # --- Teknik ---
    df = service.get_ohlcv(symbol, interval, range_)
    tech = technical_score(df)

    # --- Temel ---
    fund = fundamental_analyze(symbol)

    # --- Haber ---
    if with_sentiment:
        sent = get_sentiment(symbol, limit=4)
        sent_score = sent.get("score", 0.0)
        sent_label = sent.get("label", "veri yok")
        sent_n = sent.get("n_news", 0)
    else:
        sent_score, sent_label, sent_n = 0.0, "kapalı", 0

    # 0-100 normalize
    parts: dict[str, float] = {}
    if tech["score"] is not None:
        parts["technical"] = tech["score"]
    if sent_n > 0:
        parts["sentiment"] = 50 + 50 * sent_score
    if fund["score"] is not None:
        parts["fundamental"] = fund["score"]

    if not parts:
        composite = None
        signal = "VERİ YOK"
    else:
        total_w = sum(w[k] for k in parts)
        composite = round(sum(parts[k] * w[k] for k in parts) / total_w, 1)
        signal = _signal(composite)

    # --- özel kurallar / uyarılar ---
    flag = ""
    t = tech["score"]
    if t is not None and sent_n > 0:
        if sent_score < -0.15 and t >= 55:
            flag = "⚠ Haber riski (teknik olumlu, haber olumsuz)"
        elif sent_score > 0.15 and t >= 55 and (fund["score"] or 50) >= 60:
            flag = "💪 Üç eksen uyumlu"
        elif sent_score > 0.15 and t < 45:
            flag = "↗ Haber olumlu ama teknik zayıf"

    return {
        "symbol": symbol, "name": fund.get("name") or symbol,
        "technical": {"score": tech["score"], "label": tech["label"], "components": tech.get("components", {})},
        "sentiment": {"score": sent_score, "score100": round(50 + 50 * sent_score, 1) if sent_n else None,
                      "label": sent_label, "n_news": sent_n},
        "fundamental": {"score": fund["score"], "label": fund["label"], "buckets": fund.get("buckets", {}),
                        "source": fund.get("source")},
        "composite": composite, "signal": signal, "flag": flag,
        "weights": w,
    }


def fuse_group(group_id: str, weights: dict | None = None, with_sentiment: bool = True,
               max_workers: int = 8) -> dict:
    syms = [s.symbol for s in get_universe(group_id)]
    if not syms:
        return {"group": group_id, "results": []}

    def _one(sym):
        try:
            r = fuse(sym, weights=weights, with_sentiment=with_sentiment)
            return {
                "symbol": sym, "name": r["name"],
                "technical": r["technical"]["score"], "sentiment": r["sentiment"]["score"],
                "fundamental": r["fundamental"]["score"], "composite": r["composite"],
                "signal": r["signal"], "flag": r["flag"],
            }
        except Exception:
            return {"symbol": sym, "name": sym, "technical": None, "sentiment": 0,
                    "fundamental": None, "composite": None, "signal": "HATA", "flag": ""}

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for row in ex.map(_one, syms):
            results.append(row)
    results.sort(key=lambda r: (r["composite"] is None, -(r["composite"] or -1)))
    return {"group": group_id, "count": len(results),
            "with_sentiment": with_sentiment, "results": results}
