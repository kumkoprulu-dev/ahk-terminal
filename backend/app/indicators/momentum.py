"""Momentum göstergeleri."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.indicators._helpers import ema, rma, sma, src, wma
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


# ============================ FAZ 0 — yeni momentum göstergeleri ============================

@indicator("AwesomeOsc", "Momentum", [Param("fast", 5, 1, 100), Param("slow", 34, 2, 200)],
           ["AO"], description="Awesome Oscillator (Bill Williams)")
def ao_ind(df, fast=5, slow=34):
    hl2 = (df["high"] + df["low"]) / 2
    return (sma(hl2, int(fast)) - sma(hl2, int(slow))).to_frame("AO")


@indicator("AcceleratorOsc", "Momentum",
           [Param("fast", 5, 1, 100), Param("slow", 34, 2, 200), Param("smooth", 5, 1, 100)],
           ["AC"], description="Accelerator Oscillator (AO − SMA(AO))")
def ac_ind(df, fast=5, slow=34, smooth=5):
    hl2 = (df["high"] + df["low"]) / 2
    ao = sma(hl2, int(fast)) - sma(hl2, int(slow))
    return (ao - sma(ao, int(smooth))).to_frame("AC")


@indicator("UltimateOsc", "Momentum",
           [Param("s", 7, 1, 100), Param("m", 14, 1, 200), Param("l", 28, 1, 400)],
           ["UO"], description="Ultimate Oscillator (Williams, 3 periyot)")
def uo_ind(df, s=7, m=14, l=28):
    prev_close = df["close"].shift(1)
    bp = df["close"] - pd.concat([df["low"], prev_close], axis=1).min(axis=1)
    tr = pd.concat([df["high"], prev_close], axis=1).max(axis=1) - \
        pd.concat([df["low"], prev_close], axis=1).min(axis=1)
    tr = tr.replace(0, np.nan)

    def avg(n):
        return bp.rolling(int(n)).sum() / tr.rolling(int(n)).sum()

    uo = 100 * (4 * avg(s) + 2 * avg(m) + avg(l)) / 7
    return uo.to_frame("UO")


@indicator("CMO", "Momentum", [_SRC, Param("length", 14, 1, 200)], ["CMO"],
           description="Chande Momentum Oscillator (±100)")
def cmo_ind(df, source="close", length=14):
    d = src(df, source).diff()
    up = d.clip(lower=0).rolling(int(length)).sum()
    dn = (-d.clip(upper=0)).rolling(int(length)).sum()
    return (100 * (up - dn) / (up + dn).replace(0, np.nan)).to_frame("CMO")


@indicator("DPO", "Momentum", [_SRC, Param("length", 20, 2, 300)], ["DPO"],
           description="Detrended Price Oscillator (kaydırma nedensel)")
def dpo_ind(df, source="close", length=20):
    n = int(length)
    s = src(df, source)
    return (s - sma(s, n).shift(n // 2 + 1)).to_frame("DPO")


@indicator("KST", "Momentum",
           [Param("r1", 10, 1, 100), Param("r2", 15, 1, 100),
            Param("r3", 20, 1, 200), Param("r4", 30, 1, 300)],
           ["KST", "Signal"], description="Know Sure Thing (Pring)")
def kst_ind(df, r1=10, r2=15, r3=20, r4=30):
    c = df["close"]

    def roc(n):
        return (c / c.shift(int(n)) - 1) * 100

    rcma1 = sma(roc(r1), 10)
    rcma2 = sma(roc(r2), 10)
    rcma3 = sma(roc(r3), 10)
    rcma4 = sma(roc(r4), 15)
    kst = rcma1 * 1 + rcma2 * 2 + rcma3 * 3 + rcma4 * 4
    return pd.DataFrame({"KST": kst, "Signal": sma(kst, 9)})


@indicator("RVI", "Momentum", [Param("length", 10, 2, 200)], ["RVI", "Signal"],
           description="Relative Vigor Index")
def rvi_ind(df, length=10):
    n = int(length)
    co = df["close"] - df["open"]
    hl = (df["high"] - df["low"]).replace(0, np.nan)
    num = (co + 2 * co.shift(1) + 2 * co.shift(2) + co.shift(3)) / 6
    den = (hl + 2 * hl.shift(1) + 2 * hl.shift(2) + hl.shift(3)) / 6
    rvi = num.rolling(n).sum() / den.rolling(n).sum()
    sig = (rvi + 2 * rvi.shift(1) + 2 * rvi.shift(2) + rvi.shift(3)) / 6
    return pd.DataFrame({"RVI": rvi, "Signal": sig})


@indicator("FisherTransform", "Momentum", [Param("length", 9, 2, 200)], ["Fisher", "Trigger"],
           description="Ehlers Fisher Transform")
def fisher_ind(df, length=9):
    n = int(length)
    hl2 = (df["high"] + df["low"]) / 2
    mn = hl2.rolling(n).min()
    mx = hl2.rolling(n).max()
    rng = (mx - mn).replace(0, np.nan)
    x = (2 * ((hl2 - mn) / rng) - 1).fillna(0.0).to_numpy()
    fish = np.zeros(len(x))
    val = 0.0
    f = 0.0
    for i in range(len(x)):
        val = 0.66 * x[i] + 0.67 * val
        val = max(min(val, 0.999), -0.999)  # log tanımsızlığını önle
        f = 0.5 * np.log((1 + val) / (1 - val)) + 0.5 * f
        fish[i] = f
    fs = pd.Series(fish, index=df.index)
    return pd.DataFrame({"Fisher": fs, "Trigger": fs.shift(1)})


@indicator("CoppockCurve", "Momentum",
           [Param("roc1", 14, 1, 100), Param("roc2", 11, 1, 100), Param("wma_len", 10, 1, 100)],
           ["Coppock"], description="Coppock Eğrisi (uzun vadeli momentum)")
def coppock_ind(df, roc1=14, roc2=11, wma_len=10):
    c = df["close"]
    r1 = (c / c.shift(int(roc1)) - 1) * 100
    r2 = (c / c.shift(int(roc2)) - 1) * 100
    return wma(r1 + r2, int(wma_len)).to_frame("Coppock")


@indicator("BOP", "Momentum", [Param("smooth", 14, 1, 200)], ["BOP"],
           description="Balance of Power (güç dengesi, düzleştirilmiş)")
def bop_ind(df, smooth=14):
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    bop = (df["close"] - df["open"]) / rng
    return sma(bop, int(smooth)).to_frame("BOP")
