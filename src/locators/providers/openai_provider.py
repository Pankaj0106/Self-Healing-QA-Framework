"""OpenAI provider: asks the model for candidate locators (JSON mode).

Safety rules baked in:
- HTML is sanitized (scripts, values, tokens stripped) before send.
- Response forced to JSON via response_format -> no markdown parsing.
- Latency + token usage recorded for heal_metrics.json.
"""
from __future__ import annotations

import json
import re
import time

from .base import HealResponse, LocatorSuggestion

SYSTEM_PROMPT = """You are a test-automation engineer repairing a broken UI locator.
Given the page intent, the failed selector and an HTML snippet, propose up to {n}
replacement locators that Playwright can resolve.
Rules:
- Prefer Playwright engines: css, text=, role=, xpath.
- Confidence 0.0-1.0 (only high if the snippet clearly shows the element).
- Never propose onclick/javascript or any code, only selectors.
Reply with STRICT JSON: {{"suggestions":[{{"selector":"...","strategy":"css","confidence":0.8,"rationale":"..."}}]}}"""

_SAFE_PATTERNS = [
    (re.compile(r"<script.*?</script>", re.I | re.S), " "),
    (re.compile(r'value="[^"]*"', re.I), 'value="[redacted]"'),
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9._-]{10,}", ), "[jwt]"),  # jwt tokens
    (re.compile(r"(api[_-]?key|password|token)\s*[:=]\s*\S+", re.I), r"\1=[redacted]"),
]


def sanitize_html(html: str, max_chars: int = 12000) -> str:
    """Strip secrets + scripts before sending to the LLM."""
    out = html
    for pattern, repl in _SAFE_PATTERNS:
        out = pattern.sub(repl, out)
    return out[:max_chars]


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None,
                 base_url: str | None = None) -> None:
        from openai import OpenAI  # lazy import: keeps `pip install -e .` light

        self.model = model
        self._client = OpenAI(
            api_key=api_key,      # auth; dummy "ollama" is ignored by local servers
            base_url=base_url,    # None = api.openai.com; Ollama: http://localhost:11434/v1
        )

    def propose(self, *, intent, failed_selector, url, html_snippet, max_suggestions=3, action="click") -> HealResponse:
        start = time.perf_counter()
        content = sanitize_html(html_snippet)

        completion = self._client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            max_tokens=400,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT.format(n=max_suggestions)},
                {
                    "role": "user",
                    "content": (
                        f"Intent: {intent}\nAction: {action}\nFailed selector: {failed_selector}\n"
                        f"URL: {url}\nHTML snippet:\n{content}"
                    ),
                },
            ],
        )

        latency_ms = int((time.perf_counter() - start) * 1000)
        raw = completion.choices[0].message.content or "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"suggestions": []}

        suggestions = [
            LocatorSuggestion(
                selector=s["selector"],
                strategy=s.get("strategy", "css"),
                confidence=float(s.get("confidence", 0.0)),
                rationale=s.get("rationale", ""),
            )
            for s in data.get("suggestions", [])[:max_suggestions]
            if isinstance(s, dict) and s.get("selector")
        ]

        return HealResponse(
            suggestions=suggestions,
            model=self.model,
            latency_ms=latency_ms,
            tokens_used=completion.usage.total_tokens if completion.usage else 0,
        )
