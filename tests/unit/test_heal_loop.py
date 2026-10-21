"""Step 2 acceptance: the heal loop works offline with the mock provider.

Run: python -m pytest tests/unit -v
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.locators.classifier import FailureKind, classify
from src.locators.heal_resolver import HealResolver
from src.locators.providers.mock import MockProvider
from src.locators.registry import LocatorEntry, LocatorRegistry

# ---------- classifier ----------

def test_locator_failure_classified():
    assert classify("Timeout waiting for locator #login", element_exists=False) == FailureKind.LOCATOR_FAILURE

def test_assertion_never_heals():
    assert classify("AssertionError: expected 'Cart' to equal 'Basket'") == FailureKind.ASSERTION_FAILURE

def test_server_error_is_app_failure():
    assert classify("internal server error", status_code=503) == FailureKind.APP_FAILURE

def test_flaky_when_element_exists():
    assert classify("Timeout waiting for locator", element_exists=True) == FailureKind.FLAKY_TIMEOUT


# ---------- registry (tmp_path => no mutation of real bootstrap.json) ----------

@pytest.fixture
def registry(tmp_path: Path) -> LocatorRegistry:
    src = Path("locators/registry/bootstrap.json")
    dst = tmp_path / "registry.json"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return LocatorRegistry(dst)

def test_registry_reads_active_selector(registry: LocatorRegistry):
    e = registry.get("login_submit")
    assert e.active == "button[data-qa=login-button]"

def test_apply_heal_persists_and_keeps_history(registry: LocatorRegistry):
    registry.apply_heal("login_submit", "button:has-text('Log in')")
    reloaded = LocatorRegistry(registry.path)  # fresh read = proves persistence
    e = reloaded.get("login_submit")
    assert e.active == "button:has-text('Log in')"
    assert e.primary == "button[data-qa=login-button]"      # original untouched
    assert e.history == []                                   # first heal: no history yet

def test_rollback_restores_original(registry: LocatorRegistry):
    registry.apply_heal("email_field", "[name=email]")
    registry.rollback("email_field")
    assert registry.get("email_field").active == "input[data-qa=login-email]"


# ---------- resolver: full heal loop, offline ----------

class TinyRegistry(LocatorRegistry):
    """Minimal in-memory registry for the resolver test."""

    def __init__(self, entry: LocatorEntry):
        self._entries = {"btn": entry}
        self.path = Path("/dev/null")  # never written

    def _save(self):  # skip disk I/O
        pass

def test_resolver_heals_with_mock_provider():
    entry = LocatorEntry(key="btn", primary="#old-button", strategy="css",
                         intent="Login button")
    reg = TinyRegistry(entry)
    html = '<button data-qa="login-button">Log in</button>'

    resolver = HealResolver(registry=reg, provider=MockProvider(), max_calls=5)
    attempt = resolver.heal("btn", url="https://x.dev/login", html_snippet=html)

    assert attempt.outcome == "healed"
    assert entry.active == '[data-qa="login-button"]'        # mock found data-qa attr
    assert resolver.calls_used == 1                          # exactly one LLM call

def test_budget_cap_blocks_llm_call():
    entry = LocatorEntry(key="btn", primary="#x", strategy="css", intent="Login button")
    reg = TinyRegistry(entry)
    resolver = HealResolver(registry=reg, provider=MockProvider(), max_calls=0)

    attempt = resolver.heal("btn", url="u", html_snippet="<button>Login</button>")
    assert attempt.outcome == "skipped_budget"
    assert resolver.calls_used == 0                          # provider never invoked


class ScriptedProvider:
    """Test double returning fixed suggestions in order (validator tests)."""

    name = "scripted"

    def __init__(self, selectors: list[str]):
        from src.locators.providers.base import HealResponse, LocatorSuggestion

        self._sels = selectors
        self._HealResponse, self._Suggestion = HealResponse, LocatorSuggestion

    def propose(self, **kwargs):
        return self._HealResponse(
            suggestions=[self._Suggestion(s, "css", 0.9, "scripted") for s in self._sels],
            model="scripted", latency_ms=1, tokens_used=0,
        )


def test_validator_rejects_ambiguous_candidate():
    """1st suggestion is invalid per the validator -> 2nd one wins."""
    entry = LocatorEntry(key="btn", primary="#old", strategy="css", intent="Login")
    reg = TinyRegistry(entry)
    resolver = HealResolver(registry=reg, provider=ScriptedProvider(["#ambig", "#good"]))

    attempt = resolver.heal(
        "btn", url="u", html_snippet="<div/>",
        validate=lambda sel: sel != "#ambig",   # page says: #ambig is not usable
    )
    assert attempt.outcome == "healed"
    assert attempt.chosen_selector == "#good"
    assert reg.get("btn").active == "#good"


def test_validator_rejects_everything():
    entry = LocatorEntry(key="btn", primary="#old", strategy="css", intent="Login")
    resolver = HealResolver(
        registry=TinyRegistry(entry),
        provider=ScriptedProvider(["#a", "#b"]),
    )
    attempt = resolver.heal("btn", url="u", html_snippet="<div/>",
                            validate=lambda sel: False)
    assert attempt.outcome == "unhealable"
    assert "filtered=2" in attempt.error

def test_metrics_file_written():
    entry = LocatorEntry(key="btn", primary="#x", strategy="css", intent="Login")
    resolver = HealResolver(registry=TinyRegistry(entry), provider=MockProvider())
    resolver.heal("btn", url="u", html_snippet='<button data-qa="login">Login</button>')

    metrics = json.loads(Path("heal_metrics.json").read_text())
    assert metrics["totals"]["attempts"] == 1
    assert metrics["totals"]["healed"] == 1
    assert metrics["totals"]["heal_rate"] == 1.0


# ---------- provider factory ----------

def test_factory_default_is_mock():
    from src.locators.providers.factory import get_provider

    assert get_provider("mock").name == "mock"


# ---------- mock provider: intent-aware ranking (added Step 4) ----------

CLICK_HTML = (
    '<input data-qa="signup-name"/>'
    '<button data-qa="signup-button">Signup</button>'
    '<button data-qa="login-button">Login</button>'
)

def test_mock_click_prefers_matching_button():
    from src.locators.providers.factory import get_provider

    resp = get_provider("mock").propose(
        intent="Submit login form", failed_selector="#old",
        url="u", html_snippet=CLICK_HTML, action="click",
    )
    # input tags must never be suggested for a click; login beats signup
    assert resp.suggestions[0].selector == '[data-qa="login-button"]'

FILL_HTML = (
    '<input data-qa="signup-email"/>'
    '<input id="login-email"/>'
    '<input id="login-password"/>'
)

def test_mock_fill_prefers_matching_input():
    from src.locators.providers.factory import get_provider

    resp = get_provider("mock").propose(
        intent="Email input on login form", failed_selector="#old",
        url="u", html_snippet=FILL_HTML, action="fill",
    )
    # 'login-email' outranks 'signup-email': "email"+"login" match > "email" alone
    assert resp.suggestions[0].selector == '[id="login-email"]'
