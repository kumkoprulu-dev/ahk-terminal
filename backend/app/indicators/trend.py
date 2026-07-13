"""Trend göstergeleri."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.indicators._helpers import ema, linreg_endpoint, rma, smma, sma, src, true_range, wma
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


@indicator("TrendScore", "Trend", [_LEN(10, 2, 400)], ["TrendScore"],
           description="İdeal TrendScore: güncel kapanışın son N kapanışa göre konumu (Kendall-tarzı), ±N")
def trendscore_ind(df, length=10):
    """İdeal `Sistem.TrendScore(V, N)` yeniden yapımı.

    İdeal built-in olduğundan kaynağı script dosyalarında yok; formül davranıştan
    çıkarıldı. Kanıt: strateji eşiği HEP periyodun yarısı (TrendscoreOpt: a=periyot/2;
    ITWAsil: periyot 124 → eşik 62). Eşiğin periyotla ölçeklenmesi skorun N terimli
    işaretli bir toplam olduğunu, ama ardışık-bar yön toplamının (Σ sign(Δclose))
    trendde bile ~±0.1·N'de kalıp 62 eşiğini ASLA tetiklememesi bunun yanlış olduğunu
    gösterdi. Doğru yapı Kendall-tarzı konum toplamı:

        TrendScore[i] = Σ_{k=1..N} sign(close[i] − close[i−k])

    Güncel kapanış son N kapanışın kaçından yüksekse o kadar +1 (düşükse −1). Güçlü
    yükselişte fiyat geçmişin çoğunu geçer → skor +N'e yaklaşır; |skor| > N/2 ⇒ güncel
    kapanış son N barın >%75'inin üstünde (kalıcı trend). Aralık [−N, +N].
    """
    n = int(length)
    c = df["close"]
    score = np.zeros(len(c))
    for k in range(1, n + 1):
        score += np.sign((c - c.shift(k)).fillna(0.0).to_numpy())
    out = pd.Series(score, index=df.index)
    out.iloc[:n] = np.nan  # ilk N bar tam pencere yok
    return out.to_frame("TrendScore")


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


# ============================ FAZ 0 — yeni trend/overlay göstergeleri ============================

@indicator("MOST", "Trend",
           [_SRC, _LEN(9, 1, 200), Param("percent", 2, 0.1, 20, 0.1, "float")],
           ["MOST", "MA", "Direction"], overlay=True,
           description="MOST (Anıl Özekşi — MA + yüzde takip stopu; yön flip sinyali)")
def most_ind(df, source="close", length=9, percent=2.0):
    ma = ema(src(df, source), int(length))
    m = ma.to_numpy()
    n = len(m)
    most = np.full(n, np.nan)
    direction = np.zeros(n)
    pf = float(percent) / 100.0
    stop = m[0] if n else 0.0
    d = 1
    for i in range(n):
        if np.isnan(m[i]):
            continue
        long_stop = m[i] * (1 - pf)
        short_stop = m[i] * (1 + pf)
        if d == 1:
            stop = max(long_stop, stop)
            if m[i] < stop:
                d = -1
                stop = short_stop
        else:
            stop = min(short_stop, stop)
            if m[i] > stop:
                d = 1
                stop = long_stop
        most[i] = stop
        direction[i] = d
    return pd.DataFrame({"MOST": most, "MA": m, "Direction": direction}, index=df.index)


@indicator("VWMA", "Trend", [_LEN(20, 1, 500)], ["VWMA"], overlay=True,
           description="Hacim Ağırlıklı Hareketli Ortalama")
def vwma_ind(df, length=20):
    n = int(length)
    pv = (df["close"] * df["volume"]).rolling(n).sum()
    v = df["volume"].rolling(n).sum().replace(0, np.nan)
    return (pv / v).to_frame("VWMA")


@indicator("KAMA", "Trend",
           [_SRC, _LEN(10, 1, 200), Param("fast", 2, 1, 30), Param("slow", 30, 2, 200)],
           ["KAMA"], overlay=True, description="Kaufman Adaptif Hareketli Ortalama")
def kama_ind(df, source="close", length=10, fast=2, slow=30):
    s = src(df, source)
    n = int(length)
    change = (s - s.shift(n)).abs()
    vol = s.diff().abs().rolling(n).sum()
    er = (change / vol.replace(0, np.nan)).fillna(0.0)
    fast_sc = 2.0 / (int(fast) + 1)
    slow_sc = 2.0 / (int(slow) + 1)
    sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
    vals = s.to_numpy(dtype=float)
    scv = sc.to_numpy(dtype=float)
    out = np.full(len(s), np.nan)
    prev = vals[0]
    for i in range(len(s)):
        if np.isnan(vals[i]):
            continue
        prev = prev + scv[i] * (vals[i] - prev)
        out[i] = prev
    return pd.Series(out, index=df.index).to_frame("KAMA")


@indicator("ZLEMA", "Trend", [_SRC, _LEN(20, 1, 500)], ["ZLEMA"], overlay=True,
           description="Sıfır Gecikmeli EMA (lag düzeltmeli)")
def zlema_ind(df, source="close", length=20):
    s = src(df, source)
    lag = int((int(length) - 1) / 2)
    dsl = s + (s - s.shift(lag))
    return ema(dsl, int(length)).to_frame("ZLEMA")


@indicator("Vortex", "Trend", [_LEN(14, 2, 200)], ["VIPlus", "VIMinus"],
           description="Vortex göstergesi (VI+ / VI−)")
def vortex_ind(df, length=14):
    n = int(length)
    vm_plus = (df["high"] - df["low"].shift(1)).abs().rolling(n).sum()
    vm_minus = (df["low"] - df["high"].shift(1)).abs().rolling(n).sum()
    tr_sum = true_range(df).rolling(n).sum().replace(0, np.nan)
    return pd.DataFrame({"VIPlus": vm_plus / tr_sum, "VIMinus": vm_minus / tr_sum})


@indicator("LSMA", "Trend", [_SRC, _LEN(25, 2, 300)], ["LSMA"], overlay=True,
           description="En Küçük Kareler MA (doğrusal regresyon çizgisi sonu)")
def lsma_ind(df, source="close", length=25):
    return linreg_endpoint(src(df, source), int(length)).to_frame("LSMA")


@indicator("Alligator", "Trend",
           [Param("jaw", 13, 1, 100), Param("teeth", 8, 1, 100), Param("lips", 5, 1, 100)],
           ["Jaw", "Teeth", "Lips"], overlay=True,
           description="Williams Alligator (SMMA çene/diş/dudak)")
def alligator_ind(df, jaw=13, teeth=8, lips=5):
    hl2 = (df["high"] + df["low"]) / 2
    return pd.DataFrame({
        "Jaw": smma(hl2, int(jaw)).shift(8),
        "Teeth": smma(hl2, int(teeth)).shift(5),
        "Lips": smma(hl2, int(lips)).shift(3),
    })
