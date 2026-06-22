"""Temel analiz (fundamentals) verisi sağlayıcısı.

Kaynak önceliği:
  - ABD/global hisse (.IS / -USD / =F olmayan): Finnhub (ücretsiz katmanda çalışır) → yfinance
  - BIST (.IS): yfinance .info (kullanıcının makinesinde çalışır; sandbox IP'si 429 alabilir)
  - Kripto / emtia: temel veri yok (boş döner)

Tüm oranlar normalize edilir: marj/ROE/ROA/büyüme % cinsinden, borç/özsermaye oran,
temettü verimi % cinsinden. Fundamentals yavaş değiştiği için uzun süre önbelleklenir.
"""
from __future__ import annotations

import json
import os
import threading
import time

from app.config import CACHE_DIR, settings

# Önbellek (sembol -> (zaman, veri)); fundamentals yavaş değişir. Bellek + disk (kalıcı).
_CACHE: dict[str, tuple[float, dict]] = {}
_TTL = 6 * 3600
_CACHE_FILE = CACHE_DIR / "fundamentals.json"
_lock = threading.Lock()
_loaded = False


def _load_disk():
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        raw = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        for sym, rec in raw.items():
            _CACHE[sym] = (rec["ts"], rec["data"])
    except Exception:
        pass


def _save_disk():
    try:
        out = {s: {"ts": ts, "data": d} for s, (ts, d) in _CACHE.items()}
        tmp = str(_CACHE_FILE) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(out, f)
        os.replace(tmp, _CACHE_FILE)
    except Exception:
        pass

FIELDS = [
    "name", "sector", "pe", "forward_pe", "pb", "ps", "roe", "roa",
    "net_margin", "operating_margin", "gross_margin", "revenue_growth",
    "earnings_growth", "dividend_yield", "current_ratio", "debt_to_equity",
    "market_cap", "beta", "eps",
]


def _empty(symbol: str) -> dict:
    d = {f: None for f in FIELDS}
    d["symbol"] = symbol
    d["source"] = None
    return d


def _has_fundamentals(symbol: str) -> bool:
    return not (symbol.endswith("-USD") or symbol.endswith("=F"))


def get_fundamentals(symbol: str) -> dict:
    if not _has_fundamentals(symbol):
        return _empty(symbol)
    _load_disk()
    now = time.time()
    cached = _CACHE.get(symbol)
    if cached and now - cached[0] < _TTL:
        return cached[1]

    data = _empty(symbol)
    is_bist = symbol.endswith(".IS")
    if is_bist:
        # BIST: İş Yatırım (mali tablo + güncel fiyat) birincil
        from app.fundamentals.isyatirim import get_bist_fundamentals
        try:
            d = get_bist_fundamentals(symbol, _last_price(symbol))
        except Exception:
            d = None
        if d:
            d["name"] = _bist_name(symbol)
            data = d
    elif settings.has_finnhub:
        # ABD/global: önce Finnhub
        data = _from_finnhub(symbol) or data

    # yedek: yfinance
    if data["source"] is None:
        data = _from_yfinance(symbol) or data

    with _lock:
        _CACHE[symbol] = (now, data)
        _save_disk()
    return data


def _last_price(symbol: str) -> float | None:
    try:
        from app.data.service import get_ohlcv
        df = get_ohlcv(symbol, "1d", "5d")
        return float(df["close"].iloc[-1]) if df is not None and not df.empty else None
    except Exception:
        return None


def _bist_name(symbol: str) -> str:
    try:
        from app.data.universe import _BIST_NAMES
        code = symbol.replace(".IS", "")
        return _BIST_NAMES.get(code) or code
    except Exception:
        return symbol.replace(".IS", "")


def _from_finnhub(symbol: str) -> dict | None:
    try:
        import httpx
        r = httpx.get(
            "https://finnhub.io/api/v1/stock/metric",
            params={"symbol": symbol, "metric": "all", "token": settings.finnhub_api_key},
            timeout=12.0,
        )
        r.raise_for_status()
        m = r.json().get("metric", {})
    except Exception:
        return None
    if not m:
        return None
    d = _empty(symbol)
    d.update({
        "pe": m.get("peTTM") or m.get("peAnnual"),
        "pb": m.get("pbQuarterly") or m.get("pbAnnual"),
        "ps": m.get("psTTM") or m.get("psAnnual"),
        "roe": m.get("roeTTM"),
        "roa": m.get("roaTTM"),
        "net_margin": m.get("netProfitMarginTTM"),
        "operating_margin": m.get("operatingMarginTTM"),
        "gross_margin": m.get("grossMarginTTM"),
        "revenue_growth": m.get("revenueGrowthTTMYoy"),
        "earnings_growth": m.get("epsGrowthTTMYoy"),
        "dividend_yield": m.get("dividendYieldIndicatedAnnual"),
        "current_ratio": m.get("currentRatioQuarterly"),
        "debt_to_equity": m.get("totalDebt/totalEquityQuarterly"),
        "market_cap": m.get("marketCapitalization"),
        "beta": m.get("beta"),
        "eps": m.get("epsTTM"),
        "source": "finnhub",
    })
    return d


def _from_yfinance(symbol: str) -> dict | None:
    try:
        import yfinance as yf
        info = yf.Ticker(symbol).info
    except Exception:
        return None
    if not info or not isinstance(info, dict) or len(info) < 3:
        return None

    def pct(x):
        return round(x * 100, 2) if isinstance(x, (int, float)) else None

    dy = info.get("dividendYield")
    if isinstance(dy, (int, float)) and dy < 1:
        dy = dy * 100  # yfinance bazen kesir döner
    de = info.get("debtToEquity")
    if isinstance(de, (int, float)):
        de = de / 100  # yfinance yüzde formunda (79.5) -> oran (0.795)

    d = _empty(symbol)
    d.update({
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "pb": info.get("priceToBook"),
        "ps": info.get("priceToSalesTrailing12Months"),
        "roe": pct(info.get("returnOnEquity")),
        "roa": pct(info.get("returnOnAssets")),
        "net_margin": pct(info.get("profitMargins")),
        "operating_margin": pct(info.get("operatingMargins")),
        "gross_margin": pct(info.get("grossMargins")),
        "revenue_growth": pct(info.get("revenueGrowth")),
        "earnings_growth": pct(info.get("earningsGrowth")),
        "dividend_yield": round(dy, 2) if isinstance(dy, (int, float)) else None,
        "current_ratio": info.get("currentRatio"),
        "debt_to_equity": round(de, 3) if isinstance(de, (int, float)) else None,
        "market_cap": (info.get("marketCap") or 0) / 1e6 or None,
        "beta": info.get("beta"),
        "eps": info.get("trailingEps"),
        "source": "yfinance",
    })
    return d
