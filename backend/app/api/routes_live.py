"""Canlı fiyat akışı (WebSocket).

Yahoo'nun anlık fiyatını (regularMarketPrice) kısa aralıkla çekip abone olunan
sembolleri client'a iter. Tüm piyasalarda çalışır (BIST/ABD/kripto/emtia).
Not: Ücretsiz veri ~15dk gecikmeli olabilir; gerçek tick için lisanslı/Finnhub WS gerekir.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.data.yahoo_provider import YahooProvider

router = APIRouter()
_yahoo = YahooProvider()
POLL_SECONDS = 6


def _fetch(symbols: list[str]) -> dict:
    out: dict = {}
    if not symbols:
        return out
    with ThreadPoolExecutor(max_workers=8) as ex:
        for q in ex.map(_yahoo.quote, symbols):
            if q:
                out[q["symbol"]] = q
    return out


@router.websocket("/ws/prices")
async def ws_prices(ws: WebSocket):
    await ws.accept()
    symbols: set[str] = set()
    changed = asyncio.Event()
    stop = asyncio.Event()

    async def reader():
        try:
            while True:
                msg = await ws.receive_json()
                syms = msg.get("symbols")
                if syms is not None:
                    symbols.clear()
                    symbols.update([s for s in syms if s][:50])
                    changed.set()
        except Exception:
            stop.set()

    task = asyncio.create_task(reader())
    try:
        while not stop.is_set():
            if symbols:
                data = await asyncio.to_thread(_fetch, list(symbols))
                if data:
                    await ws.send_json({"type": "quotes", "data": data})
            changed.clear()
            try:
                await asyncio.wait_for(changed.wait(), timeout=POLL_SECONDS)
            except asyncio.TimeoutError:
                pass
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        task.cancel()
