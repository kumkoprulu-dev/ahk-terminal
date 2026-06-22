"""Hesap ve kayıtlı öğe servisi.

Depolama: DATABASE_URL ayarlıysa PostgreSQL (kalıcı — Render/üretim), aksi halde yerel
SQLite. Aynı şema iki backend'de de çalışır; SQL placeholder/şema farkları soyutlandı.
Şifreler pbkdf2-sha256 ile saklanır.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import time

from app.config import BACKEND_DIR, settings

DB_PATH = BACKEND_DIR / "data" / "users.sqlite"
_PBKDF_ROUNDS = 200_000
_PG = bool(settings.database_url)

if _PG:
    import psycopg2
    import psycopg2.errors
    from psycopg2.extras import RealDictCursor

    _DUP = (psycopg2.errors.UniqueViolation,)
    _SERIAL = "SERIAL PRIMARY KEY"
    _REAL = "DOUBLE PRECISION"
else:
    _DUP = (sqlite3.IntegrityError,)
    _SERIAL = "INTEGER PRIMARY KEY AUTOINCREMENT"
    _REAL = "REAL"


def _conn():
    if _PG:
        return psycopg2.connect(settings.database_url, cursor_factory=RealDictCursor)
    con = sqlite3.connect(str(DB_PATH), timeout=30)
    con.row_factory = sqlite3.Row
    return con


def _q(sql: str) -> str:
    return sql.replace("?", "%s") if _PG else sql


def init_db():
    if not _PG:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = _conn()
    cur = con.cursor()
    cur.execute(f"""CREATE TABLE IF NOT EXISTS users (
        id {_SERIAL}, username TEXT UNIQUE NOT NULL,
        pw_hash TEXT NOT NULL, salt TEXT NOT NULL, created_at {_REAL})""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at {_REAL})""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS saved_items (
        id {_SERIAL}, user_id INTEGER NOT NULL,
        kind TEXT NOT NULL, name TEXT NOT NULL, data TEXT NOT NULL, updated_at {_REAL},
        UNIQUE(user_id, kind, name))""")
    con.commit()
    cur.close()
    con.close()


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _PBKDF_ROUNDS).hex()


# ----------------------------- auth -----------------------------
def register(username: str, password: str) -> dict:
    username = (username or "").strip().lower()
    if len(username) < 3 or len(password) < 4:
        raise ValueError("Kullanıcı adı ≥3, şifre ≥4 karakter olmalı.")
    salt = os.urandom(16).hex()
    con = _conn()
    cur = con.cursor()
    try:
        cur.execute(_q("INSERT INTO users (username, pw_hash, salt, created_at) VALUES (?,?,?,?)"),
                    (username, _hash(password, salt), salt, time.time()))
        con.commit()
    except _DUP:
        con.rollback()
        con.close()
        raise ValueError("Bu kullanıcı adı zaten alınmış.")
    cur.close()
    con.close()
    return login(username, password)


def login(username: str, password: str) -> dict:
    username = (username or "").strip().lower()
    con = _conn()
    cur = con.cursor()
    cur.execute(_q("SELECT * FROM users WHERE username=?"), (username,))
    row = cur.fetchone()
    if not row or _hash(password, row["salt"]) != row["pw_hash"]:
        cur.close()
        con.close()
        raise ValueError("Kullanıcı adı veya şifre hatalı.")
    token = secrets.token_hex(32)
    cur.execute(_q("INSERT INTO sessions (token, user_id, created_at) VALUES (?,?,?)"),
                (token, row["id"], time.time()))
    con.commit()
    cur.close()
    con.close()
    return {"token": token, "username": username}


def user_for_token(token: str | None) -> dict | None:
    if not token:
        return None
    con = _conn()
    cur = con.cursor()
    cur.execute(_q("SELECT u.id AS id, u.username AS username FROM sessions s "
                   "JOIN users u ON u.id=s.user_id WHERE s.token=?"), (token,))
    row = cur.fetchone()
    cur.close()
    con.close()
    return {"id": row["id"], "username": row["username"]} if row else None


def logout(token: str) -> None:
    con = _conn()
    cur = con.cursor()
    cur.execute(_q("DELETE FROM sessions WHERE token=?"), (token,))
    con.commit()
    cur.close()
    con.close()


# -------------------------- saved items --------------------------
def save_item(user_id: int, kind: str, name: str, data: dict) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("İsim gerekli.")
    con = _conn()
    cur = con.cursor()
    cur.execute(_q("""INSERT INTO saved_items (user_id, kind, name, data, updated_at)
        VALUES (?,?,?,?,?)
        ON CONFLICT (user_id, kind, name) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at"""),
        (user_id, kind, name, json.dumps(data), time.time()))
    con.commit()
    cur.close()
    con.close()
    return {"kind": kind, "name": name}


def list_items(user_id: int, kind: str | None = None) -> list[dict]:
    con = _conn()
    cur = con.cursor()
    if kind:
        cur.execute(_q("SELECT id, kind, name, data, updated_at FROM saved_items "
                       "WHERE user_id=? AND kind=? ORDER BY updated_at DESC"), (user_id, kind))
    else:
        cur.execute(_q("SELECT id, kind, name, data, updated_at FROM saved_items "
                       "WHERE user_id=? ORDER BY updated_at DESC"), (user_id,))
    rows = cur.fetchall()
    cur.close()
    con.close()
    return [{"id": r["id"], "kind": r["kind"], "name": r["name"],
             "data": json.loads(r["data"]), "updated_at": r["updated_at"]} for r in rows]


def delete_item(user_id: int, item_id: int) -> None:
    con = _conn()
    cur = con.cursor()
    cur.execute(_q("DELETE FROM saved_items WHERE id=? AND user_id=?"), (item_id, user_id))
    con.commit()
    cur.close()
    con.close()
