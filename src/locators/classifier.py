"""Failure classifier.

Rule #1 of self-healing: NEVER heal a real bug.
- element not found / hidden      -> LOCATOR_FAILURE  (heal OK)
- assertion wrong (bad data)      -> ASSERTION_FAILURE (never heal)
- server 5xx / crash              -> APP_FAILURE       (never heal)
- one-off timeout, element exists -> FLAKY_TIMEOUT     (retry only)
"""
from __future__ import annotations

from enum import Enum


class FailureKind(str, Enum):
    LOCATOR_FAILURE = "locator_failure"
    ASSERTION_FAILURE = "assertion_failure"
    APP_FAILURE = "app_failure"
    FLAKY_TIMEOUT = "flaky_timeout"
    UNKNOWN = "unknown"


def classify(
    message: str,
    *,
    element_exists: bool | None = None,
    status_code: int | None = None,
) -> FailureKind:
    """Heuristic classification from error text + optional context.

    Pure function (no I/O) -> easy to unit test in tests/unit/.
    """
    m = message.lower()

    if status_code is not None and status_code >= 500:
        return FailureKind.APP_FAILURE

    # Playwright locator errors -> element missing / not actionable
    if any(s in m for s in (
        "no element found",
        "not found",
        "waiting for locator",
        "timeout waiting for",
        "locator does not exist",
    )):
        if element_exists is True:
            return FailureKind.FLAKY_TIMEOUT     # element present, just slow -> retry
        if element_exists is False:
            return FailureKind.LOCATOR_FAILURE    # element gone -> heal
        return FailureKind.FLAKY_TIMEOUT          # unknown -> retry first, heal last

    # assertion / data errors -> real bug, never heal
    if any(s in m for s in ("assert", "expected", "to equal", "to contain", "pytest")):
        return FailureKind.ASSERTION_FAILURE

    if element_exists is True:
        return FailureKind.FLAKY_TIMEOUT

    return FailureKind.UNKNOWN
