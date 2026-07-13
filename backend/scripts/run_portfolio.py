"""Varlık-seçimli grid portföy backtest'i — seçim katmanı + grid = sistem."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backtest import grid_portfolio as gp  # noqa: E402
from app.storage.results_store import get_results_store  # noqa: E402


def main():
    itv = sys.argv[1] if len(sys.argv) > 1 else "15m"
    top_n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    print(f"Portföy backtest: {itv}, top_n={top_n}, {len(gp.UNIVERSE)} varlık evreni ...")
    r = gp.run(interval=itv, bars=12000, lookback=2000, hold=672, top_n=top_n, fee_bps=3.0)
    s = r["summary"]
    print(f"\n=== SEÇİM KATMANLI GRID PORTFÖY ({r['interval']}, evren={r['universe']}, top{r['top_n']}) ===")
    print(f"  {s['periods']} dönem (her ~{r['hold']} bar), lookback {r['lookback']} bar")
    print(f"  Kârlı dönem   : {s['profitable_periods']}/{s['periods']}  (%{s['profitable_pct']})")
    print(f"  Toplam getiri : {s['total_return']}%   (eşit-ağırlık Al&Tut: {s['equalweight_buyhold']}%)")
    print(f"  CAGR          : {s['cagr']}%   Sharpe {s['sharpe']}   MaxDD {s['max_drawdown']}%")
    print(f"  Son equity    : {s['final_equity']}  (başlangıç 10.000)")
    print(f"\n  Dönem dönem seçimler:")
    for p in r["periods"]:
        pk = ", ".join(x.replace("-USDT-SWAP", "") for x in p["picks"]) or "(nakit)"
        print(f"    {p['date']}  uygun={p['n_eligible']:>2}  seç=[{pk:<22}]  ret={p['ret_pct']:>6}%")

    # Kalıcı veritabanına yaz: özet satırı + her dönem bir satır
    db = get_results_store()
    run_id = db.start_run("run_portfolio", "portfolio",
                          label=f"{r['interval']} top{r['top_n']} evren={r['universe']}",
                          params={"interval": r["interval"], "top_n": r["top_n"],
                                  "hold": r["hold"], "lookback": r["lookback"]})
    db.add_result(run_id, dict(s, _name="ÖZET"), interval=r["interval"])
    db.add_results(run_id, [
        {"_name": ", ".join(x.replace("-USDT-SWAP", "") for x in p["picks"]) or "(nakit)",
         "_interval": r["interval"], "date": p["date"], "total_return": p["ret_pct"],
         "n_eligible": p["n_eligible"]}
        for p in r["periods"]])
    print(f"\n  [DB] Özet + {len(r['periods'])} dönem kaydedildi → results.sqlite (run #{run_id})")


if __name__ == "__main__":
    main()
