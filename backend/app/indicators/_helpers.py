"""Göstergeler arası paylaşılan küçük yardımcılar (saf pandas/numpy)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def src(df: pd.DataFrame, name: str = "close") -> pd.Series:
    """Kaynak seriyi getirir: close/open/high/low/volume veya hlc3/ohlc4."""
    name = str(name).lower()
    if name in df.columns:
        return df[name].astype(float)
    if name == "hlc3":
        return (df["high"] + df["low"] + df["close"]) / 3
    if name == "ohlc4":
        return (df["open"] + df["high"] + df["low"] + df["close"]) / 4
    if name == "hl2":
        return (df["high"] + df["low"]) / 2
    return df["close"].astype(float)


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(int(n)).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=int(n), adjust=False).mean()


def wma(s: pd.Series, n: int) -> pd.Series:
    n = int(n)
    weights = np.arange(1, n + 1)
    return s.rolling(n).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)


def rma(s: pd.Series, n: int) -> pd.Series:
    """Wilder's smoothing (RSI/ATR'de kullanılır)."""
    return s.ewm(alpha=1 / int(n), adjust=False).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr


def crossover(a: pd.Series, b: pd.Series) -> pd.Series:
    """a, b'yi yukarı kestiğinde True."""
    return (a > b) & (a.shift(1) <= b.shift(1))


def crossunder(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a < b) & (a.shift(1) >= b.shift(1))
