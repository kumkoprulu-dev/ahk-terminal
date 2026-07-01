"""Kural/regex tabanlı çıkarım — Türkçe finansal metne duyarlı.

İki işlevi var:
1. LLM olmadan (mock) gerçek çıkarım yapmak (çevrimdışı demo + CI).
2. LLM çıktısını DOĞRULAYAN deterministik temel olmak (grounding kontrolü).

Türkçe sayı biçimleri: "1.000 TL", "%48", "%3,25", "32 gün", "120 ay",
"100 USD", "5.000.000 TL". Ondalık ayraç virgül, binlik ayraç noktadır.
"""
from __future__ import annotations

import re
from datetime import date

from .schema import Grounded, KatilimUrunu, UrunTipi

# --- Türkçe sayı ayrıştırma ------------------------------------------------
_AYLAR = {
    "ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "mayis": 5,
    "haziran": 6, "temmuz": 7, "ağustos": 8, "agustos": 8, "eylül": 9, "eylul": 9,
    "ekim": 10, "kasım": 11, "kasim": 11, "aralık": 12, "aralik": 12,
}


def _tr_number(s: str) -> float:
    """'5.000.000,50' -> 5000000.5 ; '%3,25' -> 3.25 ; '1.000' -> 1000."""
    s = s.strip().replace("%", "").replace("TL", "").replace("USD", "").strip()
    s = s.replace(".", "").replace(",", ".")
    return float(s)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[\.\!\?\n])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _find_sentence(text: str, span_start: int) -> str:
    """span_start indeksini içeren cümleyi döndür (kaynak alıntı)."""
    pos = 0
    for s in _sentences(text):
        idx = text.find(s, pos)
        if idx == -1:
            idx = pos
        if idx <= span_start < idx + len(s):
            return s
        pos = idx + len(s)
    # fallback: çevredeki 120 karakter
    a = max(0, span_start - 60)
    return text[a : span_start + 80].strip()


# --- Alan çıkarıcıları -----------------------------------------------------
# Oranın "kâr payı" olduğunu gösteren olumlu bağlam ipuçları
_RATE_POS = ("kâr payı", "kar payı", "kar payi", "paylaşım oran", "paylasim oran",
            "getiri oran", "yıllık brüt", "yillik brut", "kar paylaşım", "kâr paylaşım")
# Oranı YANLIŞ kılan bağlamlar (kâr payı değil): devlet katkısı, indirim, yaş...
_RATE_NEG = ("devlet katkı", "indirim", "iade", "kdv", "yaş", "yas ", "komisyon",
            "masraf", "ek puan", "ilave", "varan döviz", "döviz hediye", "%95-5", "95-5")
# Kredi/finansman oranı DEĞİL — teminat/LTV/peşinat bağlamı (aynı cümlede olursa reddet).
# "değerinin %X'ine kadar" gibi kredi-değer oranı (LTV) kalıpları.
_LTV_NEG = ("değerin", "peşinat", "kredi tutar", "teminat", "ekspertiz değer",
            "kredinin %", "anaparanın")


