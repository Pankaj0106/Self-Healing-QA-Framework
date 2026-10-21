"""Page Object base: every page action is registry-driven + heal-aware.

Heal loop (FR-03/FR-04):
    action fails -> classify() -> LOCATOR_FAILURE? -> resolver.heal() -> retry once
Real bugs (assertion/app) and flakes are re-raised untouched.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from playwright.sync_api import Locator, Page
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from src.locators.classifier import FailureKind, classify
from src.locators.heal_resolver import get_resolver
from src.locators.registry import get_registry

SNIPPET_CHARS = 12000  # matches sanitize_html() cap


class BasePage:
    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url
        self.registry = get_registry()
        self.resolver = get_resolver()

    # ---------- registry helpers ----------

    def locator(self, key: str) -> Locator:
        """Live Locator from the registry's *active* selector."""
        return self.page.locator(self.registry.get(key).active)

    # ---------- heal-wrapped actions (public API for page objects) ----------

    def click(self, key: str, *, timeout: int | None = None) -> None:
        self._act(key, lambda sel: self.page.click(sel, timeout=timeout), action="click")

    def fill(self, key: str, value: str, *, timeout: int | None = None) -> None:
        self._act(key, lambda sel: self.page.fill(sel, value, timeout=timeout), action="fill")

    def text_of(self, key: str, *, timeout: int | None = None) -> str:
        return self._act(key, lambda sel: self.page.text_content(sel, timeout=timeout) or "", action="read")

    def visible(self, key: str, *, timeout: int | None = None) -> bool:
        try:
            return self._act(key, lambda sel: self.page.wait_for(sel, timeout=timeout) is None, action="read")
        except (PlaywrightTimeoutError, PlaywrightError):
            return False

    # ---------- the heal engine ----------

    def _act(self, key: str, operation: Callable[[str], Any], action: str = "click") -> Any:
        entry = self.registry.get(key)
        try:
            return operation(entry.active)
        except (PlaywrightTimeoutError, PlaywrightError) as exc:
            return self._recover(key, exc, operation, action)

    def _recover(self, key: str, exc: Exception, operation: Callable[[str], Any], action: str) -> Any:
        """Decide: heal / retry / re-raise. Only LOCATOR_FAILURE spends a call."""
        kind = classify(str(exc), element_exists=self._exists(key))

        if kind == FailureKind.LOCATOR_FAILURE:
            attempt = self.resolver.heal(
                key,
                url=self.page.url,
                html_snippet=self.page.content()[:SNIPPET_CHARS],
                action=action,
                validate=self._unique,
            )
            if attempt.outcome == "healed":
                return operation(self.registry.get(key).active)  # retry with new selector
            raise exc  # unhealable / budget exhausted -> fail loudly (FR-04.6)

        if kind == FailureKind.FLAKY_TIMEOUT:
            return operation(self.registry.get(key).active)  # one plain retry, no LLM spend

        raise exc  # ASSERTION / APP / UNKNOWN -> never hide a real bug

    # ---------- utils ----------

    def _exists(self, key: str) -> bool:
        try:
            return self.page.locator(self.registry.get(key).active).count() > 0
        except Exception:
            return False

    def _unique(self, selector: str) -> bool:
        """Dry-run guard: candidate must resolve to exactly ONE element.

        Matches > 1 would fail later with a strict-mode violation when the
        healed selector is actually clicked — better to reject the candidate
        now and try the next-best suggestion instead.
        """
        try:
            return self.page.locator(selector).count() == 1
        except PlaywrightError:
            return False
