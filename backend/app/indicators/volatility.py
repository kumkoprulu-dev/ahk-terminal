"""Volatilite göstergeleri."""
from __future__ import annotations

import numpy as np

from app.indicators._helpers import ema, rma, sma, src, true_range
from app.indicators.registry import Param, indicator
import pandas as pd

_SRC = Param("source", "close", 0, 0, type="source")


@indicator("ATR", "Volatilite", [Param("length", 14, 1, 200)], ["ATR"],
           description="Average True Range")
def atr_ind(df, length=14):
    return rma(true_range(df), int(length)).to_frame("ATR")


@indicator("BollingerBands", "Volatilite",
           [_SRC, Param("length", 20, 1, 200), Param("mult", 2, 0.5, 5, 0.1, "float")],
           ["Upper", "Middle", "Lower"], overlay=True, description="Bollinger Bantları")
def bbands_ind(df, source="close", length=20, mult=2.0):
    s = src(df, source)
    mid = sma(s, int(length))
    sd = s.rolling(int(length)).std()
    return pd.DataFrame({
        "Upper": mid + mult * sd,
        "Middle": mid,
        "Lower": mid - mult * sd,
    })


@indicator("KeltnerChannel", "Volatilite",
           [Param("length", 20, 1, 200), Param("mult", 2, 0.5, 5, 0.1, "float")],
           ["Upper", "Middle", "Lower"], overlay=True, description="Keltner Kanalı")
def keltner_ind(df, length=20, mult=2.0):
    mid = ema(df["close"], int(length))
    atr = rma(true_range(df), int(length))
    return pd.DataFrame({
        "Upper": mid + mult * atr,
        "Middle": mid,
        "Lower": mid - mult * atr,
    })


@indicator("StdDev", "Volatilite", [_SRC, Param("length", 20, 1, 200)], ["StdDev"],
           description="Standart Sapma")
def stddev_ind(df, source="close", length=20):
    return src(df, source).rolling(int(length)).std().to_frame("StdDev")


@indicator("HistVol", "Volatilite", [Param("length", 20, 1, 252)], ["HistVol"],
           description="Tarihsel Volatilite (yıllıklandırılmış %)")
def histvol_ind(df, length=20):
    logret = np.log(df["close"] / df["close"].shift(1))
    return (logret.rolling(int(length)).std() * np.sqrt(252) * 100).to_frame("HistVol")


# ============================ FAZ 0 — yeni volatilite/rejim göstergeleri ============================

@indicator("ChoppinessIndex", "Volatilite", [Param("length", 14, 2, 200)], ["Chop"],
           description="Choppiness Index (>61.8 range/choppy, <38.2 trend) — rejim filtresi")
def chop_ind(df, length=14):
    n = int(length)
    tr_sum = true_range(df).rolling(n).sum()
    hh = df["high"].rolling(n).max()
    ll = df["low"].rolling(n).min()
    rng = (hh - ll).replace(0, np.nan)
    return (100 * np.log10(tr_sum / rng) / np.log10(n)).to_frame("Chop")


@indicator("UlcerIndex", "Volatilite", [Param("length", 14, 2, 300)], ["Ulcer"],
           description="Ulcer Index (düşüş-derinliği tabanlı risk ölçüsü)")
def ulcer_ind(df, length=14):
    n = int(length)
    roll_max = df["close"].rolling(n).max()
    dd = 100 * (df["close"] - roll_max) / roll_max
    return np.sqrt((dd ** 2).rolling(n).mean()).to_frame("Ulcer")


@indicator("ChaikinVol", "Volatilite",
           [Param("ema_len", 10, 1, 100), Param("roc_len", 10, 1, 100)],
           ["ChaikinVol"], description="Chaikin Volatility (H−L bandı değişim %)")
def chaikinvol_ind(df, ema_len=10, roc_len=10):
    hl = ema(df["high"] - df["low"], int(ema_len))
    r = int(roc_len)
    return (100 * (hl - hl.shift(r)) / hl.shift(r).replace(0, np.nan)).to_frame("ChaikinVol")


@indicator("MassIndex", "Volatilite",
           [Param("ema_len", 9, 1, 100), Param("sum_len", 25, 2, 200)],
           ["MassIndex"], description="Mass Index (dönüş sinyali — bant genişleme/daralma)")
def massindex_ind(df, ema_len=9, sum_len=25):
    rng = df["high"] - df["low"]
    e1 = ema(rng, int(ema_len))
    e2 = ema(e1, int(ema_len))
    ratio = e1 / e2.replace(0, np.nan)
    return ratio.rolling(int(sum_len)).sum().to_frame("MassIndex")
