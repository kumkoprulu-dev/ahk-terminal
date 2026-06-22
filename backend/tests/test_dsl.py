import pandas as pd
import pytest

from app.scanner.dsl import DSLError, evaluate, parse


@pytest.mark.parametrize("rule", [
    "RSI(14) < 30",
    "EMA(20) > EMA(50)",
    "EMA(20) > EMA(50) AND RSI(14) < 35",
    "MACD > Signal",
    "MACD Cross Up",
    "Volume > SMA(Volume, 20)",
    "Close < BollingerBands(20).Lower",
    "ROC(12) > 5 AND CMF(20) > 0",
    "ADX(14) > 25 AND NOT (RSI(14) > 70)",
    "Close > EMA(200) OR RSI(14) Cross Up 50",
])
def test_valid_rules_eval_to_bool_series(ohlcv, rule):
    s = evaluate(ohlcv, rule)
    assert isinstance(s, pd.Series)
    assert s.dtype == bool
    assert len(s) == len(ohlcv)


@pytest.mark.parametrize("rule", [
    "RSI(14) <",          # eksik sağ taraf
    "FOOBAR(10) > 5",     # bilinmeyen gösterge
    "RSI(14) > 30 AND",   # eksik ifade
    "((RSI(14) > 30)",    # parantez dengesiz
    "",                   # boş
])
def test_invalid_rules_raise(ohlcv, rule):
    with pytest.raises(DSLError):
        evaluate(ohlcv, rule)


def test_no_eval_injection(ohlcv):
    # eval olmadığını dolaylı doğrula: python ifadesi kural olarak çalışmamalı
    with pytest.raises(DSLError):
        evaluate(ohlcv, "__import__('os').system('echo hi')")


def test_parse_returns_ast():
    ast = parse("RSI(14) < 30")
    assert ast is not None
