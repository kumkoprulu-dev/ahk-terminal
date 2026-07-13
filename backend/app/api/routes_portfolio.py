"""Portföy optimizasyonu uç noktaları."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.backtest import edge_portfolios
from app.portfolio import service
from app.portfolio.optimizer import METHODS

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/methods")
def portfolio_methods():
    return {"methods": [{"id": k, "label": v} for k, v in METHODS.items()]}


@router.get("/edge/modes")
def edge_modes():
    """Edge portföy modları (Combo1/Combo2/cross-sectional/3-kollu)."""
    return {"modes": [{"id": k, "label": v} for k, v in edge_portfolios.MODES.items()]}


class EdgeRequest(BaseModel):
    mode: str = "combo1"
    universe: str = "kripto"
    oos_frac: float = 0.6


@router.post("/edge/run")
def edge_run(req: EdgeRequest):
    """Bir edge portföyünü sepet üzerinde koşar → metrikler + equity eğrisi."""
    try:
        return edge_portfolios.run_edge_portfolio(req.mode, req.universe, req.oos_frac)
    except ValueError as e:
        raise HTTPException(400, str(e))


class SearchRequest(BaseModel):
    level: str = "singles"
    universe: str = "kripto"
    top: int = 20
    basket_size: int = 6


@router.post("/edge/search")
def edge_search(req: SearchRequest):
    """Sistematik kombo arama (tekli/ikili gösterge tarama) → sıralı sonuç tablosu."""
    try:
        return edge_portfolios.run_combo_search(req.level, req.universe, req.top, req.basket_size)
    except ValueError as e:
        raise HTTPException(400, str(e))


class AllocRequest(BaseModel):
    crypto_total: float = 3000.0
    bist_total: float = 300000.0


@router.post("/edge/allocate")
def edge_allocate(req: AllocRequest):
    """3-kollu risk-paritesi sermaye dağılımı + hazır canlı başlatma komutları."""
    try:
        return edge_portfolios.allocate_capital(req.crypto_total, req.bist_total)
    except ValueError as e:
        raise HTTPException(400, str(e))


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
