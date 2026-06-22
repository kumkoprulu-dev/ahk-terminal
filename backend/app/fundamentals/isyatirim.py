"""İş Yatırım tabanlı BIST temel analiz verisi.

Finnhub ücretsiz katmanı BIST temeli vermez; yfinance .info da Yahoo'da 429 alabilir.
İş Yatırım'ın kamuya açık MaliTablo uç noktası BIST şirketlerinin bilanço + gelir tablosu
kalemlerini verir; oranlar bunlardan + güncel fiyattan hesaplanır.

İki tablo formatı desteklenir:
  - Sanayi/holding (financialGroup=XI_29): tam set (PE/PB/PS, marjlar, borç, cari oran…)
  - Banka/finans  (financialGroup=UFRS_K): banka kalemleriyle PE/PB/ROE/ROA/kâr büyümesi
    (banka bilançosunda marj/cari oran/borç-özsermaye anlamlı olmadığından hesaplanmaz).
"""
from __future__ import annotations

from datetime import datetime

import httpx

_URL = "https://www.isyatirim.com.tr/_layouts/15/Isyatirim.Website/Common/Data.aspx/MaliTablo"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

_EMPTY_FIELDS = (
    "name", "sector", "pe", "forward_pe", "pb", "ps", "roe", "roa", "net_margin",
    "operating_margin", "gross_margin", "revenue_growth", "earnings_growth",
    "dividend_yield", "current_ratio", "debt_to_equity", "market_cap", "beta", "eps")


def _fetch(code: str, year1: int, group: str) -> dict | None:
    # Uç nokta 4 dönem zorunlu kılar (eksikse 404). 4 yıl-sonu dönemi gönderilir.
    params = {
        "companyCode": code, "exchange": "TRY", "financialGroup": group,
        "year1": year1, "period1": 12, "year2": year1 - 1, "period2": 12,
        "year3": year1 - 2, "period3": 12, "year4": year1 - 3, "period4": 12,
    }
    try:
        r = httpx.get(_URL, params=params, headers={"User-Agent": _UA}, timeout=20.0)
        r.raise_for_status()
        rows = (r.json() or {}).get("value") or []
    except Exception:
        return None
    return {row.get("itemCode"): row for row in rows} if rows else None


def _v(items: dict, code: str, idx: int = 1):
    row = items.get(code)
    if not row:
        return None
    val = row.get(f"value{idx}")
    try:
        return float(val) if val not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _base(symbol: str) -> dict:
    d = {f: None for f in _EMPTY_FIELDS}
    d["symbol"] = symbol
    d["source"] = "isyatirim"
    return d


def _pct(a, b):
    return round(a / b * 100, 2) if (a is not None and b not in (None, 0)) else None


def get_bist_fundamentals(symbol: str, price: float | None) -> dict | None:
    code = symbol.replace(".IS", "").upper()
    now = datetime.now()
    for group, is_bank in (("XI_29", False), ("UFRS_K", True)):
        items = None
        for y1 in (now.year, now.year - 1, now.year - 2):
            cand = _fetch(code, y1, group)
            if cand and _v(cand, "3Z") is not None:  # 3Z = Net Dönem Karı (her iki formatta)
                items = cand
                break
        if items:
            return _parse_bank(symbol, price, items) if is_bank else _parse_industrial(symbol, price, items)
    return None


def _parse_industrial(symbol: str, price: float | None, items: dict) -> dict:
    equity = _v(items, "2O") or _v(items, "2N")
    ni = _v(items, "3Z")
    ni_prev = _v(items, "3Z", 2)
    rev = _v(items, "3C")
    rev_prev = _v(items, "3C", 2)
    assets = _v(items, "1BL")
    gross = _v(items, "3D")
    op = _v(items, "3DF")
    debt = (_v(items, "2AA") or 0) + (_v(items, "2BA") or 0)
    cur_a = _v(items, "1A")
    cur_l = _v(items, "2A")
    shares = _v(items, "2OA")  # Ödenmiş Sermaye (nominal 1 TL)
    eps = (ni / shares) if (shares and ni) else None
    mcap = price * shares if (price and shares) else None

    d = _base(symbol)
    d.update({
        "pe": round(mcap / ni, 2) if (mcap and ni and ni > 0) else None,
        "pb": round(mcap / equity, 2) if (mcap and equity and equity > 0) else None,
        "ps": round(mcap / rev, 2) if (mcap and rev and rev > 0) else None,
        "roe": _pct(ni, equity), "roa": _pct(ni, assets),
        "net_margin": _pct(ni, rev), "gross_margin": _pct(gross, rev), "operating_margin": _pct(op, rev),
        "revenue_growth": _pct(rev - rev_prev, rev_prev) if (rev and rev_prev) else None,
        "earnings_growth": _pct(ni - ni_prev, ni_prev) if (ni and ni_prev and ni_prev > 0) else None,
        "current_ratio": round(cur_a / cur_l, 2) if (cur_a and cur_l) else None,
        "debt_to_equity": round(debt / equity, 3) if (equity and equity > 0) else None,
        "market_cap": round(mcap / 1e6, 1) if mcap else None,
        "eps": round(eps, 2) if eps else None,
    })
    return d


def _parse_bank(symbol: str, price: float | None, items: dict) -> dict:
    """Banka/finans: bilanço yapısı farklı; PE/PB/ROE/ROA/kâr büyümesi hesaplanır."""
    equity = _v(items, "2O")          # XVI. ÖZKAYNAKLAR
    ni = _v(items, "3Z")              # NET DÖNEM KARI
    ni_prev = _v(items, "3Z", 2)
    assets = _v(items, "1Z")          # AKTİF TOPLAMI
    shares = _v(items, "2OA")         # Ödenmiş Sermaye
    eps = (ni / shares) if (shares and ni) else None
    mcap = price * shares if (price and shares) else None

    d = _base(symbol)
    d.update({
        "pe": round(mcap / ni, 2) if (mcap and ni and ni > 0) else None,
        "pb": round(mcap / equity, 2) if (mcap and equity and equity > 0) else None,
        "roe": _pct(ni, equity), "roa": _pct(ni, assets),
        "earnings_growth": _pct(ni - ni_prev, ni_prev) if (ni and ni_prev and ni_prev > 0) else None,
        "market_cap": round(mcap / 1e6, 1) if mcap else None,
        "eps": round(eps, 2) if eps else None,
    })
    return d