def extract_kar_payi(text: str) -> Grounded[float]:
    """Tüm % adaylarını puanla; 'kâr payı' bağlamına en yakın olanı seç.

    Gerçek banka sayfalarında menü/promosyon içinde birden çok % geçer; en
    yüksek olumlu-puanlı, olumsuz-bağlamsız ve net olmayan oran seçilir.
    """
    best = None  # (skor, val, pos)
    for m in re.finditer(r"%\s?(\d{1,3}(?:[.,]\d{1,2})?)", text):
        try:
            val = _tr_number(m.group(1))
        except ValueError:
            continue
        if val <= 0 or val > 200:
            continue
        # POS ipucu AYNI CÜMLEDE aranır (komşu cümleden "kâr payı" sızmasın —
        # ör. "konut değerinin %75'ine kadar" LTV'si kâr payı sayılmasın).
        sent = _find_sentence(text, m.start()).lower()
        ctx = text[max(0, m.start() - 60) : m.end() + 30].lower()  # NEG için geniş
        if "net" in sent or "stopaj sonrası" in sent or "stopaj sonrasi" in sent:
            continue  # net oran ayrı alanda
        if any(n in ctx for n in _RATE_NEG) or any(n in sent for n in _LTV_NEG):
            continue
        score = sum(2 for p in _RATE_POS if p in sent)
        # makul kâr payı aralığına hafif bonus (ör. %20–%60 TL hesapları)
        if 5 <= val <= 70:
            score += 1
        if score <= 0:
            continue
        if best is None or score > best[0] or (score == best[0] and val > best[1]):
            best = (score, val, m.start())
    if best:
        return Grounded(value=best[1], source_quote=_find_sentence(text, best[2]),
                        confidence=min(0.9, 0.55 + 0.12 * best[0]))
    return Grounded()


def extract_kar_payi_net(text: str) -> Grounded[float]:
    for m in re.finditer(r"%\s?(\d{1,3}(?:[.,]\d{1,2})?)", text):
        ctx = text[max(0, m.start() - 60) : m.end() + 10].lower()
        if "net" in ctx and ("kâr" in ctx or "kar" in ctx):
            try:
                return Grounded(value=_tr_number(m.group(1)),
                                source_quote=_find_sentence(text, m.start()), confidence=0.85)
            except ValueError:
                continue
    return Grounded()


def extract_vade(text: str) -> Grounded[int]:
    """Vadeyi gün cinsinden çıkar.

    Gerçek sayfalarda '2 gün', 'son 3 gün' gibi gürültü olabilir; bu yüzden
    önce 'vade' kelimesine YAKIN bir gün/ay ifadesi aranır, yoksa ilk makul
    eşleşmeye düşülür. Çok küçük (<7 gün) ve vade bağlamı olmayan değerler
    güvenilmez sayılır.
    """
    gun = list(re.finditer(r"(\d{1,4})\s*g[üu]n", text, re.IGNORECASE))
    ay = list(re.finditer(r"(\d{1,3})\s*ay\b", text, re.IGNORECASE))

    def near_vade(m) -> bool:
        ctx = text[max(0, m.start() - 35): m.end() + 25].lower()
        return "vade" in ctx

    # 1) 'vade' yakınındaki gün eşleşmeleri — ama ÇELİŞİRSE çekimser kal (None).
    #    Gerçek sayfalarda hesap aracı birden çok "gün" seçeneği gösterebilir;
    #    yanlış tek bir değer vermektense (düşük precision) hiç vermemek (grounding) yeğdir.
    gun_near = [m for m in gun if near_vade(m)]
    distinct = {int(m.group(1)) for m in gun_near}
    if len(distinct) == 1:
        m = gun_near[0]
        return Grounded(value=int(m.group(1)), source_quote=_find_sentence(text, m.start()), confidence=0.9)
    if len(distinct) > 1:
        return Grounded()  # belirsiz → çekimser
    for m in ay:
        if near_vade(m):
            return Grounded(value=int(m.group(1)) * 30, source_quote=_find_sentence(text, m.start()), confidence=0.8)
    # 2) vade bağlamı yok → yalnız makul (>=7 gün) tek gün eşleşmesini kabul et
    if len(gun) == 1 and int(gun[0].group(1)) >= 7:
        m = gun[0]
        return Grounded(value=int(m.group(1)), source_quote=_find_sentence(text, m.start()), confidence=0.6)
    if not gun and len(ay) == 1:
        m = ay[0]
        return Grounded(value=int(m.group(1)) * 30, source_quote=_find_sentence(text, m.start()), confidence=0.55)
    return Grounded()


