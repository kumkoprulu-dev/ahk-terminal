"""Uygulama ayarları. .env dosyasından okunur (pydantic-settings)."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ dizini (config.py -> app -> backend)
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
CACHE_DIR = BACKEND_DIR / "data" / "cache"
FRONTEND_DIR = PROJECT_DIR / "frontend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    finnhub_api_key: str = ""
    data_provider: str = "auto"  # auto | yfinance | finnhub
    cache_ttl: int = 3600
    storage_backend: str = "parquet"  # parquet | sqlite
    database_url: str = ""  # postgresql://... (TimescaleDB) — ileride

    @property
    def has_finnhub(self) -> bool:
        return bool(self.finnhub_api_key.strip())


settings = Settings()

# Önbellek dizinini hazır et
CACHE_DIR.mkdir(parents=True, exist_ok=True)
