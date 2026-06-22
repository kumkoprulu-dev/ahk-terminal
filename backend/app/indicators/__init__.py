"""Gösterge paketi. Modülleri import etmek registry'ye kaydı tetikler."""
from app.indicators import (  # noqa: F401
    trend,
    momentum,
    volume,
    volatility,
    statistical,
    quant,
    fusion_ind,
)
from app.indicators.registry import REGISTRY, compute, list_indicators  # noqa: F401
