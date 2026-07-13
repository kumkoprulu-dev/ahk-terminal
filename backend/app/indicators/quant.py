"""Kuantitatif göstergeler (çekirdek set; sonraki fazlarda HMM/PCA/Cointegration eklenecek)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.indicators._helpers import sma, src
from app.indicators.registry import Param, indicator

_SRC = Param("source", "close", 0, 0, type="source")


@indicator("KalmanFilter", "Kuantitatif",
           [_SRC, Param("process_var", 0.01, 0.0001, 1, 0.001, "float"),
            Param("measure_var", 1.0, 0.01, 100, 0.1, "float")],
           ["Kalman"], overlay=True,
           description="1B Kalman filtresi (rastgele yürüyüş modeli ile fiyat düzleştirme)")
def kalman_ind(df, source="close", process_var=0.01, measure_var=1.0):
    z = src(df, source).values
    n = len(z)
    xhat = np.zeros(n)
    p = np.zeros(n)
    if n == 0:
        return pd.DataFrame({"Kalman": xhat}, index=df.index)
    xhat[0] = z[0]
    p[0] = 1.0
    q, r = float(process_var), float(measure_var)
    for k in range(1, n):
        x_prior = xhat[k - 1]
        p_prior = p[k - 1] + q
        kgain = p_prior / (p_prior + r)
        xhat[k] = x_prior + kgain * (z[k] - x_prior)
        p[k] = (1 - kgain) * p_prior
    return pd.DataFrame({"Kalman": xhat}, index=df.index)


@indicator("HurstExponent", "Kuantitatif", [Param("length", 100, 20, 500)], ["Hurst"],
           description="Hurst üsteli (R/S). >0.5 trend, <0.5 ortalamaya dönüş")
def hurst_ind(df, length=100):
    s = np.log(df["close"]).values
    n = int(length)

    def _hurst(ts: np.ndarray) -> float:
        ts = ts[~np.isnan(ts)]
        if len(ts) < 20:
            return np.nan
        lags = range(2, min(20, len(ts) // 2))
        tau = []
        for lag in lags:
            diff = ts[lag:] - ts[:-lag]
            tau.append(np.sqrt(np.std(diff)))
        tau = np.array(tau)
        valid = tau > 0
        if valid.sum() < 3:
            return np.nan
        lg = np.log(np.array(list(lags))[valid])
        lt = np.log(tau[valid])
        poly = np.polyfit(lg, lt, 1)
        return poly[0] * 2.0

    out = pd.Series(s, index=df.index).rolling(n).apply(_hurst, raw=True)
    return out.to_frame("Hurst")


@indicator("MeanReversionScore", "Kuantitatif",
           [_SRC, Param("length", 20, 2, 500)], ["MRScore"],
           description="Ortalamaya dönüş skoru: pozitif = fiyat ortalamanın altında (al sinyali eğilimi)")
def mrs_ind(df, source="close", length=20):
    s = src(df, source)
    mean = sma(s, int(length))
    std = s.rolling(int(length)).std()
    return ((mean - s) / std.replace(0, np.nan)).to_frame("MRScore")


@indicator("FractalDim", "Kuantitatif", [Param("length", 30, 10, 200)], ["FractalDim"],
           description="Katz fraktal boyutu (1=düz, 2=çok dalgalı)")
def fractal_ind(df, length=30):
    s = df["close"].values
    n = int(length)

    def _katz(x: np.ndarray) -> float:
        x = x[~np.isnan(x)]
        m = len(x)
        if m < 3:
            return np.nan
        i = np.arange(m)
        dists = np.sqrt(1 + np.diff(x) ** 2)
        L = dists.sum()
        d = np.max(np.sqrt((i - 0) ** 2 + (x - x[0]) ** 2))
        if L == 0 or d == 0:
            return np.nan
        return np.log10(m) / (np.log10(d / L) + np.log10(m))

    out = pd.Series(s, index=df.index).rolling(n).apply(_katz, raw=True)
    return out.to_frame("FractalDim")


@indicator("EfficiencyRatio", "Kuantitatif", [_SRC, Param("length", 10, 2, 300)], ["ER"],
           description="Kaufman Efficiency Ratio (0-1): net yol / toplam yol. Yüksek=trend, düşük=choppy")
def er_ind(df, source="close", length=10):
    n = int(length)
    s = src(df, source)
    change = (s - s.shift(n)).abs()
    vol = s.diff().abs().rolling(n).sum().replace(0, np.nan)
    return (change / vol).to_frame("ER")
