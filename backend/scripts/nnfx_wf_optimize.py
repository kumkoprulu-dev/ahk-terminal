"""En iyi 5 NNFX kombosunu WALK-FORWARD + Optuna/grid ile optimize et (gerçek OOS testi).

nnfx_search.py'ın OOS triage'ından çıkan ilk 5 kombo burada parametreli hale getirilir
(baseline periyodu + confirmation periyodu her fold'un EĞİTİM diliminde optimize, sonraki
TEST diliminde OOS sınanır; volume slotu sabit). Soru: yuva şablonunun sabit-param OOS
tavanını (nnfx_search'te VWMA+Fisher+VWAP OOS Sharpe 0.33) walk-forward optimize GEÇER mi,
yoksa wf_optimize_combo'daki gibi optimizasyon-overfit mi (0.34→0.26 bozmuştu)?

Her kombo sepetin (BIST+kripto) her sembolünde WF koşturulur, semboller arası OOS ortalaması
alınır; kombolar OOS Sharpe'a göre sıralanır. Sonuç results.sqlite'a yazılır.

Kullanım:  python scripts/nnfx_wf_optimize.py            # 1d
           python scripts/nnfx_wf_optimize.py 4h
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from app.backtest import walkforward as wf  # noqa: E402
from app.data import service  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

try:
    from app.data import okx_provider  # noqa: E402
except Exception:
    okx_provider = None

INTERVAL = sys.argv[1] if len(sys.argv) > 1 else "1d"

# Parametreli yuva parçaları — {ph} yer tutucuları WF her fold'da optimize eder.
# base = baseline (trend/MA), conf = confirmation (momentum); volume slotu SABİT.
_BASE_RANGE = {"min": 20, "max": 100, "step": 10}   # MA periyodu (9 değer)
_FISHER_RANGE = {"min": 5, "max": 30, "step": 5}     # 6 değer → grid 54
_TRIX_RANGE = {"min": 9, "max": 30, "step": 3}       # 8 değer

# nnfx_search 1d OOS ilk 5'i (sabit-param OOS Sharpe yorumda).
COMBOS = [
    {   # #1 OOS 0.33
        "name": "VWMA+Fisher+VWAP",
        "long":  ["close > VWMA({base})", "FisherTransform({conf}).Fisher > FisherTransform({conf}).Trigger", "close > VWAP"],
        "exit":  ["close < VWMA({base})", "FisherTransform({conf}).Fisher < FisherTransform({conf}).Trigger", "close < VWAP"],
        "params": [{"name": "base", **_BASE_RANGE}, {"name": "conf", **_FISHER_RANGE}],
    },
    {   # #2 OOS 0.32
        "name": "DEMA+Fisher+CMF",
        "long":  ["close > DEMA({base})", "FisherTransform({conf}).Fisher > FisherTransform({conf}).Trigger", "CMF(20) > 0"],
        "exit":  ["close < DEMA({base})", "FisherTransform({conf}).Fisher < FisherTransform({conf}).Trigger", "CMF(20) < 0"],
        "params": [{"name": "base", **_BASE_RANGE}, {"name": "conf", **_FISHER_RANGE}],
    },
    {   # #3 OOS 0.32
        "name": "LSMA+TRIX+ForceIndex",
        "long":  ["close > LSMA({base})", "TRIX({conf}) > 0", "ForceIndex(13) > 0"],
        "exit":  ["close < LSMA({base})", "TRIX({conf}) < 0", "ForceIndex(13) < 0"],
        "params": [{"name": "base", **_BASE_RANGE}, {"name": "conf", **_TRIX_RANGE}],
    },
    {   # #4 OOS 0.31
        "name": "EMA+Fisher+VWAP",
        "long":  ["close > EMA({base})", "FisherTransform({conf}).Fisher > FisherTransform({conf}).Trigger", "close > VWAP"],
        "exit":  ["close < EMA({base})", "FisherTransform({conf}).Fisher < FisherTransform({conf}).Trigger", "close < VWAP"],
        "params": [{"name": "base", **_BASE_RANGE}, {"name": "conf", **_FISHER_RANGE}],
    },
    {   # #6 OOS 0.31 (ForceIndex volume, VWAP'siz varyant)
        "name": "DEMA+Fisher+ForceIndex",
        "long":  ["close > DEMA({base})", "FisherTransform({conf}).Fisher > FisherTransform({conf}).Trigger", "ForceIndex(13) > 0"],
        "exit":  ["close < DEMA({base})", "FisherTransform({conf}).Fisher < FisherTransform({conf}).Trigger", "ForceIndex(13) < 0"],
        "params": [{"name": "base", **_BASE_RANGE}, {"name": "conf", **_FISHER_RANGE}],
    },
]

# Sabit-param OOS Sharpe referansı (nnfx_search run #8) — WF ile karşılaştırmak için.
FIXED_OOS = {"VWMA+Fisher+VWAP": 0.33, "DEMA+Fisher+CMF": 0.32, "LSMA+TRIX+ForceIndex": 0.32,
             "EMA+Fisher+VWAP": 0.31, "DEMA+Fisher+ForceIndex": 0.31}

BIST = ["EREGL.IS", "KCHOL.IS", "SASA.IS", "TUPRS.IS", "SISE.IS", "FROTO.IS"]
CRYPTO = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "BNB-USDT-SWAP"]


def fetch(sym, market):
    if market == "crypto":
        bars = 1000 if INTERVAL == "1d" else 3000
        return okx_provider.get_ohlcv(sym, INTERVAL, bars=bars) if okx_provider else None
    rng = "5y" if INTERVAL in ("1d", "1wk") else "2y"
    return service.get_ohlcv(sym, INTERVAL, rng)


def build(combo):
    entry = " AND ".join(f"({r})" for r in combo["long"])
    exit_ = " OR ".join(f"({r})" for r in combo["exit"])
    return entry, exit_


def wf_kwargs():
    # günlük: train 365 / test 90; intraday: daha kısa pencere
    if INTERVAL == "1d":
        return {"train_bars": 365, "test_bars": 90}
    return {"train_bars": 500, "test_bars": 120}


def run_combo(combo, universe):
    entry, exit_ = build(combo)
    grid = int(np.prod([len(range(p["min"], p["max"] + 1, p["step"])) for p in combo["params"]]))
    rets, shps, dds, pf, vf = [], [], [], 0, 0
    per_sym = []
    for sym, market in universe:
        try:
            df = fetch(sym, market)
            if df is None or len(df) < 460:
                continue
            r = wf.run_walk_forward(symbol=sym, entry_template=entry, exit_template=exit_,
                                    params=combo["params"], interval=INTERVAL, method="grid",
                                    objective="sharpe", n_trials=grid, fee_bps=10,
                                    direction="long", df=df, **wf_kwargs())
            s = r["summary"]
            ps = [f["params"] for f in r["folds"] if f.get("params")]
            pmed = "/".join(f"{k}{int(np.median([p[k] for p in ps]))}" for k in ("base", "conf")) if ps else "-"
            rets.append(s["oos_total_return"]); shps.append(s["oos_sharpe"]); dds.append(s["oos_max_drawdown"])
            pf += s["profitable_folds"]; vf += s["valid_folds"]
            per_sym.append((sym.replace("-USDT-SWAP", ""), s["oos_sharpe"], s["oos_total_return"], pmed))
        except Exception as e:
            print(f"    {sym:<12} HATA: {str(e)[:40]}")
    if not shps:
        return None
    return {"oos_sharpe": round(float(np.mean(shps)), 3), "oos_ret": round(float(np.mean(rets)), 1),
            "oos_dd": round(float(np.mean(dds)), 1), "prof_folds": pf, "valid_folds": vf,
            "n": len(shps), "grid": grid, "per_sym": per_sym}


def main():
    universe = [(s, "bist") for s in BIST] + [(s, "crypto") for s in CRYPTO]
    print(f"NNFX top-5 WALK-FORWARD optimize ({INTERVAL}, {wf_kwargs()}, grid) — "
          f"sabit-param OOS ile karşılaştır\n")
    rec = Recorder("nnfx_wf_optimize", "walkforward",
                   label=f"NNFX top-5 WF-optimize ({INTERVAL})",
                   params={"interval": INTERVAL, "combos": [c["name"] for c in COMBOS]})
    results = []
    for combo in COMBOS:
        print(f"  ▶ {combo['name']} (grid {int(np.prod([len(range(p['min'], p['max']+1, p['step'])) for p in combo['params']]))}/fold) ...")
        r = run_combo(combo, universe)
        if r is None:
            print("    — sonuç yok"); continue
        r["name"] = combo["name"]; r["fixed_oos"] = FIXED_OOS.get(combo["name"])
        results.append(r)
        rec.add({"sharpe": r["oos_sharpe"], "total_return": r["oos_ret"], "max_drawdown": r["oos_dd"],
                 "profitable_folds": r["prof_folds"], "valid_folds": r["valid_folds"],
                 "fixed_oos_sharpe": r["fixed_oos"], "delta": round(r["oos_sharpe"] - (r["fixed_oos"] or 0), 3)},
                interval=INTERVAL, name=combo["name"])
    results.sort(key=lambda d: d["oos_sharpe"], reverse=True)
    rec.save()

    print(f"\n  {'#':>2}  {'kombo':<24}{'WF-OOS Sh':>10}{'sabit':>7}{'Δ':>7}{'ret%':>8}{'dd%':>7}"
          f"{'kârlı fold':>12}{'sem':>5}")
    print("  " + "-" * 84)
    for i, r in enumerate(results, 1):
        delta = r["oos_sharpe"] - (r["fixed_oos"] or 0)
        print(f"  {i:>2}  {r['name']:<24}{r['oos_sharpe']:>10}{r['fixed_oos']:>7}{delta:>+7.3f}"
              f"{r['oos_ret']:>8}{r['oos_dd']:>7}"
              f"{str(r['prof_folds'])+'/'+str(r['valid_folds']):>12}{r['n']:>5}")

    if results:
        best = results[0]
        avg_wf = np.mean([r["oos_sharpe"] for r in results])
        avg_fx = np.mean([r["fixed_oos"] for r in results])
        print(f"\n  === SONUÇ ===")
        print(f"  WF-optimize ort OOS Sharpe : {avg_wf:.3f}   (sabit-param ort {avg_fx:.3f})")
        verdict = "GÜÇLENDİRDİ" if avg_wf > avg_fx + 0.02 else ("BOZDU" if avg_wf < avg_fx - 0.02 else "DEĞİŞTİRMEDİ")
        print(f"  → Walk-forward optimizasyon sabit-param'ı {verdict}.")
        print(f"  En iyi: {best['name']} WF-OOS Sharpe {best['oos_sharpe']} "
              f"(kârlı fold {best['prof_folds']}/{best['valid_folds']})")


if __name__ == "__main__":
    main()
