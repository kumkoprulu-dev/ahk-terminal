"""Yönlü/trend stratejisi testi — mevcut DSL motoru (engine.simulate) ile.
Hem BIST (Yahoo) hem kripto (OKX). Trend-takip Al&Tut'u ve grid'i geçiyor mu?

Kullanım:  trend_basket.py bist    |    trend_basket.py crypto
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from app.backtest import engine  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

RULES = [
    ("EMA20>50 cross",     "EMA(20) > EMA(50)",                 "EMA(20) < EMA(50)"),
    ("EMA50>200 + Close",  "EMA(50) > EMA(200) AND Close > EMA(50)", "Close < EMA(50)"),
    ("Close>SMA200",       "Close > SMA(200)",                  "Close < SMA(200)"),
]


def get_data(market):
    if market == "bist":
        from app.data import service
        from app.data.universe import _BIST30
        syms = _BIST30
        def fetch(s):
            try: return service.get_ohlcv(s + ".IS", "1d", "3y")
            except Exception: return None
        return syms, fetch, "1d"
    else:
        from app.data import okx_provider
        from app.backtest.grid_portfolio import UNIVERSE
        syms = UNIVERSE
        def fetch(s):
            try: return okx_provider.get_ohlcv(s, "1d", bars=1000)
            except Exception: return None
        return syms, fetch, "1d"


def main():
    market = sys.argv[1] if len(sys.argv) > 1 else "bist"
    syms, fetch, itv = get_data(market)
    print(f"{market.upper()} trend backtest ({itv}) — {len(syms)} varlık çekiliyor...")
    data = {}
    for s in syms:
        df = fetch(s)
        if df is not None and len(df) > 220:
            data[s] = df
    print(f"  {len(data)} varlık kullanılıyor\n")

    rec = Recorder("trend_basket", "trend", label=f"{market.upper()} trend kuralları ({len(data)} varlık)")
    for name, entry, exit_ in RULES:
        rets, dds, bhs, trs = [], [], [], []
        for s, df in data.items():
            try:
                r = engine.simulate(df, symbol=s, entry_rule=entry, exit_rule=exit_,
                                    interval=itv, fee_bps=8, direction="long", light=True)
                m = r["metrics"]
                rets.append(m.get("total_return", 0))
                dds.append(m.get("max_drawdown", 0))
                bhs.append(m.get("buy_hold_return", 0))
                trs.append(m.get("num_trades", 0))
            except Exception:
                pass
        if rets:
            print(f"  {name:<20} ort.getiri={np.mean(rets):>7.1f}%  ort.DD={np.mean(dds):>6.1f}%  "
                  f"ort.işlem={np.mean(trs):>4.1f}   [Al&Tut ort={np.mean(bhs):>7.1f}%]")
            rec.add({"total_return": round(float(np.mean(rets)), 2),
                     "max_drawdown": round(float(np.mean(dds)), 2),
                     "num_trades": round(float(np.mean(trs)), 1),
                     "buy_hold": round(float(np.mean(bhs)), 2)},
                    interval=itv, name=f"{market.upper()} · {name}")
    rec.save()


if __name__ == "__main__":
    main()
