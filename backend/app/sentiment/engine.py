"""Duyarlılık motoru: haber çek → skorla (sözlük veya opsiyonel FinBERT) → özetle."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.data.universe import get_universe
from app.sentiment import lexicon, news

_finbert = None


def available_backends() -> list[str]:
    backends = ["lexicon"]
    try:
        import transformers  # noqa: F401
        backends.append("finbert")
    except Exception:
        pass
    return backends


def _get_finbert():
    global _finbert
    if _finbert is None:
        from transformers import pipeline
        _finbert = pipeline("sentiment-analysis", model="ProsusAI/finbert")
    return _finbert


def _score_titles(titles: list[str], backend: str) -> tuple[list[float], str]:
    """Başlık listesini skorlar. FinBERT istenip kullanılamazsa sözlüğe düşer."""
    if backend == "finbert":
        try:
            clf = _get_finbert()
            res = clf(titles)
            m = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}
            return [m.get(r["label"].lower(), 0.0) for r in res], "finbert"
        except Exception:
            pass  # fallback
    return [lexicon.score_headline(t) for t in titles], "lexicon"


def get_sentiment(symbol: str, backend: str = "lexicon", limit: int = 6) -> dict:
    items = news.fetch_news(symbol, limit=limit)
    name = news._NAME_BY_SYMBOL.get(symbol, symbol)
    if not items:
        return {"symbol": symbol, "name": name, "score": 0.0, "label": "veri yok",
                "backend": backend, "n_news": 0, "headlines": []}
    titles = [it["title"] for it in items]
    scores, used = _score_titles(titles, backend)
    for it, sc in zip(items, scores):
        it["score"] = round(float(sc), 2)
        it["label"] = lexicon.label_for(sc)
    avg = sum(scores) / len(scores)
    return {
        "symbol": symbol, "name": name, "score": round(avg, 3),
        "label": lexicon.label_for(avg), "backend": used,
        "n_news": len(items), "headlines": items,
    }


def get_group_sentiment(group_id: str, backend: str = "lexicon", limit: int = 4,
                        max_workers: int = 8) -> dict:
    syms = [s.symbol for s in get_universe(group_id)]
    if not syms:
        return {"group": group_id, "results": []}

    def _one(sym):
        try:
            r = get_sentiment(sym, backend=backend, limit=limit)
            return {"symbol": sym, "name": r["name"], "score": r["score"],
                    "label": r["label"], "n_news": r["n_news"]}
        except Exception:
            return {"symbol": sym, "name": sym, "score": 0.0, "label": "hata", "n_news": 0}

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for row in ex.map(_one, syms):
            results.append(row)
    results.sort(key=lambda r: r["score"], reverse=True)
    used = "finbert" if backend == "finbert" and "finbert" in available_backends() else "lexicon"
    return {"group": group_id, "backend": used, "count": len(results), "results": results}
