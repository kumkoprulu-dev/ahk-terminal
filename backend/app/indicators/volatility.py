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
