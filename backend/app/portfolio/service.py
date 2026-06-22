"""Portföy optimizasyonu orkestrasyonu: ağırlıklar + metrikler + etkin sınır + Monte Carlo."""
from __future__ import annotations

import numpy as np

import pandas as pd

from app.portfolio import advanced, optimizer, quantum, risk
from app.portfolio.data import load_prices, returns_stats
from app.portfolio.optimizer import METHODS, perf


def _weights_for(method: str, mu, sigma, risk_tolerance: float,
                 rets: "pd.DataFrame" = None, price: "pd.DataFrame" = None) -> np.ndarray:
    if method == "quantum":
        return quantum.quantum_weights(mu, sigma, risk_tolerance=risk_tolerance)
    if method == "cvar":
        return advanced.cvar_optimization(rets)
    if method == "black_litterman":
        return advanced.black_litterman(mu, sigma, price)
    fn = optimizer.CLASSIC.get(method)
    if fn is None:
        raise ValueError(f"Bilinmeyen yöntem: {method}")
    return fn(mu, sigma)


def _apply_fusion_tilt(w: np.ndarray, used: list[str], interval: str, range_: str) -> np.ndarray:
    """Optimize ağırlıkları TechScore ile eğer: yüksek skor → fazla ağırlık, düşük → az.
    mult = 0.5 + skor/100 (skor 50→1.0, 100→1.5, 0→0.5)."""
    from concurrent.futures import ThreadPoolExecutor

    from app.data import service as data_service
    from app.indicators import compute

    def _score(sym):
        try:
            df = data_service.get_ohlcv(sym, interval, range_)
            ts = compute("TechScore", df)["TechScore"].iloc[-1]
            return float(ts) if ts == ts else 50.0
        except Exception:
            return 50.0

    with ThreadPoolExecutor(max_workers=8) as ex:
        scores = np.array(list(ex.map(_score, used)))
    mult = np.clip(0.5 + scores / 100.0, 0.3, 1.8)
    tw = w * mult
    total = tw.sum()
    return tw / total if total > 0 else w


def optimize(
    symbols: list[str],
    interval: str = "1d",
    range_: str = "2y",
    method: str = "max_sharpe",
    risk_tolerance: float = 0.5,
    mc_horizon: int = 21,
    frontier: bool = True,
    min_fundamental: float | None = None,
    fusion_tilt: bool = False,
) -> dict:
    symbols = [s for s in dict.fromkeys(symbols) if s.strip()]
    if len(symbols) < 2:
        raise ValueError("En az 2 sembol gerekli.")
    if method not in METHODS:
        raise ValueError(f"Bilinmeyen yöntem: {method}")

    filtered_out: list[str] = []
    if min_fundamental and min_fundamental > 0:
        from concurrent.futures import ThreadPoolExecutor

        from app.fundamentals.service import analyze

        def _keep(s):
            try:
                sc = analyze(s)["score"]
            except Exception:
                sc = None
            return s, (sc is None or sc >= min_fundamental)

        with ThreadPoolExecutor(max_workers=8) as ex:
            kept = list(ex.map(_keep, symbols))
        symbols = [s for s, k in kept if k]
        filtered_out = [s for s, k in kept if not k]
        if len(symbols) < 2:
            raise ValueError(f"Temel filtre (≥{min_fundamental}) sonrası 2'den az sembol kaldı.")

    price = load_prices(symbols, interval, range_)
    if price.empty or price.shape[1] < 2:
        raise ValueError("Yeterli veri çekilemedi (en az 2 sembol).")
    used = list(price.columns)
    mu, sigma, rets = returns_stats(price, interval)

    w = _weights_for(method, mu, sigma, risk_tolerance, rets=rets, price=price)
    if fusion_tilt:
        w = _apply_fusion_tilt(w, used, interval, range_)
    ret, vol, sharpe = perf(w, mu, sigma)

    weights = sorted(
        [{"symbol": used[i], "weight": round(float(w[i]) * 100, 2)} for i in range(len(used)) if w[i] > 1e-4],
        key=lambda d: d["weight"], reverse=True,
    )

    # Tüm yöntemlerin karşılaştırması (getiri/risk/sharpe)
    comparison = []
    for m in METHODS:
        try:
            wm = _weights_for(m, mu, sigma, risk_tolerance, rets=rets, price=price)
            r, v, s = perf(wm, mu, sigma)
            comparison.append({"method": m, "label": METHODS[m],
                               "return": round(r * 100, 2), "risk": round(v * 100, 2),
                               "sharpe": round(s, 3), "n_assets": int(np.sum(wm > 1e-4))})
        except Exception:
            continue
    comparison.sort(key=lambda d: d["sharpe"], reverse=True)

    out = {
        "symbols": used,
        "n_assets_total": len(used),
        "filtered_out": filtered_out,
        "method": method,
        "method_label": METHODS[method],
        "weights": weights,
        "metrics": {
            "exp_return": round(ret * 100, 2),
            "volatility": round(vol * 100, 2),
            "sharpe": round(sharpe, 3),
            "n_holdings": len(weights),
        },
        "comparison": comparison,
        "point": {"return": round(ret * 100, 2), "risk": round(vol * 100, 2)},
        "montecarlo": risk.monte_carlo(w, rets, horizon_days=mc_horizon),
    }
    if frontier:
        out["frontier"] = optimizer.efficient_frontier(mu, sigma)
        out["cloud"] = optimizer.random_cloud(mu, sigma)
    return out
