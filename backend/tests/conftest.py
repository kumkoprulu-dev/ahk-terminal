import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def ohlcv():
    idx = pd.date_range("2022-01-01", periods=400, freq="D")
    rng = np.random.default_rng(42)
    ret = rng.normal(0.0005, 0.02, 400)
    close = 100 * np.cumprod(1 + ret)
    high = close * (1 + np.abs(rng.normal(0, 0.01, 400)))
    low = close * (1 - np.abs(rng.normal(0, 0.01, 400)))
    op = close * (1 + rng.normal(0, 0.005, 400))
    vol = rng.integers(1e5, 1e6, 400).astype(float)
    return pd.DataFrame(
        {"open": op, "high": high, "low": low, "close": close, "volume": vol},
        index=idx,
    )
