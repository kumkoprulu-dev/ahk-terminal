"""Doğal dil → tarama/strateji formülü (DSL) çevirici — kalıp tabanlı (TR + EN).

LLM gerektirmez; yaygın Türkçe/İngilizce borsa ifadelerini DSL'e çevirir. Çıktı her zaman
mevcut DSL parser'ı ile doğrulanır. Örnekler:
  "RSI 30 altında ve hacim 20 günlük ortalamanın üstünde"
    → RSI(14) < 30 AND Volume > SMA(Volume, 20)
  "EMA 20, EMA 50'yi yukarı kessin"        → EMA(20) Cross Up EMA(50)
  "aşırı satım ve güçlü trend"             → RSI(14) < 30 AND ADX(14) > 25
"""
from __future__ import annotations

import re

from app.scanner.dsl import DSLError, parse

# karşılaştırma kelimeleri
_GT = ["üstünde", "üzerinde", "üstüne", "yukarısında", "büyük", "fazla", "aşıyor", "aştı",
       "aşarsa", "geçiyor", "geçti", "geçerse", "yüksek", "yukarı", "over", "above", "greater"]
_LT = ["altında", "altına", "aşağısında", "küçük", "düşük", "azalıyor", "indi", "iniyor",
       "düşüyor", "düştü", "düşerse", "under", "below", "less", "aşağı"]
_CROSS_UP = ["yukarı kes", "yukari kes", "yukarıdan kes", "yukarı kır", "yukarı geç",
             "cross up", "crosses above", "golden"]
_CROSS_DN = ["aşağı kes", "asagi kes", "aşağıdan kes", "aşağı kır", "ölüm kes",
             "cross down", "crosses below", "death"]

# gösterge: alias -> (DSL adı, parametre alır mı, varsayılan periyot)
_IND = {
    "rsi": ("RSI", True, 14), "göreceli güç": ("RSI", True, 14),
    "macd": ("MACD", False, None),
    "ema": ("EMA", True, 20), "üssel ortalama": ("EMA", True, 20), "üstel ortalama": ("EMA", True, 20),
    "sma": ("SMA", True, 20), "basit ortalama": ("SMA", True, 20), "hareketli ortalama": ("SMA", True, 20),
    "wma": ("WMA", True, 20), "hma": ("HMA", True, 20),
    "adx": ("ADX", True, 14), "yönsel": ("ADX", True, 14),
    "cci": ("CCI", True, 20), "atr": ("ATR", True, 14), "mfi": ("MFI", True, 14),
    "stochastic": ("Stochastic", True, 14), "stokastik": ("Stochastic", True, 14),
    "williams": ("WilliamsR", True, 14), "roc": ("ROC", True, 12), "momentum": ("Momentum", True, 10),
    "cmf": ("CMF", True, 20), "obv": ("OBV", False, None),
    "techscore": ("TechScore", False, None), "teknik skor": ("TechScore", False, None),
    "z skor": ("ZScore", True, 20), "zscore": ("ZScore", True, 20),
}
_FIELDS = {"fiyat": "Close", "kapanış": "Close", "kapanis": "Close", "close": "Close",
           "hacim": "Volume", "volume": "Volume", "price": "Close"}

# tüm metinde geçerse doğrudan DSL parçası
_SPECIALS = [
    (["aşırı satım", "asiri satim", "oversold"], "RSI(14) < 30"),
    (["aşırı alım", "asiri alim", "overbought"], "RSI(14) > 70"),
    (["altın kesişim", "altin kesisim", "golden cross"], "EMA(50) Cross Up EMA(200)"),
    (["ölüm kesişim", "olum kesisim", "death cross"], "EMA(50) Cross Down EMA(200)"),
    (["hacim patlama", "yüksek hacim", "hacim artış", "yuksek hacim"], "Volume > SMA(Volume, 20)"),
    (["güçlü trend", "guclu trend", "trend güçlü"], "ADX(14) > 25"),
    (["macd al sinyal", "macd yukarı kes", "macd cross up", "macd pozitif"], "MACD Cross Up"),
    (["macd sat sinyal", "macd aşağı kes", "macd cross down", "macd negatif"], "MACD Cross Down"),
    (["bollinger üst", "üst banttan", "bollinger kırılım"], "Close > BollingerBands(20).Upper"),
    (["bollinger alt", "alt banda", "alt bandın altında"], "Close < BollingerBands(20).Lower"),
]


# Türkçe karakterleri ASCII'ye katla (diakritiksiz yazımı da desteklemek için)
_FOLD = str.maketrans({"ı": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c",
                       "â": "a", "î": "i", "û": "u"})


def _fold(s: str) -> str:
    return s.lower().translate(_FOLD)


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", _fold(t).replace("’", "'")).strip()


def _has(text: str, words: list[str]) -> bool:
    return any(_fold(w) in text for w in words)


