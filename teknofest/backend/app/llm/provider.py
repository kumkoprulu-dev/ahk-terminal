"""LLM provider soyutlaması.

Tek bir arayüz (`LLMProvider.complete`) arkasında üç omurga:

* MockProvider   — LLM yok; deterministik, çevrimdışı. Çıkarımda kural+regex
                   fallback'ine (extract.rules) düşer. CI ve demo için.
* ClaudeProvider — Anthropic Messages API'ye httpx ile doğrudan istek.
* OllamaProvider — Yerel/açık Türkçe model (Ollama /api/chat).

Tüm sağlayıcılar JSON-modunda çalışacak şekilde tasarlandı: `json_schema`
verilirse model'den yalnız JSON döndürmesi istenir ve gövde parse edilir.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from .. import config


@dataclass
class LLMResult:
    text: str
    raw: dict[str, Any] | None = None

    def json(self) -> Any:
        """Gövdeden ilk geçerli JSON nesnesini/listesini çıkar."""
        return _extract_json(self.text)


class LLMProvider:
    name = "base"

    def complete(
        self,
        system: str,
        user: str,
        *,
        force_json: bool = False,
        max_tokens: int | None = None,
    ) -> LLMResult:  # pragma: no cover - arayüz
        raise NotImplementedError

    @property
    def available(self) -> bool:
        return True


# --------------------------------------------------------------------------
class MockProvider(LLMProvider):
    """LLM yokken kullanılır. complete() boş döner; çağıran taraf
    (extractor) kural-tabanlı çıkarıma düşer. Sohbet için şablon yanıt verir."""

    name = "mock"

    def complete(self, system, user, *, force_json=False, max_tokens=None):
        return LLMResult(text="", raw={"mock": True})


# --------------------------------------------------------------------------
class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self):
        self._key = config.ANTHROPIC_API_KEY
        self._model = config.CLAUDE_MODEL
        self._url = config.CLAUDE_BASE_URL.rstrip("/") + "/v1/messages"

    @property
    def available(self) -> bool:
        return bool(self._key)

    def complete(self, system, user, *, force_json=False, max_tokens=None):
        if not self.available:
            raise RuntimeError("ANTHROPIC_API_KEY tanımlı değil")
        if force_json:
            user = user + "\n\nYANIT: Yalnızca geçerli JSON döndür, başka metin yazma."
        payload = {
            "model": self._model,
            "max_tokens": max_tokens or config.LLM_MAX_TOKENS,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        headers = {
            "x-api-key": self._key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        with httpx.Client(timeout=config.LLM_TIMEOUT) as cli:
            r = cli.post(self._url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
        text = "".join(
            blk.get("text", "") for blk in data.get("content", []) if blk.get("type") == "text"
        )
        return LLMResult(text=text, raw=data)


# --------------------------------------------------------------------------
class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self):
        self._url = config.OLLAMA_BASE_URL.rstrip("/") + "/api/chat"
        self._model = config.OLLAMA_MODEL

    @property
    def available(self) -> bool:
        try:
            with httpx.Client(timeout=2.0) as cli:
                cli.get(config.OLLAMA_BASE_URL.rstrip("/") + "/api/tags")
            return True
        except Exception:
            return False

    def complete(self, system, user, *, force_json=False, max_tokens=None):
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"num_predict": max_tokens or config.LLM_MAX_TOKENS},
        }
        if force_json:
            payload["format"] = "json"
        with httpx.Client(timeout=config.LLM_TIMEOUT) as cli:
            r = cli.post(self._url, json=payload)
            r.raise_for_status()
            data = r.json()
        text = data.get("message", {}).get("content", "")
        return LLMResult(text=text, raw=data)


# --------------------------------------------------------------------------
class OpenAICompatProvider(LLMProvider):
    """OpenAI-uyumlu /chat/completions API'leri için genel sağlayıcı.

    Groq, Google Gemini (OpenAI uçları), OpenRouter, Together vb. ÜCRETSİZ
    tier'lar bu arayüzü konuşur. TF_OPENAI_PRESET + TF_OPENAI_API_KEY yeterli.
    """

    name = "openai"

    def __init__(self):
        self._key = config.OPENAI_API_KEY
        self._model = config.OPENAI_MODEL
        self._url = config.OPENAI_BASE_URL.rstrip("/") + "/chat/completions"

    @property
    def available(self) -> bool:
        return bool(self._key)

    def complete(self, system, user, *, force_json=False, max_tokens=None):
        if not self.available:
            raise RuntimeError("TF_OPENAI_API_KEY tanımlı değil")
        payload = {
            "model": self._model,
            "max_tokens": max_tokens or config.LLM_MAX_TOKENS,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if force_json:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self._key}", "content-type": "application/json"}
        with httpx.Client(timeout=config.LLM_TIMEOUT) as cli:
            r = cli.post(self._url, headers=headers, json=payload)
            # Bazı sağlayıcılar response_format'ı desteklemez → JSON modsuz tekrar dene
            if r.status_code == 400 and force_json:
                payload.pop("response_format", None)
                r = cli.post(self._url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return LLMResult(text=text, raw=data)


# --------------------------------------------------------------------------
_PROVIDERS = {
    "mock": MockProvider,
    "claude": ClaudeProvider,
    "ollama": OllamaProvider,
    "openai": OpenAICompatProvider,
    # kısa adlar — hepsi OpenAI-uyumlu provider'a düşer (preset config'te çözülür)
    "groq": OpenAICompatProvider,
    "gemini": OpenAICompatProvider,
    "openrouter": OpenAICompatProvider,
    "together": OpenAICompatProvider,
}


def get_provider(name: str | None = None) -> LLMProvider:
    name = (name or config.LLM_PROVIDER).lower()
    # ON-PREM kilidi: bulut sağlayıcı istense bile yerel omurgaya düş.
    if config.ONPREM and name in config.CLOUD_PROVIDERS:
        oll = OllamaProvider()
        return oll if oll.available else MockProvider()
    cls = _PROVIDERS.get(name, MockProvider)
    return cls()


def _extract_json(text: str) -> Any:
    """Serbest metinden ilk JSON gövdesini güvenle çıkar."""
    if not text:
        return None
    text = text.strip()
    # ```json ... ``` bloklarını temizle
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    # Doğrudan parse denemesi
    try:
        return json.loads(text)
    except Exception:
        pass
    # İlk { veya [ ile başlayan dengeli gövdeyi yakala
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(text)):
            if text[i] == opener:
                depth += 1
            elif text[i] == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except Exception:
                        break
    return None
