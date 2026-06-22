"""Piyasa nabzı (dashboard) uç noktaları: grup geneli günlük değişim + sparkline."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException

from app.data import service
from app.data.universe import get_universe

router = APIRouter(prefix="/api/market", tags=["market"])


def _one(sym: str, name: str) -> dict | None:
    df = service.get_ohlcv(sym, "1d", "1mo")
    if df is None or len(df) < 2:
        return None
    closes = [round(float(c), 4) for c in df["close"].tail(22).tolist()]
    last = closes[-1]
    prev = closes[-2]
    change = (last - prev) / prev * 100 if prev else 0.0
    return {"symbol": sym, "name": name, "price": last,
            "change": round(change, 2), "spark": closes}


@router.get("/movers")
def movers(group: str = "bist30", limit: int = 5):
    syms = get_universe(group)
    if not syms:
        raise HTTPException(404, f"Grup bulunamadı: {group}")

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        for r in ex.map(lambda s: _one(s.symbol, s.name), syms):
            if r:
                rows.append(r)
    rows.sort(key=lambda r: r["change"], reverse=True)
    up = sum(1 for r in rows if r["change"] > 0)
    return {
        "group": group, "count": len(rows),
        "advancers": up, "decliners": len(rows) - up,
        "gainers": rows[:limit],
        "losers": rows[-limit:][::-1],
        "all": rows,
    }
