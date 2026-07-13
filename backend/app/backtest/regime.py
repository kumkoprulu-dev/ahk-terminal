"""Rejim/range skorlayıcı — 'bu varlık grid'e uygun mu (yatay/mean-reverting)?'

Grid ancak ranger/choppy varlıkta kâr eder. Bu modül platformun beyninin varlık-seçim
katmanı: bir pencerenin sonundaki değerlere bakıp grid-uygunluğu skorlar. Yalnız geçmiş
veri kullanır (look-ahead yok) → seçim, ileri (OOS) döneme uygulanır.

Göstergeler:
  ER   (Kaufman Efficiency Ratio): |net değişim|/toplam yol. ~0 choppy(iyi), ~1 trend(kötü).
  ADX  (Wilder 14): trend gücü. Düşük = trendsiz (iyi).
  Hurst: <0.5 mean-reverting(iyi), ~0.5 rastgele, >0.5 trend(kötü).
  ATR% : oynaklık — grid'in kâr edebilmesi için yeterli salınım gerekir (çok düşükse boşuna).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def efficiency_ratio(close: np.ndarray, period: int) -> float:
    if len(close) < period + 1:
        return np.nan
    net = abs(close[-1] - close[-1 - period])
    path = np.abs(np.diff(close[-1 - period:])).sum()
    return float(net / path) if path else np.nan


def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
    n = len(close)
    if n < 2 * period + 1:
        return np.nan
    up = high[1:] - high[:-1]
    dn = low[:-1] - low[1:]
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = np.maximum.reduce([
        high[1:] - low[1:],
        np.abs(high[1:] - close[:-1]),
        np.abs(low[1:] - close[:-1]),
    ])
    # Wilder yumuşatma (EMA benzeri)
    def _rma(x):
        a = 1.0 / period
        out = np.empty_like(x)
        out[0] = x[:period].mean() if len(x) >= period else x[0]
        for i in range(1, len(x)):
            out[i] = out[i - 1] * (1 - a) + x[i] * a
        return out

    atr = _rma(tr)
    pdi = 100 * _rma(plus_dm) / np.where(atr == 0, np.nan, atr)
    mdi = 100 * _rma(minus_dm) / np.where(atr == 0, np.nan, atr)
    dx = 100 * np.abs(pdi - mdi) / np.where((pdi + mdi) == 0, np.nan, pdi + mdi)
    adx_arr = _rma(np.nan_to_num(dx))
    return float(adx_arr[-1])


def atr_pct(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
    n = len(close)
    if n < period + 1:
        return np.nan
    tr = np.maximum.reduce([
        high[1:] - low[1:],
        np.abs(high[1:] - close[:-1]),
        np.abs(low[1:] - close[:-1]),
    ])
    atr = tr[-period:].mean()
    return float(atr / close[-1] * 100) if close[-1] else np.nan


def hurst(close: np.ndarray, max_lag: int = 40) -> float:
    """Basit Hurst (lag'lı fark std'sinin log-log eğimi). <0.5 mean-reverting."""
    n = len(close)
    if n < max_lag * 2:
        return np.nan
    lags = range(2, max_lag)
    tau = []
    for lag in lags:
        d = close[lag:] - close[:-lag]
        tau.append(np.sqrt(np.std(d)))
    tau = np.array(tau)
    if np.any(tau <= 0):
        return np.nan
    m = np.polyfit(np.log(list(lags)), np.log(tau), 1)
    return float(m[0] * 2.0)


def score(df: pd.DataFrame, er_period: int = 96, adx_period: int = 14) -> dict:
    """Pencerenin sonundaki grid-uygunluk göstergeleri."""
    c = df["close"].to_numpy(float)
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    return {
        "er": efficiency_ratio(c, er_period),
        "adx": adx(h, l, c, adx_period),
        "atr_pct": atr_pct(h, l, c, adx_period),
        "hurst": hurst(c),
    }


def is_grid_friendly(s: dict, *, er_max: float = 0.35, adx_max: float = 25.0,
                     atr_min: float = 0.3, hurst_max: float = 0.55) -> bool:
    """Filtre: choppy (düşük ER) + trendsiz (düşük ADX) + yeterli oynaklık + mean-reverting."""
    return (
        s["er"] == s["er"] and s["er"] <= er_max
        and s["adx"] == s["adx"] and s["adx"] <= adx_max
        and s["atr_pct"] == s["atr_pct"] and s["atr_pct"] >= atr_min
        and (s["hurst"] != s["hurst"] or s["hurst"] <= hurst_max)  # hurst NaN ise geç
    )


def rank_key(s: dict) -> float:
    """Sıralama anahtarı: en choppy (düşük ER) önce; NaN'lar sona."""
    return s["er"] if s["er"] == s["er"] else 1e9
