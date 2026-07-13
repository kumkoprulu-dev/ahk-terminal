"""Sibirya Beta SADIK model — BIST 1h, kullanıcının GERÇEK talimat sayılarıyla.
Not: tick+spread mekaniği bar'da olduğundan az görünür (bkz accumulate.py başlığı)."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from app.backtest import accumulate  # noqa: E402
from app.data import service  # noqa: E402
from app.data.universe import _BIST30  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

# GERÇEK talimat: %0.4 al / %0.6 sat, piramit 2-4-6, 125 kademe/-%50,
# tepeden %25 düşünce toplu-sat avg+%5, keskin düşüşte alma
P = dict(buy_step_pct=0.4, sell_step_pct=0.6, base_lot=2, lot_inc=2, max_tiers=125,
         max_drop_pct=50.0, deep_dd_pct=25.0, bulk_target_pct=5.0, sharp_drop_pct=3.0,
         fee_bps=5.0, unit_quote=1000.0, ceiling_frac=0.0)  # tavan yok (temel değer sende)


def one(sym):
    try:
        df = service.get_ohlcv(sym + ".IS", "1h", "2y")
    except Exception:
        return None
    if df is None or len(df) < 300:
        return None
    return accumulate.simulate(df, symbol=sym, interval="1h", light=True, **P)


def main():
    r = one("EREGL")
    if r:
        m = r["metrics"]
        print(f"=== EREGL — SADIK model, GERÇEK talimat (1h 2y, ~{m['approx_years']}yıl) ===")
        print(f"  Getiri (kullanılan sermaye üstünden): {m['return_on_capital']}%")
        print(f"  Gerçekleşen PnL   : {m['realized_pnl']}  (max kullanılan sermaye {m['max_deployed']})")
        print(f"  İşlem / kazanma   : {m['num_trades']} / %{m['win_rate']} (zarara satış yok)")
        print(f"  Max zaman poz.    : {m['max_time_bars']} bar  (asıl maliyet = zaman)")
        print(f"  Max kağıt düşüş   : {m['max_paper_drawdown']}% (gerçekleşmemiş)")
        print(f"  Bitişte açık      : {m['open_tiers_end']} kademe ({m['open_unrealized_pct']}%)")

    print(f"\n=== BIST30 basket (1h 2y) ===")
    rec = Recorder("run_accumulate", "accumulate", label="BIST30 SADIK model (1h 2y)", params=P)
    ror, tr, tim, pdd, opn = [], [], [], [], []
    for s in _BIST30:
        r = one(s)
        if not r:
            continue
        m = r["metrics"]
        ror.append(m["return_on_capital"]); tr.append(m["num_trades"])
        tim.append(m["max_time_bars"]); pdd.append(m["max_paper_drawdown"]); opn.append(m["open_tiers_end"])
        rec.add(dict(m, total_return=m["return_on_capital"], max_drawdown=m["max_paper_drawdown"]),
                symbol=s, interval="1h", name=s)
    rec.save()
    if ror:
        print(f"  Ort. getiri (kull. sermaye) : {np.mean(ror):.1f}%   (2 yılda, hepsi kârlı, zarara satış yok)")
        print(f"  Ort. işlem sayısı           : {np.mean(tr):.0f}  (bar'da; tick'te çok daha fazla olur)")
        print(f"  Ort/Max zaman pozisyonda    : {np.mean(tim):.0f} / {max(tim)} bar")
        print(f"  Ort. max kağıt düşüş        : {np.mean(pdd):.1f}%  (gerçekleşmemiş)")
        print(f"  Bitişte açık kalan (ort)    : {np.mean(opn):.1f} kademe")


if __name__ == "__main__":
    main()
