"""1m teşhis: regime_exit whipsaw'ını izole et. HEYECAN trendi yönetsin, regime_exit kapalı.
Çekirdek gün-içi gridin 1m edge'i var mı?"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backtest import grid  # noqa: E402
from app.data import okx_provider  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

SYMS = ["SOL-USDT-SWAP", "DOGE-USDT-SWAP", "LINK-USDT-SWAP"]
BASE = dict(initial_cash=10_000, lot_quote=1250, buy_step_pct=0.4, sell_step_pct=0.6,
            max_tiers=8, fee_bps=2)
VARIANTS = [
    ("regime_exit AÇIK (rma200)",   dict(regime_ma=200, exit_regime_break=True)),
    ("regime KAPALI",               dict()),
    ("regime KAPALI +HEYECAN",      dict(heyecan_ma=240)),
    ("regime KAPALI +HEYECAN+ER",   dict(heyecan_ma=240, er_period=120, er_max=0.30)),
    ("rma UZUN(1440)+HEYECAN+ER",   dict(regime_ma=1440, exit_regime_break=True, heyecan_ma=240, er_period=120, er_max=0.30)),
]

rec = Recorder("test_1m_noregime", "grid_compare", label="1m regime_exit whipsaw izolasyonu")
for sym in SYMS:
    df = okx_provider.get_ohlcv(sym, "1m", bars=25000)
    bh = round((df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100, 2)
    print(f"\n=== {sym} 1m (Al&Tut {bh}%) ===")
    print(f"  {'variant':<30}{'işlem':>7}{'ret%':>9}{'DD%':>9}{'açık':>6}")
    for name, over in VARIANTS:
        r = grid.simulate(df, symbol=sym, interval="1m", light=True, **{**BASE, **over})
        m = r["metrics"]
        print(f"  {name:<30}{m['num_trades']:>7}{m['total_return']:>9}{m['max_drawdown']:>9}{m['open_tiers_end']:>6}")
        rec.add(dict(m, buy_hold=bh), symbol=sym, interval="1m", name=f"{sym} · {name}")
rec.save()
