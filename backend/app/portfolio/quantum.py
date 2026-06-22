"""Kuantum-İlhamlı portföy seçimi: QUBO + Simulated Annealing.

NOT: Bu GERÇEK kuantum donanımı değildir. Portföy seçimi NP-zor bir QUBO problemi
olarak formüle edilir ve kuantum tavlamanın (quantum annealing) klasik analoğu olan
Simulated Annealing ile çözülür — Boltzmann kabul kuralı + geometrik soğuma.
Q-BIST projesindeki yaklaşımdan uyarlanmış ve iyileştirilmiştir: SA yalnızca hangi
hisselerin portföye gireceğini seçer; seçilen alt küme içinde ağırlıklar Markowitz
(Max Sharpe) ile sürekli olarak belirlenir (eşit ağırlık yerine).

Gerçek kuantum (QAOA/D-Wave) ileride opsiyonel olarak eklenebilir; arayüz aynı kalır.
"""
from __future__ import annotations

import numpy as np

from app.portfolio.optimizer import _clean, max_sharpe


def sa_qubo_select(
    mu: np.ndarray,
    sigma: np.ndarray,
    risk_tolerance: float = 0.5,
    num_iterations: int = 3000,
    initial_temp: float = 10.0,
    cooling_rate: float = 0.99,
    seed: int | None = 42,
) -> np.ndarray:
    """QUBO enerjisini minimize ederek seçilecek hisseleri (ikili vektör) bulur.

    Enerji: E(x) = x^T (λ·Σ − diag(μ)) x  → riski cezalandırır, getiriyi ödüllendirir.
    """
    rng = np.random.default_rng(seed)
    n = len(mu)
    Q = risk_tolerance * sigma - np.diag(mu)

    state = rng.integers(2, size=n)
    if state.sum() == 0:
        state[rng.integers(n)] = 1
    cost = state @ Q @ state
    best, best_cost = state.copy(), cost
    temp = initial_temp

    for _ in range(num_iterations):
        nb = state.copy()
        flip = rng.integers(n)
        nb[flip] = 1 - nb[flip]
        if nb.sum() == 0:
            continue
        nb_cost = nb @ Q @ nb
        diff = nb_cost - cost
        if diff < 0 or rng.random() < np.exp(-diff / max(temp, 1e-9)):
            state, cost = nb, nb_cost
            if cost < best_cost:
                best, best_cost = state.copy(), cost
        temp *= cooling_rate

    return best


def quantum_weights(mu: np.ndarray, sigma: np.ndarray, risk_tolerance: float = 0.5,
                    weighting: str = "inverse_vol") -> np.ndarray:
    """SA-QUBO ile hisse seç → alt küme içinde ağırlıkları belirle.

    weighting:
      inverse_vol (varsayılan): ters-volatilite — kuantum SEÇİMİ + risk-dengeli ağırlık.
        Bu, Max Sharpe'tan (tek hisseye yoğunlaşır) belirgin biçimde farklı, daha dağıtık
        bir portföy verir; kuantum yönteminin ayırt edici çıktısı budur.
      equal: Q-BIST orijinali (eşit ağırlık).
      markowitz: seçilen alt kümede Max Sharpe (Markowitz'e yakınsar — karşılaştırmada
        ayrışmaz, o yüzden varsayılan değil).
    """
    sel = sa_qubo_select(mu, sigma, risk_tolerance=risk_tolerance)
    idx = np.where(sel == 1)[0]
    n = len(mu)
    w = np.zeros(n)
    if len(idx) == 0:
        return np.ones(n) / n
    if len(idx) == 1:
        w[idx] = 1.0
        return w
    if weighting == "equal":
        w[idx] = 1.0 / len(idx)
        return w
    if weighting == "markowitz":
        w[idx] = max_sharpe(mu[idx], sigma[np.ix_(idx, idx)])
        return _clean(w)
    # inverse_vol: 1/σ_i ağırlık (düşük volatiliteye daha çok pay)
    vol = np.sqrt(np.diag(sigma)[idx])
    inv = 1.0 / np.where(vol > 1e-9, vol, 1e-9)
    w[idx] = inv / inv.sum()
    return _clean(w)
