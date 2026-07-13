"""Hacim göstergeleri."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.indicators._helpers import ema, sma
from app.indicators.registry import Param, indicator


@indicator("OBV", "Hacim", [], ["OBV"], description="On-Balance Volume")
def obv_ind(df):
    direction = np.sign(df["close"].diff().fillna(0))
    return (direction * df["volume"]).cumsum().to_frame("OBV")


@indicator("MFI", "Hacim", [Param("length", 14, 1, 200)], ["MFI"],
           description="Money Flow Index")
def mfi_ind(df, length=14):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    mf = tp * df["volume"]
    delta = tp.diff()
    pos = mf.where(delta > 0, 0.0).rolling(int(length)).sum()
    neg = mf.where(delta < 0, 0.0).rolling(int(length)).sum()
    mfr = pos / neg.replace(0, np.nan)
    return (100 - 100 / (1 + mfr)).to_frame("MFI")


@indicator("CMF", "Hacim", [Param("length", 20, 1, 200)], ["CMF"],
           description="Chaikin Money Flow")
def cmf_ind(df, length=20):
    hl = (df["high"] - df["low"]).replace(0, np.nan)
    mfm = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / hl
    mfv = mfm * df["volume"]
    cmf = mfv.rolling(int(length)).sum() / df["volume"].rolling(int(length)).sum()
    return cmf.to_frame("CMF")


@indicator("ADL", "Hacim", [], ["ADL"], description="Accumulation/Distribution Line")
def adl_ind(df):
    hl = (df["high"] - df["low"]).replace(0, np.nan)
    mfm = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / hl
    return (mfm * df["volume"]).fillna(0).cumsum().to_frame("ADL")


@indicator("VWAP", "Hacim", [], ["VWAP"], overlay=True,
           description="Volume Weighted Average Price (kümülatif)")
def vwap_ind(df):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    return ((tp * df["volume"]).cumsum() / df["volume"].cumsum()).to_frame("VWAP")


@indicator("VolumeOsc", "Hacim", [Param("fast", 5, 1, 100), Param("slow", 20, 1, 200)],
           ["VolumeOsc"], description="Hacim Osilatörü (%)")
def volosc_ind(df, fast=5, slow=20):
    f = sma(df["volume"], int(fast))
    s = sma(df["volume"], int(slow))
    return (100 * (f - s) / s).to_frame("VolumeOsc")


# ============================ FAZ 0 — yeni hacim göstergeleri ============================

@indicator("ForceIndex", "Hacim", [Param("length", 13, 1, 200)], ["ForceIndex"],
           description="Elder Force Index (fiyat değişimi × hacim, EMA)")
def forceindex_ind(df, length=13):
    fi = df["close"].diff() * df["volume"]
    return ema(fi, int(length)).to_frame("ForceIndex")


@indicator("EaseOfMovement", "Hacim", [Param("length", 14, 1, 200)], ["EOM"],
           description="Ease of Movement (fiyat hareketi / hacim direnci)")
def eom_ind(df, length=14):
    hl2 = (df["high"] + df["low"]) / 2
    distance = hl2.diff()
    box = (df["volume"] / 1e8) / (df["high"] - df["low"]).replace(0, np.nan)
    emv = distance / box.replace(0, np.nan)
    return sma(emv, int(length)).to_frame("EOM")


@indicator("KlingerOsc", "Hacim",
           [Param("fast", 34, 1, 200), Param("slow", 55, 2, 300), Param("signal", 13, 1, 100)],
           ["KVO", "Signal"], description="Klinger Volume Oscillator")
def klinger_ind(df, fast=34, slow=55, signal=13):
    hlc = df["high"] + df["low"] + df["close"]
    trend = np.sign(hlc.diff().fillna(0.0))
    vf = df["volume"] * trend
    kvo = ema(vf, int(fast)) - ema(vf, int(slow))
    return pd.DataFrame({"KVO": kvo, "Signal": ema(kvo, int(signal))})


@indicator("PVT", "Hacim", [], ["PVT"], description="Price Volume Trend (kümülatif)")
def pvt_ind(df):
    return (df["close"].pct_change().fillna(0.0) * df["volume"]).cumsum().to_frame("PVT")
