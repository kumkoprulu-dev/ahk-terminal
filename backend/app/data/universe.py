"""Sembol evrenleri (universe / gruplar) — tek merkez.

Buradaki gruplar uygulamanın her yerinde kullanılır: Tarayıcı (sorgu), Portföy,
sembol arama. Yeni grup eklemek = aşağıya bir tanım eklemek.

BIST sembolleri yfinance/Yahoo için '.IS', emtia vadeli için '=F', kripto için '-USD'
uzantısıyla kullanılır. Listeler statik seed'dir (endeks üyelikleri zamanla değişir);
ileride borsa API'lerinden güncellenebilir.
"""
from __future__ import annotations

from app.data.base import SymbolInfo

# --- BIST isim haritası (bilinenler; bilinmeyenler için kod kullanılır) ---
_BIST_NAMES = {
    "ASELS": "Aselsan", "THYAO": "Türk Hava Yolları", "GARAN": "Garanti BBVA",
    "AKBNK": "Akbank", "ISCTR": "İş Bankası C", "YKBNK": "Yapı Kredi",
    "KCHOL": "Koç Holding", "SAHOL": "Sabancı Holding", "SISE": "Şişecam",
    "EREGL": "Ereğli Demir Çelik", "FROTO": "Ford Otosan", "TUPRS": "Tüpraş",
    "BIMAS": "BİM", "PGSUS": "Pegasus", "TCELL": "Turkcell", "TTKOM": "Türk Telekom",
    "KOZAL": "Koza Altın", "PETKM": "Petkim", "TOASO": "Tofaş", "ARCLK": "Arçelik",
    "HEKTS": "Hektaş", "SASA": "Sasa Polyester", "KRDMD": "Kardemir D",
    "VESTL": "Vestel", "ENKAI": "Enka İnşaat", "TKFEN": "Tekfen Holding",
    "OYAKC": "Oyak Çimento", "GUBRF": "Gübre Fabrikaları", "ALARK": "Alarko Holding",
    "MGROS": "Migros", "DOHOL": "Doğan Holding", "TAVHL": "TAV Havalimanları",
    "ASTOR": "Astor Enerji", "EKGYO": "Emlak Konut GYO", "AEFES": "Anadolu Efes",
    "CCOLA": "Coca-Cola İçecek", "ULKER": "Ülker", "TTRAK": "Türk Traktör",
    "SOKM": "Şok Marketler", "BRSAN": "Borusan Boru", "KONTR": "Kontrolmatik",
    "KOZAA": "Koza Madencilik", "ODAS": "Odaş Elektrik", "AKSA": "Aksa Akrilik",
    "HALKB": "Halkbank", "VAKBN": "Vakıfbank", "AKSEN": "Aksa Enerji",
    "ENJSA": "Enerjisa", "OTKAR": "Otokar", "GESAN": "Girişim Elektrik",
    "CIMSA": "Çimsa", "AGHOL": "Anadolu Grubu Holding", "SMRTG": "Smart Güneş",
    "MAVI": "Mavi Giyim", "DOAS": "Doğuş Otomotiv", "EGEEN": "Ege Endüstri",
    "ISMEN": "İş Yatırım", "TSKB": "TSKB", "SKBNK": "Şekerbank", "TURSG": "Türkiye Sigorta",
    "BERA": "Bera Holding", "CWENE": "CW Enerji", "EUPWR": "Europower",
    "KONYA": "Konya Çimento", "NUHCM": "Nuh Çimento", "BUCIM": "Bursa Çimento",
    "KARSN": "Karsan", "ZOREN": "Zorlu Enerji", "GWIND": "Galata Wind",
    "IPEKE": "İpek Enerji", "MIATK": "Mia Teknoloji", "REEDR": "Reeder",
    "ASUZU": "Anadolu Isuzu", "BAGFS": "Bagfaş", "CLEBI": "Çelebi",
    "TABGD": "Tab Gıda", "CANTE": "Çan2 Termik", "ENERY": "Enerya",
    "ALFAS": "Alfa Solar", "AGROT": "Agrotech", "BINHO": "Bien Yapı",
    "KMPUR": "Kimteks Poliüretan", "QUAGR": "Qua Granite", "TKNSA": "Teknosa",
    "VESBE": "Vestel Beyaz Eşya", "ECILC": "EİS Eczacıbaşı", "ALBRK": "Albaraka Türk",
    "ANSGR": "Anadolu Sigorta", "GLYHO": "Global Yatırım", "ISGYO": "İş GYO",
    "SNGYO": "Sinpaş GYO", "PRKME": "Park Elektrik", "YEOTK": "Yeo Teknoloji",
    "SDTTR": "SDT Uzay", "PENTA": "Penta Teknoloji", "FENER": "Fenerbahçe",
    "TTRAK2": "", "KLSER": "Kaleseramik", "OBAMS": "Oba Makarna", "BINBN": "",
}