def extract_para_birimi(text: str) -> Grounded[str]:
    low = text.lower()
    table = [
        ("XAU", ["altın", "altin", "gram altın", "gram altin"]),
        ("USD", ["usd", "dolar", "$"]),
        ("EUR", ["eur", "euro", "€"]),
        ("TRY", ["tl", "türk lirası", "turk lirasi"]),
    ]
    for code, keys in table:
        for k in keys:
            idx = low.find(k)
            if idx != -1:
                return Grounded(value=code, source_quote=_find_sentence(text, idx), confidence=0.8)
    return Grounded()


def _amount_with_context(text: str, kind: str) -> Grounded[float]:
    """kind: 'min' | 'max'."""
    keys = {
        "min": ["minimum", "asgari", "en az", "başlayan", "baslayan", "başlar", "ile hesap"],
        "max": ["azami", "en fazla", "üst limit", "ust limit", "maksimum", "maximum"],
    }[kind]
    low = text.lower()
    num_re = r"(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*(TL|USD|EUR|gram)"
    for k in keys:
        idx = low.find(k)
        if idx == -1:
            continue
        # Anahtarın iki yanına bak: tutar ibareden önce de gelebilir
        # ("0,1 gram altından başlayan") sonra da ("minimum 1.000 TL").
        window = text[max(0, idx - 40) : idx + 80]
        cands = []
        for m in re.finditer(num_re, window, re.IGNORECASE):
            try:
                cands.append((_tr_number(m.group(1)), m))
            except ValueError:
                continue
        if cands:
            # min için en küçük, max için en büyük adayı seç
            v, _ = (min if kind == "min" else max)(cands, key=lambda x: x[0])
            return Grounded(value=v, source_quote=_find_sentence(text, idx), confidence=0.8)
    return Grounded()


def extract_min_tutar(text: str) -> Grounded[float]:
    return _amount_with_context(text, "min")


def extract_max_tutar(text: str) -> Grounded[float]:
    return _amount_with_context(text, "max")


def extract_tarih(text: str, kind: str) -> Grounded[str]:
    """kind: 'bitis' | 'baslangic'. '31 Temmuz 2026' -> ISO."""
    for m in re.finditer(r"(\d{1,2})\s+([A-Za-zçğıöşüÇĞİÖŞÜ]+)\s+(\d{4})", text):
        ctx = text[max(0, m.start() - 40) : m.end() + 45].lower()
        is_bitis = any(w in ctx for w in ["kadar", "sona er", "bitiş", "bitis", "geçerli", "sürer", "surer"])
        if (kind == "bitis") != is_bitis:
            continue
        ay = _AYLAR.get(m.group(2).lower())
        if not ay:
            continue
        try:
            iso = date(int(m.group(3)), ay, int(m.group(1))).isoformat()
        except ValueError:
            continue
        return Grounded(value=iso, source_quote=_find_sentence(text, m.start()), confidence=0.85)
    return Grounded()


def detect_urun_tipi(text: str) -> UrunTipi:
    low = text.lower()
    if "altın" in low or "altin" in low:
        return UrunTipi.altin_hesabi
    if "konut" in low or "taşıt" in low or "tasit" in low or "finansman" in low:
        return UrunTipi.finansman
    if any(c in low for c in ["dolar", "usd", "euro", "eur", "döviz", "doviz"]):
        return UrunTipi.doviz_katilma
    if "kart" in low or "harcama" in low:
        return UrunTipi.kart_kampanya
    if "sigorta" in low or "tekafül" in low or "tekaful" in low:
        return UrunTipi.katilim_sigorta
    if "katılma" in low or "katilma" in low or "hesab" in low:
        return UrunTipi.katilma_hesabi
    return UrunTipi.diger


_ADV_PATTERNS = [
    (r"masrafsız|masraf alınmaz|ücret alınmaz|ücretsiz|işletim ücreti alınmaz", "Masraf/ücret yok"),
    (r"dijital|mobil şube|mobilden|online aç", "Dijital/mobil açılış"),
    (r"ek\s*\d+\s*puan|ilave kâr payı|\+\s?\d", "İlave kâr payı avantajı"),
    (r"istediğiniz an|her an|bozdur", "Esnek/erken çekim"),
    (r"fiziki altın teslim", "Fiziki altın teslimi"),
    (r"emekli|maaş müşter", "Emekli/maaş müşterisine özel"),
]


