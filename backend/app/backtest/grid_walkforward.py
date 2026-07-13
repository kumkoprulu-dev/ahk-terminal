"""Grid stratejisi için Walk-Forward analizi.

Metodoloji walkforward.py ile aynı: veri ardışık EĞİTİM/TEST pencerelerine bölünür,
parametreler eğitimde optimize edilir, bir sonraki TEST diliminde (OOS) sınanır, tüm
OOS sonuçları tek equity eğrisinde birleşir → overfit ortaya çıkar. Fark: DSL yerine
grid.simulate ve grid parametre uzayı (buy/sell adımı, max kademe, regime_MA).

Bear defansı (exit_regime_break) her zaman açık — canlı aday baz config bu.
Lot boyutu sermayeye bağlanır: lot_quote = initial_cash / max_tiers (tam dağıtım).
"""
from __future__ import annotations

import numpy as np
import optuna
import pandas as pd

from app.backtest import grid
from app.backtest.metrics import equity_metrics
from app.data import okx_provider

optuna.logging.set_verbosity(optuna.logging.WARNING)

MAX_FOLDS = 40
OBJECTIVES = {"total_return", "sharpe", "sortino", "calmar", "profit_factor", "win_rate", "max_drawdown"}

# Optimize edilen grid parametre uzayı (aralıklar) — swing (4h+) için
SPACE = {
    "buy_step_pct":  (1.5, 6.0),   # float
    "sell_step_pct": (1.5, 6.0),   # float
    "max_tiers":     (4, 12),      # int
    "regime_ma":     (100, 300),   # int, adım 25
}
# Gün içi (1h/15m/5m/1m) için dar adım uzayı — maker emirle çok sayıda tur
SPACE_INTRADAY = {
    "buy_step_pct":  (0.4, 2.0),
    "sell_step_pct": (0.4, 2.0),
    "max_tiers":     (4, 12),
    "regime_ma":     (100, 400),
    "er_max":        (0.2, 0.5),   # range kapısı eşiği (varlık/rejim seçimi) — optimize edilir
}


def _score(m: dict, objective: str) -> float:
    if not m or m.get("num_trades", 0) == 0:
        return -1e9
    v = m.get(objective)
    return float(v) if v is not None else -1e9


def _suggest(trial: optuna.Trial, space: dict) -> dict:
    fstep = 0.1 if space["buy_step_pct"][1] <= 2.5 else 0.5  # dar uzayda ince adım
    p = {
        "buy_step_pct": round(trial.suggest_float("buy_step_pct", *space["buy_step_pct"], step=fstep), 2),
        "sell_step_pct": round(trial.suggest_float("sell_step_pct", *space["sell_step_pct"], step=fstep), 2),
        "max_tiers": trial.suggest_int("max_tiers", *space["max_tiers"]),
        "regime_ma": trial.suggest_int("regime_ma", space["regime_ma"][0], space["regime_ma"][1], step=25),
    }
    if "er_max" in space:
        p["er_max"] = round(trial.suggest_float("er_max", *space["er_max"], step=0.05), 2)
    return p


def _run(df, p: dict, *, interval, initial_cash, fee_bps, warmup=0, light=True, fixed=None) -> dict:
    fixed = fixed or {}
    return grid.simulate(
        df, interval=interval, initial_cash=initial_cash,
        lot_quote=initial_cash / p["max_tiers"],
        buy_step_pct=p["buy_step_pct"], sell_step_pct=p["sell_step_pct"],
        max_tiers=p["max_tiers"], fee_bps=fee_bps,
        regime_ma=p["regime_ma"], exit_regime_break=True,
        er_max=p.get("er_max", 1.0),
        er_period=fixed.get("er_period", 0),
        pyramid_add=fixed.get("pyramid_add", 0.0),
        heyecan_ma=fixed.get("heyecan_ma", 0),
        warmup=warmup, light=light,
    )


def optimize_on(df_train, *, interval, objective, method, n_trials, initial_cash, fee_bps, space=SPACE, fixed=None) -> dict | None:
    best = {"score": -1e9, "params": None, "metrics": None}

    def obj(trial):
        p = _suggest(trial, space)
        try:
            m = _run(df_train, p, interval=interval, initial_cash=initial_cash, fee_bps=fee_bps, fixed=fixed)["metrics"]
        except Exception:
            m = {}
        sc = _score(m, objective)
        if sc > best["score"]:
            best.update(score=sc, params=p, metrics=m)
        return sc

    sampler = optuna.samplers.TPESampler(seed=42) if method == "bayes" else optuna.samplers.RandomSampler(seed=42)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    study.optimize(obj, n_trials=int(n_trials))
    return best if best["params"] else None


