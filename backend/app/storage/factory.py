"""Depo backend seçici. STORAGE_BACKEND'e göre tekil depo döner."""
from __future__ import annotations

from app.config import CACHE_DIR, settings
from app.storage.base import Store

_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        backend = settings.storage_backend
        if backend in ("postgres", "timescale") and settings.database_url:
            try:
                from app.storage.postgres_store import PostgresStore
                _store = PostgresStore(settings.database_url)
            except Exception:
                from app.storage.parquet_store import ParquetStore
                _store = ParquetStore()  # Postgres/psycopg2 yoksa güvenli düşüş
        elif backend == "sqlite":
            from app.storage.sqlite_store import SqliteStore
            _store = SqliteStore(CACHE_DIR.parent / "market.sqlite")
        else:
            from app.storage.parquet_store import ParquetStore
            _store = ParquetStore()
    return _store
