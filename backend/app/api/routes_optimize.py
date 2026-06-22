"""Parametre optimizasyonu uç noktaları."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.backtest import optimizer
from app.scanner.dsl import DSLError

router = APIRouter(prefix="/api/optimize", tags=["optimize"])

EXAMPLES = [
    {"name": "EMA kesişim taraması",
     "entry": "EMA({fast}) > EMA({slow})", "exit": "EMA({fast}) < EMA({slow})",
     "params": [{"name": "fast", "min": 5, "max": 50, "step": 5},
                {"name": "slow", "min": 20, "max": 200, "step": 10}]},
    {"name": "RSI eşik optimizasyonu",
     "entry": "RSI({len}) < {buy}", "exit": "RSI({len}) > {sell}",
     "params": [{"name": "len", "min": 5, "max": 30, "step": 1},
                {"name": "buy", "min": 15, "max": 40, "step": 5},
                {"name": "sell", "min": 55, "max": 85, "step": 5}]},
    {"name": "Füzyon eşik optimizasyonu",
     "entry": "TechScore > {al}", "exit": "TechScore < {sat}",
     "params": [{"name": "al", "min": 55, "max": 75, "step": 5},
                {"name": "sat", "min": 30, "max": 50, "step": 5}]},
]


@router.get("/examples")
def optimize_examples():
    return {"examples": EXAMPLES, "objectives": sorted(optimizer.OBJECTIVES)}


class ParamSpec(BaseModel):
    name: str
    min: int
    max: int
    step: int = 1


class OptimizeRequest(BaseModel):
    symbol: str
    entry_template: str
    exit_template: str | None = None
    params: list[ParamSpec]
    interval: str = "1d"
    range: str = "2y"
    method: str = "bayes"          # grid | random | bayes
    objective: str = "sharpe"
    n_trials: int = 200
    fee_bps: float = 10.0
    stop_loss: float | None = None
    take_profit: float | None = None
    direction: str = "long"


@router.post("")
def optimize_run(req: OptimizeRequest):
    params = [p.model_dump() for p in req.params]
    try:
        optimizer.validate_templates(req.entry_template, req.exit_template, params)
    except DSLError as e:
        raise HTTPException(400, f"Kural hatası: {e}")
    try:
        return optimizer.run_optimization(
            symbol=req.symbol, entry_template=req.entry_template, exit_template=req.exit_template,
            params=params, interval=req.interval, range_=req.range, method=req.method,
            objective=req.objective, n_trials=req.n_trials, fee_bps=req.fee_bps,
            stop_loss=req.stop_loss, take_profit=req.take_profit, direction=req.direction,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
