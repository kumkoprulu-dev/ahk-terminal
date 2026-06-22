"""SQLite tabanlı OHLCV deposu — tek dosyalık gerçek veritabanı (sunucu gerektirmez).

İki tablo:
  ohlcv_cache : (key, symbol, interval, range, fetched_at, data) — hızlı df önbelleği (parquet blob)
  ohlcv       : (symbol, interval, date, o,h,l,c,v) — TimescaleDB-biçiminde zaman serisi tablosu

TimescaleDB'ye geçiş: aynı `ohlcv` şeması bir Postgres hypertable olur; yalnız bağlantı
(DATABASE_URL) ve sürücü değişir, sorgu mantığı aynı kalır. Bu sınıf, o geçişin
doğrulanabilir SQLite öncülüdür.
"""
from __future__ import annotations

import io
import sqlite3
import time

import pandas as pd

from app.config import settings
from app.storage.base import Store, cache_key


class SqliteStore(Store):
    def __init__(self, path: str):
        self.path = str(path)
        self._init()

    def _conn(self):
        return sqlite3.connect(self.path, timeout=30)

    def _init(self):
        con = self._conn()
        con.execute("""CREATE TABLE IF NOT EXISTS ohlcv_cache (
            key TEXT PRIMARY KEY, symbol TEXT, interval TEXT, range TEXT,
            fetched_at REAL, data BLOB)""")
        con.execute("""CREATE TABLE IF NOT EXISTS ohlcv (
            symbol TEXT, interval TEXT, date TEXT,
            open REAL, high REAL, low REAL, close REAL, volume REAL,
            PRIMARY KEY (symbol, interval, date))""")
        con.commit()
        con.close()

    def get(self, provider, symbol, interval, range_):
        key = cache_key(provider, symbol, interval, range_)
        con = self._conn()
        row = con.execute("SELECT fetched_at, data FROM ohlcv_cache WHERE key=?", (key,)).fetchone()
        con.close()
        if not row:
            return None
        fetched_at, blob = row
        if settings.cache_ttl > 0 and time.time() - fetched_at > settings.cache_ttl:
            return None
        try:
            return pd.read_parquet(io.BytesIO(blob))
        except Exception:
            return None

    def set(self, provider, symbol, interval, range_, df):
        if df is None or df.empty:
            return
        try:
            buf = io.BytesIO()
            df.to_parquet(buf)
            blob = buf.getvalue()
            key = cache_key(provider, symbol, interval, range_)
            con = self._conn()
            con.execute("INSERT OR REPLACE INTO ohlcv_cache VALUES (?,?,?,?,?,?)",
                        (key, symbol, interval, range_, time.time(), blob))
            rows = [
                (symbol, interval,
                 idx.strftime("%Y-%m-%d %H:%M:%S") if hasattr(idx, "strftime") else str(idx),
                 float(r.open), float(r.high), float(r.low), float(r.close),
                 float(r.volume) if r.volume == r.volume else 0.0)
                for idx, r in df.iterrows()
            ]
            con.executemany("INSERT OR REPLACE INTO ohlcv VALUES (?,?,?,?,?,?,?,?)", rows)
            con.commit()
            con.close()
        except Exception:
            pass
