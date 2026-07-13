"""Backtest/tarama SONUÇLARI için kalıcı veritabanı.

Scriptler (scripts/run_*.py) çalıştığında ürettikleri istatistikler eskiden yalnızca
konsola basılıyor, program kapanınca kayboluyordu. Bu depo, her çalıştırmayı (run) ve
ürettiği her sonuç satırını (strateji/kombo/dönem/sembol) tek dosyalık bir SQLite
veritabanına yazar; böylece tüm geçmiş kalıcı olur ve dashboard'dan sorgulanabilir.

İki tablo:
  runs    : (run_id, created_at, script, kind, label, params_json)
  results : (id, run_id, rank, symbol, interval, name, <ortak metrikler>, metrics_json)

Ortak metrikler (sharpe, total_return, cagr, max_drawdown, num_trades, win_rate,
profit_factor, score, final_equity) gerçek sütun olarak yükseltilir ki SQL ile
"en iyi Sharpe", "BTC'nin tüm çalıştırmaları" gibi sorgular kolay olsun; kalan her
şey metrics_json içinde saklanır.

TimescaleDB/Postgres'e geçiş: DATABASE_URL tanımlıysa psycopg2 ile aynı şema kullanılır
(SERIAL vs AUTOINCREMENT ve %s vs ? farkı _q/_pk ile soyutlandı). SQLite öncülü budur.
"""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.config import CACHE_DIR, settings

# Ortak metriklerin gerçek sütun olarak yükseltilmesi. Sağdaki liste, farklı scriptlerin
# metrik sözlüklerinde kullandığı eş anlamlı anahtarlar (ilk bulunan alınır).
_PROMOTED: dict[str, tuple[str, ...]] = {
    "sharpe": ("sharpe",),
    "total_return": ("total_return", "ret", "total_ret", "total_return_pct"),
    "cagr": ("cagr",),
    "max_drawdown": ("max_drawdown", "dd", "maxdd", "max_dd"),
    "num_trades": ("num_trades", "trades", "n_trades"),
    "win_rate": ("win_rate", "winrate"),
    "profit_factor": ("profit_factor", "pf", "prof_factor"),
    "score": ("score",),
    "final_equity": ("final_equity", "equity"),
}
_NUMERIC_COLS = ("rank", *(_PROMOTED.keys()))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _extract(metrics: dict) -> dict[str, Any]:
    """Metrik sözlüğünden yükseltilen sütunları çıkarır (eş anlamlıları tarayarak)."""
    out: dict[str, Any] = {}
    for col, keys in _PROMOTED.items():
        for k in keys:
            if k in metrics and metrics[k] is not None:
                out[col] = metrics[k]
                break
    return out


