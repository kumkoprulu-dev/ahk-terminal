"""Google News RSS üzerinden haber başlığı çekimi (httpx + XML; feedparser'a gerek yok)."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

from app.data.universe import all_symbols

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
_RSS = "https://news.google.com/rss/search"

# sembol -> şirket/varlık adı (daha iyi arama sorgusu için)
_NAME_BY_SYMBOL = {s.symbol: s.name for s in all_symbols()}


def _query_for(symbol: str) -> str:
    """Sembol tipine göre uygun arama sorgusu üretir."""
    name = _NAME_BY_SYMBOL.get(symbol, "")
    if symbol.endswith(".IS"):
        base = name or symbol.replace(".IS", "")
        return f"{base} hisse"
    if symbol.endswith("-USD"):
        return f"{name or symbol.replace('-USD', '')} crypto"
    if symbol.endswith("=F"):
        return f"{name or symbol} price"
    return f"{name or symbol} stock"


_YAHOO_SEARCH = "https://query2.finance.yahoo.com/v1/finance/search"


def fetch_google_news(symbol: str, limit: int = 8) -> list[dict]:
    """Google News RSS kaynağı."""
    is_tr = symbol.endswith(".IS")
    hl, gl, ceid = ("tr", "TR", "TR:tr") if is_tr else ("en-US", "US", "US:en")
    params = {"q": _query_for(symbol), "hl": hl, "gl": gl, "ceid": ceid}
    try:
        r = httpx.get(_RSS, params=params, headers={"User-Agent": _UA},
                      timeout=12.0, follow_redirects=True)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception:
        return []
    out: list[dict] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        source = ""
        m = re.match(r"^(.*) - ([^-]+)$", title)
        if m:
            title, source = m.group(1).strip(), m.group(2).strip()
        out.append({
            "title": title, "source": source or "Google News",
            "link": item.findtext("link") or "", "provider": "google",
            "published": _fmt_date(item.findtext("pubDate")),
        })
        if len(out) >= limit:
            break
    return out


def fetch_yahoo_news(symbol: str, limit: int = 8) -> list[dict]:
    """Yahoo Finance haber kaynağı (search endpoint)."""
    try:
        r = httpx.get(_YAHOO_SEARCH, params={"q": symbol, "newsCount": limit, "quotesCount": 0},
                      headers={"User-Agent": _UA, "Accept": "application/json"},
                      timeout=12.0, follow_redirects=True)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []
    out: list[dict] = []
    for it in data.get("news", [])[:limit]:
        title = (it.get("title") or "").strip()
        if not title:
            continue
        ts = it.get("providerPublishTime")
        pub = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M") if ts else ""
        out.append({
            "title": title, "source": it.get("publisher") or "Yahoo Finance",
            "link": it.get("link") or "", "provider": "yahoo", "published": pub,
        })
    return out


def fetch_news(symbol: str, limit: int = 6, lang: str | None = None) -> list[dict]:
    """Birden çok kaynaktan haber çeker, başlığa göre tekilleştirir, tarihe göre sıralar."""
    items = fetch_google_news(symbol, limit=limit + 4) + fetch_yahoo_news(symbol, limit=limit + 4)
    seen: set[str] = set()
    uniq: list[dict] = []
    for it in items:
        key = re.sub(r"[^a-z0-9ığüşöç]+", "", it["title"].lower())[:60]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    uniq.sort(key=lambda d: d.get("published", ""), reverse=True)
    return uniq[:limit]


def _fmt_date(s: str | None) -> str:
    if not s:
        return ""
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d %H:%M")
        except Exception:
            continue
    return s[:16]
