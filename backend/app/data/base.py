"""Veri sağlayıcı soyutlaması.

Tüm sağlayıcılar (yfinance, Finnhub, ileride lisanslı kaynaklar) bu arayüzü uygular.
OHLCV her zaman şu kolonlarla, DatetimeIndex'li bir DataFrame döner:
    open, high, low, close, volume
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd

# Desteklenen aralıklar ve gün cinsinden yaklaşık karşılıkları (range hesabı için)
INTERVALS = {"1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"}

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


@dataclass
class SymbolInfo:
    symbol: str
    name: str
    exchange: str = ""
    type: str = "stock"


class DataProvider(ABC):
    name: str = "base"

    @abstractmethod
    def get_ohlcv(
        self,
        symbol: str,
        interval: str = "1d",
        range_: str = "1y",
    ) -> pd.DataFrame:
        """OHLCV DataFrame döner (DatetimeIndex + OHLCV_COLUMNS)."""

    @abstractmethod
    def search(self, query: str) -> list[SymbolInfo]:
        """Sembol arama."""

    def quote(self, symbol: str) -> dict:
        """Anlık fiyat (opsiyonel; varsayılan son kapanış)."""
        df = self.get_ohlcv(symbol, "1d", "5d")
        if df.empty:
            return {"symbol": symbol, "price": None}
        last = df.iloc[-1]
        return {"symbol": symbol, "price": float(last["close"])}


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Kolon adlarını küçük harfe çevirir, OHLCV kolonlarını seçer, NaN satırları atar."""
    if df is None or df.empty:
        return pd.DataFrame(columns=OHLCV_COLUMNS)
    df = df.rename(columns={c: str(c).lower() for c in df.columns})
    # yfinance bazen 'adj close' döndürür; close'u kullanırız
    keep = [c for c in OHLCV_COLUMNS if c in df.columns]
    df = df[keep].copy()
    for c in OHLCV_COLUMNS:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[OHLCV_COLUMNS]
    df = df.dropna(subset=["close"])
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    df.index.name = "date"
    return df
