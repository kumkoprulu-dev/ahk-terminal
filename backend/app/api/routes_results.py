"""Kayıtlı backtest/tarama sonuçları uç noktaları (dashboard için).

Kalıcı results.sqlite (veya Postgres) veritabanındaki geçmişi okur — böylece
scriptler kapansa bile üretilen tüm istatistikler dashboard'da görünür.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.storage.results_store import get_results_store

router = APIRouter(prefix="/api/results", tags=["results"])


@router.get("/runs")
def list_runs(limit: int = 30):
    """Son çalıştırmalar (özet: script, tür, etiket, sonuç sayısı)."""
    return {"runs": get_results_store().recent_runs(limit)}


@router.get("/runs/{run_id}")
def run_detail(run_id: int, limit: int = 500):
    """Bir çalıştırmanın tüm sonuç satırları."""
    return {"run_id": run_id, "results": get_results_store().run_results(run_id, limit)}


@router.get("/top")
def top(metric: str = "sharpe", limit: int = 25, kind: str | None = None):
    """Tüm geçmiş boyunca seçili metriğe göre en iyi sonuçlar."""
    return {"metric": metric, "results": get_results_store().top_results(metric, limit, kind)}


@router.get("/live")
def live_sessions(limit: int = 30):
    """Son canlı runner oturumları + anlık birleşik PnL/pozisyon (panel için)."""
    return {"sessions": get_results_store().live_overview(limit)}


@router.get("/live/{session_id}")
def live_detail(session_id: str):
    """Bir canlı oturumun en son snapshot'ı (her robotun anlık PnL/pozisyonu)."""
    return {"session_id": session_id, "latest": get_results_store().live_latest(session_id)}


@router.get("/live/{session_id}/series")
def live_series(session_id: str):
    """Bir canlı oturumun zaman-serisi birleşik PnL'i (equity eğrisi için)."""
    return {"session_id": session_id, "series": get_results_store().live_pnl_series(session_id)}