class ResultsStore:
    """Postgres varsa oraya, yoksa tek dosyalık SQLite'a yazan sonuç deposu."""

    def __init__(self, path: str | Path | None = None):
        self.database_url = settings.database_url if settings.storage_backend in ("postgres", "timescale") else ""
        self.pg = False
        if self.database_url:
            try:
                import psycopg2  # noqa: F401
                self.pg = True
            except Exception:
                self.pg = False
        if not self.pg:
            self.path = str(path or (CACHE_DIR.parent / "results.sqlite"))
        self._init()

    # --- bağlantı / şema soyutlaması -------------------------------------------------
    def _conn(self):
        if self.pg:
            import psycopg2
            con = psycopg2.connect(self.database_url)
            con.autocommit = False
            return con
        return sqlite3.connect(self.path, timeout=30)

    def _q(self, sql: str) -> str:
        """SQLite '?' yer tutucusunu Postgres '%s' ile değiştirir."""
        return sql.replace("?", "%s") if self.pg else sql

    def _init(self):
        pk = "SERIAL PRIMARY KEY" if self.pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
        con = self._conn()
        cur = con.cursor()
        cur.execute(f"""CREATE TABLE IF NOT EXISTS runs (
            run_id {pk},
            created_at TEXT,
            script TEXT,
            kind TEXT,
            label TEXT,
            params_json TEXT)""")
        cur.execute(f"""CREATE TABLE IF NOT EXISTS results (
            id {pk},
            run_id INTEGER,
            rank INTEGER,
            symbol TEXT,
            interval TEXT,
            name TEXT,
            sharpe REAL, total_return REAL, cagr REAL, max_drawdown REAL,
            num_trades REAL, win_rate REAL, profit_factor REAL, score REAL, final_equity REAL,
            metrics_json TEXT)""")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_results_run ON results(run_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_results_symbol ON results(symbol)")
        # canlı runner snapshot'ları (periyodik PnL/pozisyon zaman serisi)
        cur.execute(f"""CREATE TABLE IF NOT EXISTS live_snapshots (
            id {pk},
            session_id TEXT,
            ts TEXT,
            script TEXT,
            label TEXT,
            name TEXT,
            symbol TEXT,
            net_pnl REAL, realized REAL, unrealized REAL, fees REAL, position REAL,
            tick INTEGER,
            metrics_json TEXT)""")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_live_session ON live_snapshots(session_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_live_ts ON live_snapshots(ts)")
        con.commit()
        con.close()

    # --- yazma -----------------------------------------------------------------------
    def start_run(self, script: str, kind: str, label: str = "", params: dict | None = None) -> int:
        """Yeni bir çalıştırma kaydı açar, run_id döner."""
        con = self._conn()
        cur = con.cursor()
        sql = self._q("INSERT INTO runs (created_at, script, kind, label, params_json) VALUES (?,?,?,?,?)")
        vals = (_now(), script, kind, label, json.dumps(params or {}, default=str, ensure_ascii=False))
        if self.pg:
            cur.execute(sql + " RETURNING run_id", vals)
            run_id = cur.fetchone()[0]
        else:
            cur.execute(sql, vals)
            run_id = cur.lastrowid
        con.commit()
        con.close()
        return int(run_id)

    def add_result(self, run_id: int, metrics: dict, *, symbol: str = "", interval: str = "",
                   name: str = "", rank: int | None = None) -> None:
        """Tek bir sonuç satırı ekler. metrics sözlüğünden ortak sütunlar otomatik çıkarılır."""
        self.add_results(run_id, [dict(metrics, _symbol=symbol, _interval=interval,
                                        _name=name, _rank=rank)])

    def add_results(self, run_id: int, rows: Iterable[dict]) -> int:
        """Toplu ekleme. Her satır bir metrik sözlüğüdür; _symbol/_interval/_name/_rank
        alanları (varsa) meta olarak alınır, kalanı metriktir. Eklenen satır sayısını döner."""
        payload = []
        for r in rows:
            r = dict(r)
            symbol = r.pop("_symbol", "") or r.pop("symbol", "") or ""
            interval = r.pop("_interval", "") or r.pop("interval", "") or ""
            name = r.pop("_name", "") or r.pop("name", "") or ""
            rank = r.pop("_rank", None)
            if rank is None:
                rank = r.pop("rank", None)
            # 'names' listesi (kombo) → okunur bir isim
            if not name and isinstance(r.get("names"), (list, tuple)):
                name = "+".join(str(x) for x in r["names"])
            prom = _extract(r)
            payload.append((
                run_id,
                int(rank) if rank is not None else None,
                str(symbol), str(interval), str(name),
                prom.get("sharpe"), prom.get("total_return"), prom.get("cagr"),
                prom.get("max_drawdown"), prom.get("num_trades"), prom.get("win_rate"),
                prom.get("profit_factor"), prom.get("score"), prom.get("final_equity"),
                json.dumps(r, default=str, ensure_ascii=False),
            ))
        if not payload:
            return 0
        con = self._conn()
        cur = con.cursor()
        sql = self._q("""INSERT INTO results
            (run_id, rank, symbol, interval, name,
             sharpe, total_return, cagr, max_drawdown, num_trades, win_rate,
             profit_factor, score, final_equity, metrics_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""")
        cur.executemany(sql, payload)
        con.commit()
        con.close()
        return len(payload)

    def record(self, script: str, kind: str, results: list[dict], *, label: str = "",
               params: dict | None = None) -> int:
        """Kısa yol: bir run açar + tüm sonuç satırlarını yazar, run_id döner."""
        run_id = self.start_run(script, kind, label=label, params=params)
        self.add_results(run_id, results)
        return run_id

    # --- okuma / sorgu ---------------------------------------------------------------
    def recent_runs(self, limit: int = 30) -> list[dict]:
        con = self._conn()
        cur = con.cursor()
        cur.execute(self._q(
            """SELECT r.run_id, r.created_at, r.script, r.kind, r.label,
                      COUNT(res.id) AS n_results
               FROM runs r LEFT JOIN results res ON res.run_id = r.run_id
               GROUP BY r.run_id, r.created_at, r.script, r.kind, r.label
               ORDER BY r.run_id DESC LIMIT ?"""), (limit,))
        cols = [c[0] for c in cur.description]
        out = [dict(zip(cols, row)) for row in cur.fetchall()]
        con.close()
        return out

    def run_results(self, run_id: int, limit: int = 500) -> list[dict]:
        con = self._conn()
        cur = con.cursor()
        cur.execute(self._q(
            """SELECT rank, symbol, interval, name, sharpe, total_return, cagr,
                      max_drawdown, num_trades, win_rate, profit_factor, score,
                      final_equity, metrics_json
               FROM results WHERE run_id=? ORDER BY COALESCE(rank, 999999), id LIMIT ?"""),
            (run_id, limit))
        cols = [c[0] for c in cur.description]
        out = [dict(zip(cols, row)) for row in cur.fetchall()]
        con.close()
        return out

    def top_results(self, metric: str = "sharpe", limit: int = 25, kind: str | None = None) -> list[dict]:
        if metric not in _PROMOTED:
            metric = "sharpe"
        where = "WHERE res.{m} IS NOT NULL".format(m=metric)
        params: list[Any] = []
        if kind:
            where += " AND r.kind=?"
            params.append(kind)
        params.append(limit)
        con = self._conn()
        cur = con.cursor()
        cur.execute(self._q(
            f"""SELECT r.created_at, r.script, r.kind, res.symbol, res.interval, res.name,
                       res.sharpe, res.total_return, res.max_drawdown, res.num_trades, res.score
                FROM results res JOIN runs r ON r.run_id = res.run_id
                {where} ORDER BY res.{metric} DESC LIMIT ?"""), tuple(params))
        cols = [c[0] for c in cur.description]
        out = [dict(zip(cols, row)) for row in cur.fetchall()]
        con.close()
        return out

    # --- canlı snapshot yazma / okuma ------------------------------------------------
    def add_live_snapshots(self, session_id: str, script: str, label: str,
                           states: Iterable[dict]) -> int:
        """Bir zaman damgası altında robot durumlarını (PnL/pozisyon) toplu yazar."""
        def _f(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        ts = _now()
        payload = []
        for st in states:
            st = dict(st)
            name = st.get("name") or st.get("symbol") or ""
            symbol = st.get("symbol") or ""
            extra = {k: v for k, v in st.items() if k not in ("logs", "recent_fills")}
            payload.append((
                session_id, ts, script, label, str(name), str(symbol),
                _f(st.get("net_pnl")), _f(st.get("realized")), _f(st.get("unrealized")),
                _f(st.get("fees")), _f(st.get("net_qty", st.get("position"))),
                int(st.get("tick") or 0),
                json.dumps(extra, default=str, ensure_ascii=False),
            ))
        if not payload:
            return 0
        con = self._conn()
        cur = con.cursor()
        cur.executemany(self._q("""INSERT INTO live_snapshots
            (session_id, ts, script, label, name, symbol,
             net_pnl, realized, unrealized, fees, position, tick, metrics_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"""), payload)
        con.commit()
        con.close()
        return len(payload)

    def recent_live_sessions(self, limit: int = 30) -> list[dict]:
        """Son canlı oturumlar (özet: script, etiket, başlangıç/son, snapshot sayısı)."""
        con = self._conn()
        cur = con.cursor()
        cur.execute(self._q(
            """SELECT session_id, script, label, MIN(ts) AS started, MAX(ts) AS last_ts,
                      COUNT(DISTINCT ts) AS snaps, COUNT(*) AS rows
               FROM live_snapshots
               GROUP BY session_id, script, label
               ORDER BY MAX(ts) DESC LIMIT ?"""), (limit,))
        cols = [c[0] for c in cur.description]
        out = [dict(zip(cols, row)) for row in cur.fetchall()]
        con.close()
        return out

    def live_overview(self, limit: int = 20) -> list[dict]:
        """Son canlı oturumlar + HER BİRİNİN anlık birleşik PnL'i (tek istekte panel için)."""
        sessions = self.recent_live_sessions(limit)
        for s in sessions:
            latest = self.live_latest(s["session_id"])
            s["net_pnl"] = sum((r["net_pnl"] or 0) for r in latest)
            s["realized"] = sum((r["realized"] or 0) for r in latest)
            s["positions"] = sum(1 for r in latest if abs(r["position"] or 0) > 1e-9)
            s["symbols"] = len(latest)
        return sessions

    def latest_session_for(self, script: str) -> str | None:
        """Bir script'in EN SON canlı oturum id'si (koordinatör için)."""
        con = self._conn()
        cur = con.cursor()
        cur.execute(self._q(
            "SELECT session_id FROM live_snapshots WHERE script=? ORDER BY ts DESC LIMIT 1"),
            (script,))
        row = cur.fetchone()
        con.close()
        return row[0] if row else None

    def live_pnl_series(self, session_id: str) -> list[dict]:
        """Bir oturumun zaman-serisi birleşik PnL'i (her ts'te semboller toplamı)."""
        con = self._conn()
        cur = con.cursor()
        cur.execute(self._q(
            """SELECT ts, SUM(net_pnl) AS net_pnl, SUM(realized) AS realized,
                      SUM(unrealized) AS unrealized, SUM(fees) AS fees
               FROM live_snapshots WHERE session_id=? GROUP BY ts ORDER BY ts"""),
            (session_id,))
        cols = [c[0] for c in cur.description]
        out = [dict(zip(cols, r)) for r in cur.fetchall()]
        con.close()
        return out

    def live_latest(self, session_id: str) -> list[dict]:
        """Bir oturumun EN SON zaman damgasındaki tüm robot satırları (anlık durum)."""
        con = self._conn()
        cur = con.cursor()
        cur.execute(self._q("SELECT MAX(ts) FROM live_snapshots WHERE session_id=?"), (session_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            con.close()
            return []
        cur.execute(self._q(
            """SELECT name, symbol, net_pnl, realized, unrealized, fees, position, tick, ts
               FROM live_snapshots WHERE session_id=? AND ts=? ORDER BY name"""),
            (session_id, row[0]))
        cols = [c[0] for c in cur.description]
        out = [dict(zip(cols, r)) for r in cur.fetchall()]
        con.close()
        return out


class Recorder:
    """Döngü-tabanlı scriptler için biriktir-sonra-yaz yardımcısı.

    Kullanım (bir script main()'inde):
        rec = Recorder("compare_grid", "grid_compare", label="4h karşılaştırma")
        for ...:
            m = grid.simulate(...)["metrics"]
            rec.add(m, symbol=sym, interval="4h", name=cfg_adi)
        rec.save()   # tümünü tek run olarak kalıcı DB'ye yazar

    add() geçtiğiniz metrik sözlüğünü aynen döndürür, böylece satır içinde de kullanılır:
        print(line(rec.add(m, symbol=sym, name=ad)))
    """

    def __init__(self, script: str, kind: str, label: str = "", params: dict | None = None):
        self.script = script
        self.kind = kind
        self.label = label
        self.params = params or {}
        self.rows: list[dict] = []

    def add(self, metrics: dict, *, symbol: str = "", interval: str = "",
            name: str = "", rank: int | None = None) -> dict:
        row = dict(metrics)
        if symbol:
            row["_symbol"] = symbol
        if interval:
            row["_interval"] = interval
        if name:
            row["_name"] = name
        if rank is not None:
            row["_rank"] = rank
        self.rows.append(row)
        return metrics

    def add_many(self, ranked: list[dict], *, symbol: str = "", interval: str = "",
                 start_rank: int = 1) -> None:
        """Sıralı bir listeyi (rank otomatik) ekler."""
        for i, d in enumerate(ranked, start_rank):
            self.add(d, symbol=symbol, interval=interval, rank=i)

    def save(self, quiet: bool = False) -> int | None:
        if not self.rows:
            return None
        run_id = get_results_store().record(self.script, self.kind, self.rows,
                                            label=self.label, params=self.params)
        if not quiet:
            print(f"  [DB] {len(self.rows)} sonuç kaydedildi → results.sqlite (run #{run_id})")
        return run_id


class LiveRecorder:
    """Canlı runner'lar için periyodik snapshot yazıcı.

    Her `snapshot(states)` çağrısı, aynı zaman damgası altında tüm robotların o anki
    metriklerini (net_pnl/realized/pozisyon...) kalıcı live_snapshots tablosuna ekler →
    süreç kapansa bile canlı PnL geçmişi DB'de kalır, dashboard'dan sorgulanabilir.

    Kullanım (bir runner main döngüsünde):
        rec = LiveRecorder("run_bist_combo", label="BIST Combo1 portföy")
        ...
        if now - last_save >= save_every:
            rec.snapshot([r.get_state() for r in robots]); last_save = now
    """

    def __init__(self, script: str, label: str = "", session_id: str | None = None):
        self.script = script
        self.label = label
        self.session_id = session_id or f"{script}-{int(time.time())}"
        self.total = 0

    def snapshot(self, states: list[dict], quiet: bool = True) -> int:
        try:
            n = get_results_store().add_live_snapshots(self.session_id, self.script,
                                                       self.label, states)
        except Exception as e:  # noqa: BLE001 — canlı akışı DB hatası kesmesin
            print(f"  [DB UYARI] snapshot yazılamadı: {e}")
            return 0
        self.total += n
        if not quiet:
            print(f"  [DB] {n} snapshot → live_snapshots (oturum {self.session_id}, toplam {self.total})")
        return n


_store: ResultsStore | None = None


def get_results_store() -> ResultsStore:
    """Süreç ömrü boyunca tekil sonuç deposu."""
    global _store
    if _store is None:
        _store = ResultsStore()
    return _store
