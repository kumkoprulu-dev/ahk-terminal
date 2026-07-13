"""Grid'in rejim bağımlılığı: uzun geçmişi 3 döneme bölüp ham grid'i her birinde koştur.
Amaç: 'yatay/yükselişte kâr, sürekli düşüşte kanama' hipotezini veriyle göster."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backtest import grid  # noqa: E402
from app.data import okx_provider  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

BASE = dict(initial_cash=10_000, lot_quote=500, buy_step_pct=3.0, sell_step_pct=3.0,
            max_tiers=8, fee_bps=8)


def main():
    rec = Recorder("regime_grid", "grid_compare", label="rejim bağımlılığı (3 dönem)")
    for sym in ["SOL-USDT-SWAP", "BTC-USDT-SWAP"]:
        df = okx_provider.get_ohlcv(sym, "4h", bars=6000)
        n = len(df)
        third = n // 3
        print(f"\n=== {sym} 4h — toplam {n} bar, 3 döneme bölünmüş ===")
        for label, seg in [("1. dönem (en eski)", df.iloc[:third]),
                           ("2. dönem (orta)",    df.iloc[third:2 * third]),
                           ("3. dönem (en yeni)", df.iloc[2 * third:])]:
            bh = round((seg['close'].iloc[-1] / seg['close'].iloc[0] - 1) * 100, 2)
            r = grid.simulate(seg, symbol=sym, interval="4h", light=True, **BASE)
            m = r["metrics"]
            rejim = "YÜKSELİŞ" if bh > 15 else ("DÜŞÜŞ" if bh < -15 else "YATAY")
            print(f"  {label:<20} [{rejim:<8} Al&Tut {bh:>7}%]  "
                  f"grid_ret={m['total_return']:>7}%  DD={m['max_drawdown']:>7}%  "
                  f"işlem={m['num_trades']:>3}  açık={m['open_tiers_end']}({m['open_unrealized_pct']}%)")
            rec.add(dict(m, buy_hold=bh, regime=rejim), symbol=sym, interval="4h",
                    name=f"{sym} · {label} ({rejim})")
    rec.save()


if __name__ == "__main__":
    main()
