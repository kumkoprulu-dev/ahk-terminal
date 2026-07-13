"""Grid parametre/rejim karşılaştırması — OKX verisinde birkaç config yan yana."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backtest import grid  # noqa: E402
from app.data import okx_provider  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

CONFIGS = [
    ("Ham grid",              dict(regime_ma=0,  ma_period=0)),
    ("+ Rejim filtresi(200)", dict(regime_ma=200, ma_period=0)),
    ("+ Rejim + MA(50)",      dict(regime_ma=200, ma_period=50)),
    ("Sık grid %2/%2",        dict(regime_ma=200, buy_step_pct=2.0, sell_step_pct=2.0)),
    ("Geniş %5/%4",           dict(regime_ma=200, buy_step_pct=5.0, sell_step_pct=4.0)),
]
BASE = dict(initial_cash=10_000, lot_quote=500, buy_step_pct=3.0, sell_step_pct=3.0,
            max_tiers=8, fee_bps=8)


def line(name, m):
    return (f"  {name:<22} ret={m.get('total_return'):>7}%  "
            f"DD={m.get('max_drawdown'):>7}%  Sharpe={m.get('sharpe'):>5}  "
            f"işlem={m.get('num_trades'):>3}  açık={m.get('open_tiers_end')}"
            f"({m.get('open_unrealized_pct')}%)  eq={m.get('final_equity')}")


def main():
    rec = Recorder("compare_grid", "grid_compare", label="config/rejim karşılaştırması 4h")
    for sym in ["SOL-USDT-SWAP", "BTC-USDT-SWAP", "ETH-USDT-SWAP"]:
        df = okx_provider.get_ohlcv(sym, "4h", bars=3000)
        bh = round((df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100, 2)
        print(f"\n=== {sym} 4h  ({len(df)} bar, Al&Tut {bh}%) ===")
        for name, over in CONFIGS:
            p = {**BASE, **over}
            r = grid.simulate(df, symbol=sym, interval="4h", light=True, **p)
            print(line(name, r["metrics"]))
            rec.add(dict(r["metrics"], buy_hold=bh), symbol=sym, interval="4h",
                    name=f"{sym} · {name}")
    rec.save()


if __name__ == "__main__":
    main()
