"""Karşılaştırma & normalizasyon motoru.

Ürünleri tip ve para birimine göre karşılaştırılabilir hale getirir,
sıralar ve "en iyi" seçimleri çıkarır. Adil karşılaştırma için kâr payı
oranlarını yıllığa (APY benzeri) sabitler ve yalnız aynı türdeki ürünleri
kıyaslar.
"""
from __future__ import annotations

from ..extract.schema import KatilimUrunu


def _flat(urunler: list[KatilimUrunu]) -> list[dict]:
    return [u.to_flat() for u in urunler]


def filtrele(
    urunler: list[KatilimUrunu],
    *,
    urun_tipi: str | None = None,
    para_birimi: str | None = None,
    min_oran: float | None = None,
    max_vade_gun: int | None = None,
    sadece_kampanya: bool | None = None,
) -> list[KatilimUrunu]:
    out = []
    for u in urunler:
        f = u.to_flat()
        if urun_tipi and f["urun_tipi"] != urun_tipi:
            continue
        if para_birimi and f["para_birimi"] != para_birimi:
            continue
        if min_oran is not None and (f["kar_payi_orani"] or 0) < min_oran:
            continue
        if max_vade_gun is not None and (f["vade_gun"] or 10**9) > max_vade_gun:
            continue
        if sadece_kampanya and not f["kampanya"]:
            continue
        out.append(u)
    return out


def sirala(urunler: list[KatilimUrunu], anahtar: str = "kar_payi_orani", artan: bool = False) -> list[dict]:
    rows = _flat(urunler)
    rows = [r for r in rows if r.get(anahtar) is not None]
    return sorted(rows, key=lambda r: r[anahtar], reverse=not artan)


def en_iyi_oran(
    urunler: list[KatilimUrunu], *, urun_tipi: str | None = None, para_birimi: str | None = None
) -> dict | None:
    pool = filtrele(urunler, urun_tipi=urun_tipi, para_birimi=para_birimi)
    sorted_rows = sirala(pool, "kar_payi_orani", artan=False)
    return sorted_rows[0] if sorted_rows else None


def karsilastir(urunler: list[KatilimUrunu], urun_tipi: str | None = None) -> dict:
    """Bir ürün tipi için tam karşılaştırma tablosu + en iyi/ortalama."""
    pool = filtrele(urunler, urun_tipi=urun_tipi)
    rows = sirala(pool, "kar_payi_orani", artan=False)
    oranlar = [r["kar_payi_orani"] for r in rows if r["kar_payi_orani"] is not None]
    return {
        "urun_tipi": urun_tipi,
        "adet": len(rows),
        "satirlar": rows,
        "en_iyi": rows[0] if rows else None,
        "ortalama_oran": round(sum(oranlar) / len(oranlar), 3) if oranlar else None,
        "oran_araligi": [min(oranlar), max(oranlar)] if oranlar else None,
    }


def getiri_hesapla(anapara: float, yillik_oran_yuzde: float, vade_gun: int) -> dict:
    """Basit (faizsiz model: kâr payı oranı yıllık brüt) getiri hesabı."""
    brut = anapara * (yillik_oran_yuzde / 100.0) * (vade_gun / 365.0)
    stopaj = brut * 0.075  # temsilî stopaj
    return {
        "anapara": anapara,
        "vade_gun": vade_gun,
        "yillik_oran": yillik_oran_yuzde,
        "brut_kar_payi": round(brut, 2),
        "tahmini_stopaj": round(stopaj, 2),
        "net_kar_payi": round(brut - stopaj, 2),
        "vade_sonu_toplam": round(anapara + brut - stopaj, 2),
    }


def skor_tablosu(urunler: list[KatilimUrunu]) -> dict:
    """Şartname 5.7 karşılaştırma kriterleri — kategori 'kazananları'.

    Katılım nüansı: MEVDUAT/katılma hesabında yüksek kâr payı iyidir;
    FİNANSMAN'da DÜŞÜK kâr payı iyidir (şartname örneği). Ayrı ele alınır.
    """
    flat = [u.to_flat() for u in urunler]

    def _pick(key, *, reverse, filt=None):
        pool = [r for r in flat if r.get(key) is not None and (filt is None or filt(r))]
        if not pool:
            return None
        return sorted(pool, key=lambda r: r[key], reverse=reverse)[0]

    def _mevduat(r):
        return r["urun_tipi"] in ("katilma_hesabi", "altin_hesabi", "doviz_katilma")

    def _finansman(r):
        return r["urun_tipi"] == "finansman"

    en_avantajli = None
    pool_av = [r for r in flat if r.get("avantajlar")]
    if pool_av:
        en_avantajli = max(pool_av, key=lambda r: len(r["avantajlar"]))

    return {
        "en_yuksek_kar_payi_mevduat": _pick("kar_payi_orani", reverse=True, filt=_mevduat),
        "en_dusuk_kar_payi_finansman": _pick("kar_payi_orani", reverse=False, filt=_finansman),
        "en_uzun_vade": _pick("vade_gun", reverse=True),
        "en_dusuk_asgari_tutar": _pick("min_tutar", reverse=False),
        "en_avantajli_kampanya": en_avantajli,
        "kriterler": [
            "En yüksek kâr payı (mevduat/katılma)",
            "En düşük kâr payı (finansman)",
            "En uzun vade",
            "En düşük asgari tutar",
            "En avantajlı (en çok avantaj)",
        ],
    }


def ozet(urunler: list[KatilimUrunu]) -> dict:
    rows = _flat(urunler)
    bankalar = sorted({r["banka"] for r in rows})
    tipler = sorted({r["urun_tipi"] for r in rows})
    grounded = sum(u.grounded_field_count() for u in urunler)
    return {
        "urun_sayisi": len(rows),
        "banka_sayisi": len(bankalar),
        "bankalar": bankalar,
        "urun_tipleri": tipler,
        "toplam_grounded_alan": grounded,
        "ort_guven": round(sum(r["guven"] for r in rows) / len(rows), 3) if rows else 0,
    }
