"""BIST sleeve yükseltme — İKİNCİ kat doğrulama (kullanıcı seçeneği 3).

bist_sleeve_validate: HMA+Fisher+Klinger elendi (WF %44), HMA+Fisher+ForceIndex geçti
(%62, ort 2.31 vs 2.20). Modest ama gerçek. Canlıya almadan bir kat daha:
  A) GENELLEME: aynı head-to-head BIST50'de (daha geniş evren) — BIST30'a özgü mü?
  B) PARAMETRE ROBUSTLUĞU: parametreli walk-forward (grid) — baseline+fisher fold-fold
     optimize; HMA+Fisher+ForceIndex, Combo1'i optimize-edilmiş OOS'ta da geçiyor mu,
     yoksa üstünlük sabit-param şansı mı? (volume slotu sabit, wf_optimize disiplini.)

Çalıştır (platform venv):  py -u scripts/bist_sleeve_validate2.py
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from app.backtest import combo_search as cs  # noqa: E402
from app.backtest import edges as E  # noqa: E402
from app.backtest import walkforward as wf  # noqa: E402
from app.data import service  # noqa: E402
from app.data.universe import get_universe  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

ANN = np.sqrt(252)


def sharpe(seg: pd.Series) -> float:
    seg = seg.dropna()
    if len(seg) < 20 or seg.std() == 0:
        return 0.0
    return float(seg.mean() / seg.std() * ANN)


def load(universe):
    dfs = {}
    for s in [x.symbol for x in get_universe(universe)]:
        try:
            df = service.get_ohlcv(s, "1d", "5y")
            if df is not None and len(df) >= 400:
                dfs[s] = df[~df.index.duplicated(keep="last")].sort_index()
        except Exception:
            pass
    return dfs


CANDS = [
    ("Combo1 SMA+Fisher+VWAP",      (E.COMBO1_ENTRY, E.COMBO1_EXIT)),
    ("HMA+Fisher+ForceIndex",       ["HMA", "Fisher", "ForceIndex"]),
    ("HMA+Fisher+Klinger",          ["HMA", "Fisher", "Klinger"]),
]

rec = Recorder("bist_sleeve_validate2", "sleeve_validation",
               label="BIST sleeve 2. kat doğrulama (BIST50 genelleme + param-WF)")


def test_A():
    print("  [A] GENELLEME — BIST50 portföyü (daha geniş evren)")
    dfs = load("bist50")
    print(f"      {len(dfs)} hisse")
    series = {}
    for label, spec in CANDS:
        e, x = spec if isinstance(spec, tuple) else cs.combo_rules(spec)
        series[label] = E.combo_portfolio_returns(dfs, e, x).dropna()
    aligned = pd.DataFrame(series).dropna()
    ref = "Combo1 SMA+Fisher+VWAP"
    win, step = 252, 63
    wins = list(range(0, len(aligned) - win + 1, step))
    refw = [sharpe(aligned[ref].iloc[s:s + win]) for s in wins]
    fracs = [0.5, 0.6, 0.7]
    print(f"      {'strateji':<26}{'son%50':>8}{'son%40':>8}{'son%30':>8}{'WFort':>8}{'>C1':>7}")
    print("      " + "-" * 65)
    for label, _ in CANDS:
        s = series[label]
        oos = [sharpe(s.iloc[int(len(s) * f):]) for f in fracs]
        w = [sharpe(aligned[label].iloc[st:st + win]) for st in wins]
        beat = "—" if label == ref else f"{sum(1 for a,b in zip(w,refw) if a>b)/len(w)*100:.0f}%"
        print(f"      {label:<26}" + "".join(f"{v:>8.2f}" for v in oos) + f"{np.mean(w):>8.2f}{beat:>7}")
        rec.add({"bist50_oos50": round(oos[0], 3), "bist50_oos40": round(oos[1], 3),
                 "bist50_wf_mean": round(float(np.mean(w)), 3),
                 "bist50_beat_c1": (None if label == ref else round(sum(1 for a,b in zip(w,refw) if a>b)/len(w)*100, 1))},
                name=f"[A-bist50] {label}")


# --- B: parametreli walk-forward (per-symbol grid) ---
WF_COMBOS = {
    "Combo1 SMA+Fisher+VWAP": {
        "entry": "Close > SMA({base}) AND FisherTransform({fis}).Fisher > FisherTransform({fis}).Trigger AND Close > VWAP",
        "exit":  "Close < SMA({base}) OR FisherTransform({fis}).Fisher < FisherTransform({fis}).Trigger OR Close < VWAP",
        "params": [{"name": "base", "min": 20, "max": 100, "step": 10}, {"name": "fis", "min": 5, "max": 30, "step": 5}],
    },
    "HMA+Fisher+ForceIndex": {
        "entry": "Close > HMA({base}) AND FisherTransform({fis}).Fisher > FisherTransform({fis}).Trigger AND ForceIndex(13) > 0",
        "exit":  "Close < HMA({base}) OR FisherTransform({fis}).Fisher < FisherTransform({fis}).Trigger OR ForceIndex(13) < 0",
        "params": [{"name": "base", "min": 10, "max": 60, "step": 5}, {"name": "fis", "min": 5, "max": 30, "step": 5}],
    },
}


def test_B():
    print("\n  [B] PARAMETRE ROBUSTLUĞU — parametreli walk-forward (BIST30, per-symbol grid)")
    dfs = load("bist30")
    syms = list(dfs)
    print(f"      {len(syms)} hisse · train 365 / test 90 · baseline+fisher fold-fold optimize")
    print(f"      {'strateji':<26}{'WF-OOS Sharpe':>15}{'kârlı fold':>13}")
    print("      " + "-" * 56)
    out = {}
    for label, cfg in WF_COMBOS.items():
        grid = int(np.prod([len(range(p["min"], p["max"] + 1, p["step"])) for p in cfg["params"]]))
        shps, pf, vf = [], 0, 0
        for s in syms:
            try:
                r = wf.run_walk_forward(symbol=s, entry_template=cfg["entry"], exit_template=cfg["exit"],
                                        params=cfg["params"], interval="1d", method="grid",
                                        objective="sharpe", n_trials=grid, train_bars=365, test_bars=90,
                                        fee_bps=10, direction="long", df=dfs[s])
                sm = r["summary"]
                shps.append(sm["oos_sharpe"]); pf += sm["profitable_folds"]; vf += sm["valid_folds"]
            except Exception:
                pass
        m = float(np.mean(shps)) if shps else 0.0
        out[label] = m
        print(f"      {label:<26}{m:>15.3f}{str(pf)+'/'+str(vf):>13}")
        rec.add({"wf_opt_oos_sharpe": round(m, 3), "profitable_folds": pf, "valid_folds": vf},
                name=f"[B-paramWF] {label}")
    return out


def main():
    print("BIST sleeve 2. kat doğrulama — genelleme (BIST50) + parametre-WF\n")
    test_A()
    wfB = test_B()
    rec.save()
    print("\n  === KARAR ===")
    c1 = wfB.get("Combo1 SMA+Fisher+VWAP", 0); fx = wfB.get("HMA+Fisher+ForceIndex", 0)
    print(f"  Param-WF: HMA+Fisher+ForceIndex {fx:.3f} vs Combo1 {c1:.3f} "
          f"→ {'ForceIndex geçti' if fx > c1 else 'Combo1 önde'}")
    print("  (BIST50 genellemesi [A] + param-WF [B] birlikte değerlendir: ikisi de ForceIndex'i")
    print("   destekliyorsa YÜKSELT; biri bile çökerse Combo1'de kal.)")


if __name__ == "__main__":
    main()
