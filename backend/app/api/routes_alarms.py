"""Alarmlar — sembol + DSL kuralı; kural son barda sağlanınca tetiklenir.

Hesap sistemindeki saved_items (kind='alarm', data={symbol, rule}) üzerine kuruludur.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.accounts import service as acc
from app.api.routes_auth import current_user
from app.data import service as data_service
from app.scanner.dsl import DSLError, evaluate, parse

router = APIRouter(prefix="/api/alarms", tags=["alarms"])


class AlarmReq(BaseModel):
    name: str
    symbol: str
    rule: str


@router.post("")
def create(req: AlarmReq, user: dict = Depends(current_user)):
    try:
        parse(req.rule)
    except DSLError as e:
        raise HTTPException(400, f"Kural hatası: {e}")
    if not req.symbol.strip():
        raise HTTPException(400, "Sembol gerekli.")
    acc.save_item(user["id"], "alarm", req.name, {"symbol": req.symbol.strip(), "rule": req.rule.strip()})
    return {"ok": True}


@router.get("")
def list_alarms(user: dict = Depends(current_user)):
    return {"alarms": acc.list_items(user["id"], "alarm")}


@router.delete("/{item_id}")
def delete(item_id: int, user: dict = Depends(current_user)):
    acc.delete_item(user["id"], item_id)
    return {"ok": True}


@router.get("/check")
def check(user: dict = Depends(current_user)):
    """Aktif alarmları son barda değerlendirir, tetiklenenleri döndürür."""
    alarms = acc.list_items(user["id"], "alarm")

    def _one(a):
        d = a["data"]
        try:
            df = data_service.get_ohlcv(d["symbol"], "1d", "6mo")
            if df is None or len(df) < 30:
                return None
            sig = evaluate(df, d["rule"])
            if bool(sig.iloc[-1]):
                return {"id": a["id"], "name": a["name"], "symbol": d["symbol"],
                        "rule": d["rule"], "price": round(float(df["close"].iloc[-1]), 4)}
        except Exception:
            return None
        return None

    triggered = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for r in ex.map(_one, alarms):
            if r:
                triggered.append(r)
    return {"count": len(alarms), "triggered": triggered}
