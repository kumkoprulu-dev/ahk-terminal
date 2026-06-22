"""Klasik portföy optimizasyon yöntemleri (ortalama-varyans tabanlı)."""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize

METHODS = {
    "max_sharpe": "Maksimum Sharpe (Markowitz)",
    "min_variance": "Minimum Varyans",
    "risk_parity": "Risk Parity",
    "max_return": "Maksimum Getiri",
    "cvar": "Minimum CVaR (kuyruk riski)",
    "black_litterman": "Black-Litterman (momentum görüşlü)",
    "equal_weight": "Eşit Ağırlık",
    "quantum": "Kuantum-İlhamlı (SA-QUBO)",
}


def perf(w: np.ndarray, mu: np.ndarray, sigma: np.ndarray) -> tuple[float, float, float]:
    """Portföy getiri, volatilite, Sharpe."""
    ret = float(w @ mu)
    vol = float(np.sqrt(w @ sigma @ w))
    sharpe = ret / vol if vol > 1e-12 else 0.0
    return ret, vol, sharpe


def _constraints(n):
    return ({"type": "eq", "fun": lambda x: np.sum(x) - 1},)


def _bounds(n):
    return tuple((0.0, 1.0) for _ in range(n))


def max_sharpe(mu, sigma) -> np.ndarray:
    n = len(mu)

    def neg_sharpe(w):
        ret, vol, _ = perf(w, mu, sigma)
        return -ret / (vol + 1e-9)

    res = minimize(neg_sharpe, np.ones(n) / n, method="SLSQP",
                   bounds=_bounds(n), constraints=_constraints(n))
    return _clean(res.x)


def min_variance(mu, sigma) -> np.ndarray:
    n = len(mu)
    res = minimize(lambda w: w @ sigma @ w, np.ones(n) / n, method="SLSQP",
                   bounds=_bounds(n), constraints=_constraints(n))
    return _clean(res.x)


def max_return(mu, sigma) -> np.ndarray:
    n = len(mu)
    res = minimize(lambda w: -(w @ mu), np.ones(n) / n, method="SLSQP",
                   bounds=_bounds(n), constraints=_constraints(n))
    return _clean(res.x)


def equal_weight(mu, sigma) -> np.ndarray:
    n = len(mu)
    return np.ones(n) / n


def risk_parity(mu, sigma) -> np.ndarray:
    """Her varlığın toplam riske katkısı eşit olacak şekilde."""
    n = len(mu)

    def obj(w):
        vol = np.sqrt(w @ sigma @ w) + 1e-12
        mrc = sigma @ w / vol            # marjinal risk katkısı
        rc = w * mrc                     # risk katkısı
        target = vol / n
        return np.sum((rc - target) ** 2)

    res = minimize(obj, np.ones(n) / n, method="SLSQP",
                   bounds=tuple((1e-4, 1.0) for _ in range(n)), constraints=_constraints(n))
    return _clean(res.x)


def efficient_frontier(mu, sigma, points: int = 30) -> list[dict]:
    """Hedef getiri ızgarasında minimum-volatilite portföyleri (etkin sınır)."""
    n = len(mu)
    lo, hi = float(mu.min()), float(mu.max())
    targets = np.linspace(lo, hi, points)
    out = []
    for t in targets:
        cons = (
            {"type": "eq", "fun": lambda x: np.sum(x) - 1},
            {"type": "eq", "fun": lambda x, t=t: x @ mu - t},
        )
        res = minimize(lambda w: w @ sigma @ w, np.ones(n) / n, method="SLSQP",
                       bounds=_bounds(n), constraints=cons)
        if res.success:
            ret, vol, sh = perf(res.x, mu, sigma)
            out.append({"return": round(ret * 100, 2), "risk": round(vol * 100, 2), "sharpe": round(sh, 3)})
    return out


def random_cloud(mu, sigma, n_port: int = 800, seed: int = 7) -> list[dict]:
    """Rastgele portföy bulutu (frontier'in arkasında scatter için)."""
    rng = np.random.default_rng(seed)
    n = len(mu)
    out = []
    for _ in range(n_port):
        w = rng.random(n)
        w /= w.sum()
        ret, vol, sh = perf(w, mu, sigma)
        out.append({"return": round(ret * 100, 2), "risk": round(vol * 100, 2), "sharpe": round(sh, 3)})
    return out


def _clean(w: np.ndarray) -> np.ndarray:
    w = np.clip(w, 0, None)
    w[w < 1e-4] = 0.0
    s = w.sum()
    return w / s if s > 0 else np.ones(len(w)) / len(w)


CLASSIC = {
    "max_sharpe": max_sharpe,
    "min_variance": min_variance,
    "max_return": max_return,
    "equal_weight": equal_weight,
    "risk_parity": risk_parity,
}
