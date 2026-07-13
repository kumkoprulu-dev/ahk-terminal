"""ER range-kapısı (varlık/rejim seçimi) + toplamalı piramit etkisi — 5 alt-coin 15m.
Soru: 'yalnız choppy/yatayda al' kapısı kaybeden varlıkları düzeltir mi?"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backtest import grid  # noqa: E402
from app.data import okx_provider  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

SYMS = ["SOL-USDT-SWAP", "DOGE-USDT-SWAP", "AVAX-USDT-SWAP", "XRP-USDT-SWAP", "LINK-USDT-SWAP"]
BASE = dict(initial_cash=10_000, lot_quote=1250, buy_step_pct=1.0, sell_step_pct=0.8,
            max_tiers=8, fee_bps=3, regime_ma=200, exit_regime_break=True)
VARIANTS = [
    ("ham", dict()),
    ("+ER kapı(.30)", dict(er_period=48, er_max=0.30)),
    ("+ER(.25)+piramit", dict(er_period=48, er_max=0.25, pyramid_add=0.4)),
]

rec = Recorder("range_gate_test", "grid_compare", label="ER range-kapısı 15m 5 coin")
print(f"  {'sembol':<16}{'variant':<20}{'işlem':>7}{'ret%':>9}{'DD%':>9}{'açık':>6}")
for sym in SYMS:
    df = okx_provider.get_ohlcv(sym, "15m", bars=12000)
    bh = round((df['close'].iloc[-1]/df['close'].iloc[0]-1)*100, 2)
    print(f"  {sym}  (Al&Tut {bh}%)")
    for name, over in VARIANTS:
        r = grid.simulate(df, symbol=sym, interval="15m", light=True, **{**BASE, **over})
        m = r["metrics"]
        print(f"  {'':<16}{name:<20}{m['num_trades']:>7}{m['total_return']:>9}{m['max_drawdown']:>9}{m['open_tiers_end']:>6}")
        rec.add(dict(m, buy_hold=bh), symbol=sym, interval="15m", name=f"{sym} · {name}")
rec.save()
