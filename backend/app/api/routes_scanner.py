"""Tarayıcı uç noktaları."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.scanner import engine
from app.scanner.dsl import DSLError

router = APIRouter(prefix="/api/scan", tags=["scanner"])

# Hazır örnek kurallar (frontend'de gösterilir)
EXAMPLES = [
    {"name": "Aşırı satım dönüşü", "rule": "RSI(14) < 35 AND Volume > SMA(Volume, 20)"},
    {"name": "Altın kesişim eğilimi", "rule": "EMA(20) > EMA(50) AND ADX(14) > 25"},
    {"name": "MACD yukarı kesişim", "rule": "MACD Cross Up AND RSI(14) > 50"},
    {"name": "Bollinger alt bandı", "rule": "Close < BollingerBands(20).Lower"},
    {"name": "Güçlü momentum", "rule": "ROC(12) > 5 AND CMF(20) > 0"},
    {"name": "Trend + hacim onayı", "rule": "Close > EMA(50) AND Volume > SMA(Volume, 20) AND ADX(14) > 20"},
    {"name": "Aşırı alım uyarısı", "rule": "RSI(14) > 70 AND Close > BollingerBands(20).Upper"},
    {"name": "Stokastik dip dönüşü", "rule": "Stochastic(14) < 20 AND MACD Cross Up"},
    {"name": "Düşüş trendi (short)", "rule": "EMA(20) < EMA(50) AND ADX(14) > 25"},
    {"name": "Para girişi (MFI+CMF)", "rule": "MFI(14) < 30 AND CMF(20) > 0.05"},
    {"name": "200 üstü teknik güç", "rule": "Close > EMA(200) AND TechScore > 60"},
    {"name": "CCI aşırı satım", "rule": "CCI(20) < -100 AND Close > EMA(50)"},
    {"name": "SuperTrend al", "rule": "SuperTrend.Direction > 0 AND RSI(14) > 50"},
    {"name": "Williams dip", "rule": "WilliamsR(14) < -80 AND Volume > SMA(Volume, 20)"},
    {"name": "Hacim patlaması", "rule": "Volume > SMA(Volume, 50) AND ROC(5) > 3"},
    {"name": "Sıkışma kırılımı", "rule": "Close > BollingerBands(20).Upper AND ADX(14) > 20"},
    {"name": "Güçlü teknik skor", "rule": "TechScore > 70"},
]


class ScanRequest(BaseModel):
    universe: str = "BIST"
    rule: str
    interval: str = "1d"
    range: str = "1y"


@router.get("/examples")
def scan_examples():
    return {"examples": EXAMPLES}


class ValidateRequest(BaseModel):
    rule: str


@router.post("/validate")
def scan_validate(req: ValidateRequest):
    try:
        engine.validate_rule(req.rule)
    except DSLError as e:
        return {"valid": False, "error": str(e)}
    return {"valid": True}


@router.post("")
def scan_run(req: ScanRequest):
    try:
        return engine.scan(req.universe, req.rule, req.interval, req.range)
    except DSLError as e:
        raise HTTPException(400, f"Kural hatası: {e}")
