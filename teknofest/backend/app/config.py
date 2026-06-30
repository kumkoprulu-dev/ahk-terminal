"""Yapılandırma — TEKNOFEST Senaryo 2 (Katılım Bankacılığı Bilgi Çıkarımı).

Tüm ayarlar ortam değişkenleriyle override edilebilir. LLM omurgası
provider soyutlamasıyla seçilir (mock | claude | ollama) — yarışmada
hem "milli/yerel" hem "en güçlü" anlatısını desteklemek için.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # teknofest/backend
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_dotenv() -> None:
    """teknofest/backend/.env varsa basitçe yükle (bağımlılık gerektirmez).
    Mevcut ortam değişkenleri korunur; .env yalnız boş olanları doldurur."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv()

# ---- LLM omurgası ---------------------------------------------------------
# "mock"   : LLM yok — kural+regex tabanlı çıkarım (çevrimdışı demo, CI).
# "claude" : Anthropic API (httpx ile doğrudan; SDK gerektirmez).
# "ollama" : Yerel/açık Türkçe model (Ollama HTTP, ör. llama3.1, trendyol).
LLM_PROVIDER = os.getenv("TF_LLM_PROVIDER", "mock").lower()

# Claude
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("TF_CLAUDE_MODEL", "claude-opus-4-8")
CLAUDE_BASE_URL = os.getenv("TF_CLAUDE_BASE_URL", "https://api.anthropic.com")

# Ollama (yerel)
OLLAMA_BASE_URL = os.getenv("TF_OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("TF_OLLAMA_MODEL", "llama3.1:8b")

# OpenAI-uyumlu ücretsiz API'ler (Groq / Gemini / OpenRouter / Together ...).
# Hazır kısa adlar: TF_OPENAI_PRESET=groq|gemini|openrouter ayarlanırsa
# base_url/model otomatik dolar; yalnız TF_OPENAI_API_KEY girmek yeterli.
_OPENAI_PRESETS = {
    "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.0-flash"),
    "openrouter": ("https://openrouter.ai/api/v1", "meta-llama/llama-3.3-70b-instruct:free"),
    "together": ("https://api.together.xyz/v1", "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free"),
}
# Preset: açık TF_OPENAI_PRESET, yoksa TF_LLM_PROVIDER bir preset adıysa onu kullan
_preset = (os.getenv("TF_OPENAI_PRESET", "").lower()
           or (LLM_PROVIDER if LLM_PROVIDER in _OPENAI_PRESETS else ""))
_p_url, _p_model = _OPENAI_PRESETS.get(_preset, ("", ""))
OPENAI_BASE_URL = os.getenv("TF_OPENAI_BASE_URL", _p_url) or "https://api.groq.com/openai/v1"
OPENAI_MODEL = os.getenv("TF_OPENAI_MODEL", _p_model) or "llama-3.3-70b-versatile"
OPENAI_API_KEY = os.getenv("TF_OPENAI_API_KEY", "")

# ---- Depolama -------------------------------------------------------------
DB_PATH = Path(os.getenv("TF_DB_PATH", str(DATA_DIR / "katilim.db")))

# ---- Çıkarım --------------------------------------------------------------
# Bir değeri "doğrulanmış" saymak için kaynak alıntı zorunlu mu?
REQUIRE_GROUNDING = os.getenv("TF_REQUIRE_GROUNDING", "1") == "1"
LLM_MAX_TOKENS = int(os.getenv("TF_LLM_MAX_TOKENS", "2000"))
LLM_TIMEOUT = float(os.getenv("TF_LLM_TIMEOUT", "60"))
