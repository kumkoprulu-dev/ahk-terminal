"""Yahoo Finance doğrudan sağlayıcı (httpx + tarayıcı User-Agent).

yfinance kütüphanesi varsayılan istek başlığıyla Yahoo tarafından 429 (rate limit)
yiyebiliyor. Yahoo chart API'sini doğrudan, gerçek bir tarayıcı UA'sı ile çağırmak
hem daha sağlam hem daha hızlı. BIST (.IS), NASDAQ ve dünya borsaları desteklenir.
"""
from __future__ import annotations

import httpx
import pandas as pd

from app.data.base import DataProvider, SymbolInfo, normalize_ohlcv

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_SEARCH = "https://query1.finance.yahoo.com/v1/finance/search"

_RANGE = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}
_INTERVAL = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "60m",
    "1d": "1d", "1wk": "1wk", "1mo": "1mo",
}


class YahooProvider(DataProvider):
    name = "yahoo"

    def __init__(self) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": _UA, "Accept": "application/json"},
            timeout=20.0,
            follow_redirects=True,
        )

    def get_ohlcv(self, symbol: str, interval: str = "1d", range_: str = "1y") -> pd.DataFrame:
        rng = range_ if range_ in _RANGE else "1y"
        itv = _INTERVAL.get(interval, "1d")
        try:
            r = self._client.get(
                _CHART.format(symbol=symbol),
                params={"range": rng, "interval": itv, "includeAdjustedClose": "true"},
            )
            r.raise_for_status()
            data = r.json()
        except Exception:
            return normalize_ohlcv(pd.DataFrame())

        result = (data.get("chart") or {}).get("result")
        if not result:
            return normalize_ohlcv(pd.DataFrame())
        res = result[0]
        ts = res.get("timestamp")
        quote = ((res.get("indicators") or {}).get("quote") or [{}])[0]
        if not ts or not quote:
            return normalize_ohlcv(pd.DataFrame())
        df = pd.DataFrame(
            {
                "open": quote.get("open"),
                "high": quote.get("high"),
                "low": quote.get("low"),
                "close": quote.get("close"),
                "volume": quote.get("volume"),
            },
            index=pd.to_datetime(ts, unit="s"),
        )
        return normalize_ohlcv(df)

    def quote(self, symbol: str) -> dict | None:
        """Anlık fiyat (chart meta.regularMarketPrice). Canlı akış için kullanılır."""
        try:
            r = self._client.get(_CHART.format(symbol=symbol),
                                  params={"range": "1d", "interval": "1m"})
            r.raise_for_status()
            meta = (((r.json().get("chart") or {}).get("result") or [{}])[0]).get("meta") or {}
        except Exception:
            return None
        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        if price is None:
            return None
        change = (price - prev) / prev * 100 if prev else 0.0
        return {"symbol": symbol, "price": round(float(price), 4),
                "change": round(float(change), 2), "time": meta.get("regularMarketTime")}

    def search(self, query: str) -> list[SymbolInfo]:
        try:
            r = self._client.get(_SEARCH, params={"q": query, "quotesCount": 15, "newsCount": 0})
            r.raise_for_status()
            data = r.json()
        except Exception:
            return []
        out: list[SymbolInfo] = []
        for q in data.get("quotes", []):
            sym = q.get("symbol")
            if not sym:
                continue
            out.append(
                SymbolInfo(
                    symbol=sym,
                    name=q.get("shortname") or q.get("longname") or "",
                    exchange=q.get("exchDisp", ""),
                    type=q.get("quoteType", "stock"),
                )
            )
        return out
