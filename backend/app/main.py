"""FastAPI uygulaması: API rotaları + statik frontend servisi."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import FRONTEND_DIR, settings
from app.api import (
    routes_data, routes_indicators, routes_scanner,
    routes_backtest, routes_optimize, routes_walkforward, routes_portfolio,
    routes_sentiment, routes_market, routes_fundamentals, routes_fusion, routes_auth,
    routes_live, routes_formula, routes_alarms, routes_results, routes_nnfx,
)
from app.accounts.service import init_db
# indicators paketini import etmek registry kaydını tetikler
import app.indicators  # noqa: F401
from app.indicators.registry import REGISTRY

app = FastAPI(title="Finansal Veri Platformu", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_data.router)
app.include_router(routes_indicators.router)
app.include_router(routes_scanner.router)
app.include_router(routes_backtest.router)
app.include_router(routes_optimize.router)
app.include_router(routes_walkforward.router)
app.include_router(routes_portfolio.router)
app.include_router(routes_sentiment.router)
app.include_router(routes_market.router)
app.include_router(routes_fundamentals.router)
app.include_router(routes_fusion.router)
app.include_router(routes_auth.router)
app.include_router(routes_live.router)
app.include_router(routes_formula.router)
app.include_router(routes_alarms.router)
app.include_router(routes_results.router)
app.include_router(routes_nnfx.router)
init_db()


@app.middleware("http")
async def no_cache_static(request, call_next):
    """Statik dosyalarda + ana sayfada no-cache — düzenlemeden sonra tarayıcı bayat
    HTML/JS sunmasın (index.html '/' yolundan gelir, /static'e girmez → ayrıca kapsanır)."""
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@app.get("/health")
def health():
    return {
        "status": "ok",
        "indicators": len(REGISTRY),
        "finnhub": settings.has_finnhub,
        "provider": settings.data_provider,
    }


# Frontend statik servisi (build adımı yok; CDN tabanlı)
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def index():
        return FileResponse(FRONTEND_DIR / "index.html")
