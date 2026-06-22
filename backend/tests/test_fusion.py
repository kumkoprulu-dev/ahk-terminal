import numpy as np
import pandas as pd
import pytest

import app.fusion.engine as fe
from app.fusion.technical import technical_score


def _trend_df(direction=1):
    idx = pd.date_range("2022-01-01", periods=260, freq="D")
    base = np.linspace(100, 100 + direction * 60, 260)
    noise = np.random.default_rng(0).normal(0, 0.5, 260)
    close = base + noise
    return pd.DataFrame({"open": close, "high": close + 1, "low": close - 1,
                         "close": close, "volume": 1e6}, index=idx)


def test_techscore_indicator_bounded():
    from app.indicators import compute
    ts = compute("TechScore", _trend_df(1))["TechScore"].dropna()
    assert len(ts) > 0
    assert ts.between(0, 100).all()


def test_technical_uptrend_bullish():
    assert technical_score(_trend_df(1))["score"] > 55


def test_technical_downtrend_bearish():
    assert technical_score(_trend_df(-1))["score"] < 45


def test_signal_thresholds():
    assert fe._signal(75) == "GÜÇLÜ AL"
    assert fe._signal(60) == "AL"
    assert fe._signal(50) == "NÖTR"
    assert fe._signal(35) == "SAT"
    assert fe._signal(20) == "GÜÇLÜ SAT"


def test_fuse_warning_flag(monkeypatch):
    """Teknik olumlu + haber olumsuz → uyarı bayrağı."""
    monkeypatch.setattr(fe.service, "get_ohlcv", lambda *a, **k: _trend_df(1))
    monkeypatch.setattr(fe, "technical_score", lambda df: {"score": 70, "label": "yukarı", "components": {}})
    monkeypatch.setattr(fe, "fundamental_analyze", lambda s: {"score": 80, "label": "güçlü", "name": "X", "buckets": {}, "source": "t"})
    monkeypatch.setattr(fe, "get_sentiment", lambda s, **k: {"score": -0.5, "label": "negatif", "n_news": 3})
    r = fe.fuse("X")
    assert r["signal"] in ("AL", "NÖTR")
    assert "Haber riski" in r["flag"]
    # composite = (70*.4 + 25*.25 + 80*.35) = 62.25
    assert abs(r["composite"] - 62.25) < 0.5


def test_fuse_three_axis_aligned(monkeypatch):
    monkeypatch.setattr(fe.service, "get_ohlcv", lambda *a, **k: _trend_df(1))
    monkeypatch.setattr(fe, "technical_score", lambda df: {"score": 72, "label": "güçlü yukarı", "components": {}})
    monkeypatch.setattr(fe, "fundamental_analyze", lambda s: {"score": 75, "label": "güçlü", "name": "X", "buckets": {}, "source": "t"})
    monkeypatch.setattr(fe, "get_sentiment", lambda s, **k: {"score": 0.5, "label": "pozitif", "n_news": 3})
    r = fe.fuse("X")
    assert "Üç eksen uyumlu" in r["flag"]
    assert r["signal"] in ("AL", "GÜÇLÜ AL")
