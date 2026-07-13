"""Dört-kollu birleşik portföy — tri_stack + NNFX kolu (Combo3).

tri_stack'in üç koluna DaviddTech/NNFX aramasının tek WF-kazananını ekler:
  A) Kripto Combo1 portföy         (long-biased, edges.COMBO1)
  B) Kripto cross-sectional        (long/short nötr, xsec_blend harman)
  C) BIST Combo1 portföy           (TL boğa, kripto ile korel ≈ 0)
  D) Kripto Combo3 portföy         (DEMA+Fisher+ForceIndex, NNFX/WF kazananı) ← YENİ

Asıl soru: Combo3 GERÇEK bağımsız edge mi, yoksa kripto Combo1'in (A) korelasyonlu bir
varyantı mı? İkisi de kripto long-only 3-gösterge kombosu → yüksek korelasyon beklenebilir.
Korel yüksekse D kol katkısı sınırlı (eleriz); düşükse risk-paritesi Sharpe'ını yükseltir.
Birleştirme tri_stack ile aynı: eq_align (kripto 7/24 ↔ BIST hafta-içi) + risk paritesi.

Çalıştır (platform venv):  py -u scripts/quad_stack.py
"""
import os
import sys
from itertools import product

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from app.backtest import edges as E  # noqa: E402
from app.data import okx_provider, service  # noqa: E402
from app.data.universe import _BIST30  # noqa: E402
from app.storage.results_store import Recorder  # noqa: E402

_REC = Recorder("quad_stack", "portfolio_stack", label="dört-kollu birleşik portföy (+NNFX Combo3)")

MAJOR = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT",
         "LTC", "BCH", "ATOM", "NEAR", "TRX", "BNB"]


def load_crypto():
    dfs, px = {}, {}
    for b in MAJOR:
        try:
            df = okx_provider.get_ohlcv(f"{b}-USDT-SWAP", "1d", bars=1000)
        except Exception:
            continue
        if df is not None and len(df) >= 500:
            dfs[b] = df; px[b] = df["close"]
    return dfs, pd.DataFrame(px).sort_index()


def load_bist(codes):
    dfs = {}
    for c in codes:
        try:
            df = service.get_ohlcv(c + ".IS", "1d", "5y")
        except Exception:
            continue
        if df is None or len(df) < 400:
            continue
        df = df[~df.index.duplicated(keep="last")].sort_index()
        dfs[c] = df
    return dfs


def _norm(s: pd.Series) -> pd.Series:
    s = s.copy()
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    return s[~s.index.duplicated(keep="last")].sort_index()


def eq_align(rets: dict[str, pd.Series]) -> pd.DataFrame:
    """Her getiri kolunu equity'ye çevir, ORTAK günlerde yeniden hizala, getiriye geri dön."""
    eqs = {k: (1 + _norm(s)).cumprod() for k, s in rets.items()}
    common = None
    for eq in eqs.values():
        common = eq.index if common is None else common.intersection(eq.index)
    out = {k: eq.reindex(common).pct_change().fillna(0.0) for k, eq in eqs.items()}
    return pd.DataFrame(out)


def line(name, s):
    t, sh, dd = E.stats(s)
    _, osh, odd = E.stats(s, 0.6)
    print(f"    {name:<32}{t:>9.1f}{sh:>8.2f}{osh:>8.2f}{dd:>8.1f}{odd:>8.1f}")
    _REC.add({"total_return": round(t, 2), "sharpe": round(sh, 3), "oos_sharpe": round(osh, 3),
              "max_drawdown": round(dd, 2), "oos_max_drawdown": round(odd, 2)},
             name=name.strip("> ").strip())
    return osh