# --- BIST endeks listeleri (kümülatif) ---
_BIST30 = [
    "ASELS", "THYAO", "GARAN", "AKBNK", "ISCTR", "YKBNK", "KCHOL", "SAHOL", "SISE",
    "EREGL", "FROTO", "TUPRS", "BIMAS", "PGSUS", "TCELL", "KOZAL", "KRDMD", "TOASO",
    "ASTOR", "SASA", "HEKTS", "ENKAI", "OYAKC", "GUBRF", "ALARK", "MGROS", "TTKOM",
    "ARCLK", "KONTR", "BRSAN",
]
_BIST50_EXTRA = [
    "PETKM", "TAVHL", "EKGYO", "AEFES", "CCOLA", "ULKER", "TTRAK", "SOKM", "DOHOL",
    "VESTL", "TKFEN", "AKSEN", "ENJSA", "OTKAR", "GESAN", "CIMSA", "AGHOL", "SMRTG",
    "MAVI", "ISMEN",
]
_BIST100_EXTRA = [
    "KOZAA", "ODAS", "AKSA", "HALKB", "VAKBN", "DOAS", "EGEEN", "TSKB", "SKBNK",
    "TURSG", "BERA", "CWENE", "EUPWR", "KONYA", "NUHCM", "BUCIM", "KARSN", "ZOREN",
    "GWIND", "IPEKE", "MIATK", "REEDR", "ASUZU", "BAGFS", "CLEBI", "TABGD", "CANTE",
    "ENERY", "ALFAS", "AGROT", "BINHO", "KMPUR", "QUAGR", "TKNSA", "VESBE", "ECILC",
    "ALBRK", "ANSGR", "GLYHO", "ISGYO", "SNGYO", "PRKME", "YEOTK", "SDTTR", "PENTA",
    "FENER", "KLSER", "OBAMS", "AKFGY", "CEMTS",
]

_BIST50 = _BIST30 + _BIST50_EXTRA
_BIST100 = _BIST50 + _BIST100_EXTRA

_NASDAQ = {
    "AAPL": "Apple", "MSFT": "Microsoft", "GOOGL": "Alphabet A", "AMZN": "Amazon",
    "NVDA": "NVIDIA", "META": "Meta Platforms", "TSLA": "Tesla", "AVGO": "Broadcom",
    "AMD": "Advanced Micro Devices", "NFLX": "Netflix", "INTC": "Intel",
    "QCOM": "Qualcomm", "CSCO": "Cisco", "ADBE": "Adobe", "PYPL": "PayPal",
    "PEP": "PepsiCo", "COST": "Costco", "TXN": "Texas Instruments", "AMAT": "Applied Materials",
    "MU": "Micron", "PLTR": "Palantir", "SBUX": "Starbucks", "MRVL": "Marvell",
    "ORCL": "Oracle", "CRM": "Salesforce",
}

_EMTIA = {
    "GC=F": "Altın", "SI=F": "Gümüş", "PL=F": "Platin", "PA=F": "Paladyum",
    "HG=F": "Bakır", "CL=F": "Ham Petrol (WTI)", "BZ=F": "Brent Petrol",
    "NG=F": "Doğalgaz", "ZW=F": "Buğday", "ZC=F": "Mısır", "ZS=F": "Soya Fasulyesi",
    "KC=F": "Kahve", "SB=F": "Şeker", "CC=F": "Kakao", "CT=F": "Pamuk",
}

_KRIPTO = {
    "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum", "BNB-USD": "BNB", "XRP-USD": "XRP",
    "SOL-USD": "Solana", "ADA-USD": "Cardano", "DOGE-USD": "Dogecoin",
    "AVAX-USD": "Avalanche", "DOT-USD": "Polkadot", "TRX-USD": "Tron",
    "LINK-USD": "Chainlink", "LTC-USD": "Litecoin", "BCH-USD": "Bitcoin Cash",
    "XLM-USD": "Stellar", "ATOM-USD": "Cosmos", "UNI-USD": "Uniswap",
    "ETC-USD": "Ethereum Classic", "FIL-USD": "Filecoin", "APT-USD": "Aptos",
    "NEAR-USD": "NEAR Protocol",
}


def _bist(codes: list[str]) -> list[SymbolInfo]:
    return [
        SymbolInfo(symbol=f"{c}.IS", name=_BIST_NAMES.get(c) or c, exchange="BIST", type="stock")
        for c in codes
    ]


def _plain(d: dict[str, str], exch: str, typ: str) -> list[SymbolInfo]:
    return [SymbolInfo(symbol=s, name=n, exchange=exch, type=typ) for s, n in d.items()]


# id -> (label, symbols)
_DEFS: dict[str, tuple[str, list[SymbolInfo]]] = {
    "bist30": ("BIST 30", _bist(_BIST30)),
    "bist50": ("BIST 50", _bist(_BIST50)),
    "bist100": ("BIST 100", _bist(_BIST100)),
    "nasdaq": ("NASDAQ", _plain(_NASDAQ, "NASDAQ", "stock")),
    "emtia": ("Emtia", _plain(_EMTIA, "Emtia", "commodity")),
    "kripto": ("Kripto", _plain(_KRIPTO, "Kripto", "crypto")),
}

UNIVERSES: dict[str, list[SymbolInfo]] = {k: v[1] for k, v in _DEFS.items()}
LABELS: dict[str, str] = {k: v[0] for k, v in _DEFS.items()}


def universe_list() -> list[dict]:
    return [{"id": k, "label": LABELS[k], "count": len(UNIVERSES[k])} for k in _DEFS]


def universe_names() -> list[str]:
    return list(_DEFS.keys())


def get_universe(name: str) -> list[SymbolInfo]:
    if not name:
        return []
    key = name.strip().lower()
    if key in UNIVERSES:
        return UNIVERSES[key]
    # geriye uyumluluk: "BIST 30" gibi etiketle de bul
    for k, label in LABELS.items():
        if label.lower() == key:
            return UNIVERSES[k]
    return []


def all_symbols() -> list[SymbolInfo]:
    seen: dict[str, SymbolInfo] = {}
    for syms in UNIVERSES.values():
        for s in syms:
            seen.setdefault(s.symbol, s)
    return list(seen.values())


def search_local(query: str, limit: int = 30) -> list[SymbolInfo]:
    q = query.strip().lower()
    if not q:
        return []
    res = [s for s in all_symbols() if q in s.symbol.lower() or q in s.name.lower()]
    return res[:limit]