def extract_avantajlar(text: str) -> list[str]:
    out = []
    for pat, label in _ADV_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            out.append(label)
    return out


def extract_kosullar(text: str) -> list[str]:
    out = []
    if re.search(r"yeni (müşter|gelen)|son \d+ ay|müşterisi olmayan|ilk vade", text, re.IGNORECASE):
        out.append("Yeni müşteri / yeni para koşulu")
    if re.search(r"vade(den)? önce|erken çek", text, re.IGNORECASE):
        out.append("Vade öncesi çekimde kâr payı kısıtı")
    return out


# --- Şartname 5.3 ek alanlar -----------------------------------------------
def extract_taksit(text: str) -> Grounded[int]:
    """Taksit sayısı: 'X taksit' ya da finansmanda 'X ay' (=X taksit)."""
    m = re.search(r"(\d{1,3})\s*taksit", text, re.IGNORECASE)
    if m:
        return Grounded(value=int(m.group(1)), source_quote=_find_sentence(text, m.start()), confidence=0.9)
    if re.search(r"finansman|kredi|konut|taşıt|tasit", text, re.IGNORECASE):
        m = re.search(r"(\d{1,3})\s*ay", text, re.IGNORECASE)
        if m:
            return Grounded(value=int(m.group(1)), source_quote=_find_sentence(text, m.start()), confidence=0.7)
    return Grounded()


def detect_masrafsiz(text: str) -> tuple[bool, Grounded[str]]:
    """Masrafsız mı + tahsis ücreti durumu."""
    low = text.lower()
    masrafsiz_pat = r"(masrafsız|masraf alınmaz|dosya masrafı (yok|alınmaz|alınmamakta)|" \
                    r"tahsis ücreti (yok|alınmaz|alınmamakta)|ücret alınmaz|işletim ücreti alınmaz|" \
                    r"masrafı bulunmamakta|ekspertiz (ücreti )?(banka|ücretsiz))"
    m = re.search(masrafsiz_pat, low)
    if m:
        return True, Grounded(value="alınmaz", source_quote=_find_sentence(text, m.start()), confidence=0.85)
    # Tahsis ücreti tutarı verilmişse
    m2 = re.search(r"tahsis ücreti[^.]{0,30}?(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*(TL|₺)", text, re.IGNORECASE)
    if m2:
        return False, Grounded(value=m2.group(1) + " TL",
                               source_quote=_find_sentence(text, m2.start()), confidence=0.8)
    return False, Grounded()


def extract_odul(text: str) -> Grounded[str]:
    """Ödül miktarı: 'X TL alışveriş çeki/hediye/ödül/iade'."""
    m = re.search(r"(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*(TL|₺)[^.]{0,25}?"
                  r"(çek|hediye|ödül|iade|puan|para)", text, re.IGNORECASE)
    if m:
        return Grounded(value=f"{m.group(1)} TL {m.group(3)}",
                        source_quote=_find_sentence(text, m.start()), confidence=0.8)
    return Grounded()


def extract_indirim(text: str) -> Grounded[float]:
    for m in re.finditer(r"%\s?(\d{1,3}(?:[.,]\d{1,2})?)", text):
        ctx = text[max(0, m.start() - 30): m.end() + 25].lower()
        if "indirim" in ctx:
            try:
                return Grounded(value=_tr_number(m.group(1)),
                                source_quote=_find_sentence(text, m.start()), confidence=0.85)
            except ValueError:
                continue
    return Grounded()


def extract_alisveris_puani(text: str) -> Grounded[str]:
    m = re.search(r"(\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*(TL|₺|puan)[^.]{0,20}?"
                  r"(alışveriş puanı|puan|worldpuan|bonus|paracık)", text, re.IGNORECASE)
    if m:
        return Grounded(value=f"{m.group(1)} {m.group(3)}",
                        source_quote=_find_sentence(text, m.start()), confidence=0.75)
    return Grounded()


