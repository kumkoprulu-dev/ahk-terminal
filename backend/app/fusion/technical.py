"""Teknik skor — TechScore göstergesinin son barı + bileşen detayları.

Skor hesabı tek yerde: indicators/fusion_ind.py (TechScore — vektörel, backtest edilebilir).
Buradaki technical_score onun son değerini alır ve gösterim için bileşenleri ekler.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.indicators import compute
from app.indicators._helpers import ema


def technical_score(df: pd.DataFrame) -> dict:
    if df is None or len(df) < 50:
        return {"score": None, "label": "veri yok", "direction": 0.0, "components": {}}
    series = compute("TechScore", df)["TechScore"]
    val = series.iloc[-1]
    if val != val:  # NaN
        return {"score": None, "label": "veri yok", "direction": 0.0, "components": {}}
    score = round(float(val), 1)

    close = df["close"]
    c, e20, e50, e200 = (float(close.iloc[-1]), float(ema(close, 20).iloc[-1]),
                         float(ema(close, 50).iloc[-1]), float(ema(close, 200).iloc[-1]))
    align = (np.sign(c - e20) + np.sign(e20 - e50) + np.sign(e50 - e200)) / 3.0
    rsi = float(compute("RSI", df)["RSI"].iloc[-1])
    adx = float(compute("ADX", df)["ADX"].iloc[-1])
    hist = float(compute("MACD", df)["Hist"].iloc[-1])
    return {
        "score": score,
        "label": _label(score),
        "direction": round((score - 50) / 50, 3),
        "components": {
            "ema_align": round(float(align), 2), "adx": round(adx, 1) if adx == adx else None,
            "rsi": round(rsi, 1) if rsi == rsi else None, "macd_hist": round(hist, 4) if hist == hist else None,
        },
    }


def _label(score: float) -> str:
    if score >= 70:
        return "güçlü yukarı"
    if score >= 55:
        return "yukarı"
    if score >= 45:
        return "nötr"
    if score >= 30:
        return "aşağı"
    return "güçlü aşağı"
