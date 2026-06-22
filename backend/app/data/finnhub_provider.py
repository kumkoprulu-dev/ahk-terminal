"""Finnhub tabanlı sağlayıcı. API anahtarı gerektirir (config.settings.finnhub_api_key).

Not: Finnhub ücretsiz katmanında stock candle (OHLCV) erişimi sınırlı olabilir.
Bu yüzden sembol arama + quote için Finnhub, OHLCV'de hata olursa çağıran taraf
yfinance'e düşer (provider router).
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pandas as pd

from app.config import settings
from app.data.base import DataProvider, SymbolInfo, normalize_ohlcv

_RESOLUTION_MAP = {
    "1m": "1", "5m": "5", "15m": "15", "30m": "30", "1h": "60",
    "1d": "D", "1wk": "W", "1mo": "M",
}
_RANGE_DAYS = {
    "1d": 1, "5d": 5, "1mo": 31, "3mo": 93, "6mo": 186,
    "1y": 366, "2y": 731, "5y": 1827, "10y": 3653, "max": 7305,
}


class FinnhubProvider(DataProvider):
    name = "finnhub"

    def __init__(self) -> None:
        import finnhub

        self._client = finnhub.Client(api_key=settings.finnhub_api_key)

    def get_ohlcv(self, symbol: str, interval: str = "1d", range_: str = "1y") -> pd.DataFrame:
        resolution = _RESOLUTION_MAP.get(interval, "D")
        days = _RANGE_DAYS.get(range_, 366)
        now = int(time.time())
        start = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())

        res = self._client.stock_candles(symbol, resolution, start, now)
        if not res or res.get("s") != "ok":
            return normalize_ohlcv(pd.DataFrame())
        df = pd.DataFrame(
            {
                "open": res["o"],
                "high": res["h"],
                "low": res["l"],
                "close": res["c"],
                "volume": res["v"],
            },
            index=pd.to_datetime(res["t"], unit="s"),
        )
        return normalize_ohlcv(df)

    def search(self, query: str) -> list[SymbolInfo]:
        try:
            res = self._client.symbol_lookup(query)
        except Exception:
            return []
        out: list[SymbolInfo] = []
        for item in (res or {}).get("result", [])[:25]:
            out.append(
                SymbolInfo(
                    symbol=item.get("symbol", ""),
                    name=item.get("description", ""),
                    type=item.get("type", "stock"),
                )
            )
        return out
