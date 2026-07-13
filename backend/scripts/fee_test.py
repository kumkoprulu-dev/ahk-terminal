"""%0.4 al / %0.6 sat config'i gerçek veride, farklı ücretlerle — komisyonu kurtarıyor mu?"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backtest import grid  # noqa: E402
from app.data import okx_provider  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

SYMS = ["SOL-USDT-SWAP", "DOGE-USDT-SWAP", "LINK-USDT-SWAP"]
FEES = [2, 5, 10]  # maker / taker / spot-taker (bps, tek yön)
BASE = dict(initial_cash=10_000, lot_quote=1250, buy_step_pct=0.4, sell_step_pct=0.6,
            max_tiers=8, regime_ma=200, exit_regime_break=True)

rec = Recorder("fee_test", "grid_compare", label="ücret duyarlılığı 15m (%0.4/%0.6)")
for sym in SYMS:
    df = okx_provider.get_ohlcv(sym, "15m", bars=6000)
    bh = round((df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100, 2)
    span = (df.index[-1] - df.index[0]).days
    print(f"\n=== {sym} 15m ({len(df)} bar, {span}g, Al&Tut {bh}%) ===")
    print(f"  {'ücret(tek/dönüş)':<20}{'işlem':>7}{'ret%':>9}{'DD%':>9}{'açık':>6}  [ER kapısız]")
    for fee in FEES:
        r = grid.simulate(df, symbol=sym, interval="15m", light=True, fee_bps=fee, **BASE)
        m = r["metrics"]
        print(f"  {f'{fee}/{2*fee}bps':<20}{m['num_trades']:>7}{m['total_return']:>9}{m['max_drawdown']:>9}{m['open_tiers_end']:>6}")
        rec.add(dict(m, fee_bps=fee, gate=False, buy_hold=bh), symbol=sym, interval="15m",
                name=f"{sym} · {fee}bps")
    # ER range-kapısı ile (yalnız choppy'de al)
    print(f"  {'--- +ER kapısı (er_max=.30) ---':<20}")
    for fee in [2, 5]:
        r = grid.simulate(df, symbol=sym, interval="15m", light=True, fee_bps=fee,
                          er_period=48, er_max=0.30, **BASE)
        m = r["metrics"]
        print(f"  {f'{fee}/{2*fee}bps':<20}{m['num_trades']:>7}{m['total_return']:>9}{m['max_drawdown']:>9}{m['open_tiers_end']:>6}")
        rec.add(dict(m, fee_bps=fee, gate=True, buy_hold=bh), symbol=sym, interval="15m",
                name=f"{sym} · {fee}bps +ER")
rec.save()
