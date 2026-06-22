"""Temel analiz uç noktaları."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter
from pydantic import BaseModel

from app.data.universe import get_universe
from app.fundamentals import service

router = APIRouter(prefix="/api/fundamentals", tags=["fundamentals"])


@router.get("")
def fundamentals(symbol: str):
    return service.analyze(symbol)


class GroupRequest(BaseModel):
    group: str


@router.post("/group")
def fundamentals_group(req: GroupRequest):
    syms = [s.symbol for s in get_universe(req.group)]

    def _one(sym):
        try:
            a = service.analyze(sym)
            return {"symbol": sym, "name": a["name"], "score": a["score"],
                    "label": a["label"], "buckets": a["buckets"], "source": a["source"]}
        except Exception:
            return {"symbol": sym, "name": sym, "score": None, "label": "hata", "buckets": {}, "source": None}

    rows = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for r in ex.map(_one, syms):
            rows.append(r)
    rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or -1)))
    return {"group": req.group, "count": len(rows), "results": rows}
