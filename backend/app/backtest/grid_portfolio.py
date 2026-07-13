"""Varlık-seçimli grid portföy backtest'i (seçim katmanı + grid = sistem).

Her yeniden-dengeleme noktasında:
  1. Geçmiş `lookback` penceresiyle TÜM evreni skorla (regime.py) → grid-uygun (ranger)
     varlıkları filtrele, en choppy `top_n` tanesini seç. (Yalnız geçmiş veri → look-ahead yok.)
  2. Sermayeyi seçilenlere eşit böl; her birinde grid'i İLERİ `hold` penceresinde koştur
     (warmup=lookback → MA'lar tanımlı). Hiç uygun yoksa → nakitte bekle.
  3. Dönem sonu equity'leri topla → bir sonraki döneme taşı (bileşik + rebalance).

Çıktı: birleşik portföy equity + dönem dönem seçimler + eşit-ağırlık Al&Tut karşılaştırması.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.backtest import grid, regime
from app.backtest.metrics import equity_metrics
from app.data import okx_provider

UNIVERSE = [
    "BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "XRP-USDT-SWAP", "DOGE-USDT-SWAP",
    "ADA-USDT-SWAP", "AVAX-USDT-SWAP", "LINK-USDT-SWAP", "DOT-USDT-SWAP", "LTC-USDT-SWAP",
    "BCH-USDT-SWAP", "ATOM-USDT-SWAP", "NEAR-USDT-SWAP", "APT-USDT-SWAP", "TRX-USDT-SWAP",
]


def run(
    universe: list[str] | None = None,
    interval: str = "15m",
    bars: int = 12000,
    lookback: int = 2000,
    hold: int = 672,
    top_n: int = 3,
    initial_cash: float = 10_000.0,
    fee_bps: float = 3.0,
    grid_params: dict | None = None,
    er_max: float = 0.35,
    adx_max: float = 25.0,
    fetch=None,
) -> dict:
    """fetch: sembol -> OHLCV DataFrame. None ise OKX (bars ile). BIST için Yahoo fetch geç."""
    universe = universe or UNIVERSE
    if fetch is None:
        def fetch(sym):
            return okx_provider.get_ohlcv(sym, interval, bars=bars)
    gp = grid_params or dict(buy_step_pct=0.5, sell_step_pct=0.7, max_tiers=8,
                             regime_ma=1440, exit_regime_break=True, heyecan_ma=240)

    # veri çek + ortak zaman eksenine hizala
    data = {}
    for sym in universe:
        df = fetch(sym)
        if df is not None and not df.empty and len(df) > lookback + hold:
            data[sym] = df
    if len(data) < top_n:
        raise ValueError("Yeterli veri/sembol yok.")
    common = None
    for df in data.values():
        common = df.index if common is None else common.intersection(df.index)
    common = common.sort_values()
    data = {s: df.reindex(common) for s, df in data.items()}
    n = len(common)

    cash = initial_cash
    seg_eq: list[pd.Series] = []
    periods: list[dict] = []
    start = lookback

    while start + hold <= n:
        t = start
        # 1) skorla + seç (geçmiş pencere)
        scored = []
        for sym, df in data.items():
            win = df.iloc[t - lookback:t]
            if win["close"].isna().any():
                continue
            s = regime.score(win)
            if regime.is_grid_friendly(s, er_max=er_max, adx_max=adx_max):
                scored.append((sym, s))
        scored.sort(key=lambda x: regime.rank_key(x[1]))
        picks = [s for s, _ in scored[:top_n]]

        # 2) seçilenlerde ileri pencerede grid koştur (eşit sermaye)
        fwd_idx = common[t:t + hold]
        if picks:
            per = cash / len(picks)
            end_vals = []
            seg_frames = []
            for sym in picks:
                sub = data[sym].iloc[t - lookback:t + hold]
                r = grid.simulate(sub, symbol=sym, interval=interval, initial_cash=per,
                                  lot_quote=per / gp["max_tiers"], fee_bps=fee_bps,
                                  warmup=lookback, light=False, **gp)
                ev = [pt["value"] for pt in r["equity"]]
                seg_frames.append(pd.Series(ev, index=fwd_idx[:len(ev)]))
                end_vals.append(ev[-1] if ev else per)
            # portföy equity = seçilenlerin toplamı (hizalı)
            port = pd.concat(seg_frames, axis=1).sum(axis=1)
            seg_eq.append(port)
            new_cash = float(sum(end_vals))
        else:
            # nakitte bekle
            seg_eq.append(pd.Series([cash] * len(fwd_idx), index=fwd_idx))
            new_cash = cash

        periods.append({
            "date": common[t].strftime("%Y-%m-%d %H:%M"),
            "picks": picks, "n_eligible": len(scored),
            "cash_start": round(cash, 2), "cash_end": round(new_cash, 2),
            "ret_pct": round((new_cash / cash - 1) * 100, 2) if cash else 0.0,
        })
        cash = new_cash
        start += hold

    # birleşik equity zinciri
    combined = pd.concat(seg_eq) if seg_eq else pd.Series(dtype=float)
    combined = combined[~combined.index.duplicated(keep="first")]
    m = equity_metrics(combined, interval) if len(combined) > 1 else {}

    # eşit-ağırlık Al&Tut (test bölgesi)
    test_idx = common[lookback:]
    bh_rets = []
    for sym, df in data.items():
        c = df["close"].reindex(test_idx).dropna()
        if len(c) > 1:
            bh_rets.append(c.iloc[-1] / c.iloc[0] - 1)
    bh = float(np.mean(bh_rets)) * 100 if bh_rets else 0.0

    prof = sum(1 for p in periods if p["ret_pct"] > 0)
    return {
        "interval": interval, "universe": len(data), "top_n": top_n,
        "lookback": lookback, "hold": hold,
        "summary": {
            "periods": len(periods),
            "profitable_periods": prof,
            "profitable_pct": round(prof / len(periods) * 100, 1) if periods else 0,
            "total_return": m.get("total_return", 0),
            "sharpe": m.get("sharpe", 0),
            "max_drawdown": m.get("max_drawdown", 0),
            "cagr": m.get("cagr", 0),
            "final_equity": round(cash, 2),
            "equalweight_buyhold": round(bh, 2),
        },
        "periods": periods,
        "equity": [{"time": int(t.timestamp()), "value": round(float(v), 2)}
                   for t, v in combined.items()],
    }
