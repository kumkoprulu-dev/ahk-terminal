"""Hacim göstergeleri."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.indicators._helpers import sma
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
