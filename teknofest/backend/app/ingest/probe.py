"""Gerçek katılım bankası URL'lerini yoklama aracı.

Her aday URL için: HTTP durumu, temizlenmiş metin uzunluğu ve domaine özgü
anahtar terimlerin (kâr payı, katılma, %, vade) görünüp görünmediğini ölçer.
Böylece hangi URL'lerin httpx ile canlı çıkarıma uygun olduğunu görürüz.

Çalıştırma:
    python -m app.ingest.probe
"""
from __future__ import annotations

import re

from .scraper import fetch_clean

# Aday URL'ler — banka: [url, ...]. İlk çalışan/zengin olan canlı kaynak seçilir.
CANDIDATES: dict[str, list[str]] = {
    "Kuveyt Türk": [
        "https://www.kuveytturk.com.tr/bireysel/mevduat-ve-yatirim/katilma-hesaplari",
        "https://www.kuveytturk.com.tr/bireysel/mevduat-ve-yatirim",
        "https://www.kuveytturk.com.tr/kampanyalar",
    ],
    "Albaraka Türk": [
        "https://www.albaraka.com.tr/katilim-hesaplari",
        "https://www.albaraka.com.tr/bireysel/mevduat-urunleri",
        "https://www.albaraka.com.tr/kampanyalar",
    ],
    "Türkiye Finans": [
        "https://www.turkiyefinans.com.tr/tr-tr/bireysel/mevduat-ve-yatirim/Sayfalar/kar-payli-kobi-hesabi.aspx",
        "https://www.turkiyefinans.com.tr/tr-tr/bireysel/mevduat-ve-yatirim",
        "https://www.turkiyefinans.com.tr/tr-tr/kampanyalar",
    ],
    "Ziraat Katılım": [
        "https://www.ziraatkatilim.com.tr/bireysel/katilim-fonu",
        "https://www.ziraatkatilim.com.tr/bireysel/hesaplar",
        "https://www.ziraatkatilim.com.tr/kampanyalar",
    ],
    "Vakıf Katılım": [
        "https://www.vakifkatilim.com.tr/tr/bireysel/katilim-hesaplari",
        "https://www.vakifkatilim.com.tr/tr/bireysel",
        "https://www.vakifkatilim.com.tr/tr/kampanyalar",
    ],
    "Emlak Katılım": [
        "https://www.emlakkatilim.com.tr/bireysel/mevduat",
        "https://www.emlakkatilim.com.tr/bireysel",
        "https://www.emlakkatilim.com.tr/kampanyalar",
    ],
}

KEY_TERMS = ["kâr payı", "kar payı", "katılma", "katılım", "vade", "kampanya"]


def probe_url(url: str) -> dict:
    text = fetch_clean(url)
    low = text.lower()
    pct = len(re.findall(r"%\s?\d", text))
    hits = [t for t in KEY_TERMS if t in low]
    return {
        "url": url,
        "ok": bool(text),
        "len": len(text),
        "pct_count": pct,
        "terms": hits,
        "usable": bool(text) and len(text) > 400 and len(hits) >= 1,
    }


def probe_all() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for banka, urls in CANDIDATES.items():
        out[banka] = [probe_url(u) for u in urls]
    return out


if __name__ == "__main__":
    res = probe_all()
    for banka, rows in res.items():
        print(f"\n=== {banka} ===")
        for r in rows:
            flag = "USABLE" if r["usable"] else ("ok-thin" if r["ok"] else "FAIL")
            print(f"  [{flag}] len={r['len']:>6} %={r['pct_count']:>3} terms={r['terms']}  {r['url']}")
