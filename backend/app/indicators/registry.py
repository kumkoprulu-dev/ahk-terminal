"""Gösterge kayıt sistemi (registry).

Her gösterge `@indicator(...)` ile kaydedilir. Tek bir noktadan listelenir
(metadata: ad, grup, parametreler, çıktılar, çizim tipi) ve hesaplanır.
Yeni gösterge eklemek = bir fonksiyon yaz + dekore et. 1000 göstergeye giden yol budur.

Gösterge fonksiyonu sözleşmesi:
    def fn(df: pd.DataFrame, **params) -> pd.DataFrame
    df: open/high/low/close/volume kolonlu DatetimeIndex'li çerçeve.
    dönüş: çıktı kolonlarını (outputs) içeren DataFrame (aynı index).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd


@dataclass
class Param:
    name: str
    default: float
    min: float
    max: float
    step: float = 1
    type: str = "int"  # int | float | source


@dataclass
class IndicatorSpec:
    name: str
    group: str
    func: Callable[..., pd.DataFrame]
    params: list[Param] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    overlay: bool = False  # True: fiyat grafiğinin üstüne çizilir; False: alt panel
    description: str = ""

    def meta(self) -> dict:
        return {
            "name": self.name,
            "group": self.group,
            "overlay": self.overlay,
            "description": self.description,
            "outputs": self.outputs,
            "params": [
                {
                    "name": p.name, "default": p.default, "min": p.min,
                    "max": p.max, "step": p.step, "type": p.type,
                }
                for p in self.params
            ],
        }


REGISTRY: dict[str, IndicatorSpec] = {}


def indicator(
    name: str,
    group: str,
    params: list[Param] | None = None,
    outputs: list[str] | None = None,
    overlay: bool = False,
    description: str = "",
):
    def deco(func: Callable[..., pd.DataFrame]) -> Callable[..., pd.DataFrame]:
        spec = IndicatorSpec(
            name=name,
            group=group,
            func=func,
            params=params or [],
            outputs=outputs or [name],
            overlay=overlay,
            description=description,
        )
        key = name.upper()
        if key in REGISTRY:
            raise ValueError(f"Gösterge zaten kayıtlı: {name}")
        REGISTRY[key] = spec
        return func

    return deco


def _coerce_params(spec: IndicatorSpec, params: dict) -> dict:
    """Gelen parametreleri spec'e göre tipler ve eksikleri varsayılanla doldurur."""
    out: dict = {}
    for p in spec.params:
        if p.type == "source":
            out[p.name] = params.get(p.name, p.default)
            continue
        val = params.get(p.name, p.default)
        try:
            val = int(val) if p.type == "int" else float(val)
        except (TypeError, ValueError):
            val = p.default
        out[p.name] = val
    return out


def compute(name: str, df: pd.DataFrame, params: dict | None = None) -> pd.DataFrame:
    spec = REGISTRY.get(name.upper())
    if spec is None:
        raise KeyError(f"Bilinmeyen gösterge: {name}")
    kwargs = _coerce_params(spec, params or {})
    result = spec.func(df, **kwargs)
    if isinstance(result, pd.Series):
        result = result.to_frame(spec.outputs[0])
    return result


def list_indicators() -> list[dict]:
    return [spec.meta() for spec in sorted(REGISTRY.values(), key=lambda s: (s.group, s.name))]


def groups() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for spec in REGISTRY.values():
        out.setdefault(spec.group, []).append(spec.name)
    for g in out:
        out[g].sort()
    return out
