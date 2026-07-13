"""Bağımsız 'edge' hesaplayıcıları — hem backtest hem canlı runner için ortak çekirdek.

İçerik: Combo1/Combo2 DSL kuralları, DSL pozisyon/getiri, eşit-ağırlık portföy getirisi,
cross-sectional momentum getirisi, metrik. Tek yerde → backtest ile canlı arasında parite.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.scanner.dsl import evaluate

# OOS-doğrulanan kombolar
COMBO1_ENTRY = "Close > SMA(50) AND FisherTransform(9).Fisher > FisherTransform(9).Trigger AND Close > VWAP"
COMBO1_EXIT = "Close < SMA(50) OR FisherTransform(9).Fisher < FisherTransform(9).Trigger OR Close < VWAP"
COMBO2_ENTRY = "FisherTransform(9).Fisher > FisherTransform(9).Trigger AND ForceIndex(13) > 0 AND AwesomeOsc(5,34) > 0"
COMBO2_EXIT = "FisherTransform(9).Fisher < FisherTransform(9).Trigger OR ForceIndex(13) < 0 OR AwesomeOsc(5,34) < 0"
# Combo3 — DaviddTech/NNFX yuva şablonu araması + WF'in tek kazananı (nnfx_search run #8 →
# nnfx_wf_optimize run #9: 5 kombodan WF'te İYİLEŞEN + kârlı-fold %52 olan TEK kombo).
# Sabit param (DEMA20/Fisher9/Force13) — optimize edilmedi (WF optimizasyonu diğerlerini bozdu).
COMBO3_ENTRY = "Close > DEMA(20) AND FisherTransform(9).Fisher > FisherTransform(9).Trigger AND ForceIndex(13) > 0"
COMBO3_EXIT = "Close < DEMA(20) OR FisherTransform(9).Fisher < FisherTransform(9).Trigger OR ForceIndex(13) < 0"
FEE = 10 / 1e4


def combo_position(df: pd.DataFrame, entry: str, exit_: str) -> np.ndarray:
    """DSL giriş/çıkış → 0/1 pozisyon dizisi (durum makinesi; engine.simulate ile aynı)."""
    ent = evaluate(df, entry).fillna(False).to_numpy()
    ex = evaluate(df, exit_).fillna(False).to_numpy()
    n = len(df)
    pos = np.zeros(n)
    inp = False
    for i in range(n):
        if not inp and ent[i]:
            inp = True
        elif inp and ex[i]:
            inp = False
        pos[i] = 1.0 if inp else 0.0
    return pos


def dsl_returns(df: pd.DataFrame, entry: str, exit_: str, fee: float = FEE) -> pd.Series:
    """Long-only kombo günlük net getiri (poz[t-1]×r[t] − değişim komisyonu)."""
    pos = combo_position(df, entry, exit_)
    close = df["close"].to_numpy(float)
    n = len(df)
    r = np.zeros(n)
    r[1:] = close[1:] / close[:-1] - 1
    turn = np.zeros(n)
    turn[1:] = np.abs(np.diff(pos))
    net = np.concatenate([[0.0], pos[:-1] * r[1:]]) - turn * fee
    return pd.Series(net, index=df.index)


def combo_portfolio_returns(dfs: dict[str, pd.DataFrame], entry: str, exit_: str) -> pd.Series:
    """Eşit-ağırlık kombo portföyü günlük getirisi (varlıklar arası ortalama)."""
    cols = {k: dsl_returns(df, entry, exit_) for k, df in dfs.items()}
    return pd.DataFrame(cols).sort_index().mean(axis=1)


def xsec_returns(prices: pd.DataFrame, lookback: int = 60, k: int = 3,
                 rebal: int = 5, fee: float = FEE) -> pd.Series:
    """Cross-sectional momentum: top-k long / bottom-k short, dolar-nötr, periyodik rebalans."""
    rets = prices.pct_change()
    mom = prices.pct_change(lookback)
    dates = prices.index
    W = pd.DataFrame(0.0, index=dates, columns=prices.columns)
    cur = pd.Series(0.0, index=prices.columns)
    for i in range(len(dates)):
        if i < lookback + 1:
            continue
        if i % rebal == 0:
            m = mom.iloc[i].dropna()
            if len(m) >= 2 * k:
                rank = m.sort_values()
                cur = pd.Series(0.0, index=prices.columns)
                cur[rank.index[-k:]] = 1.0 / k
                cur[rank.index[:k]] = -1.0 / k
        W.iloc[i] = cur.values
    gross = (W.shift(1) * rets).sum(axis=1)
    turn = W.diff().abs().sum(axis=1)
    return (gross - turn * fee).fillna(0.0)


def xsec_blend_returns(prices: pd.DataFrame, lookbacks=(20, 30, 60, 90), k: int = 3,
                       rebal: int = 5, fee: float = FEE) -> pd.Series:
    """Sağlam cross-sectional: her rebalansta lookback'lerin SIRALAMALARINI ortala →
    kompozit sıra ile top-k long / bottom-k short. Tek-lookback kırılganlığını giderir."""
    rets = prices.pct_change()
    moms = {lb: prices.pct_change(lb) for lb in lookbacks}
    dates = prices.index
    W = pd.DataFrame(0.0, index=dates, columns=prices.columns)
    cur = pd.Series(0.0, index=prices.columns)
    max_lb = max(lookbacks)
    for i in range(len(dates)):
        if i < max_lb + 1:
            continue
        if i % rebal == 0:
            # her lookback için sıra (yüksek momentum = yüksek sıra), ortalama al
            ranks = []
            for lb in lookbacks:
                m = moms[lb].iloc[i].dropna()
                if len(m) >= 2 * k:
                    ranks.append(m.rank())
            if ranks:
                comp = pd.concat(ranks, axis=1).mean(axis=1).dropna()
                if len(comp) >= 2 * k:
                    order = comp.sort_values()
                    cur = pd.Series(0.0, index=prices.columns)
                    cur[order.index[-k:]] = 1.0 / k
                    cur[order.index[:k]] = -1.0 / k
        W.iloc[i] = cur.values
    gross = (W.shift(1) * rets).sum(axis=1)
    turn = W.diff().abs().sum(axis=1)
    return (gross - turn * fee).fillna(0.0)


def stats(ret: pd.Series, frac: float = 0.0) -> tuple[float, float, float]:
    """(toplam getiri%, yıllık Sharpe, MaxDD%) — frac>0 ise son (1-frac) dilim (OOS)."""
    ret = ret.dropna()
    ret = ret.iloc[int(len(ret) * frac):]
    if len(ret) < 30:
        return 0.0, 0.0, 0.0
    eq = (1 + ret).cumprod()
    total = (eq.iloc[-1] - 1) * 100
    shp = ret.mean() / ret.std() * np.sqrt(365) if ret.std() > 0 else 0.0
    dd = ((eq - eq.cummax()) / eq.cummax()).min() * 100
    return total, shp, dd
