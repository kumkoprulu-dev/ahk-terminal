"""Gün içi grid testi: ince zaman dilimi + dar adım → çok sayıda alım-satım turu.
Kullanıcı sezgisi: saatlik/dakikalık içinde grid defalarca alıp satar."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backtest import grid  # noqa: E402
from app.data import okx_provider  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

# (interval, bars) — ince dilimde daha çok bar
TFS = [("1h", 8000), ("15m", 12000), ("5m", 12000)]
# dar grid adımları (gün içi salınım): (buy_step, sell_step)
STEPS = [(0.5, 0.5), (1.0, 0.8), (1.5, 1.2)]
FEES = [2, 5]  # maker ~2bps, taker ~5bps — ücret duyarlılığı


def main():
    sym = sys.argv[1] if len(sys.argv) > 1 else "SOL-USDT-SWAP"
    rec = Recorder("intraday_grid", "grid_compare", label=f"{sym} gün-içi adım×ücret taraması")
    for itv, bars in TFS:
        df = okx_provider.get_ohlcv(sym, itv, bars=bars)
        if df.empty:
            print(f"{itv}: veri yok"); continue
        bh = round((df['close'].iloc[-1]/df['close'].iloc[0]-1)*100, 2)
        span = df.index[-1] - df.index[0]
        print(f"\n=== {sym} {itv}  ({len(df)} bar, {span.days}g, Al&Tut {bh}%) ===")
        print(f"  {'adım(al/sat)':<14}{'ücret':<7}{'işlem':>7}{'ret%':>9}{'DD%':>9}{'açık':>6}{'gerçekleşmemiş%':>16}")
        for buy, sell in STEPS:
            for fee in FEES:
                r = grid.simulate(df, symbol=sym, interval=itv, light=True,
                                  initial_cash=10_000, lot_quote=1250, buy_step_pct=buy,
                                  sell_step_pct=sell, max_tiers=8, fee_bps=fee,
                                  regime_ma=200, exit_regime_break=True)
                m = r["metrics"]
                print(f"  {f'{buy}/{sell}':<14}{f'{fee}bps':<7}{m['num_trades']:>7}"
                      f"{m['total_return']:>9}{m['max_drawdown']:>9}{m['open_tiers_end']:>6}"
                      f"{m['open_unrealized_pct']:>16}")
                rec.add(dict(m, buy_step=buy, sell_step=sell, fee_bps=fee, buy_hold=bh),
                        symbol=sym, interval=itv, name=f"{itv} {buy}/{sell} {fee}bps")
    rec.save()


if __name__ == "__main__":
    main()
