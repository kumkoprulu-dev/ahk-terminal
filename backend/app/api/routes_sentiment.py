"""Duyarlılık (sentiment) uç noktaları."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.sentiment import engine

router = APIRouter(prefix="/api/sentiment", tags=["sentiment"])


@router.get("/backends")
def backends():
    return {"backends": engine.available_backends()}


@router.get("")
def sentiment_symbol(symbol: str, backend: str = "lexicon", limit: int = 6):
    return engine.get_sentiment(symbol, backend=backend, limit=limit)


class GroupRequest(BaseModel):
    group: str
    backend: str = "lexicon"
    limit: int = 4


@router.post("/group")
def sentiment_group(req: GroupRequest):
    return engine.get_group_sentiment(req.group, backend=req.backend, limit=req.limit)
