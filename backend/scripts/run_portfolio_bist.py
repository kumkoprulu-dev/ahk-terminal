"""Seçim katmanlı grid portföy — BIST30, Yahoo verisi. Sibirya'nın ana vatanı."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backtest import grid_portfolio as gp  # noqa: E402
from app.data import service  # noqa: E402
from app.data.universe import _BIST30  # noqa: E402
from app.storage.results_store import get_results_store  # noqa: E402

INTERVAL = "1h"
RANGE = "2y"


def fetch(sym):
    try:
        return service.get_ohlcv(sym + ".IS", INTERVAL, RANGE)
    except Exception:
        return None


def main():
    top_n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    gparams = dict(buy_step_pct=1.0, sell_step_pct=1.2, max_tiers=8,
                   regime_ma=480, exit_regime_break=True, heyecan_ma=120)
    print(f"BIST30 portföy backtest: {INTERVAL} {RANGE}, top_n={top_n} ... (Yahoo, 30 sembol çekiliyor)")
    r = gp.run(universe=_BIST30, interval=INTERVAL, lookback=1000, hold=250, top_n=top_n,
               fee_bps=5.0, grid_params=gparams, er_max=0.35, adx_max=25.0, fetch=fetch)
    s = r["summary"]
    print(f"\n=== BIST30 SEÇİM KATMANLI GRID ({INTERVAL}, evren={r['universe']}, top{r['top_n']}) ===")
    print(f"  {s['periods']} dönem (her ~{r['hold']} bar), lookback {r['lookback']} bar")
    print(f"  Kârlı dönem   : {s['profitable_periods']}/{s['periods']}  (%{s['profitable_pct']})")
    print(f"  Toplam getiri : {s['total_return']}%   (eşit-ağırlık Al&Tut: {s['equalweight_buyhold']}%)")
    print(f"  CAGR          : {s['cagr']}%   Sharpe {s['sharpe']}   MaxDD {s['max_drawdown']}%")
    print(f"  Son equity    : {s['final_equity']}  (başlangıç 10.000)")
    print(f"\n  Dönem dönem seçimler:")
    for p in r["periods"]:
        pk = ", ".join(p["picks"]) or "(nakit)"
        print(f"    {p['date']}  uygun={p['n_eligible']:>2}  seç=[{pk:<26}]  ret={p['ret_pct']:>7}%")

    # Kalıcı DB: özet + her dönem
    db = get_results_store()
    run_id = db.start_run("run_portfolio_bist", "portfolio",
                          label=f"BIST30 {INTERVAL} top{r['top_n']}",
                          params=dict(gparams, interval=INTERVAL, range=RANGE, top_n=r["top_n"]))
    db.add_result(run_id, dict(s, _name="ÖZET"), interval=INTERVAL)
    db.add_results(run_id, [
        {"_name": ", ".join(p["picks"]) or "(nakit)", "_interval": INTERVAL,
         "date": p["date"], "total_return": p["ret_pct"], "n_eligible": p["n_eligible"]}
        for p in r["periods"]])
    print(f"\n  [DB] Özet + {len(r['periods'])} dönem kaydedildi → results.sqlite (run #{run_id})")


if __name__ == "__main__":
    main()
