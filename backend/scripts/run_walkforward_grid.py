"""Grid walk-forward'u OKX verisinde çalıştırır ve fold fold OOS sonuçları basar."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backtest import grid_walkforward as gwf  # noqa: E402
from app.storage.results_store import get_results_store  # noqa: E402


def show(r: dict) -> None:
    s = r["summary"]
    print(f"\n=== {r['symbol']} {r['interval']}  walk-forward "
          f"(eğitim {r['train_bars']} / test {r['test_bars']} bar, hedef={r['objective']}) ===")
    print(f"  {r['bars']} bar, {s['folds']} fold\n")
    print(f"  {'fold':<5}{'test dönemi':<34}{'IS skor':>9}{'OOS ret%':>10}{'OOS DD%':>10}"
          f"{'işlem':>7}{'açık':>6}  parametre")
    for f in r["folds"]:
        p = f.get("params")
        ps = (f"buy{p['buy_step_pct']} sell{p['sell_step_pct']} tier{p['max_tiers']} rma{p['regime_ma']}"
              if p else "—")
        print(f"  {f['fold']:<5}{f['test_start']+' → '+f['test_end']:<34}"
              f"{_n(f['is_score']):>9}{_n(f['oos_return']):>10}{_n(f['oos_maxdd']):>10}"
              f"{_n(f['oos_trades']):>7}{_n(f.get('oos_open_end')):>6}  {ps}")
    print(f"\n  --- ÖZET (out-of-sample) ---")
    print(f"  Kârlı fold oranı : {s['profitable_folds']}/{s['valid_folds']}  (%{s['profitable_pct']})")
    print(f"  Ort. OOS getiri  : {s['avg_oos_return']}%   (fold başına)")
    print(f"  Birleşik OOS ret : {s['oos_total_return']}%   Sharpe={s['oos_sharpe']}   MaxDD={s['oos_max_drawdown']}%")
    print(f"  Son equity       : {s['final_equity']}  (başlangıç 10.000)")


def _n(x):
    return "—" if x is None else x


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "SOL-USDT-SWAP"
    itv = sys.argv[2] if len(sys.argv) > 2 else "4h"
    print(f"Grid walk-forward çalışıyor: {sym} {itv} ... (OKX veri + Optuna, ~1-2 dk)")
    r = gwf.run(symbol=sym, interval=itv, bars=6000, train_bars=1200, test_bars=300,
                method="bayes", objective="sharpe", n_trials=40)
    show(r)

    # Kalıcı DB: OOS özet + her fold bir satır
    s = r["summary"]
    db = get_results_store()
    run_id = db.start_run("run_walkforward_grid", "walkforward",
                          label=f"{sym} {itv} WF", params={"train_bars": r["train_bars"],
                          "test_bars": r["test_bars"], "objective": r["objective"]})
    db.add_result(run_id, {"total_return": s["oos_total_return"], "sharpe": s["oos_sharpe"],
                           "max_drawdown": s["oos_max_drawdown"], "final_equity": s["final_equity"],
                           "profitable_folds": s["profitable_folds"], "valid_folds": s["valid_folds"],
                           "_name": "OOS ÖZET"}, symbol=sym, interval=itv)
    db.add_results(run_id, [
        {"_name": f"fold {f['fold']} ({f['test_start']}→{f['test_end']})", "_symbol": sym,
         "_interval": itv, "_rank": f["fold"], "total_return": f.get("oos_return"),
         "max_drawdown": f.get("oos_maxdd"), "num_trades": f.get("oos_trades"),
         "score": f.get("is_score"), "params": f.get("params")}
        for f in r["folds"]])
    print(f"\n  [DB] OOS özet + {len(r['folds'])} fold kaydedildi → results.sqlite (run #{run_id})")
