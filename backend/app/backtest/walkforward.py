"""Walk-Forward Analizi.

Veri ardışık eğitim/test pencerelerine bölünür. Her pencerede parametreler EĞİTİM
diliminde optimize edilir, bulunan en iyi parametre bir sonraki TEST diliminde
(out-of-sample / OOS) sınanır. Tüm OOS test sonuçları tek bir sürekli equity eğrisinde
birleştirilir. Bu, eğitimde ezberleyip testte çöken (overfit) stratejileri ortaya çıkarır.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.backtest import engine, optimizer
from app.backtest.metrics import equity_metrics
from app.data import service

MAX_FOLDS = 40


def _is_daily(interval: str) -> bool:
    return interval in ("1d", "1wk", "1mo")


def _fmt_t(t, interval):
    return t.strftime("%Y-%m-%d") if _is_daily(interval) else int(t.timestamp())


def run_walk_forward(
    symbol: str,
    entry_template: str,
    exit_template: str | None = None,
    params: list[dict] | None = None,
    interval: str = "1d",
    range_: str = "5y",
    method: str = "bayes",
    objective: str = "sharpe",
    n_trials: int = 60,
    train_bars: int = 252,
    test_bars: int = 63,
    fee_bps: float = 10.0,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    direction: str = "long",
    initial_cash: float = 10_000.0,
) -> dict:
    params = params or []
    names = [p["name"] for p in params]
    missing = [n for n in optimizer.find_placeholders(entry_template, exit_template) if n not in names]
    if missing:
        raise ValueError(f"Aralığı tanımlanmamış parametre(ler): {', '.join(missing)}")
    if not params:
        raise ValueError("En az bir parametre aralığı gerekli ({param} yer tutucusu).")
    train_bars, test_bars = int(train_bars), int(test_bars)
    if train_bars < 30 or test_bars < 5:
        raise ValueError("Eğitim ≥30, test ≥5 bar olmalı.")

    df = service.get_ohlcv(symbol, interval, range_)
    if df is None or len(df) < train_bars + test_bars + 5:
        raise ValueError("Yetersiz veri: eğitim+test penceresi mevcut veriden büyük.")

    n = len(df)
    folds: list[dict] = []
    seg_equities: list[pd.Series] = []
    start = 0
    fold_no = 0

    while start + train_bars + test_bars <= n and fold_no < MAX_FOLDS:
        train = df.iloc[start:start + train_bars]
        test = df.iloc[start + train_bars:start + train_bars + test_bars]
        fold_no += 1

        opt = optimizer.optimize_on(
            train, entry_template, exit_template, params, interval=interval, method=method,
            objective=objective, n_trials=n_trials, fee_bps=fee_bps, stop_loss=stop_loss,
            take_profit=take_profit, direction=direction, top=1,
        )
        best = opt["best"]
        base = {
            "fold": fold_no,
            "train_start": _fmt_t(train.index[0], interval), "train_end": _fmt_t(train.index[-1], interval),
            "test_start": _fmt_t(test.index[0], interval), "test_end": _fmt_t(test.index[-1], interval),
        }
        if not best:
            folds.append({**base, "params": None, "is_score": None,
                          "oos_return": None, "oos_sharpe": None, "oos_maxdd": None, "oos_trades": 0})
            start += test_bars
            continue

        e = optimizer.substitute(entry_template, best["params"])
        x = optimizer.substitute(exit_template, best["params"])
        # Test simülasyonu eğitim verisini ısınma (warmup) olarak içerir → göstergeler
        # test başında doğru hesaplanır, işlemler yalnız test bölgesinde açılır.
        test_full = df.iloc[start:start + train_bars + test_bars]
        tr = engine.simulate(
            test_full, symbol=symbol, entry_rule=e, exit_rule=x, interval=interval,
            initial_cash=initial_cash, fee_bps=fee_bps, stop_loss=stop_loss,
            take_profit=take_profit, direction=direction, light=False, warmup=train_bars,
        )
        tm = tr["metrics"]
        eq_vals = [pt["value"] for pt in tr["equity"]]
        if len(eq_vals) >= 2:
            seg_equities.append(pd.Series(eq_vals, index=test.index[:len(eq_vals)]))
        folds.append({
            **base, "params": best["params"], "is_score": best["score"],
            "oos_return": tm.get("total_return"), "oos_sharpe": tm.get("sharpe"),
            "oos_maxdd": tm.get("max_drawdown"), "oos_trades": tm.get("num_trades"),
        })
        start += test_bars

    # OOS equity birleştirme (zincirleme getiriler)
    oos_idx, oos_vals = [], []
    running = initial_cash
    for seg in seg_equities:
        b = seg.iloc[0]
        for t, v in seg.items():
            oos_idx.append(t)
            oos_vals.append(running * (v / b if b else 1.0))
        running *= (seg.iloc[-1] / b if b else 1.0)
    combined = pd.Series(oos_vals, index=pd.DatetimeIndex(oos_idx)) if oos_vals else pd.Series(dtype=float)
    oos_metrics = equity_metrics(combined, interval) if len(combined) > 1 else {}

    valid = [f for f in folds if f.get("params")]
    oos_rets = [f["oos_return"] for f in valid if f["oos_return"] is not None]
    is_scores = [f["is_score"] for f in valid if f["is_score"] is not None]
    profitable = sum(1 for r in oos_rets if r > 0)

    summary = {
        "folds": len(folds),
        "valid_folds": len(valid),
        "profitable_folds": profitable,
        "profitable_pct": round(profitable / len(oos_rets) * 100, 1) if oos_rets else 0,
        "avg_oos_return": round(float(np.mean(oos_rets)), 2) if oos_rets else 0,
        "avg_is_score": round(float(np.mean(is_scores)), 3) if is_scores else 0,
        "oos_total_return": oos_metrics.get("total_return", 0),
        "oos_sharpe": oos_metrics.get("sharpe", 0),
        "oos_max_drawdown": oos_metrics.get("max_drawdown", 0),
        "final_equity": round(float(running), 2),
    }
    equity = [{"time": _fmt_t(t, interval), "value": round(float(v), 2)}
              for t, v in zip(combined.index, combined.values)]

    return {
        "symbol": symbol, "interval": interval, "range": range_, "method": method,
        "objective": objective, "train_bars": train_bars, "test_bars": test_bars,
        "summary": summary, "folds": folds, "equity": equity,
        "entry_template": entry_template, "exit_template": exit_template,
    }
