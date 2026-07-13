"""Kayıtlı backtest/tarama sonuçlarını görüntüler (results.sqlite).

Kullanım (backend dizininden):
  venv\\Scripts\\python.exe scripts\\results_db.py runs            # son çalıştırmalar
  venv\\Scripts\\python.exe scripts\\results_db.py show 12         # #12 run'ın sonuçları
  venv\\Scripts\\python.exe scripts\\results_db.py top sharpe 20   # en iyi 20 (metriğe göre)
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.storage.results_store import get_results_store  # noqa: E402


def _f(v, w=8, d=2):
    return f"{v:>{w}.{d}f}" if isinstance(v, (int, float)) else f"{'':>{w}}"


def runs(limit=30):
    db = get_results_store()
    rows = db.recent_runs(limit)
    if not rows:
        print("Henüz kayıtlı çalıştırma yok. Bir scripts/run_*.py çalıştırın.")
        return
    print(f"\n  {'#':>4}  {'tarih':<20}{'script':<18}{'tür':<16}{'sonuç':>6}  etiket")
    print("  " + "-" * 92)
    for r in rows:
        print(f"  {r['run_id']:>4}  {r['created_at'][:19]:<20}{r['script']:<18}"
              f"{r['kind']:<16}{r['n_results']:>6}  {r['label']}")


def show(run_id, limit=500):
    db = get_results_store()
    rows = db.run_results(int(run_id), limit)
    if not rows:
        print(f"#{run_id} için sonuç bulunamadı.")
        return
    print(f"\n  === Run #{run_id} — {len(rows)} sonuç ===")
    print(f"  {'#':>4}  {'sembol/isim':<26}{'itv':<6}{'Sharpe':>8}{'getiri%':>9}"
          f"{'DD%':>8}{'işlem':>7}{'skor':>8}")
    print("  " + "-" * 84)
    for r in rows:
        label = (r["name"] or r["symbol"] or "")[:26]
        rank = r["rank"] if r["rank"] is not None else ""
        print(f"  {str(rank):>4}  {label:<26}{(r['interval'] or ''):<6}"
              f"{_f(r['sharpe'])}{_f(r['total_return'],9)}{_f(r['max_drawdown'])}"
              f"{_f(r['num_trades'],7,0)}{_f(r['score'])}")


def top(metric="sharpe", limit=25):
    db = get_results_store()
    rows = db.top_results(metric, int(limit))
    if not rows:
        print("Kayıt yok.")
        return
    print(f"\n  === En iyi {len(rows)} (metrik: {metric}) ===")
    print(f"  {'sembol/isim':<28}{'itv':<6}{'Sharpe':>8}{'getiri%':>9}{'DD%':>8}"
          f"{'işlem':>7}  {'tür':<14}{'tarih':<12}")
    print("  " + "-" * 96)
    for r in rows:
        label = (r["name"] or r["symbol"] or "")[:28]
        print(f"  {label:<28}{(r['interval'] or ''):<6}{_f(r['sharpe'])}"
              f"{_f(r['total_return'],9)}{_f(r['max_drawdown'])}{_f(r['num_trades'],7,0)}"
              f"  {r['kind']:<14}{r['created_at'][:10]:<12}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "runs"
    args = sys.argv[2:]
    if cmd == "runs":
        runs(int(args[0]) if args else 30)
    elif cmd == "show":
        show(args[0] if args else 1, int(args[1]) if len(args) > 1 else 500)
    elif cmd == "top":
        top(args[0] if args else "sharpe", args[1] if len(args) > 1 else 25)
    else:
        print(__doc__)
