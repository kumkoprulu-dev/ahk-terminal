"""Parametre optimizasyonu — şablon kural + parametre aralıkları.

Kural şablonunda `{param}` yer tutucuları kullanılır, örn:
    entry = "EMA({fast}) > EMA({slow}) AND RSI({rsi}) < 40"
    params = [{name:"fast",min:5,max:50,step:5}, {name:"slow",min:20,max:200,step:10}, ...]

Sistem kombinasyonları üretir, her birini (önceden çekilmiş veride) backtest eder ve
seçilen hedef metriğe göre sıralar. Yöntemler Optuna ile birleşik:
    grid   -> GridSampler (tüm/altküme kombinasyonlar)
    random -> RandomSampler
    bayes  -> TPESampler (Bayesian)
"""
from __future__ import annotations

import re

import optuna

from app.backtest import engine
from app.data import service

optuna.logging.set_verbosity(optuna.logging.WARNING)

_PLACEHOLDER = re.compile(r"\{(\w+)\}")

# Hedef metrik -> hep "maximize" (max_drawdown negatif saklandığından maksimize doğru yön)
OBJECTIVES = {
    "total_return", "sharpe", "sortino", "calmar",
    "profit_factor", "win_rate", "max_drawdown",
}
_RESULT_KEYS = ("total_return", "sharpe", "sortino", "max_drawdown",
                "calmar", "profit_factor", "win_rate", "num_trades")


def find_placeholders(*templates: str | None) -> list[str]:
    names: list[str] = []
    for t in templates:
        if not t:
            continue
        for m in _PLACEHOLDER.finditer(t):
            if m.group(1) not in names:
                names.append(m.group(1))
    return names


def substitute(template: str | None, params: dict) -> str | None:
    if not template:
        return template
    out = template
    for k, v in params.items():
        out = out.replace("{" + k + "}", str(int(v)))
    return out


def _score(metrics: dict, objective: str) -> float:
    if not metrics or metrics.get("num_trades", 0) == 0:
        return -1e9
    val = metrics.get(objective)
    return float(val) if val is not None else -1e9


def run_optimization(
    symbol: str,
    entry_template: str,
    exit_template: str | None = None,
    params: list[dict] | None = None,
    interval: str = "1d",
    range_: str = "2y",
    method: str = "bayes",
    objective: str = "sharpe",
    n_trials: int = 200,
    max_combos: int = 2000,
    fee_bps: float = 10.0,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    direction: str = "long",
) -> dict:
    params = params or []
    if objective not in OBJECTIVES:
        objective = "sharpe"

    names = [p["name"] for p in params]
    missing = [n for n in find_placeholders(entry_template, exit_template) if n not in names]
    if missing:
        raise ValueError(f"Aralığı tanımlanmamış parametre(ler): {', '.join(missing)}")
    if not params:
        raise ValueError("En az bir parametre aralığı gerekli ({param} yer tutucusu).")

    df = service.get_ohlcv(symbol, interval, range_)
    if df is None or len(df) < 30:
        raise ValueError(f"Yetersiz veri: {symbol}")

    out = optimize_on(
        df, entry_template, exit_template, params, interval=interval, method=method,
        objective=objective, n_trials=n_trials, max_combos=max_combos, fee_bps=fee_bps,
        stop_loss=stop_loss, take_profit=take_profit, direction=direction,
    )
    out["symbol"] = symbol
    return out


def optimize_on(
    df,
    entry_template: str,
    exit_template: str | None,
    params: list[dict],
    interval: str = "1d",
    method: str = "bayes",
    objective: str = "sharpe",
    n_trials: int = 200,
    max_combos: int = 2000,
    fee_bps: float = 10.0,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    direction: str = "long",
    top: int = 60,
) -> dict:
    """Önceden çekilmiş (ya da dilimlenmiş) df üzerinde optimizasyon — walk-forward bunu kullanır."""
    if objective not in OBJECTIVES:
        objective = "sharpe"

    # Arama uzayı ve toplam kombinasyon
    space: dict[str, list[int]] = {}
    total_combos = 1
    for p in params:
        lo, hi, st = int(p["min"]), int(p["max"]), max(int(p.get("step", 1) or 1), 1)
        vals = list(range(lo, min(hi, lo if hi < lo else hi) + 1, st)) or [lo]
        space[p["name"]] = vals
        total_combos *= len(vals)

    results: list[dict] = []
    seen: set[tuple] = set()

    def objective_fn(trial: optuna.Trial) -> float:
        pdict = {}
        for p in params:
            lo, hi, st = int(p["min"]), int(p["max"]), max(int(p.get("step", 1) or 1), 1)
            pdict[p["name"]] = trial.suggest_int(p["name"], lo, max(hi, lo), step=st)
        key = tuple(sorted(pdict.items()))
        if key in seen:
            return _score(_last_metrics.get(key, {}), objective)
        e = substitute(entry_template, pdict)
        x = substitute(exit_template, pdict)
        try:
            res = engine.simulate(
                df, entry_rule=e, exit_rule=x, interval=interval,
                fee_bps=fee_bps, stop_loss=stop_loss, take_profit=take_profit,
                direction=direction, light=True,
            )
            m = res["metrics"]
        except Exception:
            m = {}
        sc = _score(m, objective)
        seen.add(key)
        _last_metrics[key] = m
        if m:
            results.append({
                "params": pdict,
                "score": round(sc, 4) if sc > -1e8 else None,
                "metrics": {k: m.get(k) for k in _RESULT_KEYS},
            })
        return sc

    _last_metrics: dict = {}

    if method == "grid":
        sampler = optuna.samplers.GridSampler(space)
        n = min(total_combos, max_combos)
    elif method == "random":
        sampler = optuna.samplers.RandomSampler(seed=42)
        n = min(n_trials, total_combos)
    else:
        method = "bayes"
        sampler = optuna.samplers.TPESampler(seed=42)
        n = min(n_trials, total_combos)

    study = optuna.create_study(direction="maximize", sampler=sampler)
    study.optimize(objective_fn, n_trials=int(n))

    results.sort(key=lambda r: (r["score"] is None, -(r["score"] if r["score"] is not None else -1e9)))
    best = results[0] if results else None
    return {
        "method": method,
        "objective": objective,
        "total_combos": total_combos,
        "evaluated": len(results),
        "best": best,
        "results": results[:top],
        "entry_template": entry_template,
        "exit_template": exit_template,
    }


def validate_templates(entry_template: str, exit_template: str | None, params: list[dict]) -> None:
    """Orta değerlerle yerine koyup DSL'i doğrular."""
    from app.scanner.dsl import parse

    mid = {p["name"]: (int(p["min"]) + int(p["max"])) // 2 for p in (params or [])}
    parse(substitute(entry_template, mid))
    if exit_template and exit_template.strip():
        parse(substitute(exit_template, mid))
