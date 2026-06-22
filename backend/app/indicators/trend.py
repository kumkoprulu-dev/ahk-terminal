"""Trend göstergeleri."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.indicators._helpers import ema, rma, sma, src, true_range, wma
from app.indicators.registry import Param, indicator

_LEN = lambda d, mn, mx: Param("length", d, mn, mx, type="int")  # noqa: E731
_SRC = Param("source", "close", 0, 0, type="source")


@indicator("SMA", "Trend", [_SRC, _LEN(20, 1, 500)], ["SMA"], overlay=True,
           description="Basit Hareketli Ortalama")
def sma_ind(df, source="close", length=20):
    return sma(src(df, source), length).to_frame("SMA")


@indicator("EMA", "Trend", [_SRC, _LEN(20, 1, 500)], ["EMA"], overlay=True,
           description="Üstel Hareketli Ortalama")
def ema_ind(df, source="close", length=20):
    return ema(src(df, source), length).to_frame("EMA")


@indicator("WMA", "Trend", [_SRC, _LEN(20, 1, 500)], ["WMA"], overlay=True,
           description="Ağırlıklı Hareketli Ortalama")
def wma_ind(df, source="close", length=20):
    return wma(src(df, source), length).to_frame("WMA")


@indicator("HMA", "Trend", [_SRC, _LEN(20, 2, 500)], ["HMA"], overlay=True,
           description="Hull Hareketli Ortalama")
def hma_ind(df, source="close", length=20):
    s = src(df, source)
    half = max(int(length / 2), 1)
    sqrt_n = max(int(np.sqrt(length)), 1)
    raw = 2 * wma(s, half) - wma(s, length)
    return wma(raw, sqrt_n).to_frame("HMA")


@indicator("DEMA", "Trend", [_SRC, _LEN(20, 1, 500)], ["DEMA"], overlay=True,
           description="Çift Üstel Hareketli Ortalama")
def dema_ind(df, source="close", length=20):
    s = src(df, source)
    e1 = ema(s, length)
    e2 = ema(e1, length)
    return (2 * e1 - e2).to_frame("DEMA")


@indicator("TEMA", "Trend", [_SRC, _LEN(20, 1, 500)], ["TEMA"], overlay=True,
           description="Üçlü Üstel Hareketli Ortalama")
def tema_ind(df, source="close", length=20):
    s = src(df, source)
    e1 = ema(s, length)
    e2 = ema(e1, length)
    e3 = ema(e2, length)
    return (3 * e1 - 3 * e2 + e3).to_frame("TEMA")


@indicator(
    "SuperTrend", "Trend",
    [Param("length", 10, 1, 100, type="int"), Param("multiplier", 3, 0.5, 10, 0.5, "float")],
    ["SuperTrend", "Direction"], overlay=True,
    description="SuperTrend (ATR tabanlı trend takip)",
)
def supertrend_ind(df, length=10, multiplier=3.0):
    hl2 = (df["high"] + df["low"]) / 2
    atr = rma(true_range(df), length)
    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr
    close = df["close"]
    st = pd.Series(index=df.index, dtype=float)
    dir_ = pd.Series(index=df.index, dtype=float)
    final_upper = upper.copy()
    final_lower = lower.copy()
    for i in range(len(df)):
        if i == 0:
            st.iloc[i] = upper.iloc[i]
            dir_.iloc[i] = -1
            continue
        final_upper.iloc[i] = (
            min(upper.iloc[i], final_upper.iloc[i - 1])
            if close.iloc[i - 1] <= final_upper.iloc[i - 1] else upper.iloc[i]
        )
        final_lower.iloc[i] = (
            max(lower.iloc[i], final_lower.iloc[i - 1])
            if close.iloc[i - 1] >= final_lower.iloc[i - 1] else lower.iloc[i]
        )
        if close.iloc[i] > final_upper.iloc[i - 1]:
            dir_.iloc[i] = 1
        elif close.iloc[i] < final_lower.iloc[i - 1]:
            dir_.iloc[i] = -1
        else:
            dir_.iloc[i] = dir_.iloc[i - 1]
        st.iloc[i] = final_lower.iloc[i] if dir_.iloc[i] == 1 else final_upper.iloc[i]
    return pd.DataFrame({"SuperTrend": st, "Direction": dir_})


@indicator(
    "Ichimoku", "Trend",
    [Param("conversion", 9, 1, 60), Param("base", 26, 1, 120), Param("span_b", 52, 1, 240)],
    ["Tenkan", "Kijun", "SpanA", "SpanB"], overlay=True,
    description="Ichimoku Kinko Hyo",
)
def ichimoku_ind(df, conversion=9, base=26, span_b=52):
    high, low = df["high"], df["low"]

    def mid(n):
        return (high.rolling(int(n)).max() + low.rolling(int(n)).min()) / 2

    tenkan = mid(conversion)
    kijun = mid(base)
    span_a = ((tenkan + kijun) / 2).shift(int(base))
    span_bb = mid(span_b).shift(int(base))
    return pd.DataFrame({"Tenkan": tenkan, "Kijun": kijun, "SpanA": span_a, "SpanB": span_bb})


@indicator(
    "PSAR", "Trend",
    [Param("step", 0.02, 0.01, 0.2, 0.01, "float"), Param("max_step", 0.2, 0.05, 0.5, 0.05, "float")],
    ["PSAR"], overlay=True, description="Parabolic SAR",
)
def psar_ind(df, step=0.02, max_step=0.2):
    high, low = df["high"].values, df["low"].values
    n = len(df)
    psar = np.zeros(n)
    if n == 0:
        return pd.DataFrame({"PSAR": psar}, index=df.index)
    bull = True
    af = step
    ep = high[0]
    psar[0] = low[0]
    for i in range(1, n):
        psar[i] = psar[i - 1] + af * (ep - psar[i - 1])
        if bull:
            if low[i] < psar[i]:
                bull = False
                psar[i] = ep
                ep = low[i]
                af = step
            else:
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + step, max_step)
        else:
            if high[i] > psar[i]:
                bull = True
                psar[i] = ep
                ep = high[i]
                af = step
            else:
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + step, max_step)
    return pd.DataFrame({"PSAR": psar}, index=df.index)


@indicator("Donchian", "Trend", [_LEN(20, 1, 200)], ["Upper", "Middle", "Lower"],
           overlay=True, description="Donchian Kanalı")
def donchian_ind(df, length=20):
    upper = df["high"].rolling(int(length)).max()
    lower = df["low"].rolling(int(length)).min()
    middle = (upper + lower) / 2
    return pd.DataFrame({"Upper": upper, "Middle": middle, "Lower": lower})


@indicator("Aroon", "Trend", [_LEN(25, 1, 200)], ["AroonUp", "AroonDown", "AroonOsc"],
           description="Aroon göstergesi")
def aroon_ind(df, length=25):
    n = int(length)
    high, low = df["high"], df["low"]
    up = high.rolling(n + 1).apply(lambda x: (n - x.argmax()) / n * 100, raw=True)
    down = low.rolling(n + 1).apply(lambda x: (n - x.argmin()) / n * 100, raw=True)
    return pd.DataFrame({"AroonUp": up, "AroonDown": down, "AroonOsc": up - down})


@indicator("ADX", "Trend", [_LEN(14, 1, 100)], ["ADX", "PlusDI", "MinusDI"],
           description="Average Directional Index")
def adx_ind(df, length=14):
    n = int(length)
    high, low = df["high"], df["low"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr = rma(true_range(df), n)
    plus_di = 100 * rma(pd.Series(plus_dm, index=df.index), n) / atr
    minus_di = 100 * rma(pd.Series(minus_dm, index=df.index), n) / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = rma(dx, n)
    return pd.DataFrame({"ADX": adx, "PlusDI": plus_di, "MinusDI": minus_di})
