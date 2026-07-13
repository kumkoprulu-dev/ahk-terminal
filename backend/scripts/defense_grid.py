"""Bear defansı testi: ham grid vs +regime_exit vs +stop_dd, 3 rejim döneminde."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backtest import grid  # noqa: E402
from app.data import okx_provider  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

BASE = dict(initial_cash=10_000, lot_quote=500, buy_step_pct=3.0, sell_step_pct=3.0,
            max_tiers=8, fee_bps=8, regime_ma=200)
VARIANTS = [
    ("ham grid",          dict()),
    ("+regime_exit",      dict(exit_regime_break=True)),
    ("+stop_dd %25",      dict(stop_dd_pct=25.0)),
    ("+ikisi",            dict(exit_regime_break=True, stop_dd_pct=30.0)),
]


def main():
    rec = Recorder("defense_grid", "grid_compare", label="bear defansı (regime_exit/stop_dd)")
    for sym in ["SOL-USDT-SWAP", "BTC-USDT-SWAP"]:
        df = okx_provider.get_ohlcv(sym, "4h", bars=6000)
        n = len(df); third = n // 3
        segs = [("YÜKSELİŞ", df.iloc[:third]), ("YÜKSELİŞ2", df.iloc[third:2*third]),
                ("DÜŞÜŞ", df.iloc[2*third:])]
        print(f"\n=== {sym} 4h ===")
        for rejim, seg in segs:
            bh = round((seg['close'].iloc[-1]/seg['close'].iloc[0]-1)*100, 2)
            print(f"  [{rejim}  Al&Tut {bh}%]")
            for name, over in VARIANTS:
                r = grid.simulate(seg, symbol=sym, interval="4h", light=True, **{**BASE, **over})
                m = r["metrics"]
                print(f"     {name:<16} ret={m['total_return']:>7}%  DD={m['max_drawdown']:>7}%  "
                      f"işlem={m['num_trades']:>3}  açık={m['open_tiers_end']}({m['open_unrealized_pct']}%)")
                rec.add(dict(m, buy_hold=bh, regime=rejim), symbol=sym, interval="4h",
                        name=f"{sym} · {rejim} · {name}")
    rec.save()


if __name__ == "__main__":
    main()
