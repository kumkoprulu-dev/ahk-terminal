"""Metinden formül (doğal dil → DSL) uç noktası."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.nlp.formula import to_formula

router = APIRouter(prefix="/api/formula", tags=["formula"])


class FormulaRequest(BaseModel):
    text: str


@router.post("")
def formula(req: FormulaRequest):
    return to_formula(req.text)
