"""TEKNOFEST 2026 — Yapay Zeka Dil Ajanları Yarışması / Senaryo 2.

Katılım Bankacılığı Finansal Metin Madenciliği, Bilgi Çıkarımı ve
Akıllı Dashboard-Asistan Çözümü.

Çalıştırma:
    uvicorn app.main:app --app-dir teknofest/backend --port 8090
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import store
from .api import router

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

app = FastAPI(title="KatılımLens — TEKNOFEST Senaryo 2", version="1.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.on_event("startup")
def _startup():
    store.init_db()


app.include_router(router, prefix="/api")


@app.get("/")
def index():
    idx = FRONTEND_DIR / "index.html"
    if idx.exists():
        return FileResponse(idx)
    return RedirectResponse("/docs")


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
