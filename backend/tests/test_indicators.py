import numpy as np

from app.indicators import REGISTRY, compute


def test_all_indicators_compute(ohlcv):
    """Tüm kayıtlı göstergeler hata vermeden, doğru uzunlukta sonuç üretmeli."""
    assert len(REGISTRY) >= 40
    for name in REGISTRY:
        res = compute(name, ohlcv)
        assert len(res) == len(ohlcv), name
        assert res.shape[1] >= 1, name


def test_rsi_matches_ta(ohlcv):
    """RSI, `ta` ile aynı Wilder düzleştirmesini kullanır; başlangıç tohumu farklı
    olduğundan değerler ısınma sonrası yakınsar. Yakınsayan bölgeyi karşılaştır."""
    import ta
    ours = compute("RSI", ohlcv, {"length": 14})["RSI"]
    ref = ta.momentum.RSIIndicator(ohlcv["close"], window=14).rsi()
    diff = (ours - ref).abs().dropna()
    # Wilder düzleştirmesi üstel yakınsar; son 100 bar birebir aynı olmalı
    assert diff.iloc[-100:].max() < 1e-6, f"RSI yakınsama sapması: {diff.iloc[-100:].max()}"


def test_ema_matches_ta(ohlcv):
    import ta
    ours = compute("EMA", ohlcv, {"length": 20})["EMA"]
    ref = ta.trend.EMAIndicator(ohlcv["close"], window=20).ema_indicator()
    diff = (ours - ref).abs().dropna()
    assert diff.max() < 1e-6


def test_macd_outputs(ohlcv):
    res = compute("MACD", ohlcv)
    assert list(res.columns) == ["MACD", "Signal", "Hist"]


def test_rsi_bounds(ohlcv):
    rsi = compute("RSI", ohlcv)["RSI"].dropna()
    assert rsi.min() >= 0 and rsi.max() <= 100


def test_hurst_range(ohlcv):
    h = compute("HurstExponent", ohlcv, {"length": 100})["Hurst"].dropna()
    assert len(h) > 0
    assert h.between(0, 1.5).mean() > 0.8  # çoğu değer makul aralıkta
