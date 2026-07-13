"""BIST sleeve yükseltme doğrulaması — HMA+Fisher+Klinger, Combo1'i GERÇEKTEN geçiyor mu?

NNFX BIST30 portföyünde Combo1'i (SMA+Fisher+VWAP, OOS 0.53) geçti (HMA+Fisher+Klinger 1.09).
Ama kripto HMA'sı tek metrikte parlayıp portföy-OOS'ta çökmüştü → aynı disiplini uygula:
yükseltme yalnızca ÇOK PENCEREDE + ZAMAN İÇİNDE tutarlıysa canlıya alınır (tek-pencere şansı değil).

Üç katman (hepsi portföy seviyesi, sabit param, optimize YOK):
  1) Farklı OOS pencereleri: son %50/40/30/20 → her birinde Sharpe.
  2) Kronolojik alt-dönemler (4 eşit blok): her dönemde Sharpe (zaman içi tutarlılık).
  3) Yuvarlanan walk-forward (252g pencere, 63g adım): kaç pencerede aday > Combo1.

Çalıştır (platform venv):  py -u scripts/bist_sleeve_validate.py
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

ANN = np.sqrt(252)  # BIST ~252 işlem günü (kripto 365 değil) — göreli kıyasta zaten sadeleşir


def sharpe(seg: pd.Series) -> float:
    seg = seg.dropna()
    if len(seg) < 20 or seg.std() == 0:
        return 0.0
    return float(seg.mean() / seg.std() * ANN)


def load_bist30():
    dfs = {}
    for s in [x.symbol for x in get_universe("bist30")]:
        try:
            df = service.get_ohlcv(s, "1d", "5y")
            if df is not None and len(df) >= 400:
                dfs[s] = df[~df.index.duplicated(keep="last")].sort_index()
        except Exception:
            pass
    return dfs


CANDIDATES = [
    ("Combo1 SMA+Fisher+VWAP (mevcut)", (E.COMBO1_ENTRY, E.COMBO1_EXIT)),
    ("HMA+Fisher+Klinger (aday)",       ["HMA", "Fisher", "Klinger"]),
    ("HMA+Fisher+ForceIndex (çapraz)",  ["HMA", "Fisher", "ForceIndex"]),
    ("ZLEMA+Fisher+ForceIndex (çapraz)", ["ZLEMA", "Fisher", "ForceIndex"]),
]


def main():
    print("BIST sleeve yükseltme doğrulaması (BIST30 portföyü, sabit param)\n")
    dfs = load_bist30()
    print(f"  {len(dfs)} hisse yüklendi\n")

    series = {}
    for label, spec in CANDIDATES:
        e, x = spec if isinstance(spec, tuple) else cs.combo_rules(spec)
        series[label] = E.combo_portfolio_returns(dfs, e, x).dropna()

    ref_label = CANDIDATES[0][0]
    ref = series[ref_label]
    rec = Recorder("bist_sleeve_validate", "sleeve_validation",
                   label="BIST sleeve yükseltme doğrulama (HMA+Fisher+Klinger vs Combo1)")

    # --- 1) Farklı OOS pencereleri ---
    print("  [1] FARKLI OOS PENCERELERİ (Sharpe)")
    fracs = [0.5, 0.6, 0.7, 0.8]
    print(f"      {'strateji':<34}" + "".join(f"son%{int((1-f)*100):>7}" for f in fracs))
    print("      " + "-" * 66)
    for label, _ in CANDIDATES:
        s = series[label]
        vals = [sharpe(s.iloc[int(len(s) * f):]) for f in fracs]
        print(f"      {label:<34}" + "".join(f"{v:>9.2f}" for v in vals))
        rec.add({f"oos_last{int((1-f)*100)}": round(v, 3) for f, v in zip(fracs, vals)}, name=f"[oos] {label}")

    # --- 2) Kronolojik alt-dönemler (4 eşit blok) ---
    print("\n  [2] KRONOLOJİK ALT-DÖNEMLER (4 eşit blok, Sharpe)")
    print(f"      {'strateji':<34}{'D1':>9}{'D2':>9}{'D3':>9}{'D4':>9}")
    print("      " + "-" * 70)
    for label, _ in CANDIDATES:
        s = series[label]
        n = len(s); q = n // 4
        blocks = [sharpe(s.iloc[i * q:(i + 1) * q if i < 3 else n]) for i in range(4)]
        print(f"      {label:<34}" + "".join(f"{b:>9.2f}" for b in blocks))
        rec.add({f"blok{i+1}": round(b, 3) for i, b in enumerate(blocks)}, name=f"[donem] {label}")

    # --- 3) Yuvarlanan walk-forward (252g pencere, 63g adım) ---
    print("\n  [3] YUVARLANAN WALK-FORWARD (252g pencere, 63g adım)")
    win, step = 252, 63
    cand_labels = [c[0] for c in CANDIDATES[1:]]
    idx = ref.index
    # ortak: tüm serileri aynı index'e hizala
    aligned = pd.DataFrame(series).dropna()
    n = len(aligned)
    windows = list(range(0, n - win + 1, step))
    print(f"      {len(windows)} pencere · her stratejinin ort pencere-Sharpe'ı + Combo1'i geçme oranı")
    print(f"      {'strateji':<34}{'ortSharpe':>11}{'medSharpe':>11}{'>Combo1':>10}")
    print("      " + "-" * 68)
    ref_wins = [sharpe(aligned[ref_label].iloc[s:s + win]) for s in windows]
    for label, _ in CANDIDATES:
        w = [sharpe(aligned[label].iloc[s:s + win]) for s in windows]
        beat = sum(1 for a, b in zip(w, ref_wins) if a > b) / len(w) * 100 if label != ref_label else 0
        tag = "" if label != ref_label else " (referans)"
        print(f"      {label:<34}{np.mean(w):>11.2f}{np.median(w):>11.2f}"
              f"{('—' if label==ref_label else f'{beat:.0f}%'):>10}{tag}")
        rec.add({"wf_mean_sharpe": round(float(np.mean(w)), 3),
                 "wf_median_sharpe": round(float(np.median(w)), 3),
                 "wf_beat_combo1_pct": round(beat, 1)}, name=f"[wf] {label}")

    rec.save()

    # --- Karar ---
    cand = "HMA+Fisher+Klinger (aday)"
    s_c, s_r = series[cand], ref
    oos_all = all(sharpe(s_c.iloc[int(len(s_c) * f):]) > sharpe(s_r.iloc[int(len(s_r) * f):]) for f in fracs)
    w_c = [sharpe(aligned[cand].iloc[s:s + win]) for s in windows]
    beat_pct = sum(1 for a, b in zip(w_c, ref_wins) if a > b) / len(w_c) * 100
    print("\n  === KARAR ===")
    print(f"  Aday tüm OOS pencerelerinde Combo1'i geçiyor mu : {'EVET' if oos_all else 'HAYIR'}")
    print(f"  Yuvarlanan pencerelerde Combo1'i geçme oranı     : {beat_pct:.0f}%")
    verdict = ("YÜKSELT" if oos_all and beat_pct >= 60 else
               "KISMEN — dikkatli" if beat_pct >= 50 else "YÜKSELTME")
    print(f"  → {verdict}")


if __name__ == "__main__":
    main()
