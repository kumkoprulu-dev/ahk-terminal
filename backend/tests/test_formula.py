import pytest

from app.nlp.formula import to_formula


@pytest.mark.parametrize("text,expected", [
    ("RSI 30 altında", "RSI(14) < 30"),
    ("aşırı satım ve güçlü trend", "RSI(14) < 30 AND ADX(14) > 25"),
    ("EMA 20, EMA 50 üstünde", "EMA(20) > EMA(50)"),
    ("fiyat 200 günlük ortalamanın üstünde", "Close > SMA(Close, 200)"),
    ("macd yukarı kessin", "MACD Cross Up"),
    ("altın kesişim", "EMA(50) Cross Up EMA(200)"),
    ("teknik skor 60 üstünde", "TechScore > 60"),
    ("cci -100 altında", "CCI(20) < -100"),
    ("hacim 20 günlük ortalamanın üstünde", "Volume > SMA(Volume, 20)"),
])
def test_translations(text, expected):
    r = to_formula(text)
    assert r["valid"], r
    assert r["rule"] == expected


def test_compound_or():
    r = to_formula("rsi 40 altına insin veya macd aşağı kessin")
    assert r["valid"] and r["rule"] == "RSI(14) < 40 OR MACD Cross Down"


def test_empty_and_garbage():
    assert not to_formula("")["valid"]
    assert not to_formula("merhaba nasılsın")["valid"]


def test_output_parses_as_dsl():
    from app.scanner.dsl import parse
    for t in ["RSI 30 altında ve hacim ortalamanın üstünde", "adx 25 üstünde", "altın kesişim"]:
        r = to_formula(t)
        if r["valid"]:
            parse(r["rule"])  # hata vermemeli
