"""Gösterge uç noktaları: liste/metadata ve hesaplama."""
from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.data import service
from app.indicators import compute, list_indicators
from app.indicators.registry import REGISTRY, groups

router = APIRouter(prefix="/api/indicators", tags=["indicators"])


@router.get("")
def indicators_list():
    return {"count": len(REGISTRY), "groups": groups(), "indicators": list_indicators()}


class ComputeRequest(BaseModel):
    symbol: str
    indicator: str
    params: dict = {}
    interval: str = "1d"
    range: str = "1y"


@router.post("/compute")
def indicators_compute(req: ComputeRequest):
    spec = REGISTRY.get(req.indicator.upper())
    if spec is None:
        raise HTTPException(404, f"Bilinmeyen gösterge: {req.indicator}")
    df = service.get_ohlcv(req.symbol, req.interval, req.range)
    if df is None or df.empty:
        raise HTTPException(404, f"Veri bulunamadı: {req.symbol}")
    result = compute(req.indicator, df, req.params)

    series = {}
    for col in result.columns:
        points = []
        for idx, val in result[col].items():
            if val is None or (isinstance(val, float) and np.isnan(val)):
                continue
            t = idx.strftime("%Y-%m-%d") if req.interval in ("1d", "1wk", "1mo") else int(idx.timestamp())
            points.append({"time": t, "value": round(float(val), 6)})
        series[col] = points
    return {
        "symbol": req.symbol,
        "indicator": spec.name,
        "overlay": spec.overlay,
        "outputs": spec.outputs,
        "series": series,
    }
