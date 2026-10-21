"""Provider factory: LLM_PROVIDER env var picks the backend.

    LLM_PROVIDER=mock    -> free, offline (default, unit tests, CI)
    LLM_PROVIDER=openai  -> gpt-4o-mini
    LLM_PROVIDER=ollama  -> local model (free)
"""
from __future__ import annotations

import os

from .base import LLMProvider
from .mock import MockProvider


def get_provider(name: str | None = None, model: str | None = None) -> LLMProvider:
    name = (name or os.getenv("LLM_PROVIDER", "mock")).lower()

    if name == "mock":
        return MockProvider()

    if name == "openai":
        from .openai_provider import OpenAIProvider  # lazy: needs `openai` installed

        return OpenAIProvider(model=model or os.getenv("LLM_MODEL", "gpt-4o-mini"))

    if name == "ollama":
        from .openai_provider import OpenAIProvider  # ollama exposes an OpenAI-compatible API

        return OpenAIProvider(
            model=model or os.getenv("LLM_MODEL", "qwen2.5:3b"),
            api_key="ollama",  # required formality: local server ignores auth
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        )

    raise ValueError(f"Unknown LLM_PROVIDER={name!r} (use mock|openai|ollama)")
