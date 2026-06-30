"""SQLite kalıcı depo — çıkarılan ürünler + ham kaynak metinler.

Ürün, JSON olarak (grounding kanıtıyla birlikte) saklanır; ayrıca chatbot'un
RAG'ı için ham kaynak metin de tutulur.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config
from .extract.schema import KatilimUrunu


@contextmanager
def _conn():
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS urunler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                banka TEXT NOT NULL,
                urun_adi TEXT NOT NULL,
                urun_tipi TEXT,
                kar_payi REAL,
                vade_gun INTEGER,
                para_birimi TEXT,
                guven REAL,
                kaynak_url TEXT,
                payload TEXT NOT NULL,
                cekildigi_tarih TEXT,
                UNIQUE(banka, urun_adi)
            );
            CREATE TABLE IF NOT EXISTS kaynaklar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                banka TEXT NOT NULL,
                url TEXT,
                metin TEXT NOT NULL,
                eklendi TEXT
            );
            """
        )


def save_urun(u: KatilimUrunu) -> None:
    flat = u.to_flat()
    payload = json.dumps(u.model_dump(mode="json"), ensure_ascii=False)
    with _conn() as con:
        con.execute(
            """INSERT INTO urunler
               (banka, urun_adi, urun_tipi, kar_payi, vade_gun, para_birimi, guven,
                kaynak_url, payload, cekildigi_tarih)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(banka, urun_adi) DO UPDATE SET
                 urun_tipi=excluded.urun_tipi, kar_payi=excluded.kar_payi,
                 vade_gun=excluded.vade_gun, para_birimi=excluded.para_birimi,
                 guven=excluded.guven, kaynak_url=excluded.kaynak_url,
                 payload=excluded.payload, cekildigi_tarih=excluded.cekildigi_tarih
            """,
            (
                flat["banka"], flat["urun_adi"], flat["urun_tipi"], flat["kar_payi_orani"],
                flat["vade_gun"], flat["para_birimi"], flat["guven"], flat["kaynak_url"],
                payload, u.cekildigi_tarih,
            ),
        )


def save_kaynak(banka: str, url: str | None, metin: str) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO kaynaklar (banka, url, metin, eklendi) VALUES (?,?,?,?)",
            (banka, url, metin, datetime.now(timezone.utc).isoformat()),
        )


def list_urunler() -> list[dict]:
    with _conn() as con:
        rows = con.execute("SELECT payload FROM urunler ORDER BY banka, urun_adi").fetchall()
    return [json.loads(r["payload"]) for r in rows]


def list_flat() -> list[dict]:
    out = []
    for p in list_urunler():
        u = KatilimUrunu.model_validate(p)
        out.append(u.to_flat())
    return out


def get_kaynaklar() -> list[dict]:
    with _conn() as con:
        rows = con.execute("SELECT banka, url, metin FROM kaynaklar").fetchall()
    return [dict(r) for r in rows]


def clear() -> None:
    with _conn() as con:
        con.execute("DELETE FROM urunler")
        con.execute("DELETE FROM kaynaklar")


def count() -> int:
    with _conn() as con:
        return con.execute("SELECT COUNT(*) c FROM urunler").fetchone()["c"]