def run(
    symbol: str = "SOL-USDT-SWAP",
    interval: str = "4h",
    bars: int = 6000,
    train_bars: int = 1200,
    test_bars: int = 300,
    method: str = "bayes",
    objective: str = "sharpe",
    n_trials: int = 40,
    initial_cash: float = 10_000.0,
    fee_bps: float = 8.0,
    space: dict | None = None,
    er_period: int = 0,
    pyramid_add: float = 0.0,
    heyecan_ma: int = 0,
) -> dict:
    if objective not in OBJECTIVES:
        objective = "sharpe"
    if space is None:
        space = SPACE_INTRADAY if interval in ("1m", "5m", "15m", "30m", "1h") else SPACE
    fixed = {"er_period": er_period, "pyramid_add": pyramid_add, "heyecan_ma": heyecan_ma}
    df = okx_provider.get_ohlcv(symbol, interval, bars=bars)
    if df.empty or len(df) < train_bars + test_bars + 5:
        raise ValueError("Yetersiz veri: eğitim+test penceresi mevcut veriden büyük.")

    n = len(df)
    folds: list[dict] = []
    seg_eq: list[pd.Series] = []
    start = 0
    fold_no = 0

    while start + train_bars + test_bars <= n and fold_no < MAX_FOLDS:
        train = df.iloc[start:start + train_bars]
        test = df.iloc[start + train_bars:start + train_bars + test_bars]
        fold_no += 1

        best = optimize_on(train, interval=interval, objective=objective, method=method,
                           n_trials=n_trials, initial_cash=initial_cash, fee_bps=fee_bps, space=space, fixed=fixed)
        base = {
            "fold": fold_no,
            "train_start": _t(train.index[0]), "train_end": _t(train.index[-1]),
            "test_start": _t(test.index[0]), "test_end": _t(test.index[-1]),
        }
        if not best:
            folds.append({**base, "params": None, "is_score": None,
                          "oos_return": None, "oos_sharpe": None, "oos_maxdd": None, "oos_trades": 0})
            start += test_bars
            continue

        # OOS: train'i ısınma olarak dahil et → regime_MA test başında tanımlı
        test_full = df.iloc[start:start + train_bars + test_bars]
        tr = _run(test_full, best["params"], interval=interval, initial_cash=initial_cash,
                  fee_bps=fee_bps, warmup=train_bars, light=False, fixed=fixed)
        tm = tr["metrics"]
        eq_vals = [pt["value"] for pt in tr["equity"]]
        if len(eq_vals) >= 2:
            seg_eq.append(pd.Series(eq_vals, index=test.index[:len(eq_vals)]))
        folds.append({
            **base, "params": best["params"], "is_score": round(best["score"], 4),
            "oos_return": tm.get("total_return"), "oos_sharpe": tm.get("sharpe"),
            "oos_maxdd": tm.get("max_drawdown"), "oos_trades": tm.get("num_trades"),
            "oos_open_end": tm.get("open_tiers_end"),
        })
        start += test_bars

    # OOS equity zincirleme
    oos_idx, oos_vals = [], []
    running = initial_cash
    for seg in seg_eq:
        b = seg.iloc[0]
        for t, v in seg.items():
            oos_idx.append(t)
            oos_vals.append(running * (v / b if b else 1.0))
        running *= (seg.iloc[-1] / b if b else 1.0)
    combined = pd.Series(oos_vals, index=pd.DatetimeIndex(oos_idx)) if oos_vals else pd.Series(dtype=float)
    oos_m = equity_metrics(combined, interval) if len(combined) > 1 else {}

    valid = [f for f in folds if f.get("params")]
    oos_rets = [f["oos_return"] for f in valid if f["oos_return"] is not None]
    profitable = sum(1 for r in oos_rets if r > 0)
    is_scores = [f["is_score"] for f in valid if f["is_score"] is not None]

    summary = {
        "folds": len(folds), "valid_folds": len(valid), "profitable_folds": profitable,
        "profitable_pct": round(profitable / len(oos_rets) * 100, 1) if oos_rets else 0,
        "avg_oos_return": round(float(np.mean(oos_rets)), 2) if oos_rets else 0,
        "avg_is_score": round(float(np.mean(is_scores)), 3) if is_scores else 0,
        "oos_total_return": oos_m.get("total_return", 0),
        "oos_sharpe": oos_m.get("sharpe", 0),
        "oos_max_drawdown": oos_m.get("max_drawdown", 0),
        "final_equity": round(float(running), 2),
    }
    return {
        "symbol": symbol, "interval": interval, "bars": n, "method": method,
        "objective": objective, "train_bars": train_bars, "test_bars": test_bars,
        "summary": summary, "folds": folds,
        "equity": [{"time": int(t.timestamp()), "value": round(float(v), 2)} for t, v in combined.items()],
    }


def _t(t) -> str:
    return t.strftime("%Y-%m-%d %H:%M")
