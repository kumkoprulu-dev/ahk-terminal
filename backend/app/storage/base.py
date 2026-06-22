"""OHLCV deposu arayüzü. Backend'ler (Parquet, SQLite, ileride TimescaleDB) bunu uygular."""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod

import pandas as pd


def cache_key(provider: str, symbol: str, interval: str, range_: str) -> str:
    raw = f"{provider}|{symbol}|{interval}|{range_}".lower()
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


class Store(ABC):
    @abstractmethod
    def get(self, provider: str, symbol: str, interval: str, range_: str) -> pd.DataFrame | None: ...

    @abstractmethod
    def set(self, provider: str, symbol: str, interval: str, range_: str, df: pd.DataFrame) -> None: ...
