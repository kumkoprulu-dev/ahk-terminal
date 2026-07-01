"""Gold (altın standart) veri seti — örnek kaynaklardan beklenen değerler.

Çıkarım doğruluğunu ölçmek için elle etiketlenmiş referans. Her giriş, bir
banka kaynağına karşılık beklenen alan değerlerini taşır. None = alan metinde
yok demektir (model de None vermeli).
"""
from __future__ import annotations

GOLD = {
    "Kuveyt Türk": {
        "urun_tipi": "katilma_hesabi",
        "kar_payi_orani": 48.0,
        "kar_payi_orani_net": None,
        "vade_gun": 32,
        "para_birimi": "TRY",
        "min_tutar": 1000.0,
        "kampanya_bitis": "2026-07-31",
    },
    "Albaraka Türk": {
        "urun_tipi": "altin_hesabi",
        "kar_payi_orani": 3.25,
        "kar_payi_orani_net": None,
        "vade_gun": 90,
        "para_birimi": "XAU",
        "min_tutar": 1.0,
        "kampanya_bitis": None,
    },
    "Türkiye Finans": {
        "urun_tipi": "doviz_katilma",
        "kar_payi_orani": 4.75,
        "kar_payi_orani_net": None,
        "vade_gun": 180,
        "para_birimi": "USD",
        "min_tutar": 100.0,
        "kampanya_bitis": "2026-08-15",
    },
    "Ziraat Katılım": {
        "urun_tipi": "finansman",
        "kar_payi_orani": 2.89,
        "kar_payi_orani_net": None,
        "vade_gun": 3600,
        "para_birimi": None,
        "min_tutar": None,
        "kampanya_bitis": None,
    },
    "Vakıf Katılım": {
        "urun_tipi": "katilma_hesabi",
        "kar_payi_orani": 50.0,
        "kar_payi_orani_net": 46.0,
        "vade_gun": 32,
        "para_birimi": "TRY",
        "min_tutar": 10000.0,
        "kampanya_bitis": "2026-09-30",
    },
    "Emlak Katılım": {
        "urun_tipi": "altin_hesabi",
        "kar_payi_orani": 2.10,
        "kar_payi_orani_net": None,
        "vade_gun": 7,
        "para_birimi": "XAU",
        "min_tutar": 0.1,
        "kampanya_bitis": None,
    },
    "Hayat Finans": {
        "urun_tipi": "katilma_hesabi",
        "kar_payi_orani": 49.0,
        "kar_payi_orani_net": None,
        "vade_gun": 32,
        "para_birimi": "TRY",
        "min_tutar": 100.0,
        "kampanya_bitis": "2026-09-30",
    },
    "TOM Katılım": {
        "urun_tipi": "katilma_hesabi",
        "kar_payi_orani": 47.5,
        "kar_payi_orani_net": None,
        "vade_gun": 45,
        "para_birimi": "TRY",
        "min_tutar": 1000.0,
        "kampanya_bitis": None,
    },
    "Dünya Katılım": {
        "urun_tipi": "finansman",
        "kar_payi_orani": 2.79,
        "kar_payi_orani_net": None,
        "vade_gun": 3600,
        "para_birimi": None,
        "min_tutar": None,
        "kampanya_bitis": None,
    },
    "Adil Katılım": {
        "urun_tipi": "altin_hesabi",
        "kar_payi_orani": 3.10,
        "kar_payi_orani_net": None,
        "vade_gun": 90,
        "para_birimi": "XAU",
        "min_tutar": 1.0,
        "kampanya_bitis": None,
    },
}

ALANLAR = [
    "urun_tipi", "kar_payi_orani", "kar_payi_orani_net",
    "vade_gun", "para_birimi", "min_tutar", "kampanya_bitis",
]
