"""Veri uç noktaları: sembol arama, OHLCV, quote, universe listeleri."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.data import service
from app.data.universe import get_universe, universe_list, LABELS

router = APIRouter(prefix="/api", tags=["data"])


@router.get("/universes")
def list_universes():
    return {"universes": universe_list()}


@router.get("/universes/{name}")
def universe_detail(name: str):
    syms = get_universe(name)
    if not syms:
        raise HTTPException(404, f"Universe bulunamadı: {name}")
    return {"id": name, "label": LABELS.get(name, name), "symbols": [s.__dict__ for s in syms]}


@router.get("/symbols/search")
def symbols_search(q: str = Query(..., min_length=1)):
    return {"query": q, "results": [s.__dict__ for s in service.search(q)]}


@router.get("/ohlcv")
def ohlcv(
    symbol: str,
    interval: str = "1d",
    range: str = "1y",  # noqa: A002 (FastAPI query adı)
):
    df = service.get_ohlcv(symbol, interval, range)
    if df is None or df.empty:
        raise HTTPException(404, f"Veri bulunamadı: {symbol}")
    candles = [
        {
            "time": idx.strftime("%Y-%m-%d") if interval in ("1d", "1wk", "1mo")
            else int(idx.timestamp()),
            "open": round(float(r.open), 4),
            "high": round(float(r.high), 4),
            "low": round(float(r.low), 4),
            "close": round(float(r.close), 4),
            "volume": int(r.volume) if r.volume == r.volume else 0,
        }
        for idx, r in df.iterrows()
    ]
    return {"symbol": symbol, "interval": interval, "range": range, "candles": candles}


@router.get("/quote")
def quote(symbol: str):
    return service.quote(symbol)