def _extract_terms(text: str) -> list[str]:
    """Metindeki DSL operandlarını (gösterge/alan/ortalama/sayı) SIRAYLA çıkarır.

    Türkçe yapısı 'A B üstünde' = A > B olduğundan iki operand da karşılaştırma kelimesinden
    önce gelebilir. Periyot/eşik ayrımı: hareketli ortalamada sayı=periyot; osilatörde sayı
    yalnız 'günlük' ile birlikteyse periyot, aksi halde eşik (ayrı sayı terimi)."""
    spans: list[tuple[int, str]] = []
    consumed = [False] * len(text)

    def add(s: int, e: int, term: str):
        if s >= e or any(consumed[s:e]):
            return
        for i in range(s, e):
            consumed[i] = True
        spans.append((s, term))

    # "N günlük [üssel] [hareketli] ortalama" — öncesinde 'hacim' varsa Volume ortalaması
    for m in re.finditer(r"(\d+)\s*gunluk\s*(ussel|ustel)?\s*(hareketli\s*)?ortalama", text):
        name = "EMA" if m.group(2) else "SMA"
        pre = text[max(0, m.start() - 18):m.start()]
        fld = "Volume" if ("hacim" in pre or "volume" in pre) else "Close"
        add(m.start(), m.end(), f"{name}({fld}, {m.group(1)})")

    # göstergeler (uzun alias önce)
    for alias, (dsl, takes, default) in sorted(_IND.items(), key=lambda x: -len(x[0])):
        alias_f = _fold(alias)
        for m in re.finditer(r"\b" + re.escape(alias_f) + r"\b(\s*(\d+))?", text):
            numtok = m.group(2)
            if dsl == "BB":
                add(m.start(), m.end(), "BollingerBands(20).Upper")
            elif not takes:
                add(m.start(), m.start() + len(alias_f), dsl)
            elif dsl in ("EMA", "SMA", "WMA", "HMA"):
                add(m.start(), m.end(), f"{dsl}({int(numtok) if numtok else default})")
            else:
                near = text[m.start():m.end() + 8]
                if numtok and "gunluk" in near:
                    add(m.start(), m.end(), f"{dsl}({numtok})")
                else:  # sayıyı tüketme; eşik olarak kalsın
                    add(m.start(), m.start() + len(alias_f), f"{dsl}({default})")

    # alanlar
    for k, v in _FIELDS.items():
        for m in re.finditer(r"\b" + re.escape(_fold(k)) + r"\b", text):
            add(m.start(), m.end(), v)

    # düz sayılar (negatif dahil, tüketilmemiş)
    for m in re.finditer(r"-?\d+\.?\d*", text):
        add(m.start(), m.end(), m.group(0))

    spans.sort()
    return [t for _, t in spans]


def _clause_to_dsl(clause: str) -> str | None:
    c = clause.strip()
    if not c:
        return None

    for words, dsl in _SPECIALS:
        if _has(c, words):
            return dsl

    # kesişim
    if _has(c, _CROSS_UP) or _has(c, _CROSS_DN):
        direction = "Cross Up" if _has(c, _CROSS_UP) else "Cross Down"
        cleaned = c
        for w in _CROSS_UP + _CROSS_DN:
            cleaned = cleaned.replace(w, " ")
        terms = _extract_terms(cleaned)
        if len(terms) >= 2:
            return f"{terms[0]} {direction} {terms[1]}"
        if terms and terms[0].startswith("MACD"):
            return f"MACD {direction}"
        if terms:
            return f"{terms[0]} {direction} 0"
        return None

    # karşılaştırma
    op = ">" if _has(c, _GT) else ("<" if _has(c, _LT) else None)
    if op is None:
        return None
    terms = _extract_terms(c)
    if len(terms) >= 2:
        return f"{terms[0]} {op} {terms[1]}"
    return None


def to_formula(text: str) -> dict:
    t = _norm(text)
    if not t:
        return {"rule": "", "valid": False, "error": "Boş metin"}

    # bağlaçlara böl (ve/veya/and/or), bağlacı koru (metin ASCII'ye katlanmış)
    tokens = re.split(r"\s+(ve ayrica|ve|veya|and|or)\s+", " " + t + " ")
    clauses: list[tuple[str, str]] = []
    conn = None
    for tok in tokens:
        tok = tok.strip()
        if tok in ("ve", "ve ayrica", "and"):
            conn = "AND"
        elif tok in ("veya", "or"):
            conn = "OR"
        elif tok:
            clauses.append((conn, tok))
            conn = None

    parts: list[str] = []
    for connector, cl in clauses:
        frag = _clause_to_dsl(cl)
        if not frag:
            continue
        if parts:
            parts.append(connector or "AND")
        parts.append(frag)

    rule = " ".join(parts)
    if not rule:
        return {"rule": "", "valid": False,
                "error": "Metinden formül çıkarılamadı. Örnek: 'RSI 30 altında ve hacim ortalamanın üstünde'."}
    try:
        parse(rule)
        return {"rule": rule, "valid": True, "error": None}
    except DSLError as e:
        return {"rule": rule, "valid": False, "error": str(e)}
