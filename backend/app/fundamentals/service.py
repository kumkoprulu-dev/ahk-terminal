"""Temel analiz facade: veri + skor birleşik."""
from __future__ import annotations

from app.fundamentals.provider import get_fundamentals
from app.fundamentals.score import fundamental_score


def analyze(symbol: str) -> dict:
    fund = get_fundamentals(symbol)
    sc = fundamental_score(fund)
    return {
        "symbol": symbol,
        "name": fund.get("name") or symbol,
        "source": fund.get("source"),
        "metrics": {k: fund.get(k) for k in (
            "pe", "forward_pe", "pb", "ps", "roe", "roa", "net_margin",
            "operating_margin", "gross_margin", "revenue_growth", "earnings_growth",
            "dividend_yield", "current_ratio", "debt_to_equity", "market_cap", "beta", "eps",
        )},
        "score": sc["score"],
        "label": sc["label"],
        "buckets": sc["buckets"],
        "details": sc["details"],
    }
