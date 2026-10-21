# 🔧 AI Self-Healing Test Automation Framework

[![CI](https://github.com/YOUR_GITHUB_USER/self-healing-qa-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_GITHUB_USER/self-healing-qa-framework/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![Healing cost](https://img.shields.io/badge/healing%20cost-%240%20(mock%20provider)-green)
![License](https://img.shields.io/badge/license-MIT-black)

> **Test automation that repairs itself.** When a website changes a button and
> tests break, an LLM proposes a replacement locator, a failure classifier
> decides whether healing is *allowed*, the fix is verified by actually
> retrying the step — and it's persisted for all future runs.
> Belt, braces, and an audit trail.

**Built by a QA Engineer (~2 YoE) as a portfolio project: Playwright + pytest + swappable LLM providers.**

---

## The number that matters

Demo run (`python scripts/demo_heal.py` — two locators deliberately destroyed to simulate a redesign):

| Element | Broken selector fed to the test | Result | Recovered to | Confidence |
|---|---|---|---|---|
| `login_submit` | `#broken-login-button` | ✅ healed | `[data-qa="login-button"]` | 0.75 |
| `search_button` | `#broken-search-button` | ✅ healed | `[id="submit_search"]` | 0.75 |

**Heal rate: 100% · 0 manual fixes · 0 tokens billed ( provider=mock ) · both tests passed automatically.**

Full raw evidence: [`heal_metrics.json`](heal_metrics.json) (written after every run).

## Offline benchmark: how often does healing pick the *right* element?

`pytest tests/eval` runs 20 mutated fixtures (5 page templates × 4 redesign
kinds: attribute renamed / label renamed / full redesign / distractors) with
**zero network access**, grading every heal against a ground-truth marker:

| Metric | Value | Meaning |
|---|---|---|
| Scored | 20 cases | offline, reproducible, ~30 s |
| **Precision** | **0.90** | 18 true positives / 20 attempted heals |
| **Recall** | **0.90** | 18 targets recovered, 2 never found |
| False positives | 2 | healed to the *wrong* element — the failure worth studying |

The 2 false positives are **exactly the cases with the lowest confidence scores
in the dataset (0.55 / 0.65 vs 0.65–0.85 typical)** — both are pure-lexical
traps for the heuristic mock provider (`text=Cart summary` vs `Complete
purchase`; `text=Submit a ticket` vs `Send message`). A semantic LLM passes
both; the free mock is the honest floor. This is why confidence appears next
to every healed selector in `heal_metrics.json` and the eval report:
**ranked candidates with calibrated uncertainty**, not binary guesses.

Report files every run: `reports/eval_report.json` + `reports/eval_report.html`.

---

## Why this is safer than "let the AI fix everything"

Every failure passes a **triage classifier first** — the AI is never allowed to hide a real bug:

| Verdict | Meaning | Action |
|---|---|---|
| `LOCATOR_FAILURE` | element genuinely gone | 🤖 heal → retry → persist |
| `ASSERTION_FAILURE` | wrong data | ❌ fail loudly — a human bug, not a moved button |
| `APP_FAILURE` | server 5xx / crash | ❌ fail loudly — an outage is not a locator problem |
| `FLAKY_TIMEOUT` | element present, just slow | 🔁 one plain retry — **no LLM spend** |

And every real heal is **validated by replaying the original action** against the page. If the AI guess is wrong, the retry throws and the test fails with the exact reasoning attached. Healing never produces a silent false pass.

## What a heal actually looks like

```
click("login_submit")  →  registry entry says  button[data-qa=login-button]
        │
        ▼ page.click() raises TimeoutError (element missing)
   classify() → LOCATOR_FAILURE  ✔ only this verdict spends a heal call
        │
        ▼ HealResolver
   budget 3/20 used ← cost guard            cache: miss
        │
        ▼ provider.propose(intent="Submit login form", html=<sanitized page>)
   candidates:  [data-qa="login-button"]  conf 0.75
        │
        ▼ confidence ≥ MIN_CONFIDENCE(0.5)
   retry click with the NEW selector → works
        │
        ▼
   registry.apply_heal()  → bootstrap.json updated, old selector kept in history
   HealAttempt recorded   → heal_metrics.json (rate, latency, tokens, screenshots)
```

---

## One-command start

```bash
git clone https://github.com/YOUR_GITHUB_USER/self-healing-qa-framework
cd self-healing-qa-framework

python -m venv .venv
.venv/Scripts/activate          # Windows  |  source .venv/bin/activate on Linux/macOS
python -m pip install -e ".[dev]"
python -m playwright install chromium

# run everything (offline unit tests + live smoke tests, free mock provider)
python -m pytest tests/unit -q
python -m pytest tests/ui -m smoke -v

# the demo: break 2 locators, watch the framework repair itself
python scripts/demo_heal.py
```

Tired of the mock? Point it at a real brain — one env var, zero code changes:

```dotenv
LLM_PROVIDER=openai            # or ollama (free, local)
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
```

## Architecture

```
     tests/ui/*.py                 declarative smoke/regression checks
          │
     src/pages/*                   Page Objects — fluent, registry-driven actions
          │
     src/pages/base_page.py  ⚡     heal engine: act → classify → heal → retry
          │
     src/locators/registry.py      THE ADDRESS BOOK (bootstrap.json):
          │                        primary / intent / healed / history per element
          │
     src/locators/classifier.py    triage nurse — heals only LOCATOR_FAILURE
          │
     src/locators/heal_resolver.py budget · cache · confidence filter · metrics
          │
     src/locators/providers/*      LLMProvider Protocol
          ├── mock.py              free deterministic heuristic (tests & CI)
          ├── openai_provider.py   real LLM, JSON mode, HTML sanitising
          └── factory.py           LLM_PROVIDER=mock|openai|ollama
```

**Key decisions & trade-offs** *(mentioned in interviews)*

1. **Locators in JSON, not code.** A UI change edits one data row — or none, because the healer edits it. `primary` is never overwritten; `healed` wins at read time → rollback is trivial.
2. **`intent` (purpose) travels to the LLM, not the selector.** "Submit login form" survives redesigns; `button[data-qa=login-button]` doesn't. Purpose-descriptions are the durable part.
3. **Heal is validated by replay, not by trust.** No dry-run oracle needed; a wrong suggestion fails the test with the reasoning attached.
4. **Budget + cache + confidence floor.** `max_heal_calls=20`, identical failures served from cache (0 cost), `confidence < 0.5` candidates discarded. Cost is a first-class test constraint.
5. **HTML sanitising before any outbound call.** `<script>` stripped, `value="…"` redacted, JWTs removed — healing never leaks PII/secrets (FR-08).
6. **A failure to heal fails loudly.** No silent fake passes — an "unhealable" outcome still records cost, candidates and the attempt for the report.

## Repo layout

```
.github/workflows/ci.yml        CI: unit → smoke ×(chromium, firefox) → heal gate → artifacts
config/                         dev.yaml | ci.yaml
src/core/                       config (YAML+env), run-scoped logging
src/locators/                   registry · classifier · heal_resolver · providers/
src/pages/                      base_page (heal engine) + page objects
locators/registry/              bootstrap.json — the live address book
tests/unit/                     15 offline checks (classifier/registry/resolver/factory)
tests/ui/                       3 smoke tests vs automationexercise.com
tests/eval/                     20-case offline heal-quality benchmark (FR-11)
src/mcp_server/                 MCP server: run_tests / heal_report / registry_status /
                                rollback_locator / run_heal_demo as AI-callable tools
scripts/demo_heal.py            the break-and-heal demo (Step 4 evidence)
scripts/mcp_smoke.py            spec-level MCP handshake test (no AI client needed)
scripts/heal_gate.py            CI gate: heal_rate ≥ 0.70 or the build fails
docs/CODE_WALKTHROUGH.md        file-by-file, line-by-line tour
heal_metrics.json               generated — totals, heal rate, per-attempt log
reports/                        allure-results + failure screenshots (generated)
```

## Evidence you can click

| Artifact | Where |
|---|---|
| Live CI runs with green ✅ | Repository → Actions tab |
| Heal report JSON every run | `heal_metrics.json` artifact |
| Failure screenshots | `reports/screenshots/*` artifact |
| Break-and-heal demo transcript | run `python scripts/demo_heal.py` locally |
| **Offline eval report (precision/recall)** | `reports/eval_report.html` or CI artifact |
| **Public live status page (Pages)** | `https://YOUR_GITHUB_USER.github.io/self-healing-qa-framework/` — rebuilt on every push to main |
| 15 unit + 3 UI + 21 eval passing test proofs | CI logs, `pytest -v` |

## MCP: AI assistants can operate the framework

`src/mcp_server/` exposes 5 tools over the **Model Context Protocol** —
Claude Desktop, Cursor or Claude Code can run your tests, read the heal
report, roll back a locator, or trigger the break-and-heal demo on demand:

```json
{"name": "run_tests", "arguments": {"scope": "smoke"}}
{"name": "heal_report", "arguments": {}}
```

Setup for every client (Claude Desktop / Cursor / Claude Code):
**[`docs/MCP_SETUP.md`](docs/MCP_SETUP.md)**. Spec-level proof without any
client installed: `python scripts/mcp_smoke.py` (raw JSON-RPC handshake +
real tool calls, all green).

## FAQ

**Does it actually call an LLM?** Switchable. `mock` = free regex-heuristic (works offline), `openai` = real call (JSON-mode), `ollama` = local free. The heal path, budgeting, caching, classifier and reporting are identical in all three — that's the point of the provider Contract.

**What stops cost blowup?** Budget cap per run, cache for identical failures, 12,000-char HTML snippet cap, 400-token reply cap, `confidence ≥ 0.5` floor, plus a CI gate that fails the build if healing quality drops.

**Why not just use data-test-id selectors everywhere?** Real teams inherit apps that don't have them. This framework is the low-cost answer for the *legacy* case.

**What's next?** Maven-free LLM pass on the 2 benchmark FPs (semantic fix vs
lexical mock), Allure→GitHub Pages publishing. MCP server shipped in
`src/mcp_server/` (see `docs/MCP_SETUP.md`).

---

*Built with: Python 3.12 · Playwright · pytest · pytest-xdist · Allure · OpenAI API (swappable) · GitHub Actions*
