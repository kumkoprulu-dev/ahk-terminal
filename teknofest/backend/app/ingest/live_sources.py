"""Gerçek katılım bankası canlı kaynak kayıt defteri (DOĞRULANMIŞ URL'ler).

Bu URL'ler probe ile test edilmiş ve httpx (server-render) ile gerçek içerik
döndürdüğü teyit edilmiştir. Her giriş bir ürün/kampanya sayfasıdır.

JS-SPA bankaları (ör. Emlak Katılım) httpx ile içerik vermez; bunlar
`render_required=True` ile işaretlenir ve canlı çekimde paketli örnek veriye
düşülür (headless tarayıcı entegrasyonu yol haritasındadır).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LiveSource:
    banka: str
    urun_adi: str
    url: str
    para_birimi_ipucu: str | None = None   # url/başlıktan bilinen para birimi
    render_required: bool = False          # JS-SPA → httpx yetersiz


LIVE_SOURCES: list[LiveSource] = [
    # --- Kuveyt Türk (server-render, oran içerir) ---
    LiveSource("Kuveyt Türk", "Katılma Hesabı",
               "https://www.kuveytturk.com.tr/kendim-icin/hesaplar/katilma-hesaplari/katilma-hesabi",
               para_birimi_ipucu="TRY"),
    LiveSource("Kuveyt Türk", "Dijital Katılma Hesabı",
               "https://www.kuveytturk.com.tr/kendim-icin/hesaplar/katilma-hesaplari/dijital-katilma-hesabi",
               para_birimi_ipucu="TRY"),
    # --- Vakıf Katılım ---
    LiveSource("Vakıf Katılım", "Katılma Hesabı",
               "https://www.vakifkatilim.com.tr/tr/kendim-icin/hesaplar/katilma-hesaplari/katilma-hesabi",
               para_birimi_ipucu="TRY"),
    LiveSource("Vakıf Katılım", "Kâr Paylaşım Oranları",
               "https://www.vakifkatilim.com.tr/tr/kendim-icin/hesaplar/katilma-hesaplari/kar-paylasim-oranlari",
               para_birimi_ipucu="TRY"),
    # --- Albaraka Türk ---
    LiveSource("Albaraka Türk", "Katılma Hesapları",
               "https://www.albaraka.com.tr/tr/bireysel/hesaplar/katilma-hesaplari",
               para_birimi_ipucu="TRY"),
    LiveSource("Albaraka Türk", "Vade Farksız Kampanyası",
               "https://www.albaraka.com.tr/tr/kampanyalar/detay/vade-farksiz-kampanyasi",
               para_birimi_ipucu="TRY"),
    # --- Türkiye Finans (ASP.NET, <form> korunur) ---
    LiveSource("Türkiye Finans", "Kampanyalar",
               "https://www.turkiyefinans.com.tr/tr-tr/kampanyalar",
               para_birimi_ipucu="TRY"),
    # --- Ziraat Katılım ---
    LiveSource("Ziraat Katılım", "Hesaplar",
               "https://www.ziraatkatilim.com.tr/bireysel/hesaplar",
               para_birimi_ipucu="TRY"),
    # --- Emlak Katılım (JS-SPA → render gerekli, örneğe düşer) ---
    LiveSource("Emlak Katılım", "Katılma Hesapları",
               "https://www.emlakkatilim.com.tr/tr/bireysel/hesaplar/katilma-hesaplari",
               para_birimi_ipucu="TRY", render_required=True),
]


def get_live_sources() -> list[LiveSource]:
    return list(LIVE_SOURCES)
