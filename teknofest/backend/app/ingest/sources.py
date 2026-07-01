"""Katılım bankası kaynak kayıt defteri + paketlenmiş örnek metinler.

Gerçek çekimde `scraper.fetch_clean(url)` kullanılır. Demo/CI ve hakem
sunumunun internet olmadan da çalışması için her bankadan gerçekçi (sentetik
ama domaine sadık) ürün/kampanya metinleri burada paketlenir.

NOT: Metinler örnek/sentetiktir; oranlar temsilîdir. Amaç bilgi-çıkarım
doğruluğunu göstermek, gerçek oran yayınlamak değil.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BankSource:
    banka: str
    url: str
    sample_text: str


# BDDK Liste/77 — Türkiye'deki TÜM katılım bankaları (şartname 5.1). 3'ü dijital.
KATILIM_BANKALARI = [
    "Kuveyt Türk",
    "Albaraka Türk",
    "Türkiye Finans",
    "Ziraat Katılım",
    "Vakıf Katılım",
    "Emlak Katılım",
    "Hayat Finans",       # dijital
    "TOM Katılım",        # dijital
    "Dünya Katılım",
    "Adil Katılım",       # dijital
]


SAMPLE_SOURCES: list[BankSource] = [
    BankSource(
        banka="Kuveyt Türk",
        url="https://www.kuveytturk.com.tr/ornek/katilma-hesabi",
        sample_text=(
            "Katılma Hesabı ile birikimleriniz faizsiz bankacılık ilkelerine uygun şekilde "
            "değerlendirilir. 32 gün vadeli TL katılma hesabında brüt yıllık kâr payı oranı %48 "
            "olarak gerçekleşmektedir. Hesap açmak için minimum 1.000 TL tutar yeterlidir; üst "
            "limit bulunmamaktadır. Kâr payı vade sonunda hesabınıza yansıtılır. Dijitalden açılan "
            "hesaplarda ek 2 puan kâr payı avantajı sunulmaktadır. Kampanya 31 Temmuz 2026 "
            "tarihine kadar geçerlidir."
        ),
    ),
    BankSource(
        banka="Albaraka Türk",
        url="https://www.albaraka.com.tr/ornek/altin-katilma",
        sample_text=(
            "Altın Katılma Hesabı, gram altın bazında birikim yapmanızı sağlar. Minimum 1 gram "
            "altın ile hesap açabilirsiniz. 90 gün vadeli altın katılma hesabında yıllık kâr payı "
            "oranı brüt %3,25'tir. Fiziki altın teslimi şubelerimizden yapılabilir. Hesap işletim "
            "ücreti alınmaz. Mobil şubeden açılışta ilk ay masrafsızdır."
        ),
    ),
    BankSource(
        banka="Türkiye Finans",
        url="https://www.turkiyefinans.com.tr/ornek/doviz-katilma",
        sample_text=(
            "Dolar (USD) katılma hesabı ile döviz birikimlerinizi değerlendirin. 180 gün vade için "
            "yıllık brüt kâr payı oranı %4,75 seviyesindedir. Asgari hesap açılış tutarı 100 USD'dir. "
            "Vadeden önce çekim yapılması halinde kâr payı tahakkuk etmez. Yeni müşterilere özel ilk "
            "vadede +0,50 puan ilave kâr payı tanımlanır. Kampanya 15 Ağustos 2026'da sona erer."
        ),
    ),
    BankSource(
        banka="Ziraat Katılım",
        url="https://www.ziraatkatilim.com.tr/ornek/konut-finansmani",
        sample_text=(
            "Konut Finansmanı (faizsiz) ile ev sahibi olun. 120 ay vadeye kadar finansman imkânı "
            "sunulmaktadır. Aylık kâr payı oranı %2,89'dan başlamaktadır. Konut değerinin en fazla "
            "%80'i kadar finansman kullandırılır. Dosya masrafı alınmaz. Emekli ve maaş müşterilerine "
            "özel indirimli oranlar geçerlidir."
        ),
    ),
    BankSource(
        banka="Vakıf Katılım",
        url="https://www.vakifkatilim.com.tr/ornek/katilma-hesabi",
        sample_text=(
            "TL Katılma Hesabı kampanyası! 32 günlük vadede yeni gelen birikimlere brüt yıllık %50 "
            "kâr payı oranı uygulanır. Minimum tutar 10.000 TL, azami tutar 5.000.000 TL'dir. "
            "Stopaj sonrası net kâr payı oranı yaklaşık %46'dır. Kampanyadan yalnızca son 3 ayda "
            "müşterisi olmayanlar yararlanabilir. Kampanya 30 Eylül 2026 tarihine kadar sürer."
        ),
    ),
    BankSource(
        banka="Emlak Katılım",
        url="https://www.emlakkatilim.com.tr/ornek/altin-gunluk",
        sample_text=(
            "Günlük Altın Hesabı ile her gün kâr payı kazanın. Vade 7 gün, yıllık brüt kâr payı oranı "
            "altında %2,10'dur. 0,1 gram altından başlayan tutarlarla hesap açılabilir. Hesap "
            "tamamen dijital açılır, şubeye gitmenize gerek yoktur. İstediğiniz an bozdurabilirsiniz."
        ),
    ),
    BankSource(
        banka="Hayat Finans",
        url="https://www.hayatfinans.com.tr/ornek/e-katilma",
        sample_text=(
            "e-Katılma Hesabı tamamen dijital açılır. 32 gün vadeli TL katılma hesabında yeni "
            "müşterilere özel brüt yıllık kâr payı oranı %49'dur. Minimum 100 TL ile hesap açabilirsiniz. "
            "Uygulamadan açılışta hiçbir masraf alınmaz. Kampanya 30 Eylül 2026 tarihine kadar geçerlidir."
        ),
    ),
    BankSource(
        banka="TOM Katılım",
        url="https://www.tombank.com.tr/ornek/tom-katilma",
        sample_text=(
            "TOM Katılma Hesabı ile dijitalden kâr payı kazanın. 45 gün vade için brüt yıllık kâr payı "
            "oranı %47,5 olarak uygulanır. Asgari tutar 1.000 TL'dir. Tahsis ücreti ya da işletim masrafı "
            "alınmaz. Sadece uygulama üzerinden yeni gelen birikimlere sunulur."
        ),
    ),
    BankSource(
        banka="Dünya Katılım",
        url="https://www.dunyakatilim.com.tr/ornek/konut-finansmani",
        sample_text=(
            "Konut Finansmanı (faizsiz) kampanyası ile ev sahibi olun. 120 ay vadeye kadar finansman; "
            "aylık kâr payı oranı %2,79'dan başlar. Konut değerinin %75'ine kadar finansman kullandırılır. "
            "Dosya masrafı ve ekspertiz ücreti alınmaz. Maaş müşterilerine özel indirimli oran uygulanır."
        ),
    ),
    BankSource(
        banka="Adil Katılım",
        url="https://www.adilbank.com.tr/ornek/altin-katilma",
        sample_text=(
            "Adil Altın Katılma Hesabı ile gram altın biriktirin. 90 gün vadeli altın hesabında yıllık "
            "brüt kâr payı oranı %3,10'dur. Minimum 1 gram altın ile açılır. Fiziki altın teslimi "
            "yapılabilir. Hesap tamamen dijital, işletim ücreti alınmaz."
        ),
    ),
]


def get_sample_sources() -> list[BankSource]:
    return list(SAMPLE_SOURCES)
