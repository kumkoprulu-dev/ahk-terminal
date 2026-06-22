"""Çok-sembol fiyat matrisi + getiri istatistikleri (mu, sigma)."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from app.data import service

TRADING_DAYS = 252


def load_prices(symbols: list[str], interval: str = "1d", range_: str = "2y") -> pd.DataFrame:
    """Sembollerin kapanış fiyatlarını ortak tarihlerde hizalı bir DataFrame'e çeker.
    Yetersiz verisi olan semboller atılır."""
    closes: dict[str, pd.Series] = {}

    def _one(sym: str):
        df = service.get_ohlcv(sym, interval, range_)
        if df is None or len(df) < 30:
            return sym, None
        return sym, df["close"].rename(sym)

    with ThreadPoolExecutor(max_workers=8) as ex:
        for sym, s in ex.map(_one, symbols):
            if s is not None:
                closes[sym] = s

    if not closes:
        return pd.DataFrame()
    price = pd.concat(closes.values(), axis=1, join="inner").dropna()
    return price


def returns_stats(price: pd.DataFrame, interval: str = "1d"):
    """Yıllıklandırılmış beklenen getiri (mu) ve kovaryans (sigma) + günlük getiriler."""
    ppy = {"1d": TRADING_DAYS, "1wk": 52, "1mo": 12}.get(interval, TRADING_DAYS)
    rets = price.pct_change().dropna()
    mu = rets.mean().values * ppy
    sigma = rets.cov().values * ppy
    return mu, sigma, rets
