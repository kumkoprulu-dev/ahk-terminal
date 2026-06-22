"""Momentum göstergeleri."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.indicators._helpers import ema, rma, sma, src
from app.indicators.registry import Param, indicator

_SRC = Param("source", "close", 0, 0, type="source")


@indicator("RSI", "Momentum", [_SRC, Param("length", 14, 1, 200)], ["RSI"],
           description="Relative Strength Index")
def rsi_ind(df, source="close", length=14):
    s = src(df, source)
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    rs = rma(gain, length) / rma(loss, length).replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    return rsi.to_frame("RSI")


@indicator("Stochastic", "Momentum",
           [Param("k", 14, 1, 100), Param("d", 3, 1, 50), Param("smooth", 3, 1, 50)],
           ["K", "D"], description="Stokastik Osilatör")
def stoch_ind(df, k=14, d=3, smooth=3):
    low_min = df["low"].rolling(int(k)).min()
    high_max = df["high"].rolling(int(k)).max()
    raw_k = 100 * (df["close"] - low_min) / (high_max - low_min).replace(0, np.nan)
    k_line = sma(raw_k, int(smooth))
    d_line = sma(k_line, int(d))
    return pd.DataFrame({"K": k_line, "D": d_line})


@indicator("StochRSI", "Momentum",
           [Param("rsi_length", 14, 1, 200), Param("stoch_length", 14, 1, 200),
            Param("k", 3, 1, 50), Param("d", 3, 1, 50)],
           ["K", "D"], description="Stochastic RSI")
def stochrsi_ind(df, rsi_length=14, stoch_length=14, k=3, d=3):
    rsi = rsi_ind(df, "close", rsi_length)["RSI"]
    low = rsi.rolling(int(stoch_length)).min()
    high = rsi.rolling(int(stoch_length)).max()
    stoch = 100 * (rsi - low) / (high - low).replace(0, np.nan)
    k_line = sma(stoch, int(k))
    d_line = sma(k_line, int(d))
    return pd.DataFrame({"K": k_line, "D": d_line})


@indicator("MACD", "Momentum",
           [_SRC, Param("fast", 12, 1, 200), Param("slow", 26, 1, 400), Param("signal", 9, 1, 100)],
           ["MACD", "Signal", "Hist"], description="Moving Average Convergence Divergence")
def macd_ind(df, source="close", fast=12, slow=26, signal=9):
    s = src(df, source)
    macd = ema(s, int(fast)) - ema(s, int(slow))
    sig = ema(macd, int(signal))
    return pd.DataFrame({"MACD": macd, "Signal": sig, "Hist": macd - sig})


@indicator("CCI", "Momentum", [Param("length", 20, 1, 200)], ["CCI"],
           description="Commodity Channel Index")
def cci_ind(df, length=20):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    ma = sma(tp, int(length))
    md = (tp - ma).abs().rolling(int(length)).mean()
    return ((tp - ma) / (0.015 * md)).to_frame("CCI")


@indicator("ROC", "Momentum", [_SRC, Param("length", 12, 1, 200)], ["ROC"],
           description="Rate of Change (%)")
def roc_ind(df, source="close", length=12):
    s = src(df, source)
    return (s.pct_change(int(length)) * 100).to_frame("ROC")


@indicator("Momentum", "Momentum", [_SRC, Param("length", 10, 1, 200)], ["Momentum"],
           description="Momentum (fiyat farkı)")
def momentum_ind(df, source="close", length=10):
    s = src(df, source)
    return (s - s.shift(int(length))).to_frame("Momentum")


@indicator("WilliamsR", "Momentum", [Param("length", 14, 1, 200)], ["WilliamsR"],
           description="Williams %R")
def williamsr_ind(df, length=14):
    high = df["high"].rolling(int(length)).max()
    low = df["low"].rolling(int(length)).min()
    wr = -100 * (high - df["close"]) / (high - low).replace(0, np.nan)
    return wr.to_frame("WilliamsR")


@indicator("TSI", "Momentum", [Param("long", 25, 1, 200), Param("short", 13, 1, 100)],
           ["TSI"], description="True Strength Index")
def tsi_ind(df, long=25, short=13):
    m = df["close"].diff()
    ds = ema(ema(m, int(long)), int(short))
    das = ema(ema(m.abs(), int(long)), int(short))
    return (100 * ds / das.replace(0, np.nan)).to_frame("TSI")


@indicator("PPO", "Momentum", [Param("fast", 12, 1, 200), Param("slow", 26, 1, 400)],
           ["PPO"], description="Percentage Price Oscillator")
def ppo_ind(df, fast=12, slow=26):
    fast_e = ema(df["close"], int(fast))
    slow_e = ema(df["close"], int(slow))
    return (100 * (fast_e - slow_e) / slow_e).to_frame("PPO")


@indicator("TRIX", "Momentum", [Param("length", 15, 1, 200)], ["TRIX"],
           description="TRIX (üçlü düzleştirilmiş ROC)")
def trix_ind(df, length=15):
    e = ema(ema(ema(df["close"], int(length)), int(length)), int(length))
    return (e.pct_change() * 100).to_frame("TRIX")
