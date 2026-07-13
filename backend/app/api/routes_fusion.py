"""Füzyon (Teknik + Haber + Temel) uç noktaları."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.fusion import engine

router = APIRouter(prefix="/api/fusion", tags=["fusion"])


@router.get("")
def fusion_symbol(symbol: str):
    return engine.fuse(symbol)


class WeightSpec(BaseModel):
    technical: float = 0.32
    sentiment: float = 0.20
    fundamental: float = 0.28
    edge: float = 0.20


class GroupRequest(BaseModel):
    group: str
    weights: WeightSpec | None = None
    with_sentiment: bool = True


@router.post("/group")
def fusion_group(req: GroupRequest):
    w = req.weights.model_dump() if req.weights else None
    return engine.fuse_group(req.group, weights=w, with_sentiment=req.with_sentiment)
