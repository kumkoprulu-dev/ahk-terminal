"""Portföy optimizasyonu uç noktaları."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.portfolio import service
from app.portfolio.optimizer import METHODS

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/methods")
def portfolio_methods():
    return {"methods": [{"id": k, "label": v} for k, v in METHODS.items()]}


class PortfolioRequest(BaseModel):
    symbols: list[str]
    interval: str = "1d"
    range: str = "2y"
    method: str = "max_sharpe"
    risk_tolerance: float = 0.5
    mc_horizon: int = 21
    min_fundamental: float | None = None
    fusion_tilt: bool = False


@router.post("/optimize")
def portfolio_optimize(req: PortfolioRequest):
    try:
        return service.optimize(
            symbols=req.symbols, interval=req.interval, range_=req.range,
            method=req.method, risk_tolerance=req.risk_tolerance, mc_horizon=req.mc_horizon,
            min_fundamental=req.min_fundamental, fusion_tilt=req.fusion_tilt,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
