"""Heal resolver: propose -> validate -> verify -> persist.

Flow when a test hits LOCATOR_FAILURE:
  1. build prompt context (url, html snippet, intent)
  2. ask provider for up to 3 candidate selectors (latency + tokens logged)
  3. syntactically validate candidates (dry-run against page)
  4. first candidate that satisfies the original action wins
  5. registry.apply_heal(key, winner)  -> saved for all future runs
  6. everything (hit/miss, confidence, cost) -> heal_metrics.json

Guards:
  - MAX_HEAL_CALLS_PER_RUN caps spend
  - MIN_CONFIDENCE filters low-quality guesses
  - cache dedupes identical failures
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.core.logger import logger
from src.locators.providers.base import LLMProvider
from src.locators.providers.factory import get_provider
from src.locators.registry import LocatorRegistry, get_registry

MIN_CONFIDENCE = 0.5
METRICS_PATH = Path(__file__).resolve().parents[2] / "heal_metrics.json"


@dataclass
class HealAttempt:
    locator_key: str
    url: str
    failed_selector: str
    outcome: str                     # healed | unhealable | skipped_budget | cache_hit
    chosen_selector: str | None = None
    confidence: float = 0.0
    model: str = ""
    latency_ms: int = 0
    tokens_used: int = 0
    candidates_tried: int = 0
    error: str = ""
    ts: float = field(default_factory=time.time)


class HealResolver:
    def __init__(
        self,
        registry: LocatorRegistry | None = None,
        provider: LLMProvider | None = None,
        *,
        max_calls: int = 20,
        enabled: bool = True,
    ) -> None:
        self.registry = registry or get_registry()
        self.provider = provider or get_provider()
        self.max_calls = max_calls
        self.enabled = enabled
        self.calls_used = 0
        self._cache: dict[str, list] = {}   # (url, selector, intent) -> suggestions
        self.attempts: list[HealAttempt] = []

    # ---------- public API ----------

    def heal(self, locator_key: str, *, url: str, html_snippet: str,
             action: str = "click", validate=None) -> HealAttempt:
        entry = self.registry.get(locator_key)

        if not self.enabled:
            return self._record(locator_key, url, entry.primary, "skipped_budget", error="healing disabled")
        if self.calls_used >= self.max_calls:
            return self._record(locator_key, url, entry.primary, "skipped_budget",
                                error=f"budget {self.max_calls} exhausted")

        cache_key = (url, entry.primary, entry.intent, action)
        suggestions = self._cache.get(cache_key)
        cached = suggestions is not None
        if suggestions is None:
            self.calls_used += 1
            response = self.provider.propose(
                intent=entry.intent,
                failed_selector=entry.primary,
                url=url,
                html_snippet=html_snippet,
                action=action,
            )
            suggestions = response.suggestions
            self._cache[cache_key] = [asdict(s) for s in suggestions]
            model, latency, tokens = response.model, response.latency_ms, response.tokens_used
        else:
            from src.locators.providers.base import LocatorSuggestion

            suggestions = [LocatorSuggestion(**s) for s in suggestions]
            model, latency, tokens = "cache", 0, 0

        if cached:
            self._record(locator_key, url, entry.primary, "cache_hit")
            # fall through: reuse suggestions without new LLM call

        candidates = [s for s in suggestions if s.confidence >= MIN_CONFIDENCE]
        candidates.sort(key=lambda s: s.confidence, reverse=True)
        rejected: list[str] = []

        for cand in candidates:
            # dry-run: syntax + presence check delegated to caller (step 3 UI glue)
            # here we only accept candidates that are non-empty strings
            if not cand.selector:
                continue
            if validate is not None and not validate(cand.selector):
                rejected.append(cand.selector)   # ambiguous/invalid -> try next
                continue
            self.registry.apply_heal(locator_key, cand.selector)
            attempt = self._record(
                locator_key, url, entry.primary, "healed",
                chosen_selector=cand.selector, confidence=cand.confidence,
                model=model, latency_ms=latency, tokens_used=tokens,
                candidates_tried=len(candidates),
            )
            logger.info(
                f"HEAL ok | {locator_key} -> {cand.selector!r} "
                f"(conf={cand.confidence}, {latency}ms, {tokens} tok)"
            )
            return attempt

        return self._record(
            locator_key, url, entry.primary, "unhealable",
            model=model, latency_ms=latency, tokens_used=tokens,
            candidates_tried=len(candidates),
            error=f"no candidate passed (filtered={len(rejected)}, "
                  f"below-confidence={len(candidates) - len(rejected)})",
        )

    # ---------- persistence ----------

    def _record(self, key: str, url: str, failed: str, outcome: str, **kw) -> HealAttempt:
        attempt = HealAttempt(locator_key=key, url=url, failed_selector=failed, outcome=outcome, **kw)
        self.attempts.append(attempt)
        self.flush()
        return attempt

    def flush(self) -> None:
        """Write heal_metrics.json (read by CI + README badges)."""
        healed = sum(1 for a in self.attempts if a.outcome == "healed")
        tried = sum(1 for a in self.attempts if a.outcome in ("healed", "unhealable"))
        tokens = sum(a.tokens_used for a in self.attempts)
        metrics = {
            "generated_at": time.time(),
            "totals": {
                "attempts": len(self.attempts),
                "healed": healed,
                "unhealable": sum(1 for a in self.attempts if a.outcome == "unhealable"),
                "budget_skips": sum(1 for a in self.attempts if a.outcome == "skipped_budget"),
                "cache_hits": sum(1 for a in self.attempts if a.outcome == "cache_hit"),
                "heal_rate": round(healed / tried, 3) if tried else None,
                "llm_calls": self.calls_used,
                "tokens": tokens,
                "model": getattr(self.provider, "name", "?"),
            },
            "attempts": [asdict(a) for a in self.attempts],
            "registry": self.registry.export(),
        }
        METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")


_resolver: HealResolver | None = None


def get_resolver() -> HealResolver:
    global _resolver
    if _resolver is None:
        from src.core.config import load_settings

        s = load_settings()
        _resolver = HealResolver(max_calls=s.max_heal_calls, enabled=s.heal_enabled)
    return _resolver
