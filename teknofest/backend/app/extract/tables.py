"""Oran-tablosu segmentasyonu — katılım bankası tablolarını yapısal çıkarım.

Katılım bankaları getiriyi çoğunlukla SABİT % oran olarak değil, KÂR PAYLAŞIM
ORANI olarak yayınlar (ör. "90-10" = %90 müşteri / %10 banka). Bu modül:
  * Bir sayfadaki tabloların hangilerinin oran/paylaşım tablosu olduğunu bulur,
  * Paylaşım oranı kademe×vade ızgarasını çözer (grounding ile),
  * Varsa "Brüt Oran (Yıllık)" gibi gerçek yıllık oranı yakalar,
  * Asgari tutarı (Açılış/Alt Bakiye) çıkarır,
  * LLM için yalnız ilgili tabloların temiz markdown bloğunu üretir.
"""
from __future__ import annotations

import re

from ..ingest.scraper import Table
from .schema import Grounded

_RATE_HINTS = ("kâr payı", "kar payı", "kar payi", "paylaşım", "paylasim",
               "oran", "getiri", "vade", "katılma", "katilma")
_RATIO_RE = re.compile(r"\b(\d{2,3})\s*-\s*(\d{1,3})\b")     # 90-10
_PCT_RE = re.compile(r"%\s?(\d{1,3}(?:[.,]\d{1,2})?)")
_AMOUNT_RE = re.compile(r"\b(\d{1,3}(?:\.\d{3})+|\d{3,})\b")  # 25.000 / 1000


def _blob(t: Table) -> str:
    return " ".join([t.caption, *t.headers, *[" ".join(r) for r in t.rows]]).lower()


def is_rate_table(t: Table) -> bool:
    blob = _blob(t)
    has_hint = any(h in blob for h in _RATE_HINTS)
    has_signal = bool(_RATIO_RE.search(blob) or _PCT_RE.search(blob))
    return has_hint and has_signal


def rate_tables(tables: list[Table]) -> list[Table]:
    return [t for t in tables if is_rate_table(t)]


def tables_markdown(tables: list[Table], limit: int = 4) -> str:
    """İlgili oran tablolarını LLM için temiz markdown bloğuna çevirir."""
    rt = rate_tables(tables)[:limit]
    return "\n\n".join(t.to_markdown() for t in rt)


def _max_maturity_col(headers: list[str]) -> int | None:
    """En uzun vade sütununun indeksini bul (ör. '6 Aylık' > '1 Aylık')."""
    best_idx, best_days = None, -1
    for i, h in enumerate(headers):
        m = re.search(r"(\d+)\s*ay", h.lower())
        d = int(m.group(1)) * 30 if m else None
        if d is None:
            m2 = re.search(r"(\d+)\s*g[üu]n", h.lower())
            d = int(m2.group(1)) if m2 else None
        if d is not None and d > best_days:
            best_days, best_idx = d, i
    return best_idx


def extract_from_tables(tables: list[Table]) -> dict:
    """Tablolardan paylaşım oranı, yıllık oran ve asgari tutarı çıkar (grounding'li).

    Dönüş: {'paylasim_orani': Grounded[str], 'kar_payi_orani': Grounded[float],
            'min_tutar': Grounded[float]}
    """
    res: dict[str, Grounded] = {}
    for t in rate_tables(tables):
        blob_rows = [" ".join(r) for r in t.rows]

        # 1) Gerçek yıllık brüt oran (hesap-makinesi/duyuru tablosu)
        #    "Brüt Oran (Yıllık)" başlıklı ve >0 değerli bir hücre.
        for hi, h in enumerate(t.headers):
            if ("brüt oran" in h.lower() or "brut oran" in h.lower()) and "yıl" in h.lower():
                for r in t.rows:
                    if hi < len(r):
                        m = _PCT_RE.search(r[hi])
                        if m:
                            val = float(m.group(1).replace(",", "."))
                            if val > 0 and "kar_payi_orani" not in res:
                                cap = t.caption or "Oran tablosu"
                                res["kar_payi_orani"] = Grounded(
                                    value=val, source_quote=f"{cap}: {h} %{m.group(1)}",
                                    confidence=0.85)

        # 2) Paylaşım oranı ızgarası (kademe × vade → 90-10)
        if "paylaşım" in t.caption.lower() or "paylasim" in t.caption.lower() \
                or any(_RATIO_RE.search(br) for br in blob_rows):
            mat_idx = _max_maturity_col(t.headers)
            # İlk kademe satırını (genelde "Klasik") tercih et
            for r in t.rows:
                kademe = r[0] if r else ""
                # vade sütunu varsa oradan, yoksa satırdaki en yüksek paylaşımı al
                cell = r[mat_idx] if (mat_idx is not None and mat_idx < len(r)) else " ".join(r)
                mm = _RATIO_RE.search(cell)
                if mm and "paylasim_orani" not in res:
                    musteri, banka = mm.group(1), mm.group(2)
                    etiket = f"{musteri}-{banka}"
                    vade_h = t.headers[mat_idx] if (mat_idx is not None and mat_idx < len(t.headers)) else ""
                    note = f"{etiket} ({kademe}{', ' + vade_h if vade_h else ''})".strip()
                    cap = t.caption or "Kâr paylaşım oranları"
                    quote = f"{cap}: {kademe} {vade_h} → {etiket}".replace("  ", " ").strip()
                    res["paylasim_orani"] = Grounded(
                        value=note, source_quote=quote, confidence=0.85)
                    break

        # 3) Asgari tutar (Açılış/Alt Bakiye sütunu)
        for hi, h in enumerate(t.headers):
            if "bakiye" in h.lower() and "min_tutar" not in res:
                vals = []
                for r in t.rows:
                    if hi < len(r):
                        am = _AMOUNT_RE.search(r[hi].replace(".", ""))
                        if am:
                            try:
                                vals.append(float(am.group(1)))
                            except ValueError:
                                pass
                if vals:
                    cap = t.caption or "Oran tablosu"
                    res["min_tutar"] = Grounded(
                        value=min(vals), source_quote=f"{cap}: {h} asgari {min(vals):,.0f}",
                        confidence=0.7)
    return res
