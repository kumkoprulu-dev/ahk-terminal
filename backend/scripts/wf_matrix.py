"""Walk-forward matrisi: sembol × zaman dilimi × hedef — robust config var mı?
Sadece OOS özet satırı basar."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backtest import grid_walkforward as gwf  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

# (interval, bars, train, test) — zaman dilimine göre pencere
WIN = {
    "4h": (6000, 1200, 300),
    "1d": (1800, 365, 120),
}
RUNS = [
    ("BTC-USDT-SWAP", "4h", "sharpe"),
    ("BTC-USDT-SWAP", "4h", "total_return"),
    ("SOL-USDT-SWAP", "4h", "total_return"),
    ("BTC-USDT-SWAP", "1d", "sharpe"),
    ("SOL-USDT-SWAP", "1d", "sharpe"),
    ("ETH-USDT-SWAP", "1d", "sharpe"),
]

rec = Recorder("wf_matrix", "walkforward_matrix", label="sembol×tf×hedef OOS matrisi")
print(f"  {'sembol':<16}{'tf':<5}{'hedef':<14}{'kârlı fold':>12}{'OOS ret%':>10}{'Sharpe':>8}{'MaxDD%':>9}{'eq':>9}")
for sym, itv, obj in RUNS:
    bars, tr, te = WIN[itv]
    try:
        r = gwf.run(symbol=sym, interval=itv, bars=bars, train_bars=tr, test_bars=te,
                    method="bayes", objective=obj, n_trials=30)
        s = r["summary"]
        print(f"  {sym:<16}{itv:<5}{obj:<14}"
              f"{str(s['profitable_folds'])+'/'+str(s['valid_folds']):>12}"
              f"{s['oos_total_return']:>10}{s['oos_sharpe']:>8}{s['oos_max_drawdown']:>9}{s['final_equity']:>9}")
        rec.add({"total_return": s["oos_total_return"], "sharpe": s["oos_sharpe"],
                 "max_drawdown": s["oos_max_drawdown"], "final_equity": s["final_equity"],
                 "profitable_folds": s["profitable_folds"], "valid_folds": s["valid_folds"],
                 "objective": obj}, symbol=sym, interval=itv, name=f"{sym} {itv} {obj}")
    except Exception as e:
        print(f"  {sym:<16}{itv:<5}{obj:<14}  HATA: {e}")
rec.save()
