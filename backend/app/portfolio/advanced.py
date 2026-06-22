"""İleri portföy yöntemleri: CVaR (Rockafellar-Uryasev LP) ve Black-Litterman."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import linprog

from app.portfolio.optimizer import _clean, max_sharpe


def cvar_optimization(rets: pd.DataFrame, alpha: float = 0.95) -> np.ndarray:
    """CVaR (Conditional Value at Risk) minimizasyonu — kuyruk riskini en aza indirir.

    Rockafellar-Uryasev doğrusal programı:
      min  var + 1/((1-α)T) Σ u_t
      s.t. u_t ≥ -r_t·w - var,  u_t ≥ 0,  Σw=1,  w≥0
    """
    R = rets.values
    T, n = R.shape
    if T < 10:
        return np.ones(n) / n
    # değişkenler: w(n), var(1), u(T)
    c = np.concatenate([np.zeros(n), [1.0], np.ones(T) / ((1 - alpha) * T)])
    A_ub = np.hstack([-R, -np.ones((T, 1)), -np.eye(T)])
    b_ub = np.zeros(T)
    A_eq = np.concatenate([np.ones(n), [0.0], np.zeros(T)]).reshape(1, -1)
    b_eq = [1.0]
    bounds = [(0, 1)] * n + [(None, None)] + [(0, None)] * T
    try:
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
        w = res.x[:n] if res.success else np.ones(n) / n
    except Exception:
        w = np.ones(n) / n
    return _clean(np.asarray(w))


def _momentum_views(price: pd.DataFrame, lookback: int = 63) -> np.ndarray:
    """Fiyatlardan momentum görüşü: son `lookback` gün getirisi, varlıklar arası standardize."""
    n = price.shape[1]
    lb = min(lookback, len(price) - 1)
    if lb < 5:
        return np.zeros(n)
    ret = price.iloc[-1].values / price.iloc[-1 - lb].values - 1.0
    mean, std = ret.mean(), ret.std()
    return (ret - mean) / std if std > 1e-9 else np.zeros(n)


def black_litterman(mu_hist: np.ndarray, sigma: np.ndarray, price: pd.DataFrame,
                    delta: float = 2.5, tau: float = 0.05, view_strength: float = 0.10) -> np.ndarray:
    """Black-Litterman: denge (equilibrium) öncülü + momentum görüşleri → posterior getiri.

    Eşit ağırlık piyasa öncülü Π = δ·Σ·w_eq; mutlak görüşler momentumdan türetilir.
    Posterior getiri Max Sharpe ile optimize edilir.
    """
    n = len(mu_hist)
    w_eq = np.ones(n) / n
    pi = delta * sigma @ w_eq  # denge getirileri

    z = _momentum_views(price)
    if np.allclose(z, 0):
        post = pi
    else:
        q = view_strength * z  # mutlak görüş: yıllık beklenen aşırı getiri ~
        P = np.eye(n)
        try:
            tau_sigma_inv = np.linalg.inv(tau * sigma + 1e-8 * np.eye(n))
            omega_inv = np.linalg.inv(np.diag(np.diag(tau * sigma)) + 1e-6 * np.eye(n))
            post = np.linalg.inv(tau_sigma_inv + P.T @ omega_inv @ P) @ (tau_sigma_inv @ pi + P.T @ omega_inv @ q)
        except np.linalg.LinAlgError:
            post = pi
    return max_sharpe(post, sigma)
