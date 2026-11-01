"""Provider-agnostic LLM access.

The LLM is used for understanding (intent extraction, policy compilation) and never for
authorization. Every call returns JSON that is validated by a Pydantic schema before use.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

import httpx

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

log = get_logger("llm")


class LLMUnavailable(RuntimeError):
    pass


class LLMProvider(Protocol):
    name: str
    model: str

    def complete_json(self, system: str, user: str) -> dict[str, Any]: ...


class OpenAICompatibleProvider:
    """Works with OpenAI and any OpenAI-compatible endpoint (set OPENAI_BASE_URL)."""

    name = "openai"

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.model = settings.llm_model
        self._client = httpx.Client(
            base_url=settings.openai_base_url,
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            timeout=settings.llm_timeout_seconds,
            transport=transport,
        )

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        try:
            resp = self._client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
            if not isinstance(data, dict):
                raise ValueError("LLM did not return a JSON object")
            return data
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            log.warning("LLM call failed", extra={"data": {"error": str(exc)}})
            raise LLMUnavailable(str(exc)) from exc


_provider: LLMProvider | None = None
_override: bool = False


def get_llm() -> LLMProvider | None:
    """Returns the configured provider, or None when no LLM is configured."""
    global _provider
    if _override:
        return _provider
    settings = get_settings()
    if not settings.llm_configured:
        return None
    if _provider is None:
        _provider = OpenAICompatibleProvider(settings)
    return _provider


def set_llm(provider: LLMProvider | None) -> None:
    """Test hook: force a specific provider (or None) regardless of configuration."""
    global _provider, _override
    _provider = provider
    _override = True


def reset_llm() -> None:
    global _provider, _override
    _provider = None
    _override = False
