"""pytest fixtures: settings -> browser -> page (+ failure screenshots).

Scope strategy:
  session browser  -> launch Chromium once per CI job (biggest time saver)
  function page     -> fresh context per test (cookie/state isolation)
"""
from __future__ import annotations

import time

import pytest
from playwright.sync_api import sync_playwright

from src.core.config import Settings, load_settings
from src.core.logger import logger


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Store each phase's result on the item so fixtures can read it."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


@pytest.fixture(scope="session")
def settings() -> Settings:
    return load_settings()


@pytest.fixture(scope="session")
def browser(settings: Settings):
    with sync_playwright() as p:
        launcher = getattr(p, settings.browser)  # chromium | firefox | webkit
        b = launcher.launch(headless=settings.headless)
        yield b
        b.close()


@pytest.fixture()
def page(browser, settings: Settings, request):
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        ignore_https_errors=True,
    )
    pg = context.new_page()
    pg.set_default_timeout(settings.timeout_ms)
    yield pg
    # screenshot on failure (FR-09 evidence)
    rep = getattr(request.node, "rep_call", None)
    if rep is not None and rep.failed:
        out = f"reports/screenshots/{request.node.name}-{int(time.time())}.png"
        try:
            pg.screenshot(path=out, full_page=True)
            logger.error(f"FAILED test -> screenshot {out}")
        except Exception as exc:  # page may already be closed/crashed
            logger.warning(f"screenshot skipped: {exc}")
    context.close()
