"""Backtest performans metrikleri (equity eğrisi ve trade listesinden)."""
from __future__ import annotations

import numpy as np
import pandas as pd

# Aralık -> yılda periyot sayısı (yıllıklandırma için)
PERIODS_PER_YEAR = {
    "1m": 252 * 390, "5m": 252 * 78, "15m": 252 * 26, "30m": 252 * 13,
    "1h": 252 * 7, "1d": 252, "1wk": 52, "1mo": 12,
}


def equity_metrics(equity: pd.Series, interval: str = "1d") -> dict:
    """Equity eğrisinden getiri/risk metrikleri."""
    ppy = PERIODS_PER_YEAR.get(interval, 252)
    equity = equity.dropna()
    if len(equity) < 2:
        return {}
    rets = equity.pct_change().dropna()
    n = len(rets)
    total_return = equity.iloc[-1] / equity.iloc[0] - 1
    years = n / ppy if ppy else 0
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else 0.0

    std = rets.std()
    sharpe = (rets.mean() / std * np.sqrt(ppy)) if std else 0.0
    downside = rets[rets < 0].std()
    sortino = (rets.mean() / downside * np.sqrt(ppy)) if downside else 0.0

    cummax = equity.cummax()
    drawdown = equity / cummax - 1
    max_dd = drawdown.min()
    calmar = (cagr / abs(max_dd)) if max_dd < 0 else 0.0

    vol = std * np.sqrt(ppy)
    return {
        "total_return": _pct(total_return),
        "cagr": _pct(cagr),
        "sharpe": _r(sharpe),
        "sortino": _r(sortino),
        "max_drawdown": _pct(max_dd),
        "calmar": _r(calmar),
        "volatility": _pct(vol),
    }


def trade_metrics(trades: list[dict]) -> dict:
    """Trade listesinden kazanma oranı, profit factor vb."""
    if not trades:
        return {"num_trades": 0, "win_rate": 0, "profit_factor": 0,
                "avg_win": 0, "avg_loss": 0, "avg_bars": 0, "best": 0, "worst": 0}
    pnls = np.array([t["pnl"] for t in trades])
    rets = np.array([t["return_pct"] for t in trades])  # yüzde
    win_mask = pnls > 0
    gross_win = pnls[win_mask].sum()
    gross_loss = -pnls[pnls < 0].sum()
    win_rets = rets[win_mask]
    loss_rets = rets[~win_mask]
    return {
        "num_trades": len(trades),
        "win_rate": _pct(int(win_mask.sum()) / len(trades)),
        "profit_factor": _r(gross_win / gross_loss) if gross_loss > 0 else (999.0 if gross_win > 0 else 0.0),
        "avg_win": _r(float(win_rets.mean())) if len(win_rets) else 0.0,    # yüzde
        "avg_loss": _r(float(loss_rets.mean())) if len(loss_rets) else 0.0,  # yüzde
        "avg_bars": _r(float(np.mean([t["bars"] for t in trades]))),
        "best": _r(float(rets.max())),
        "worst": _r(float(rets.min())),
    }


def _pct(x: float) -> float:
    return round(float(x) * 100, 2) if x == x else 0.0


def _r(x: float, d: int = 2) -> float:
    return round(float(x), d) if x == x else 0.0