def detect_kampanya_turu(text: str, urun_adi: str = "") -> "KampanyaTuru":
    from .schema import KampanyaTuru
    low = (urun_adi + " " + text).lower()
    if "konut" in low or "ev sahibi" in low or "mortgage" in low:
        return KampanyaTuru.konut
    if "taşıt" in low or "tasit" in low or "araç" in low or "arac " in low or "otomobil" in low:
        return KampanyaTuru.tasit
    if "ihtiyaç" in low or "ihtiyac" in low:
        return KampanyaTuru.ihtiyac
    if "alışveriş puanı" in low or "alisveris puani" in low or "worldpuan" in low:
        return KampanyaTuru.alisveris_puani
    if "kart" in low or "harcama" in low:
        return KampanyaTuru.kart
    if "yatırım" in low or "yatirim" in low or "fon" in low:
        return KampanyaTuru.yatirim
    if re.search(r"yeni (müşteri|gelen|gel)", low) or "müşterisi olmayan" in low:
        return KampanyaTuru.yeni_musteri
    if "finansman" in low:
        return KampanyaTuru.finansman
    return KampanyaTuru.yok


def detect_hedef_kitle(text: str) -> list[str]:
    low = text.lower()
    out = []
    if re.search(r"yeni (müşteri|gelen|gel)|müşterisi olmayan|ilk defa|son \d+ ay", low):
        out.append("Yeni müşteri")
    if "mevcut müşter" in low or "mevcut müşteri" in low:
        out.append("Mevcut müşteri")
    if "maaş müşter" in low or "maaşını" in low or "maaş" in low:
        out.append("Maaş müşterisi")
    if "emekli" in low:
        out.append("Emekli")
    return out


def rule_extract(banka: str, urun_adi: str, text: str, url: str | None = None) -> KatilimUrunu:
    """Tek metinden tek ürün çıkar (kural tabanlı)."""
    kamp_bitis = extract_tarih(text, "bitis")
    masrafsiz, tahsis = detect_masrafsiz(text)
    return KatilimUrunu(
        banka=banka,
        urun_adi=urun_adi,
        urun_tipi=detect_urun_tipi(text),
        kar_payi_orani=extract_kar_payi(text),
        kar_payi_orani_net=extract_kar_payi_net(text),
        vade_gun=extract_vade(text),
        para_birimi=extract_para_birimi(text),
        min_tutar=extract_min_tutar(text),
        max_tutar=extract_max_tutar(text),
        taksit_sayisi=extract_taksit(text),
        tahsis_ucreti=tahsis,
        masrafsiz=masrafsiz,
        kampanya_turu=detect_kampanya_turu(text, urun_adi),
        odul_miktari=extract_odul(text),
        indirim_orani=extract_indirim(text),
        alisveris_puani=extract_alisveris_puani(text),
        hedef_kitle=detect_hedef_kitle(text),
        avantajlar=extract_avantajlar(text),
        kosullar=extract_kosullar(text),
        kampanya=bool(re.search(r"kampanya", text, re.IGNORECASE)),
        kampanya_baslangic=extract_tarih(text, "baslangic"),
        kampanya_bitis=kamp_bitis,
        kaynak_url=url,
        cekildigi_tarih=date.today().isoformat(),
    )


def guess_urun_adi(text: str) -> str:
    """Metnin başındaki ürün adını tahmin et (ilk cümlenin baş ibaresi)."""
    first = _sentences(text)[0] if _sentences(text) else text[:40]
    m = re.match(r"([A-Za-zçğıöşüÇĞİÖŞÜ0-9 ()]+?)(?: ile | ,|,| kampanyas|\.| ile)", first)
    return (m.group(1).strip() if m else first[:40]).strip() or "Ürün"
