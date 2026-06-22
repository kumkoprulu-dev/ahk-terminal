"""Füzyon göstergeleri — teknik birleşik skor (backtest edilebilir, vektörel).

TechScore: trend (EMA20/50/200 dizilimi, ADX gücüyle ölçeklenir) + momentum (RSI, MACD)
→ her bar için 0-100 skor. Registry'de olduğu için Strateji/Optimize/Walk-Forward/Tarayıcı
ve grafikte doğrudan kullanılabilir, örn:  TechScore > 62
"""
from __future__ import annotations

import numpy as np

from app.indicators._helpers import ema
from app.indicators.registry import compute, indicator


@indicator("TechScore", "Füzyon", [], ["TechScore"], description="Teknik füzyon skoru 0-100 (trend+ADX+RSI+MACD)")
def techscore_ind(df):
    close = df["close"]
    e20 = ema(close, 20)
    e50 = ema(close, 50)
    e200 = ema(close, 200)

    align = (np.sign(close - e20) + np.sign(e20 - e50) + np.sign(e50 - e200)) / 3.0
    rsi = compute("RSI", df)["RSI"]
    adx = compute("ADX", df)["ADX"]
    hist = compute("MACD", df)["Hist"]

    adx_conf = (adx / 40.0).clip(0, 1).fillna(0.3)
    rsi_norm = ((rsi - 50.0) / 30.0).clip(-1, 1)
    rsi_norm = rsi_norm.mask(rsi > 75, 0.25).mask(rsi < 25, -0.25)
    macd_dir = np.sign(hist)

    direction = (0.45 * align * (0.5 + 0.5 * adx_conf) + 0.30 * rsi_norm + 0.25 * macd_dir).clip(-1, 1)
    return (50 + 50 * direction).to_frame("TechScore")
