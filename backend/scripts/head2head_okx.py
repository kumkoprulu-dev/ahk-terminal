"""Kafa kafaya OKX karşılaştırması: Combo vs Trend vs Grid vs Al&Tut (aynı OOS penceresi).

Kullanıcı sorusu: combo backtest sonucu trend ve grid'i geçiyor mu?
Aynı kripto evreni (OKX 15 varlık, günlük), her sembolde ilk %60 ISINMA / son %40 OOS.
Tüm stratejiler yalnız OOS'ta işlem açar (warmup=split), metrikler OOS bölgesinden.
  • Al&Tut     : referans (OOS buy&hold)
  • Grid       : Sibirya kademe/paçal + bear defansı (exit_regime_break 200-MA)
  • Trend      : EMA(20)>EMA(50) cross (önceki OOS edge)
  • Combo-1    : SMA+Fisher+VWAP (trend+momentum+hacim)
  • Combo-2    : Fisher+Force+Awesome (OOS şampiyon)
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from app.backtest import engine, grid  # noqa: E402
from app.backtest.grid_portfolio import UNIVERSE  # noqa: E402
from app.data import okx_provider  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

_REC = Recorder("head2head_okx", "head2head", label="Combo/Trend/Grid/Al&Tut kafa kafaya (OKX)")

TREND_E, TREND_X = "EMA(20) > EMA(50)", "EMA(20) < EMA(50)"
C1_E = "Close > SMA(50) AND FisherTransform(9).Fisher > FisherTransform(9).Trigger AND Close > VWAP"
C1_X = "Close < SMA(50) OR FisherTransform(9).Fisher < FisherTransform(9).Trigger OR Close < VWAP"
C2_E = "FisherTransform(9).Fisher > FisherTransform(9).Trigger AND ForceIndex(13) > 0 AND AwesomeOsc(5,34) > 0"
C2_X = "FisherTransform(9).Fisher < FisherTransform(9).Trigger OR ForceIndex(13) < 0 OR AwesomeOsc(5,34) < 0"


def dsl_oos(df, e, x, split):
    r = engine.simulate(df, entry_rule=e, exit_rule=x, interval="1d",
                        fee_bps=10, direction="long", warmup=split, light=True)
    return r["metrics"]


def grid_oos(df, split):
    r = grid.simulate(df, interval="1d", buy_step_pct=4.0, sell_step_pct=4.0, max_tiers=8,
                      lot_quote=500.0, fee_bps=8.0, regime_ma=200, exit_regime_break=True,
                      warmup=split, light=True)
    return r["metrics"]


def eval_window(df, sl_start, sl_end, warmup):
    """df[sl_start:sl_end] penceresinde, ilk `warmup` bar ısınma; tüm stratejiler OOS metrik."""
    d = df.iloc[sl_start:sl_end]
    t = dsl_oos(d, TREND_E, TREND_X, warmup)
    c1 = dsl_oos(d, C1_E, C1_X, warmup)
    c2 = dsl_oos(d, C2_E, C2_X, warmup)
    g = grid_oos(d, warmup)
    return {
        "Al&Tut": (t["buy_hold_return"], 0, 0),
        "Grid": (g["total_return"], g["sharpe"], g["max_drawdown"]),
        "Trend(EMA)": (t["total_return"], t["sharpe"], t["max_drawdown"]),
        "Combo1 SMA+Fis+VWAP": (c1["total_return"], c1["sharpe"], c1["max_drawdown"]),
        "Combo2 Fis+For+Awe": (c2["total_return"], c2["sharpe"], c2["max_drawdown"]),
    }


def run_window(title, window_fn):
    keys = ["Al&Tut", "Grid", "Trend(EMA)", "Combo1 SMA+Fis+VWAP", "Combo2 Fis+For+Awe"]
    agg = {k: [] for k in keys}
    n_ok = 0
    for sym in UNIVERSE:
        df = okx_provider.get_ohlcv(sym, "1d", bars=1000)
        if df is None or len(df) < 400:
            continue
        try:
            res = window_fn(df)
        except Exception as ex:
            print(f"  {sym}: HATA {str(ex)[:40]}"); continue
        n_ok += 1
        for k in keys:
            agg[k].append(res[k])
    bh_list = [x[0] for x in agg["Al&Tut"]]
    print(f"\n  === {title} (OOS, {n_ok} varlık) ===")
    print(f"  {'strateji':<22}{'ort.getiri%':>12}{'ort.Sharpe':>12}{'ort.MaxDD%':>12}{'>Al&Tut':>9}")
    for k in keys:
        rets = [x[0] for x in agg[k]]
        shps = [x[1] for x in agg[k]]
        dds = [x[2] for x in agg[k]]
        beat = sum(1 for a, b in zip(rets, bh_list) if a > b)
        print(f"  {k:<22}{np.mean(rets):>12.1f}{np.mean(shps):>12.3f}"
              f"{np.mean(dds):>12.1f}{f'{beat}/{n_ok}':>9}")
        _REC.add({"total_return": round(float(np.mean(rets)), 2),
                  "sharpe": round(float(np.mean(shps)), 3),
                  "max_drawdown": round(float(np.mean(dds)), 2),
                  "beat_buyhold": f"{beat}/{n_ok}", "window": title},
                 interval="1d", name=f"{title} · {k}")


def main():
    print("Kafa kafaya OKX (15 varlık, 1d) — 3 dönem: erken / geç(ayı) / tüm\n")
    # erken yarı: df[:60%], ilk 150 ısınma → test [150 : 60%]
    run_window("ERKEN YARI", lambda df: eval_window(df, 0, int(len(df) * 0.6), 150))
    # geç %40: df tümü, warmup=60% → test son %40 (bilinen ayı)
    run_window("GEÇ %40 (ayı)", lambda df: eval_window(df, 0, len(df), int(len(df) * 0.6)))
    # tüm dönem: df tümü, ilk 150 ısınma
    run_window("TÜM DÖNEM", lambda df: eval_window(df, 0, len(df), 150))
    _REC.save()


if __name__ == "__main__":
    main()
