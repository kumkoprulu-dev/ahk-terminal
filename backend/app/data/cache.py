"""OHLCV önbellek cephesi — seçili depo backend'ine yönlendirir.

Backend STORAGE_BACKEND ile seçilir: parquet (varsayılan) | sqlite (TimescaleDB-hazır).
Çağıran katman (data.service) yalnızca get()/set() görür; backend değişimi şeffaftır.
"""
from __future__ import annotations

import pandas as pd

from app.storage.factory import get_store


def get(provider: str, symbol: str, interval: str, range_: str) -> pd.DataFrame | None:
    return get_store().get(provider, symbol, interval, range_)


def set(provider: str, symbol: str, interval: str, range_: str, df: pd.DataFrame) -> None:
    get_store().set(provider, symbol, interval, range_, df)
