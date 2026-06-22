import pytest

import app.data.service as service
from app.backtest import optimizer


@pytest.fixture
def patch_data(monkeypatch, ohlcv):
    monkeypatch.setattr(service, "get_ohlcv", lambda *a, **k: ohlcv)


def test_find_placeholders():
    names = optimizer.find_placeholders("EMA({fast}) > EMA({slow})", "RSI({rsi}) > 50")
    assert names == ["fast", "slow", "rsi"]


def test_substitute():
    assert optimizer.substitute("EMA({fast}) > EMA({slow})", {"fast": 10, "slow": 30}) == "EMA(10) > EMA(30)"


def test_grid_evaluates_all(patch_data):
    res = optimizer.run_optimization(
        "TEST", "EMA({fast}) > EMA({slow})", "EMA({fast}) < EMA({slow})",
        params=[{"name": "fast", "min": 5, "max": 15, "step": 5},
                {"name": "slow", "min": 20, "max": 40, "step": 10}],
        method="grid", objective="sharpe", range_="2y",
    )
    assert res["total_combos"] == 3 * 3
    assert res["evaluated"] >= 1
    assert res["best"] is not None
    # sonuçlar skora göre azalan sıralı
    scores = [r["score"] for r in res["results"] if r["score"] is not None]
    assert scores == sorted(scores, reverse=True)


def test_bayes_runs(patch_data):
    res = optimizer.run_optimization(
        "TEST", "RSI({len}) < {buy}", "RSI({len}) > {sell}",
        params=[{"name": "len", "min": 5, "max": 20, "step": 1},
                {"name": "buy", "min": 20, "max": 40, "step": 5},
                {"name": "sell", "min": 55, "max": 80, "step": 5}],
        method="bayes", objective="total_return", n_trials=20, range_="2y",
    )
    assert res["method"] == "bayes"
    assert res["evaluated"] >= 1


def test_missing_param_raises(patch_data):
    with pytest.raises(ValueError):
        optimizer.run_optimization(
            "TEST", "EMA({fast}) > EMA({slow})",
            params=[{"name": "fast", "min": 5, "max": 15, "step": 5}],
            method="grid", range_="2y",
        )
