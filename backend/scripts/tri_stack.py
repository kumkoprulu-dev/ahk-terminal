"""Üç-kollu birleşik portföy — korelasyonsuzluğu paraya çevir.

Kollar (üçü de bağımsız, birbirine korelasyonsuz):
  A) Kripto Combo1 portföy   (long-biased, edges.COMBO1)
  B) Kripto cross-sectional  (long/short nötr, xsec_blend harman)
  C) BIST Combo1 portföy     (TL boğa, kripto ile korel ≈ 0)

Adil birleştirme: kripto 7/24, BIST hafta-içi → her kolu equity-eğrisine çevir, ORTAK
günlerde yeniden hizala (kripto hafta sonu getirisi Pazartesi barına bileşiklenir, kaybolmaz).
Sonra ağırlık taraması: birleşik Sharpe korelasyonsuzluktan ne kadar yükseliyor?

Çalıştır (platform venv):  py -u scripts/tri_stack.py
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

_REC = Recorder("tri_stack", "portfolio_stack", label="üç-kollu birleşik portföy")

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
    """Her getiri kolunu equity'ye çevir, ORTAK günlerde yeniden hizala, getiriye geri dön.
    Boşluk (kripto hafta sonu) bir sonraki ortak barın getirisine bileşiklenir."""
    eqs = {k: (1 + _norm(s)).cumprod() for k, s in rets.items()}
    common = None
    for eq in eqs.values():
        common = eq.index if common is None else common.intersection(eq.index)
    out = {k: eq.reindex(common).pct_change().fillna(0.0) for k, eq in eqs.items()}
    return pd.DataFrame(out)


def line(name, s):
    t, sh, dd = E.stats(s)
    _, osh, odd = E.stats(s, 0.6)
    print(f"    {name:<28}{t:>9.1f}{sh:>8.2f}{osh:>8.2f}{dd:>8.1f}{odd:>8.1f}")
    _REC.add({"total_return": round(t, 2), "sharpe": round(sh, 3), "oos_sharpe": round(osh, 3),
              "max_drawdown": round(dd, 2), "oos_max_drawdown": round(odd, 2)},
             name=name.strip("> ").strip())


def main():
    print("Üç-kollu birleşik portföy — kripto Combo1 + kripto xsec + BIST Combo1")
    print("Veri çekiliyor (OKX 15 major + BIST30 Yahoo) ...")
    cdfs, cpx = load_crypto()
    bdfs = load_bist(_BIST30)
    print(f"  kripto {len(cdfs)} varlık, BIST {len(bdfs)} varlık")

    A = E.combo_portfolio_returns(cdfs, E.COMBO1_ENTRY, E.COMBO1_EXIT)   # kripto Combo1
    B = E.xsec_blend_returns(cpx, k=3)                                    # kripto xsec (L/S)
    C = E.combo_portfolio_returns(bdfs, E.COMBO1_ENTRY, E.COMBO1_EXIT)   # BIST Combo1

    R = eq_align({"kriptoCombo1": A, "kriptoXsec": B, "bistCombo1": C})
    R = R.dropna()
    print(f"  ortak takvim: {len(R)} gün ({R.index[0].date()} → {R.index[-1].date()})")

    print("\n  === Kollar arası korelasyon (tam dönem) ===")
    cm = R.corr()
    print(cm.round(2).to_string().replace("\n", "\n    ").rjust(0))
    _REC.params = {"common_days": len(R), "start": str(R.index[0].date()),
                   "end": str(R.index[-1].date()), "arms": list(R.columns),
                   "corr": cm.round(3).to_dict()}

    print(f"\n  === Tek kol + referans harmanlar ({'TÜM%':>0}) ===")
    print(f"    {'kol':<28}{'TÜM%':>9}{'TÜMShp':>8}{'OOSShp':>8}{'DD%':>8}{'OOSDD':>8}")
    for name in R.columns:
        line(name, R[name])
    eqw = R.mean(axis=1)
    line(">> Eşit ağırlık (1/3)", eqw)
    # ters-vol risk paritesi (tam dönem vol)
    iv = 1.0 / R.std()
    rp = (R * (iv / iv.sum())).sum(axis=1)
    line(">> Risk paritesi (ters-vol)", rp)

    # --- ağırlık taraması (simplex, adım 0.1) ---
    best_oos, best_tot = None, None
    grid = [i / 10 for i in range(11)]
    for wa, wb in product(grid, grid):
        wc = round(1 - wa - wb, 4)
        if wc < -1e-9 or wc > 1:
            continue
        comb = wa * R["kriptoCombo1"] + wb * R["kriptoXsec"] + wc * R["bistCombo1"]
        _, sh, _ = E.stats(comb)
        _, osh, _ = E.stats(comb, 0.6)
        w = (round(wa, 1), round(wb, 1), round(wc, 1))
        if best_oos is None or osh > best_oos[0]:
            best_oos = (osh, sh, w)
        if best_tot is None or sh > best_tot[0]:
            best_tot = (sh, osh, w)

    print("\n  === Ağırlık taraması (kripto Combo1 / kripto Xsec / BIST Combo1) ===")
    o_osh, o_sh, o_w = best_oos
    print(f"    En iyi OOS Sharpe : {o_osh:.2f} (TÜM {o_sh:.2f})  ağırlık {o_w}")
    t_sh, t_osh, t_w = best_tot
    print(f"    En iyi TÜM Sharpe : {t_sh:.2f} (OOS {t_osh:.2f})  ağırlık {t_w}")
    print("\n    Seçilmiş ağırlıklar:")
    for label, w in [("Eşit 1/3", (1/3, 1/3, 1/3)),
                     ("En iyi OOS", o_w), ("En iyi TÜM", t_w)]:
        comb = w[0]*R["kriptoCombo1"] + w[1]*R["kriptoXsec"] + w[2]*R["bistCombo1"]
        line(f"{label} {tuple(round(x,2) for x in w)}", comb)
    _REC.save()


if __name__ == "__main__":
    main()
