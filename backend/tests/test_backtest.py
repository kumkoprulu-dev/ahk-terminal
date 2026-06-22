import numpy as np
import pytest

from app.backtest import engine
from app.backtest.metrics import equity_metrics, trade_metrics
import app.data.service as service
import pandas as pd


@pytest.fixture
def patch_data(monkeypatch, ohlcv):
    monkeypatch.setattr(service, "get_ohlcv", lambda *a, **k: ohlcv)


def test_backtest_runs(patch_data):
    res = engine.run("TEST", "RSI(14) < 40", "RSI(14) > 60", range_="2y")
    assert "metrics" in res and "equity" in res and "trades" in res
    assert len(res["equity"]) == 400
    m = res["metrics"]
    for key in ("total_return", "sharpe", "max_drawdown", "num_trades", "win_rate", "buy_hold_return"):
        assert key in m


def test_backtest_trades_have_fields(patch_data):
    res = engine.run("TEST", "MACD Cross Up", "MACD Cross Down", range_="2y")
    for t in res["trades"]:
        assert t["exit_price"] > 0 and t["entry_price"] > 0
        assert "return_pct" in t and "bars" in t and "reason" in t


def test_stop_loss_caps_loss(patch_data):
    # stop %3 ile en kötü trade -%3'ten çok aşağı olmamalı (bar içi gap hariç)
    res = engine.run("TEST", "MACD Cross Up", "MACD Cross Down", range_="2y", stop_loss=3)
    for t in res["trades"]:
        if t["reason"] == "stop":
            assert t["return_pct"] <= 0


def test_invalid_rule_raises():
    from app.scanner.dsl import DSLError
    with pytest.raises(DSLError):
        engine.validate_rules("RSI(14) <", None)


def test_equity_metrics_monotonic_growth():
    eq = pd.Series(np.linspace(100, 200, 300), index=pd.date_range("2022-01-01", periods=300))
    m = equity_metrics(eq, "1d")
    assert m["total_return"] == 100.0
    assert m["max_drawdown"] == 0.0  # düşüş yok
    assert m["sharpe"] > 0
