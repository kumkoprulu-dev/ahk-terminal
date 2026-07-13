"""Sibirya grid backtest'ini OKX verisinde çalıştırır ve özet basar.

Kullanım (backend dizininden):
  venv\Scripts\python.exe scripts\run_grid.py SOL-USDT-SWAP 4h 3000
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")  # Türkçe/ok karakterleri konsolda
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/

from app.backtest import grid  # noqa: E402
from app.storage.results_store import get_results_store  # noqa: E402


def show(r: dict) -> None:
    m = r["metrics"]
    print(f"\n=== {r['symbol']}  {r['interval']}  ({m.get('bars')} bar) ===")
    print(f"  Dönem            : {m.get('period')}")
    print(f"  Toplam getiri    : {m.get('total_return')}%   (Al&Tut: {m.get('buy_hold_return')}%)")
    print(f"  CAGR             : {m.get('cagr')}%")
    print(f"  Sharpe / Sortino : {m.get('sharpe')} / {m.get('sortino')}")
    print(f"  Max Drawdown     : {m.get('max_drawdown')}%   Calmar: {m.get('calmar')}")
    print(f"  İşlem sayısı     : {m.get('num_trades')}   Kazanma: {m.get('win_rate')}%   PF: {m.get('profit_factor')}")
    print(f"  Ort. tutuş       : {m.get('avg_bars')} bar   Max eşzamanlı kademe: {m.get('max_concurrent_tiers')}")
    print(f"  Bitişte açık     : {m.get('open_tiers_end')} kademe   gerçekleşmemiş: {m.get('open_unrealized_pct')}%")
    print(f"  Son equity       : {m.get('final_equity')}")


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "SOL-USDT-SWAP"
    itv = sys.argv[2] if len(sys.argv) > 2 else "4h"
    bars = int(sys.argv[3]) if len(sys.argv) > 3 else 3000
    print(f"OKX'ten {sym} {itv} verisi çekiliyor ({bars} bar hedef)...")
    params = dict(bars=bars, initial_cash=10_000, lot_quote=500, buy_step_pct=3.0,
                  sell_step_pct=3.0, max_tiers=8, fee_bps=8)
    r = grid.run_okx(sym, itv, light=True, **params)
    show(r)

    # Sonuçları kalıcı veritabanına yaz (program kapansa da kaybolmaz)
    db = get_results_store()
    run_id = db.record("run_grid", "grid",
                       [dict(r["metrics"], _symbol=r["symbol"], _interval=r["interval"])],
                       label=f"{r['symbol']} {r['interval']}", params=params)
    print(f"\n  [DB] Sonuç kaydedildi → results.sqlite (run #{run_id})")
    print("\n  Son 5 işlem:")
    for t in r["trades"][-5:]:
        print(f"    {t['entry_date']} @ {t['entry_price']} → {t['exit_date']} @ {t['exit_price']}  "
              f"{t['return_pct']}%  ({t['bars']} bar)")
