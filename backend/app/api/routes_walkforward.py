"""Walk-Forward analizi uç noktası."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.backtest import optimizer, walkforward
from app.scanner.dsl import DSLError

router = APIRouter(prefix="/api/walkforward", tags=["walkforward"])


class ParamSpec(BaseModel):
    name: str
    min: int
    max: int
    step: int = 1


class WalkForwardRequest(BaseModel):
    symbol: str
    entry_template: str
    exit_template: str | None = None
    params: list[ParamSpec]
    interval: str = "1d"
    range: str = "5y"
    method: str = "bayes"
    objective: str = "sharpe"
    n_trials: int = 60
    train_bars: int = 252
    test_bars: int = 63
    fee_bps: float = 10.0
    stop_loss: float | None = None
    take_profit: float | None = None
    direction: str = "long"


@router.post("")
def walkforward_run(req: WalkForwardRequest):
    params = [p.model_dump() for p in req.params]
    try:
        optimizer.validate_templates(req.entry_template, req.exit_template, params)
    except DSLError as e:
        raise HTTPException(400, f"Kural hatası: {e}")
    try:
        return walkforward.run_walk_forward(
            symbol=req.symbol, entry_template=req.entry_template, exit_template=req.exit_template,
            params=params, interval=req.interval, range_=req.range, method=req.method,
            objective=req.objective, n_trials=req.n_trials, train_bars=req.train_bars,
            test_bars=req.test_bars, fee_bps=req.fee_bps, stop_loss=req.stop_loss,
            take_profit=req.take_profit, direction=req.direction,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
