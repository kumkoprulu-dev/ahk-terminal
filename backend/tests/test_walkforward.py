import pytest

import app.data.service as service
from app.backtest import walkforward, engine


@pytest.fixture
def patch_data(monkeypatch, ohlcv):
    monkeypatch.setattr(service, "get_ohlcv", lambda *a, **k: ohlcv)


def test_walk_forward_runs(patch_data):
    res = walkforward.run_walk_forward(
        "TEST", "EMA({fast}) > EMA({slow})", "EMA({fast}) < EMA({slow})",
        params=[{"name": "fast", "min": 5, "max": 15, "step": 5},
                {"name": "slow", "min": 20, "max": 40, "step": 10}],
        method="grid", objective="sharpe", range_="2y",
        train_bars=150, test_bars=50, n_trials=20,
    )
    assert res["summary"]["folds"] >= 2
    assert "equity" in res and "folds" in res
    # her fold'un eğitim ve test tarihleri var
    for f in res["folds"]:
        assert f["train_start"] and f["test_end"]


def test_warmup_suppresses_pre_window_trades(ohlcv):
    """warmup bölgesinde işlem açılmamalı; tüm trade'ler warmup sonrası."""
    res = engine.simulate(ohlcv, entry_rule="MACD Cross Up", exit_rule="MACD Cross Down",
                          warmup=200, light=False)
    # equity uzunluğu = toplam - warmup
    assert len(res["equity"]) == len(ohlcv) - 200


def test_insufficient_data_raises(patch_data):
    with pytest.raises(ValueError):
        walkforward.run_walk_forward(
            "TEST", "EMA({fast}) > EMA({slow})",
            params=[{"name": "fast", "min": 5, "max": 15, "step": 5},
                    {"name": "slow", "min": 20, "max": 40, "step": 10}],
            train_bars=500, test_bars=200, range_="2y",  # 700 > 400 bar
        )
