"""Veri servisi facade'ı: sağlayıcı seçimi + önbellek + yedeğe düşme (fallback).

Sıralama:
  OHLCV  : Yahoo (doğrudan httpx) → yfinance kütüphanesi (yedek) → Finnhub (yalnızca DATA_PROVIDER=finnhub)
  Arama  : yerel universe + Yahoo arama (+ Finnhub varsa)
  Quote  : Yahoo OHLCV son kapanış; Finnhub varsa anlık quote

Çağıran katman (API, tarayıcı) yalnızca burayı kullanır.
"""
from __future__ import annotations

import pandas as pd

from app.config import settings
from app.data import cache
from app.data.base import SymbolInfo, normalize_ohlcv
from app.data.universe import search_local
from app.data.yahoo_provider import YahooProvider

_yahoo = YahooProvider()
_yf = None
_finnhub = None


def _get_yf():
    global _yf
    if _yf is None:
        from app.data.yfinance_provider import YFinanceProvider

        _yf = YFinanceProvider()
    return _yf


def _get_finnhub():
    global _finnhub
    if _finnhub is None and settings.has_finnhub:
        from app.data.finnhub_provider import FinnhubProvider

        _finnhub = FinnhubProvider()
    return _finnhub


def get_ohlcv(symbol: str, interval: str = "1d", range_: str = "1y") -> pd.DataFrame:
    """Önbellekli OHLCV. Yahoo birincil; boş dönerse yfinance yedeği denenir."""
    cached = cache.get("auto", symbol, interval, range_)
    if cached is not None and not cached.empty:
        return cached

    df = pd.DataFrame()

    # DATA_PROVIDER=finnhub açıkça istenmişse önce onu dene (ücretli katman gerekir)
    if settings.data_provider == "finnhub" and settings.has_finnhub:
        try:
            df = _get_finnhub().get_ohlcv(symbol, interval, range_)
        except Exception:
            df = pd.DataFrame()

    if df is None or df.empty:
        df = _yahoo.get_ohlcv(symbol, interval, range_)

    if df is None or df.empty:
        try:
            df = _get_yf().get_ohlcv(symbol, interval, range_)
        except Exception:
            df = pd.DataFrame()

    df = normalize_ohlcv(df)
    if not df.empty:
        cache.set("auto", symbol, interval, range_, df)
    return df


def search(query: str) -> list[SymbolInfo]:
    """Önce yerel universe; sonra Yahoo arama; Finnhub varsa ek."""
    results = list(search_local(query))
    seen = {s.symbol for s in results}

    def _merge(items):
        for s in items:
            if s.symbol not in seen:
                results.append(s)
                seen.add(s.symbol)

    try:
        _merge(_yahoo.search(query))
    except Exception:
        pass
    fh = _get_finnhub()
    if fh is not None:
        try:
            _merge(fh.search(query))
        except Exception:
            pass
    return results[:30]


def quote(symbol: str) -> dict:
    df = get_ohlcv(symbol, "1d", "5d")
    if df.empty:
        return {"symbol": symbol, "price": None, "change": None}
    last = float(df.iloc[-1]["close"])
    prev = float(df.iloc[-2]["close"]) if len(df) > 1 else last
    change = (last - prev) / prev * 100 if prev else 0.0
    return {"symbol": symbol, "price": last, "change": round(change, 2)}
