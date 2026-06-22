"""İstatistiksel göstergeler (tek seri üzerinde, kayan pencere)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.indicators._helpers import sma, src
from app.indicators.registry import Param, indicator

_SRC = Param("source", "close", 0, 0, type="source")
_ANN = np.sqrt(252)


@indicator("ZScore", "İstatistiksel", [_SRC, Param("length", 20, 2, 500)], ["ZScore"],
           description="Z-Skoru (ortalamadan kaç standart sapma)")
def zscore_ind(df, source="close", length=20):
    s = src(df, source)
    mean = sma(s, int(length))
    std = s.rolling(int(length)).std()
    return ((s - mean) / std.replace(0, np.nan)).to_frame("ZScore")


@indicator("Sharpe", "İstatistiksel", [Param("length", 60, 5, 500)], ["Sharpe"],
           description="Kayan Sharpe oranı (yıllıklandırılmış, rf=0)")
def sharpe_ind(df, length=60):
    r = df["close"].pct_change()
    mean = r.rolling(int(length)).mean()
    std = r.rolling(int(length)).std()
    return (mean / std.replace(0, np.nan) * _ANN).to_frame("Sharpe")


@indicator("Sortino", "İstatistiksel", [Param("length", 60, 5, 500)], ["Sortino"],
           description="Kayan Sortino oranı (aşağı yön riski)")
def sortino_ind(df, length=60):
    r = df["close"].pct_change()
    mean = r.rolling(int(length)).mean()
    downside = r.where(r < 0, 0.0)
    dstd = downside.rolling(int(length)).std()
    return (mean / dstd.replace(0, np.nan) * _ANN).to_frame("Sortino")


@indicator("Calmar", "İstatistiksel", [Param("length", 120, 10, 750)], ["Calmar"],
           description="Kayan Calmar oranı (getiri / maks düşüş)")
def calmar_ind(df, length=120):
    n = int(length)
    r = df["close"].pct_change()
    ann_ret = r.rolling(n).mean() * 252

    def max_dd(x):
        cum = np.cumprod(1 + x)
        peak = np.maximum.accumulate(cum)
        dd = (cum - peak) / peak
        return -dd.min() if len(dd) else np.nan

    mdd = r.rolling(n).apply(max_dd, raw=True)
    return (ann_ret / mdd.replace(0, np.nan)).to_frame("Calmar")


@indicator("Kurtosis", "İstatistiksel", [Param("length", 60, 4, 500)], ["Kurtosis"],
           description="Kayan basıklık (kurtosis)")
def kurtosis_ind(df, length=60):
    return df["close"].pct_change().rolling(int(length)).kurt().to_frame("Kurtosis")


@indicator("Skewness", "İstatistiksel", [Param("length", 60, 3, 500)], ["Skewness"],
           description="Kayan çarpıklık (skewness)")
def skewness_ind(df, length=60):
    return df["close"].pct_change().rolling(int(length)).skew().to_frame("Skewness")
