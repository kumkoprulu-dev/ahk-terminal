"""PostgreSQL / TimescaleDB OHLCV deposu.

DURUM: Bu backend Postgres + (opsiyonel) TimescaleDB eklentisi ve `psycopg2` gerektirir
(`pip install psycopg2-binary`). Bu ortamda Postgres KURULU OLMADIĞINDAN canlı
doğrulanmamıştır; SQLite backend'i (storage/sqlite_store.py) doğrulanmış öncülüdür ve
aynı `ohlcv` zaman serisi şemasını kullanır.

Etkinleştirmek için .env:
    STORAGE_BACKEND=timescale
    DATABASE_URL=postgresql://user:pass@localhost:5432/market

`ohlcv` tablosu TimescaleDB varsa hypertable'a dönüştürülür (zaman serisi optimizasyonu).
"""
from __future__ import annotations

import io
import time

import pandas as pd

from app.config import settings
from app.storage.base import Store, cache_key


class PostgresStore(Store):
    def __init__(self, dsn: str):
        import psycopg2  # lazy: yalnız bu backend seçiliyse gerekir

        self._psycopg2 = psycopg2
        self.dsn = dsn
        self._init()

    def _conn(self):
        return self._psycopg2.connect(self.dsn)

    def _init(self):
        con = self._conn()
        con.autocommit = True  # her DDL bağımsız commit; bir hata öncekileri geri almasın
        cur = con.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS ohlcv_cache (
            key TEXT PRIMARY KEY, symbol TEXT, interval TEXT, range TEXT,
            fetched_at DOUBLE PRECISION, data BYTEA)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS ohlcv (
            symbol TEXT, interval TEXT, date TIMESTAMPTZ,
            open DOUBLE PRECISION, high DOUBLE PRECISION, low DOUBLE PRECISION,
            close DOUBLE PRECISION, volume DOUBLE PRECISION,
            PRIMARY KEY (symbol, interval, date))""")
        # TimescaleDB varsa hypertable yap (yoksa sessizce geç — tablolar zaten oluştu)
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
            cur.execute("SELECT create_hypertable('ohlcv','date', if_not_exists => TRUE)")
        except Exception:
            pass
        cur.close()
        con.close()

    def get(self, provider, symbol, interval, range_):
        key = cache_key(provider, symbol, interval, range_)
        con = self._conn()
        cur = con.cursor()
        cur.execute("SELECT fetched_at, data FROM ohlcv_cache WHERE key=%s", (key,))
        row = cur.fetchone()
        cur.close()
        con.close()
        if not row:
            return None
        fetched_at, blob = row
        if settings.cache_ttl > 0 and time.time() - fetched_at > settings.cache_ttl:
            return None
        try:
            return pd.read_parquet(io.BytesIO(bytes(blob)))
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
            cur = con.cursor()
            cur.execute("""INSERT INTO ohlcv_cache VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (key) DO UPDATE SET fetched_at=EXCLUDED.fetched_at, data=EXCLUDED.data""",
                (key, symbol, interval, range_, time.time(), self._psycopg2.Binary(blob)))
            rows = [
                (symbol, interval, idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx,
                 float(r.open), float(r.high), float(r.low), float(r.close),
                 float(r.volume) if r.volume == r.volume else 0.0)
                for idx, r in df.iterrows()
            ]
            cur.executemany("""INSERT INTO ohlcv VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (symbol, interval, date) DO UPDATE SET
                open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                close=EXCLUDED.close, volume=EXCLUDED.volume""", rows)
            con.commit()
            cur.close()
            con.close()
        except Exception:
            pass
