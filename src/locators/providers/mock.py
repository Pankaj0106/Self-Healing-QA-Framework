"""Mock provider: no network, no cost, deterministic.

Heuristic (lies between "regex" and "LLM"):
1. Parse tags of the kind implied by the action:
   - click -> <button> / <a>   (things you can click)
   - fill / read -> <input> / <textarea>
2. For each tag: candidate locator = data-qa/id/name attr if present,
   else its visible text (buttons only).
3. Score = how many INTENT words appear in (attr value + inner text).
   Intent words = 4+ letter words from the intent string, e.g. "Submit login
   form" -> {submit, login, form}. This is what makes it intent-aware:
   for "Email input on login form", [id=login-email] outranks
   [data-qa=signup-email] (login+email beat email alone).

Used by unit tests, CI (no key) and the break-and-heal demo. The production
path is openai_provider.py / ollama.
"""
from __future__ import annotations

import re
import time

from .base import HealResponse, LocatorSuggestion

_TAG_CLICK = re.compile(r"<(button|a)\b([^>]*)>([^<]{0,60})", re.I)
_TAG_INPUT = re.compile(r"<(input|textarea)\b([^>]*?)/?>", re.I)
_ATTR = re.compile(r"\b(data-qa|id|name)\s*=\s*[\"']([^\"']+)[\"']", re.I)
_WORD = re.compile(r"[a-z]{4,}")
MAX_CONF, BASE_CONF, STEP = 0.95, 0.55, 0.10


def _words(intent: str) -> set[str]:
    return set(_WORD.findall(intent.lower()))


def _score(text: str, intent_words: set[str]) -> int:
    low = text.lower()
    return sum(1 for w in intent_words if w in low)


class MockProvider:
    name = "mock"

    def propose(self, *, intent, failed_selector, url, html_snippet,
                max_suggestions=3, action="click") -> HealResponse:
        start = time.perf_counter()
        intent_words = _words(intent)

        finder = _TAG_CLICK if action == "click" else _TAG_INPUT
        rows: list[tuple[int, int, LocatorSuggestion]] = []

        for m in finder.finditer(html_snippet):
            attrs = m.group(2)
            inner = m.group(3) if action == "click" else ""

            am = _ATTR.search(attrs)
            if am:
                value = am.group(2)
                score = _score(value, intent_words) + _score(inner, intent_words)
                sug = LocatorSuggestion(
                    selector=f'[{am.group(1)}="{value}"]',
                    strategy="css",
                    confidence=min(MAX_CONF, BASE_CONF + STEP * score),
                    rationale=f"mock: {am.group(1)}={value!r} matches {score} intent word(s)",
                )
            else:
                text = inner.strip()
                if not (2 <= len(text) <= 40):
                    continue
                score = _score(text, intent_words)
                sug = LocatorSuggestion(
                    selector=f"text={text[:30]}",
                    strategy="text",
                    confidence=min(MAX_CONF, BASE_CONF + STEP * score),
                    rationale=f"mock: visible text {text[:30]!r} matches {score} intent word(s)",
                )

            # rank: best intent-match first; on ties, earlier in the HTML wins
            rows.append((-score, m.start(), sug))

        rows.sort(key=lambda r: (r[0], r[1]))

        positives = [r for r in rows if r[0] < 0]           # score >= 1
        ranked = positives or rows                          # fallback: pure position
        suggestions = [r[2] for r in ranked[:max_suggestions]]

        return HealResponse(
            suggestions=[s for s in suggestions if s.confidence >= BASE_CONF],
            model="mock-1",
            latency_ms=max(int((time.perf_counter() - start) * 1000), 1),
            tokens_used=0,
        )
