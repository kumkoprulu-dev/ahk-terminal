import sqlite3

import numpy as np
import pandas as pd
import pytest

from app.storage.parquet_store import ParquetStore
from app.storage.sqlite_store import SqliteStore


@pytest.fixture
def df():
    idx = pd.date_range("2024-01-01", periods=40, freq="D")
    idx.name = "date"
    return pd.DataFrame({
        "open": np.arange(40.0), "high": np.arange(40.0) + 1, "low": np.arange(40.0) - 1,
        "close": np.arange(40.0) + 0.5, "volume": np.arange(40.0) * 100,
    }, index=idx)


def test_parquet_roundtrip(df):
    s = ParquetStore()
    s.set("auto", "ZZTEST", "1d", "1y", df)
    out = s.get("auto", "ZZTEST", "1d", "1y")
    assert out is not None and len(out) == 40


def test_sqlite_roundtrip_and_timeseries_table(df, tmp_path):
    path = tmp_path / "m.sqlite"
    s = SqliteStore(str(path))
    s.set("auto", "ZZTEST", "1d", "1y", df)
    out = s.get("auto", "ZZTEST", "1d", "1y")
    assert out is not None and len(out) == 40

    # TimescaleDB-biçimli ohlcv tablosu dolmuş olmalı
    con = sqlite3.connect(str(path))
    n = con.execute("SELECT COUNT(*) FROM ohlcv WHERE symbol='ZZTEST'").fetchone()[0]
    con.close()
    assert n == 40


def test_sqlite_upsert_no_duplicate(df, tmp_path):
    path = tmp_path / "m.sqlite"
    s = SqliteStore(str(path))
    s.set("auto", "ZZTEST", "1d", "1y", df)
    s.set("auto", "ZZTEST", "1d", "1y", df)  # tekrar yaz → çoğaltma olmamalı
    con = sqlite3.connect(str(path))
    n = con.execute("SELECT COUNT(*) FROM ohlcv WHERE symbol='ZZTEST'").fetchone()[0]
    con.close()
    assert n == 40
