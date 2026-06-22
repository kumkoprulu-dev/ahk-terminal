"""Monte Carlo stres testi: portföy VaR / CVaR ve başarı olasılıkları (Q-BIST'ten uyarlandı)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def monte_carlo(
    weights: np.ndarray,
    rets: pd.DataFrame,
    horizon_days: int = 21,
    n_sims: int = 10000,
    confidence: float = 0.95,
    seed: int = 7,
) -> dict:
    """Çok değişkenli normal dağılımdan senaryo üretip portföy getiri dağılımını çıkarır.

    horizon_days: ufuk (örn. 21 ≈ 1 ay). VaR/CVaR bu ufuk için kümülatif getiridir.
    """
    rng = np.random.default_rng(seed)
    mean = rets.mean().values
    cov = rets.cov().values
    n_assets = len(weights)

    # horizon_days günlük yolları topla (basit toplam ≈ log-getiri yaklaşımı)
    sims = rng.multivariate_normal(mean, cov, size=(n_sims, horizon_days))  # (n, h, assets)
    port_daily = sims @ weights                                            # (n, h)
    port_cum = port_daily.sum(axis=1)                                      # ufuk getirisi

    alpha = (1 - confidence) * 100
    var = -np.percentile(port_cum, alpha)            # pozitif sayı = kayıp
    tail = port_cum[port_cum <= -var]
    cvar = -tail.mean() if len(tail) else var

    return {
        "horizon_days": horizon_days,
        "confidence": int(confidence * 100),
        "var": round(float(var) * 100, 2),                # % kayıp
        "cvar": round(float(cvar) * 100, 2),
        "prob_positive": round(float(np.mean(port_cum > 0)) * 100, 1),
        "expected": round(float(np.mean(port_cum)) * 100, 2),
        "best": round(float(np.percentile(port_cum, 95)) * 100, 2),
        "worst": round(float(np.percentile(port_cum, 1)) * 100, 2),
        # histogram (frontend için 40 kova)
        "hist": _histogram(port_cum * 100, bins=40),
    }


def _histogram(x: np.ndarray, bins: int = 40) -> list[dict]:
    counts, edges = np.histogram(x, bins=bins)
    return [{"x": round(float((edges[i] + edges[i + 1]) / 2), 2), "n": int(counts[i])}
            for i in range(len(counts))]
