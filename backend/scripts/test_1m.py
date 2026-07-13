"""1 dakikalık gerçekçi test: piramit + ER range-kapısı + HEYECAN katman katman.
Config: 0.4 al / 0.6 sat, maker 2bps, regime_exit. 1m = gün içi salınım en gerçekçi."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backtest import grid  # noqa: E402
from app.data import okx_provider  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

SYMS = ["SOL-USDT-SWAP", "DOGE-USDT-SWAP", "LINK-USDT-SWAP"]
BASE = dict(initial_cash=10_000, lot_quote=1250, buy_step_pct=0.4, sell_step_pct=0.6,
            max_tiers=8, fee_bps=2, regime_ma=200, exit_regime_break=True)
VARIANTS = [
    ("ham",                    dict()),
    ("+piramit",               dict(pyramid_add=0.4)),
    ("+piramit+ER",            dict(pyramid_add=0.4, er_period=120, er_max=0.30)),
    ("+piramit+ER+HEYECAN",    dict(pyramid_add=0.4, er_period=120, er_max=0.30, heyecan_ma=240)),
]

rec = Recorder("test_1m", "grid_compare", label="1m piramit+ER+HEYECAN katmanları")
for sym in SYMS:
    df = okx_provider.get_ohlcv(sym, "1m", bars=25000)
    bh = round((df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100, 2)
    span = (df.index[-1] - df.index[0]).days
    print(f"\n=== {sym} 1m ({len(df)} bar, {span}g, Al&Tut {bh}%) ===")
    print(f"  {'variant':<22}{'işlem':>7}{'ret%':>9}{'DD%':>9}{'açık':>6}{'gerçekleşmemiş%':>16}")
    for name, over in VARIANTS:
        r = grid.simulate(df, symbol=sym, interval="1m", light=True, **{**BASE, **over})
        m = r["metrics"]
        print(f"  {name:<22}{m['num_trades']:>7}{m['total_return']:>9}{m['max_drawdown']:>9}"
              f"{m['open_tiers_end']:>6}{m['open_unrealized_pct']:>16}")
        rec.add(dict(m, buy_hold=bh), symbol=sym, interval="1m", name=f"{sym} · {name}")
rec.save()
