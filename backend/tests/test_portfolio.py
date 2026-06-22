import numpy as np
import pandas as pd
import pytest

import app.portfolio.service as psvc
from app.portfolio import optimizer, quantum
from app.data.universe import get_universe, universe_list


@pytest.fixture
def patch_prices(monkeypatch):
    def fake_load(symbols, interval="1d", range_="2y"):
        idx = pd.date_range("2022-01-01", periods=400, freq="D")
        rng = np.random.default_rng(1)
        data = {}
        for k, s in enumerate(symbols):
            ret = rng.normal(0.0004 + k * 0.0001, 0.015 + k * 0.002, 400)
            data[s] = 100 * np.cumprod(1 + ret)
        return pd.DataFrame(data, index=idx)
    monkeypatch.setattr(psvc, "load_prices", fake_load)


def test_universe_groups_exist():
    ids = {u["id"] for u in universe_list()}
    assert {"bist30", "bist50", "bist100", "nasdaq", "emtia", "kripto"} <= ids
    assert len(get_universe("bist100")) == 100
    assert len(get_universe("emtia")) >= 10
    # case-insensitive + label ile erişim
    assert get_universe("BIST 30") == get_universe("bist30")


def test_weights_sum_to_one(patch_prices):
    for m in optimizer.METHODS:
        res = psvc.optimize(["A", "B", "C", "D", "E"], method=m, range_="2y")
        total = sum(w["weight"] for w in res["weights"])
        assert abs(total - 100) < 1.0, m  # yüzde toplamı ~100


def test_comparison_and_frontier(patch_prices):
    res = psvc.optimize(["A", "B", "C", "D"], method="max_sharpe")
    assert len(res["comparison"]) == len(optimizer.METHODS)
    assert len(res["frontier"]) > 5
    assert "var" in res["montecarlo"] and "cvar" in res["montecarlo"]


def test_quantum_competitive(patch_prices):
    """Kuantum (SA-QUBO + Markowitz ağırlık) eşit ağırlıktan daha iyi Sharpe vermeli."""
    res = psvc.optimize(["A", "B", "C", "D", "E", "F"], method="quantum")
    comp = {c["method"]: c["sharpe"] for c in res["comparison"]}
    assert comp["quantum"] >= comp["equal_weight"] - 1e-6


def test_min_two_symbols():
    with pytest.raises(ValueError):
        psvc.optimize(["A"], method="max_sharpe")
