"""Parquet dosya tabanlı OHLCV deposu (varsayılan; sunucu gerektirmez)."""
from __future__ import annotations

import time

import pandas as pd

from app.config import CACHE_DIR, settings
from app.storage.base import Store, cache_key


class ParquetStore(Store):
    def _path(self, provider, symbol, interval, range_):
        return CACHE_DIR / f"{cache_key(provider, symbol, interval, range_)}.parquet"

    def get(self, provider, symbol, interval, range_):
        p = self._path(provider, symbol, interval, range_)
        if not p.exists():
            return None
        if settings.cache_ttl > 0 and time.time() - p.stat().st_mtime > settings.cache_ttl:
            return None
        try:
            return pd.read_parquet(p)
        except Exception:
            return None

    def set(self, provider, symbol, interval, range_, df):
        if df is None or df.empty:
            return
        try:
            df.to_parquet(self._path(provider, symbol, interval, range_))
        except Exception:
            pass
