"""Backtest uç noktaları."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.backtest import engine
from app.scanner.dsl import DSLError

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

EXAMPLES = [
    # ⭐ Doğrulanmış edge'ler (combo_search + zamansal OOS + walk-forward'dan geçen keeper'lar)
    {"name": "Combo1 · SMA+Fisher+VWAP", "tag": "edge",
     "desc": "trend+momentum+hacim, long-only · all-weather · canlı KRİPTO sleeve (8091)",
     "entry": "Close > SMA(50) AND FisherTransform(9).Fisher > FisherTransform(9).Trigger AND Close > VWAP",
     "exit": "Close < SMA(50) OR FisherTransform(9).Fisher < FisherTransform(9).Trigger OR Close < VWAP"},
    {"name": "BIST Combo · HMA+Fisher+ForceIndex", "tag": "edge",
     "desc": "BIST'e özgü yükseltme (NNFX + 3 kat doğrulama, Combo1'i BIST30/50'de %62 geçti) · canlı BIST sleeve (8094)",
     "entry": "Close > HMA(20) AND FisherTransform(9).Fisher > FisherTransform(9).Trigger AND ForceIndex(13) > 0",
     "exit": "Close < HMA(20) OR FisherTransform(9).Fisher < FisherTransform(9).Trigger OR ForceIndex(13) < 0"},
    {"name": "Combo2 · Fisher+Force+Awesome", "tag": "edge",
     "desc": "momentum üçlüsü, agresif-boğa · OOS şampiyon",
     "entry": "FisherTransform(9).Fisher > FisherTransform(9).Trigger AND ForceIndex(13) > 0 AND AwesomeOsc(5,34) > 0",
     "exit": "FisherTransform(9).Fisher < FisherTransform(9).Trigger OR ForceIndex(13) < 0 OR AwesomeOsc(5,34) < 0"},
    {"name": "ZLEMA + Awesome", "tag": "edge",
     "desc": "yapısal arama en iyi trend+momentum ikilisi (OOS)",
     "entry": "Close > ZLEMA(20) AND AwesomeOsc(5,34) > 0",
     "exit": "Close < ZLEMA(20) OR AwesomeOsc(5,34) < 0"},
    {"name": "RSI ortalamaya dönüş",
     "entry": "RSI(14) < 30", "exit": "RSI(14) > 55"},
    {"name": "EMA kesişim trend",
     "entry": "EMA(20) > EMA(50) AND ADX(14) > 20", "exit": "EMA(20) < EMA(50)"},
    {"name": "MACD momentum",
     "entry": "MACD Cross Up", "exit": "MACD Cross Down"},
    {"name": "Bollinger kırılım",
     "entry": "Close > BollingerBands(20).Upper", "exit": "Close < BollingerBands(20).Middle"},
    {"name": "Füzyon teknik skor",
     "entry": "TechScore > 62", "exit": "TechScore < 45"},
    {"name": "Stokastik salınım",
     "entry": "Stochastic(14) < 20", "exit": "Stochastic(14) > 80"},
    {"name": "SuperTrend takip",
     "entry": "SuperTrend.Direction > 0", "exit": "SuperTrend.Direction < 0"},
    {"name": "Trend + RSI filtre",
     "entry": "Close > EMA(200) AND RSI(14) > 50", "exit": "Close < EMA(50)"},
    {"name": "Çift onay (MACD+RSI)",
     "entry": "MACD Cross Up AND RSI(14) > 50", "exit": "RSI(14) > 70"},
    {"name": "CCI ortalamaya dönüş",
     "entry": "CCI(20) < -100", "exit": "CCI(20) > 100"},
    {"name": "Williams %R dönüşü",
     "entry": "WilliamsR(14) < -80", "exit": "WilliamsR(14) > -20"},
    {"name": "Hacimli momentum",
     "entry": "ROC(12) > 5 AND Volume > SMA(Volume, 20)", "exit": "ROC(12) < 0"},
]


@router.get("/examples")
def backtest_examples():
    return {"examples": EXAMPLES}


class BacktestRequest(BaseModel):
    symbol: str
    entry_rule: str
    exit_rule: str | None = None
    interval: str = "1d"
    range: str = "2y"
    initial_cash: float = 10_000.0
    fee_bps: float = 10.0
    stop_loss: float | None = None
    take_profit: float | None = None
    direction: str = "long"


@router.post("")
def backtest_run(req: BacktestRequest):
    try:
        engine.validate_rules(req.entry_rule, req.exit_rule)
    except DSLError as e:
        raise HTTPException(400, f"Kural hatası: {e}")
    try:
        return engine.run(
            symbol=req.symbol, entry_rule=req.entry_rule, exit_rule=req.exit_rule,
            interval=req.interval, range_=req.range, initial_cash=req.initial_cash,
            fee_bps=req.fee_bps, stop_loss=req.stop_loss, take_profit=req.take_profit,
            direction=req.direction,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
