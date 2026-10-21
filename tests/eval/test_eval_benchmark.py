"""Heal-quality benchmark (FR-11): offline, deterministic, no site needed.

Pipeline under test (exactly the live path, minus the browser click):
  provider.propose(intent, action, html) -> ranked candidates
  uniqueness guard                        (mirrors BasePage strict-mode)
  candidate resolves to == ground-truth marker? -> true_positive

Edge handling:
  resolves-to-nothing  -> skipped by the uniqueness guard (same as live)
  resolves-elsewhere   -> false_positive  (graded worse than a miss)
  nothing survivable   -> miss

Output: reports/eval_report.json + eval_report.html (numbers for README/CI).
"""
from __future__ import annotations

import html as _html
import json
from pathlib import Path

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from src.locators.providers.mock import MockProvider
from tests.eval.fixtures import CASES

REPORTS = Path(__file__).resolve().parents[2] / "reports"

pytestmark = [pytest.mark.eval]


def _unique(page: Page, selector: str) -> bool:
    """Dry-run guard: an unambiguous element exists (or invalid selector)."""
    try:
        return page.locator(selector).count() == 1
    except PlaywrightError:
        return False


def _same_target(page: Page, selector: str, marker: str) -> bool:
    """Do two selectors resolve to the *same DOM node*?"""
    try:
        first = page.locator(selector).first
        second = page.locator(marker).first
        return bool(page.evaluate(
            "([x, y]) => x === y",
            [first.evaluate_handle("el => el"), second.evaluate_handle("el => el")],
        ))
    except PlaywrightError:
        return False


@pytest.fixture(scope="session")
def ledger(request):
    """Collects per-case rows; writes the JSON+HTML report at session end."""
    rows: list[dict] = []

    def _write() -> None:
        REPORTS.mkdir(parents=True, exist_ok=True)
        verdicts = [r["verdict"] for r in rows]
        tp = verdicts.count("true_positive")
        fp = verdicts.count("false_positive")
        miss = verdicts.count("miss")
        precision = round(tp / (tp + fp), 3) if tp + fp else None
        recall = round(tp / (tp + fp + miss), 3) if tp + fp + miss else None
        data = {
            "scored": len(rows),
            "true_positive": tp,
            "false_positive": fp,
            "miss": miss,
            "precision": precision,   # how clean are the heals it does make?
            "recall": recall,         # how many targets can it reach at all?
            "cases": rows,
        }
        (REPORTS / "eval_report.json").write_text(
            json.dumps(data, indent=2), encoding="utf-8")

        rows_html = "".join(
            f"<tr><td>{_html.escape(r['key'])}</td>"
            f"<td>{_html.escape(r['verdict'])}</td>"
            f"<td>{_html.escape(str(r['chosen']))}</td>"
            f"<td>{_html.escape(str(r['confidence']))}</td>"
            f"<td>{_html.escape(str(r['rationale']))}</td></tr>"
            for r in rows
        )
        (REPORTS / "eval_report.html").write_text(
            "<h1>Heal-quality benchmark (offline)</h1>"
            f"<p>scored={len(rows)} TP={tp} FP={fp} miss={miss} "
            f"precision={precision} recall={recall}</p>"
            "<table border='1' cellpadding='6'>"
            "<tr><th>case</th><th>verdict</th><th>healed selector</th>"
            "<th>confidence</th><th>rationale</th></tr>"
            f"{rows_html}</table>",
            encoding="utf-8",
        )
        print(f"\n[eval] report -> {REPORTS / 'eval_report.html'} "
              f"(TP={tp} FP={fp} miss={miss})")

    request.addfinalizer(_write)
    return rows


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["key"])
def test_heal_quality(case, browser, ledger):
    with browser.new_context() as ctx:
        page = ctx.new_page()
        page.set_content(case["html"])

        # fixture sanity: ground truth itself must be unambiguous
        assert _unique(page, case["marker"]), \
            f"bad fixture: marker not unique on {case['key']}"

        resp = MockProvider().propose(
            intent=case["intent"],
            failed_selector="#__broken__",
            url="eval://fixture",
            html_snippet=case["html"],
            action=case["action"],
        )

        verdict, chosen, conf, why = "miss", None, None, "no surviving candidate"
        for cand in resp.suggestions:
            if not _unique(page, cand.selector):
                continue                     # mirrors BasePage strict-mode guard
            if _same_target(page, cand.selector, case["marker"]):
                verdict = "true_positive"
            else:
                verdict = "false_positive"
            chosen, conf, why = cand.selector, cand.confidence, cand.rationale
            break

        ledger.append({
            "key": case["key"],
            "verdict": verdict,
            "chosen": chosen,
            "confidence": conf,
            "rationale": why,
        })


def test_benchmark_scope_is_20_cases():
    keys = [c["key"] for c in CASES]
    assert len(CASES) == 20
    assert len(set(keys)) == 20
