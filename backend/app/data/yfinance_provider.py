"""yfinance tabanlı sağlayıcı. Anahtarsız çalışır; BIST (.IS), NASDAQ, dünya borsaları."""
from __future__ import annotations

import pandas as pd

from app.data.base import DataProvider, SymbolInfo, normalize_ohlcv

# range_ -> yfinance period; interval bizim formatımız -> yfinance interval
_PERIOD_MAP = {
    "1d": "1d", "5d": "5d", "1mo": "1mo", "3mo": "3mo", "6mo": "6mo",
    "1y": "1y", "2y": "2y", "5y": "5y", "10y": "10y", "max": "max",
}
_INTERVAL_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "60m",
    "1d": "1d", "1wk": "1wk", "1mo": "1mo",
}


class YFinanceProvider(DataProvider):
    name = "yfinance"

    def get_ohlcv(self, symbol: str, interval: str = "1d", range_: str = "1y") -> pd.DataFrame:
        import yfinance as yf

        period = _PERIOD_MAP.get(range_, "1y")
        yf_interval = _INTERVAL_MAP.get(interval, "1d")
        df = yf.download(
            symbol,
            period=period,
            interval=yf_interval,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        if df is None or df.empty:
            return normalize_ohlcv(pd.DataFrame())
        # yfinance çoklu sembolde MultiIndex kolon döndürür; tek sembolde düzleştir
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return normalize_ohlcv(df)

    def search(self, query: str) -> list[SymbolInfo]:
        # yfinance'in resmi arama API'si yok; universe içinden filtreleme api katmanında yapılır.
        return []
