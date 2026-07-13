"""Yeni pazar (NASDAQ / emtia) NNFX sleeve doğrulaması — Klinger gerçek mi serap mı?

NASDAQ NNFX araması top-30'un HEPSİ Klinger volume ile geldi (OOS 0.59), AMA aynı desen
BIST'te single-OOS #1 Klinger'i WF'de ELEMİŞTİ (%44). Aynı 3-kat disiplin + Klinger↔ForceIndex
yarışı + DOĞRU benchmark (NASDAQ'ta Al&Tut asıl rakip, Combo1 değil):
  1) Farklı OOS pencereleri (son %50/40/30)
  2) Kronolojik alt-dönemler (4 blok)
  3) Yuvarlanan walk-forward (252/63): ort Sharpe + Al&Tut'u geçme oranı

Kullanım:  py -u scripts/market_sleeve_validate.py [nasdaq|emtia]  (varsayılan nasdaq)
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from app.backtest import combo_search as cs  # noqa: E402
from app.backtest import edges as E  # noqa: E402
from app.data import service  # noqa: E402
from app.data.universe import get_universe  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

UNIVERSE = sys.argv[1] if len(sys.argv) > 1 else "nasdaq"
ANN = np.sqrt(252)


def sharpe(seg: pd.Series) -> float:
    seg = seg.dropna()
    if len(seg) < 20 or seg.std() == 0:
        return 0.0
    return float(seg.mean() / seg.std() * ANN)


def load(universe, cap=12):
    dfs = {}
    for s in [x.symbol for x in get_universe(universe)][:cap]:
        try:
            df = service.get_ohlcv(s, "1d", "5y")
            if df is not None and len(df) >= 400:
                dfs[s] = df[~df.index.duplicated(keep="last")].sort_index()
        except Exception:
            pass
    return dfs


# NASDAQ NNFX'in en iyileri + Klinger↔ForceIndex yarışı + Al&Tut + Combo1
CANDS = [
    ("Al&Tut (benchmark)",      "BH"),
    ("VWMA+RSI+Klinger",        ["VWMA", "RSI", "Klinger"]),
    ("VWMA+RSI+ForceIndex",     ["VWMA", "RSI", "ForceIndex"]),
    ("EMA+CMO+Klinger",         ["EMA", "CMO", "Klinger"]),
    ("EMA+CMO+ForceIndex",      ["EMA", "CMO", "ForceIndex"]),
    ("Combo1 SMA+Fisher+VWAP",  (E.COMBO1_ENTRY, E.COMBO1_EXIT)),
]


def build_series(dfs):
    bh = pd.DataFrame({k: v["close"].pct_change() for k, v in dfs.items()}).mean(axis=1)
    series = {}
    for label, spec in CANDS:
        if spec == "BH":
            series[label] = bh.dropna()
        else:
            e, x = spec if isinstance(spec, tuple) else cs.combo_rules(spec)
            series[label] = E.combo_portfolio_returns(dfs, e, x).dropna()
    return series


def main():
    print(f"'{UNIVERSE}' NNFX sleeve doğrulaması — Klinger gerçek mi serap mı (benchmark Al&Tut)\n")
    dfs = load(UNIVERSE)
    print(f"  {len(dfs)} sembol: {', '.join(dfs)}\n")
    series = build_series(dfs)
    ref = "Al&Tut (benchmark)"
    rec = Recorder("market_sleeve_validate", "sleeve_validation",
                   label=f"{UNIVERSE} NNFX sleeve doğrulama (Klinger vs ForceIndex vs Al&Tut)",
                   params={"universe": UNIVERSE, "symbols": sorted(dfs)})

    # 1) farklı OOS pencereleri
    print("  [1] FARKLI OOS PENCERELERİ (Sharpe)")
    fracs = [0.5, 0.6, 0.7]
    print(f"      {'strateji':<26}{'son%50':>8}{'son%40':>8}{'son%30':>8}")
    print("      " + "-" * 50)
    for label, _ in CANDS:
        s = series[label]
        vals = [sharpe(s.iloc[int(len(s) * f):]) for f in fracs]
        print(f"      {label:<26}" + "".join(f"{v:>8.2f}" for v in vals))
        rec.add({f"oos{int((1-f)*100)}": round(v, 3) for f, v in zip(fracs, vals)}, name=f"[oos] {label}")

    # 2) kronolojik alt-dönemler
    print("\n  [2] KRONOLOJİK ALT-DÖNEMLER (4 blok, Sharpe)")
    print(f"      {'strateji':<26}{'D1':>8}{'D2':>8}{'D3':>8}{'D4':>8}")
    print("      " + "-" * 58)
    for label, _ in CANDS:
        s = series[label]; n = len(s); q = n // 4
        blocks = [sharpe(s.iloc[i * q:(i + 1) * q if i < 3 else n]) for i in range(4)]
        print(f"      {label:<26}" + "".join(f"{b:>8.2f}" for b in blocks))
        rec.add({f"blok{i+1}": round(b, 3) for i, b in enumerate(blocks)}, name=f"[donem] {label}")

    # 3) yuvarlanan walk-forward — Al&Tut'u geçme oranı
    print("\n  [3] YUVARLANAN WALK-FORWARD (252g/63g) — Al&Tut'u geçme oranı")
    aligned = pd.DataFrame(series).dropna()
    win, step = 252, 63
    wins = list(range(0, len(aligned) - win + 1, step))
    refw = [sharpe(aligned[ref].iloc[s:s + win]) for s in wins]
    print(f"      {len(wins)} pencere")
    print(f"      {'strateji':<26}{'ortSharpe':>11}{'medSharpe':>11}{'>Al&Tut':>10}")
    print("      " + "-" * 60)
    for label, _ in CANDS:
        w = [sharpe(aligned[label].iloc[s:s + win]) for s in wins]
        beat = "—" if label == ref else f"{sum(1 for a,b in zip(w,refw) if a>b)/len(w)*100:.0f}%"
        print(f"      {label:<26}{np.mean(w):>11.2f}{np.median(w):>11.2f}{beat:>10}")
        rec.add({"wf_mean_sharpe": round(float(np.mean(w)), 3), "wf_median_sharpe": round(float(np.median(w)), 3),
                 "wf_beat_bh_pct": (None if label == ref else round(sum(1 for a,b in zip(w,refw) if a>b)/len(w)*100, 1))},
                name=f"[wf] {label}")
    rec.save()

    # Klinger vs ForceIndex kararı
    print("\n  === KLINGER SERAP MI? ===")
    for k, f in [("VWMA+RSI+Klinger", "VWMA+RSI+ForceIndex"), ("EMA+CMO+Klinger", "EMA+CMO+ForceIndex")]:
        wk = np.mean([sharpe(aligned[k].iloc[s:s + win]) for s in wins])
        wf = np.mean([sharpe(aligned[f].iloc[s:s + win]) for s in wins])
        print(f"  {k:<22} WF ort {wk:.2f}  vs  {f:<22} WF ort {wf:.2f}"
              f"  → {'Klinger tutuyor' if wk >= wf else 'ForceIndex daha sağlam'}")


if __name__ == "__main__":
    main()