def main():
    print("Dört-kollu birleşik portföy — kripto Combo1 + xsec + BIST Combo1 + kripto Combo3(NNFX)")
    print("Veri çekiliyor (OKX 15 major + BIST30 Yahoo) ...")
    cdfs, cpx = load_crypto()
    bdfs = load_bist(_BIST30)
    print(f"  kripto {len(cdfs)} varlık, BIST {len(bdfs)} varlık")

    A = E.combo_portfolio_returns(cdfs, E.COMBO1_ENTRY, E.COMBO1_EXIT)   # kripto Combo1
    B = E.xsec_blend_returns(cpx, k=3)                                    # kripto xsec (L/S)
    C = E.combo_portfolio_returns(bdfs, E.COMBO1_ENTRY, E.COMBO1_EXIT)   # BIST Combo1
    D = E.combo_portfolio_returns(cdfs, E.COMBO3_ENTRY, E.COMBO3_EXIT)   # kripto Combo3 (NNFX)

    R = eq_align({"kriptoCombo1": A, "kriptoXsec": B, "bistCombo1": C, "kriptoCombo3": D})
    R = R.dropna()
    print(f"  ortak takvim: {len(R)} gün ({R.index[0].date()} → {R.index[-1].date()})")

    print("\n  === Kollar arası korelasyon (tam dönem) ===")
    cm = R.corr()
    print("    " + cm.round(2).to_string().replace("\n", "\n    "))
    # Combo3'ün Combo1 ile korelasyonu asıl karar kriteri
    ac = cm.loc["kriptoCombo3", "kriptoCombo1"]
    print(f"\n  → Combo3 ↔ Combo1 korelasyon = {ac:.2f}  "
          f"({'YÜKSEK — bağımsız değil, varyant' if ac > 0.6 else 'DÜŞÜK — bağımsız edge!' if ac < 0.35 else 'ORTA'})")
    _REC.params = {"common_days": len(R), "start": str(R.index[0].date()),
                   "end": str(R.index[-1].date()), "arms": list(R.columns),
                   "corr": cm.round(3).to_dict(), "combo3_combo1_corr": round(float(ac), 3)}

    print(f"\n  === Tek kol + harmanlar ===")
    print(f"    {'kol':<32}{'TÜM%':>9}{'TÜMShp':>8}{'OOSShp':>8}{'DD%':>8}{'OOSDD':>8}")
    for name in R.columns:
        line(name, R[name])

    # 3-kol (D'siz) referans vs 4-kol risk paritesi — D kol katkısını izole et
    def rp(cols):
        sub = R[cols]
        iv = 1.0 / sub.std()
        return (sub * (iv / iv.sum())).sum(axis=1)

    print()
    tri_cols = ["kriptoCombo1", "kriptoXsec", "bistCombo1"]
    line(">> 3-kol risk paritesi (D'siz)", rp(tri_cols))
    line(">> 4-kol risk paritesi (+Combo3)", rp(list(R.columns)))
    line(">> 4-kol eşit ağırlık (1/4)", R.mean(axis=1))

    # --- 4-kol ağırlık taraması (simplex, adım 0.1) ---
    best_oos = None
    grid = [i / 10 for i in range(11)]
    for wa, wb, wc in product(grid, grid, grid):
        wd = round(1 - wa - wb - wc, 4)
        if wd < -1e-9 or wd > 1:
            continue
        comb = wa*R["kriptoCombo1"] + wb*R["kriptoXsec"] + wc*R["bistCombo1"] + wd*R["kriptoCombo3"]
        _, osh, _ = E.stats(comb, 0.6)
        w = (round(wa, 1), round(wb, 1), round(wc, 1), round(wd, 1))
        if best_oos is None or osh > best_oos[0]:
            best_oos = (osh, w)

    print("\n  === 4-kol ağırlık taraması (Combo1/Xsec/BIST/Combo3) ===")
    o_osh, o_w = best_oos
    print(f"    En iyi OOS Sharpe : {o_osh:.2f}  ağırlık {o_w}  (⚠ in-sample seçim = overfit; deploy=risk paritesi)")
    _REC.save()


if __name__ == "__main__":
    main()
