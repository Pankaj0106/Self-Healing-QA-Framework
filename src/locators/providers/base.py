"""Provider interface: every backend (mock/openai/ollama) implements this.

Adhering to a Protocol keeps the resolver provider-agnostic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LocatorSuggestion:
    selector: str
    strategy: str          # css | text | xpath
    confidence: float      # 0..1
    rationale: str = ""


@dataclass(frozen=True)
class HealResponse:
    suggestions: list[LocatorSuggestion]
    model: str
    latency_ms: int
    tokens_used: int = 0


class LLMProvider(Protocol):
    """Structural typing: any object with propose() works here."""

    name: str

    def propose(
        self,
        *,
        intent: str,
        failed_selector: str,
        url: str,
        html_snippet: str,
        max_suggestions: int = 3,
        action: str = "click",
    ) -> HealResponse:
        ...
