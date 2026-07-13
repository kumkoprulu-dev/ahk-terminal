"""Edge portföyleri servisi — UI'dan çalıştırılabilir strateji-sepet getirisi.

`edges.py` çekirdeğini (Combo1/Combo2 portföy, cross-sectional harman, 3-kollu risk
paritesi) tek bir servis arkasında toplar; API (routes_portfolio) ve scriptler aynı yeri
çağırır. Sonuç: metrikler (TÜM/OOS Sharpe, getiri, DD) + equity eğrisi + (3-kollu için)
kol kırılımı → frontend gösterir.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.backtest import combo_search as CS
from app.backtest import edges as E
from app.data import okx_provider, service
from app.data.universe import get_universe

# İkili aramada kombinatorik patlamayı önlemek için güçlü gösterge kısa listesi
# (combo_search bulgularının MVP göstergeleri + kategori çeşitliliği)
PAIR_SHORTLIST = ["SMA", "HMA", "ZLEMA", "TEMA", "MOST", "SuperTrend",
                  "RSI", "Fisher", "TRIX", "PPO", "AwesomeOsc", "CMO",
                  "VWAP", "MFI", "ForceIndex", "CMF"]

# Combo1/xsec'in doğrulandığı likit major kripto evreni (OKX perp)
MAJOR = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT",
         "LTC", "BCH", "ATOM", "NEAR", "TRX", "BNB"]

MODES = {
    "combo1": "Combo1 portföy (SMA+Fisher+VWAP, long-only)",
    "combo2": "Combo2 portföy (Fisher+Force+Awesome, agresif)",
    "xsec": "Cross-sectional momentum (harman, long/short nötr)",
    "tristack": "3-Kollu risk paritesi (kripto Combo1 + xsec + BIST Combo1)",
}


def _load_crypto(bases, bars=1000):
    dfs, px = {}, {}
    for b in bases:
        try:
            df = okx_provider.get_ohlcv(f"{b}-USDT-SWAP", "1d", bars=bars)
        except Exception:
            continue
        if df is not None and len(df) >= 300:
            dfs[b] = df; px[b] = df["close"]
    return dfs, pd.DataFrame(px).sort_index()


def _load_stock(symbols, range_="5y"):
    dfs, px = {}, {}
    for s in symbols:
        try:
            df = service.get_ohlcv(s, "1d", range_)
        except Exception:
            continue
        if df is not None and len(df) >= 250:
            df = df[~df.index.duplicated(keep="last")].sort_index()
            dfs[s] = df; px[s] = df["close"]
    return dfs, pd.DataFrame(px).sort_index()


def _load_universe(universe):
    """universe id → (dfs, prices). Kripto OKX'ten (doğrulanan evren), gerisi Yahoo'dan."""
    if universe == "kripto":
        return _load_crypto(MAJOR)
    syms = [s.symbol for s in get_universe(universe)]
    return _load_stock(syms)


def _equity(ret: pd.Series, max_points=400):
    """Getiri serisi → kümülatif equity noktaları [{t, v}], gerekiyorsa seyreltilmiş."""
    ret = ret.dropna()
    if len(ret) < 2:
        return []
    eq = (1 + ret).cumprod()
    idx = eq.index
    step = max(1, len(eq) // max_points)
    out = []
    for i in range(0, len(eq), step):
        out.append({"t": str(idx[i])[:10], "v": round(float(eq.iloc[i]), 4)})
    if out and out[-1]["t"] != str(idx[-1])[:10]:
        out.append({"t": str(idx[-1])[:10], "v": round(float(eq.iloc[-1]), 4)})
    return out


def _metrics(ret: pd.Series, oos_frac=0.6):
    total, shp, dd = E.stats(ret)
    _, oshp, odd = E.stats(ret, oos_frac)
    return {"total_return": round(total, 2), "sharpe": round(shp, 3),
            "oos_sharpe": round(oshp, 3), "max_drawdown": round(dd, 2),
            "oos_max_drawdown": round(odd, 2), "bars": int(ret.dropna().shape[0])}


def _norm(s: pd.Series) -> pd.Series:
    s = s.copy()
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    return s[~s.index.duplicated(keep="last")].sort_index()


def _eq_align(rets: dict[str, pd.Series]) -> pd.DataFrame:
    eqs = {k: (1 + _norm(s)).cumprod() for k, s in rets.items()}
    common = None
    for eq in eqs.values():
        common = eq.index if common is None else common.intersection(eq.index)
    return pd.DataFrame({k: eq.reindex(common).pct_change().fillna(0.0)
                         for k, eq in eqs.items()})


def _tristack():
    """3-kollu risk paritesi (tri_stack.py çekirdeği) — sabit kompozisyon, cross-asset."""
    cdfs, cpx = _load_crypto(MAJOR)
    bdfs, _ = _load_stock([s.symbol for s in get_universe("bist30")])
    A = E.combo_portfolio_returns(cdfs, E.COMBO1_ENTRY, E.COMBO1_EXIT)
    B = E.xsec_blend_returns(cpx, k=3)
    C = E.combo_portfolio_returns(bdfs, E.COMBO1_ENTRY, E.COMBO1_EXIT)
    R = _eq_align({"kriptoCombo1": A, "kriptoXsec": B, "bistCombo1": C}).dropna()
    if R.empty:
        raise ValueError("3-kollu için ortak veri bulunamadı")
    iv = 1.0 / R.std()
    w = iv / iv.sum()
    combined = (R * w).sum(axis=1)
    arms = []
    for k in R.columns:
        m = _metrics(R[k])
        arms.append({"name": k, "weight": round(float(w[k]) * 100, 1), **m})
    return combined, arms, {"assets": len(cdfs) + len(bdfs), "common_days": len(R)}


def run_edge_portfolio(mode: str, universe: str = "kripto", oos_frac: float = 0.6) -> dict:
    if mode not in MODES:
        raise ValueError(f"bilinmeyen mod: {mode}")

    if mode == "tristack":
        combined, arms, info = _tristack()
        return {"mode": mode, "label": MODES[mode], "universe": "cross-asset",
                "metrics": _metrics(combined, oos_frac), "equity": _equity(combined),
                "arms": arms, "info": info}

    dfs, prices = _load_universe(universe)
    if len(dfs) < 3:
        raise ValueError(f"yetersiz varlık yüklendi ({len(dfs)}) — evren: {universe}")

    if mode == "combo1":
        ret = E.combo_portfolio_returns(dfs, E.COMBO1_ENTRY, E.COMBO1_EXIT)
    elif mode == "combo2":
        ret = E.combo_portfolio_returns(dfs, E.COMBO2_ENTRY, E.COMBO2_EXIT)
    elif mode == "xsec":
        k = 5 if len(dfs) >= 20 else 3
        ret = E.xsec_blend_returns(prices, k=k)
    else:
        raise ValueError(mode)

    bh = prices.pct_change().mean(axis=1).fillna(0.0)     # eşit-ağırlık Al&Tut benchmark
    return {"mode": mode, "label": MODES[mode], "universe": universe,
            "metrics": _metrics(ret, oos_frac), "equity": _equity(ret),
            "benchmark": _equity(bh), "benchmark_metrics": _metrics(bh, oos_frac),
            "info": {"assets": len(dfs)}}


def allocate_capital(crypto_total: float = 3000.0, bist_total: float = 300000.0) -> dict:
    """3-kollu risk-paritesi dağıtımı + hazır canlı başlatma komutları (koordinatör).

    Komutlar platform VENV python'uyla üretilir (sys.executable = bu server'ı çalıştıran
    yorumlayıcı) — global `py` backend bağımlılıklarına (pydantic_settings vb.) sahip değil."""
    import os
    import sys
    py = f'"{sys.executable}"'   # venv python tam yolu (boşluklu path için tırnak)
    # Runner'lar execution/zargan_quant altında; komuta cd gömülür ki cwd farketmesin
    exec_dir = os.environ.get(
        "ZARGAN_DIR", r"C:\Users\CASPER\Desktop\AHK-Trading\execution\zargan_quant")
    cd = f'cd /d "{exec_dir}" && '
    _, arms, info = _tristack()
    w = {a["name"]: a["weight"] / 100 for a in arms}
    wc1, wxs = w.get("kriptoCombo1", 0.5), w.get("kriptoXsec", 0.3)
    csum = wc1 + wxs or 1.0
    c1_notional = crypto_total * wc1 / csum
    xsec_gross = crypto_total * wxs / csum
    sleeves = [
        {"sleeve": "Kripto Combo1", "script": "run_combo_portfolio.py", "port": 8091,
         "weight": round(wc1 * 100, 1), "capital": round(c1_notional), "ccy": "USDT",
         "command": f"{cd}{py} -u run_combo_portfolio.py --notional {c1_notional:.0f} --dashboard"},
        {"sleeve": "Kripto cross-sectional", "script": "run_xsec.py", "port": 8093,
         "weight": round(wxs * 100, 1), "capital": round(xsec_gross), "ccy": "USDT",
         "command": f"{cd}{py} -u run_xsec.py --gross {xsec_gross:.0f} --dashboard"},
        {"sleeve": "BIST Combo1", "script": "run_bist_combo.py", "port": 8094,
         "weight": round(w.get("bistCombo1", 0.4) * 100, 1), "capital": round(bist_total), "ccy": "TRY",
         "command": f"{cd}{py} -u run_bist_combo.py --notional {bist_total:.0f} --dashboard"},
    ]
    return {"weights": {a["name"]: a["weight"] for a in arms}, "sleeves": sleeves,
            "coordinator": f"{cd}{py} -u portfolio_stack.py --dashboard  # birleşik izleme (8095)",
            "info": info, "python": sys.executable,
            "note": "Kripto (USDT) ve BIST (TRY) ayrı kova; ağırlıklar göreli riski gösterir. "
                    "Komutlar platform venv python'uyla — global 'py' backend'i import edemez."}


def run_combo_search(level: str = "singles", universe: str = "kripto", top: int = 20,
                     basket_size: int = 6) -> dict:
    """Sistematik kombo arama (combo_search) — sepet üzerinde tekli/ikili göstergeleri
    tarayıp semboller-arası ort. Sharpe'a göre sıralar. UI'dan çalıştırılır (in-sample triage)."""
    dfs, _ = _load_universe(universe)
    if len(dfs) < 2:
        raise ValueError(f"yetersiz varlık ({len(dfs)}) — evren: {universe}")
    # hız için sepeti sınırla (in-sample triage; tam arama scriptlerde)
    basket = dict(list(dfs.items())[:max(2, basket_size)])
    if level == "singles":
        res = CS.rank_singles(basket)
    elif level == "pairs":
        res = CS.rank_pairs(PAIR_SHORTLIST, basket, cross_cat_only=True)
    else:
        raise ValueError(f"bilinmeyen seviye: {level} (singles|pairs)")
    rows = [{"name": "+".join(r["names"]), "sharpe": r["sharpe"], "total_return": r["ret"],
             "max_drawdown": r["dd"], "num_trades": r["trades"], "prof_pct": r["prof_pct"],
             "beat_bh": r["beat_bh"], "score": r["score"]}
            for r in res if r["n"] > 0][:top]
    return {"level": level, "universe": universe, "n_basket": len(basket),
            "basket": list(basket.keys()), "results": rows}
