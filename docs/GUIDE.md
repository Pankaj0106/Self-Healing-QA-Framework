# 📘 The Complete Project Guide — Self-Healing QA Framework

**Read this once and you'll know where everything lives, what it does, why it exists, and how to run it.**

*Companion documents: `REQUIREMENTS.md` (what the product must do) ·
`docs/CODE_WALKTHROUGH.md` (line-by-line code tour) ·
`docs/DECISIONS.md` (why key choices were made) ·
`docs/MCP_SETUP.md` (connecting AI clients).*

---

## Part 1 — The project in 60 seconds

A UI test automation framework that **repairs itself**: when a website redesign
moves a button, the framework detects the failure, a *classifier* decides
whether healing is allowed, an *LLM provider* proposes replacement selectors,
the fix is *verified by retrying the real action*, then **persisted permanently**
with full audit history. Cost is capped, cache avoids repeat spend, and a CI
*gate* fails the build if healing quality drops.

| Fact | Value |
|---|---|
| Language | Python 3.11+ |
| Automation | Playwright + pytest |
| Healing "brains" | mock (free) / Ollama (local, free) / OpenAI gpt-4o-mini (paid) — switch by ONE env var |
| Target site | automationexercise.com (swap via config) |
| Test count | **39**: 15 unit + 21 eval + 3 UI smoke |
| CI | GitHub Actions: unit → smoke×2 browsers → heal gate → eval → Pages |
| Location on disk | `\\wsl.localhost\Ubuntu\home\pankaj\self_healing_qa_framework` (WSL: `/home/pankaj/self_healing_qa_framework`) |

---

## Part 2 — The annotated map (what every file IS)

```
self_healing_qa_framework/
│
│  📄 ROOT — 'front door' files
├── README.md ............... recruiter-facing pitch: numbers, demo evidence,
│                             architecture, FAQ. The 2 minutes someone gives your repo.
├── REQUIREMENTS.md ......... the spec: vision, goals G1-G6, functional requirements
│                             FR-01..FR-13, NFRs, architecture, acceptance criteria,
│                             3-week plan, risks. (You built against this.)
├── LICENSE ................. MIT — required for a public repo
├── pyproject.toml .......... project identity + dependency list + pytest config
│                             (markers, Allure always-on) + optional dep groups
│                             dev=[ruff,black,mypy,pytest-mock], mcp=[mcp>=1.2,<2]
├── Makefile ................ shortcut commands; TABS mandatory indentation.
│                             setup/test/smoke/eval/gate/demo/mcp/mcp-smoke/report
├── .env.example ............ TEMPLATE of private settings — copy to .env locally,
│                             NEVER commit .env (gitignored)
├── .gitignore .............. what git must never store: .env, reports/, _site/,
│                             __pycache__/, .venv/, generated artifacts
├── heal_metrics.json ....... ⚙️ GENERATED. Every healing event: outcome, chosen
│                             selector, confidence, latency, tokens + totals
│                             (heal_rate) + registry snapshot. README evidence.
├── .pytest_cache/ .......... ⚙️ GENERATED. pytest's speed caches. Ignore.
│
│  ⚙️ CONFIG — settings per environment
├── config/
│   ├── dev.yaml ............ YOUR machine: base_url, browser, headless(true/false),
│   │                         timeout_ms 10000, heal_enabled, max_heal_calls 20,
│   │                         llm_provider mock → Ollama per ADR-001 when activated
│   └── ci.yaml ............. GitHub machines: headless, timeout 15000
│
│  🧠 src/ — the product code (importable package 'src')
├── src/__init__.py ......... empty marker: makes 'src' an importable package
│
│  src/core/ — foundation (knows nothing of testing)
│   ├── __init__.py
│   ├── config.py ........... Settings loader. ROOT found via __file__.parents[2].
│   │                         Flow: .env (load_dotenv) → pick config/{ENV}.yaml →
│   │                         yaml.safe_load → ENV VARS OVERRIDE yaml values
│   │                         (BASE_URL, LLM_PROVIDER, LLM_MODEL, HEADLESS,
│   │                         MAX_HEAL_CALLS_PER_RUN) → frozen dataclass Settings.
│   │                         'frozen' = immutable after creation.
│   └── logger.py ........... loguru with an 8-char RUN_ID per process bound onto
│                             every line — filter one CI run's logs with grep.
│
│  src/locators/ — the self-healing brain
│   ├── __init__.py
│   ├── registry.py ......... The address book reader/writer. LocatorEntry dataclass
│   │                         (key/primary/strategy/intent/healed/history).
│   │                         entry.active = healed ?? primary (single truth).
│   │                         apply_heal() → writes JSON TO DISK IMMEDIATELY;
│   │                         rollback(); get_registry() singleton.
│   ├── classifier.py ....... The triage nurse (PURE function = no I/O, instantly
│   │                         testable). Types: LOCATOR_FAILURE (heal allowed!) /
│   │                         ASSERTION_FAILURE (never heal) / APP_FAILURE (never) /
│   │                         FLAKY_TIMEOUT (retry only) / UNKNOWN.
│   ├── heal_resolver.py .... The healing loop. HealAttempt dataclass per event.
│   │                         heal(key, url, html_snippet, action, validate):
│   │                         disabled → skipped_budget | calls_used >= max →
│   │                         skipped_budget | else provider.propose → cache →
│   │                         filter confidence < 0.5 → sort desc → validate(sel)
│   │                         dry-run guard → first survivor wins →
│   │                         registry.apply_heal() | else 'unhealable' (test fails
│   │                         LOUDLY). flush() → heal_metrics.json after EVERY
│   │                         attempt. get_resolver() singleton from settings.
│   └── providers/           The consultant layer (one Protocol, three brains)
│       ├── base.py ......... Protocol 'LLMProvider' + dataclasses
│       │                     LocatorSuggestion & HealResponse (latency/tokens).
│       ├── mock.py ......... FREE deterministic heuristic = current default. Parses
│       │                     the html snippet per action type (click→button/a,
│       │                     fill/read→input/textarea), scores each by intent-word
│       │                     overlap, ranks. Units + CI + live demo all pass.
│       │                     Benchmark verdict: precision 0.90, recall 0.90 (20 cases).
│       ├── openai_provider.py  Real LLM (also serves Ollama). sanitize_html()
│       │                     FIRST (script strip, value redact, JWT removal, 12k
│       │                     cap) → chat.completions temperature=0, JSON mode,
│       │                     max_tokens=400 → parse → suggestions. base_url param
│       │                     = Ollama localhost:11434/v1 works here too.
│       └── factory.py ...... get_provider() — LLM_PROVIDER=mock|openai|ollama.
│                             Lazy imports (only import what's actually used).
│                             Unknown value → loud ValueError.
│
│  src/pages/ — the robot's hands (Page Object Model)
│   ├── __init__.py
│   ├── base_page.py ....... THE HEAL ENGINE. click/fill/text_of/visible all
│   │                         funnel into _act(key, operation, action) where
│   │                         operation is a closure. On Playwright error →
│   │                         _recover(): classify → LOCATOR? heal(validate=_
│   │                         _unique) → retry ONCE with new selector; FLAKY?
│   │                         plain retry; else re-raise. _unique() = dry-run
│   │                         count()==1 guard (strict-mode protection, built Step 6).
│   ├── home_page.py ....... open() (goto wait_until='domcontentloaded', 45s for ad-
│   │                         heavy site) · go_to_signup_login() · go_to_products().
│   ├── login_page.py ...... login_with(email,pwd) [fill+fill+click, heal-eligible]
│   │                         · expect_error(text) + expect_form_visible()
│   │                         [Playwright assertions — NEVER healed, by design]
│   └── products_page.py ... search(term) · expect_results() (text-based check).
│
│  🛤 src/mcp_server/ — AI assistants operate the framework (MCP protocol)
│   └── server.py .......... FastMCP stdio server, 5 tools:
│                             run_tests(scope) / heal_report() / registry_status()
│                             / rollback_locator(key) / run_heal_demo(keep).
│                             Registry loaded per call; subprocess for pytest
│                             (timeout 900s). Run: make mcp. Prove w/o client:
                             make mcp-smoke.
│
│  🧪 tests/ — the proofs
├── tests/__init__.py
├── tests/conftest.py ....... pytest's auto-loaded fixture/hook file:
│                             settings (session) • browser (session, ONE Chromium)
│                             • page (function: fresh context per test;
│                             set_default_timeout; ON FAILURE -> screenshot
│                             reports/screenshots/*.png) • hookwrapper stores
│                             rep_setup/call/teardown on the test item.
│
│  tests/unit/ — 15 offline brain checks, seconds, no network
│   └── test_heal_loop.py ... classifier 4 (incl. the real bug we fixed:
│   │                         element-present was healing instead of retrying) ·
│   │                         registry 3 (heal persists + rollback, via tmp_path) ·
│   │                         resolver 3 (heal w/ MockProvider, budget=0 blocks
│   │                         LLM, metrics written) + 2 validator tests
│   │                         (reject ambiguous → next candidate; reject all →
│   │                         'unhealable' + filtered=N error) · metrics file ·
│   │                         factory default · 2 intent-ranking tests (click
│   │                         prefers buttons→login; fill prefers login-email over
│   │                         signup-email). ScriptedProvider = hand-rolled test double.
│
│  tests/ui/ — 3 smoke tests against the REAL internet
│   └── test_smoke.py ...... pytestmark=smoke. login form visible · invalid
│   │                         password shows exact error (deterministic fake
│   │                         account) · product search shows 'Searched Products'.
│
│  tests/eval/ — 21: the 20-case heal-quality benchmark + scope check
│   ├── fixtures.py ........ 5 templates (login/signup/products/cart/contact) ×
│   │                         4 mutation kinds (attr_rename / text_rename /
│   │                         redesign / distractors) = 20. Each: intent, action,
│   │                         html, marker (ground truth Playwright selector).
│   └── test_eval_benchmark.py  browser fixture + page.set_content(html) (NO
│                             internet). Mirrors live pipeline exactly:
│                             provider.propose → uniqueness guard → compare healed
│                             node vs marker via evaluate handles → verdict
│                             true_positive / false_positive / miss.
│                             Session 'ledger' fixture writes reports/
│                             eval_report.json + .html (precision/recall + table).
│                             RESULT: TP=18 FP=2 miss=0 → 0.90 / 0.90. FPs are
│                             the LOWEST-confidence cases (lexical traps the
│                             mock misses by design honesty).
│
│  📖 locators/ — the ADDRESS BOOK (data, not code)
├── locators/README.md ...... what the registry is, entry schema
└── locators/registry/
    └── bootstrap.json ...... 12 elements: primary / strategy / intent
                              (THE AI's clue - purpose survives redesigns!) /
                              healed (null | new selector; wins on read) /
                              history (past heals; rollback trail). The healer
                              EDITS this file — the original is never overwritten.
│
│  🚀 .github/workflows/ — the cloud robot
└── ci.yml .................. 5 jobs. triggers: push main, PRs, nightly cron
                              03:00 UTC, manual button.
    unit ......... pip cache → install -e ".[dev]" → pytest tests/unit -q
    ui ........... needs:unit. MATRIX ×(chromium,firefox), fail-fast:false.
                   env LLM_PROVIDER=mock (CI heals are $0!). playwright install
                   --with-deps → smoke → scripts/heal_gate.py --min 0.70 →
                   ALWAYS upload allure-results + screenshots artifacts.
    eval ......... needs:ui. offline benchmark + eval-report artifact.
    publish ...... needs:[ui,eval], only on main refs. permissions pages:write +
                   id-token:write + concurrency. Re-runs eval + demo_heal ITSELF
                   (evidence generated on GitHub's machines, not copied!)
                   → build_status_page.py → deploy → YOUR Pages URL.
│
│  🛠 scripts/ — one-command workers
├── scripts/demo_heal.py .... BREAK 2 locators (#broken-...) → run the 2 affected
│                             tests via subprocess → mock healer repairs LIVE →
│                             prints HEAL REPORT table → RESTORES registry
│                             (--keep to inspect). Idempotent. Resume money-shot.
├── scripts/heal_gate.py .... CI gate. No metrics / 0 attempts → PASS.
│                             heal_rate < min (0.70) → FAIL. Convert
│                             "AI feels accurate" into a measurable release gate.
├── scripts/build_status_page.py → _site/index.html for Pages; exits non-zero
│                             if generated inputs are missing (publishes garbage-proof).
└── scripts/mcp_smoke.py .... raw newline-delimited JSON-RPC vs the MCP server:
                              initialize → tools/list (5 expected) → real tool
                              calls. Proves the MCP integration WITHOUT any AI
                              client installed.
│
│  📚 docs/ — you are here
├── docs/GUIDE.md ........... this master guide
├── docs/CODE_WALKTHROUGH.md line-by-line code tour + full execution trace +
│                             Python-for-testers glossary
├── docs/DECISIONS.md ....... ADR-001: Ollama chosen as the provider-of-record
│                             (mock stays CI default; OpenAI = paid comparison).
│                             Context/options/consequences/how-to-verify.
└── docs/MCP_SETUP.md ....... JSON blocks for Claude Desktop / Cursor / Claude Code
                              + tool table + safety notes.
│
│  ⚙️ GENERATED OUTPUT — never commit (gitignored)
├── reports/allure-results/ . Allure JSON per test + attachments (prompt/response
│                             evidence of heal calls). Render with: make report
├── reports/screenshots/ .... auto-screenshot on every failing UI test
├── reports/eval_report.{json,html}  benchmark output
└── _site/ .................. the status page build for GitHub Pages
```

**Legend:** 🧠 = brain · 🛤 = integration · 🧪 = tests · ⚙️ = generated/config · 📖 = data · 🚀 = CI · 🛠 = scripts · 📚 = docs

---

## Part 3 — The two golden flows (memorize these)

### The happy path (what happens ~99% of the time)

```
pytest tests/ui -m smoke
 → conftest: settings → browser (once) → page (fresh context)
 → HomePage().open().go_to_signup_login()
 → BasePage._act(): registry.get("signup_login_btn").active
   = "text=Signup / Login"  → page.click(...) ✅ DONE
 → expect(...) assertions (never healing, by design)
```
**0 LLM calls. 0 cost.**

### The healing path (the money shot)

```
click("login_submit") → registry.active = button[data-qa=login-button]
   → TimeoutError! 10s
 → _recover(): classify(timeout msg, element_exists=False)
   → LOCATOR_FAILURE ✔ (only THIS verdict spends a heal)
 → resolver.heal():
     budget 1/20 ✔ · cache MISS → provider.propose(
        intent="Submit login form", action="click", html=<sanitized page>)
     candidates ranked by confidence → uniqueness dry-run → survivor
 → registry.apply_heal("login_submit", new) ← SAVED TO DISK FOREVER
     (+ old kept in history, metrics flushed)
 → back in _recover: retry ONCE with the NEW selector → works → test PASSES
 → next run: registry active = healed selector → no heal needed (arguably 0 cost)
```

**If the failure were an assertion bug or a 500** → classifier says NEVER HEAL → test fails loudly with the true cause. **If the element was merely slow** → one plain retry, 0 LLM calls. This branch discipline is the interview centerpiece.

---

## Part 4 — Run everything (a recipe for every mood)

```powershell
# FIRST-TIME SETUP (once)
cd \\wsl.localhost\Ubuntu\home\pankaj\self_healing_qa_framework
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m playwright install chromium
Copy-Item .env.example .env        # optional: real LLM keys later
```

| You want to… | Command | Takes |
|---|---|---|
| verify the brain offline | `python -m pytest tests/unit -q` | 3-7s |
| run REAL UI smoke | `python -m pytest tests/ui -m smoke -v` | 15-50s |
| see everything | `python -m pytest tests/unit tests/eval tests/ui` | ~1.5 min |
| watch the self-heal demo | `python scripts/demo_heal.py` | ~1 min |
| run the benchmark | `python -m pytest tests/eval -q` | 30s |
| see eval numbers | `reports/eval_report.html` / `.json` | — |
| apply the quality gate | `python scripts/heal_gate.py --min 0.70` | instant |
| browser you can watch | `$env:HEADLESS="false"` + run smoke | slower |
| Allure report | `allure serve reports/allure-results` | — |
| AI clients operate the framework | `python -m src.mcp_server.server` (needs `pip install -e ".[mcp]"`) | server |
| prove MCP without a client | `python scripts/mcp_smoke.py` | 5s |
| rebuild the Pages page locally | `python scripts/build_status_page.py` | instant |
| switch to LOCAL FREE LLM | set `LLM_PROVIDER=ollama` (+ `ollama pull qwen2.5:3b`) | once |
| switch to real OpenAI | set `LLM_PROVIDER=openai` + `OPENAI_API_KEY=sk-...` | once |

Via Make (Linux/WSL): `make setup / test / smoke / eval / gate / demo / mcp / mcp-smoke / report`

---

## Part 5 — Settings & configuration deep dive

| Setting | Where | What it changes |
|---|---|---|
| `base_url` | yaml + `BASE_URL` env | which website is tested |
| `browser` | yaml | chromium / firefox / webkit (CI matrix overrides via `getattr(p, browser)`) |
| `headless` | yaml + `HEADLESS` | invisible vs visible browser |
| `timeout_ms` | yaml | default wait for every page action |
| `heal_enabled` | yaml | buys you an instant "healing OFF" toggle for A/B comparisons |
| `max_heal_calls` | yaml + env | per-run LLM budget (spending guard) |
| `llm_provider` / `llm_model` | yaml + env | the consultant brain (mock \ openai \ ollama) |
| `OLLAMA_BASE_URL` | env only | local Ollama endpoint (default localhost:11434/v1) |
| `ENV` | env | dev.yaml vs ci.yaml |
| `smoke` marker | pyproject | what CI's fast job runs |

**Priority rule:** env var > yaml. CI changes behavior ONLY with env vars — no code changed ever.

---

## Part 6 — Data formats you'll actually touch

### 1. Registry entry (`locators/registry/bootstrap.json`)
```json
"login_submit": {
  "primary": "button[data-qa=login-button]",   // original — never mutated
  "strategy": "css",                            // css | text | xpath | role
  "intent": "Submit login form",               // HUMAN PURPOSE → shown to the AI
  "healed": null,                               // set when the healer wins
  "history": []                                 // audit trail of past heals
}
```
- Add a new element = add one JSON block (+ maybe a helper method in a page object).
- A heal writes `healed` — read-time, `active = healed ?? primary`.
- Roll back = empty `healed` (`rollback_locator` power-tool or by hand).

### 2. heal attempt (`heal_metrics.json`)
```json
{
  "locator_key": "login_submit",
  "url": "https://automationexercise.com/login",
  "failed_selector": "#broken-login-button",
  "outcome": "healed",                 // healed|unhealable|skipped_budget|cache_hit
  "chosen_selector": "[data-qa=\"login-button\"]",
  "confidence": 0.75,
  "model": "mock-1", "latency_ms": 3, "tokens_used": 0,
  "candidates_tried": 2, "error": "", "ts": 1792416249.13
}
```
`totals` at the top = heal_rate, spend, model. This IS your resume evidence.

### 3. Benchmark case (`tests/eval/fixtures.py`)
```python
_case("login", "redesign", "click", html=..., marker='button:has-text("Sign in")')
#          page    mutation     action    the broken HTML   ground truth selector
```

---

## Part 7 — Troubleshooting (every failure seen so far + fixes)

| Symptom | Cause | Fix |
|---|---|---|
| `page.goto` TimeoutError on loaded site | ad-heavy page never reaches 'load' | already handled (`domcontentloaded` + 45s); retry |
| `ModuleNotFoundError: playwright/dotenv/allure` | deps not installed **inside the venv** | `.venv\Scripts\Activate.ps1` then `pip install -e ".[dev]"` |
| `unrecognized arguments: --alluredir` | allure-pytest missing | `pip install allure-pytest` |
| `Executable doesn't exist` for chromium | browser not downloaded | `python -m playwright install chromium` |
| `unrecognized .mcp.server.fastmcp` (ModuleNotFoundError) | mcp v2 installed; FastMCP renamed | **pinned mcp>=1.2,<2** (fixed in Step 7) |
| MCP smoke hangs, then crashes | same as above | fixed; `python scripts/mcp_smoke.py` to verify |
| all-day test failure — screenshot exists? | yes — evidence for a real defect | open `reports/screenshots/*.png`, read the ERROR log line |
| PowerShell activation blocked | script policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (once, admin) |
| `NameError` in a test | missing method | method added in the corresponding step (kept in git) |
| heal attempt says `unhealable` | no candidate passed the confidence/uniqueness/validate guard | test fails LOUDLY by design (never a silent fake pass); check the `error` field + rationale |
| CI firefox job fails: `Executable doesn't exist .../chromium_headless_shell-...` | matrix wired the browser to the INSTALLER but not to the TESTS (tests read `config/*.yaml` `browser:`) | `BROWSER: ${{ matrix.browser }}` env in the job + `os.getenv("BROWSER", …)` override in `config.py` — fixed; rule: *launch what you installed* |

---

## Part 8 — Where every requirement lives (FR → implementation)

| FR | Requirement | Implementation location | Status |
|---|---|---|---|
| FR-01 | registry-driven locators | `src/locators/registry.py` + `locators/registry/bootstrap.json` | ✅ |
| FR-02 | ≥6 flows | `tests/ui/test_smoke.py` (3 smoke) + `tests/eval/fixtures.py` (5 pages) | ✅ (cart/checkout + signup live-flow pending) |
| FR-03 | failure classification | `src/locators/classifier.py` (pure function) | ✅ |
| FR-04 | heal protocol + guards | `src/locators/heal_resolver.py` + `base_page._recover` | ✅ |
| FR-05 | persistence + rollback | `registry.apply_heal/rollback` (immediate disk write) | ✅ |
| FR-06 | telemetry | `heal_metrics.json` (+ flush after every attempt) | ✅ |
| FR-07 | provider abstraction + cost cap | `providers/{base,mock,openai,factory}.py`, `max_heal_calls`, cache | ✅ |
| FR-08 | prompts + safety | `prompts/` inlined in `openai_provider.SYSTEM_PROMPT` + `sanitize_html()` | ✅ (move file per-provider as backlog) |
| FR-09 | reporting | `allure-pytest`, screenshots, `eval_report.{html,json}`, Pages job | ✅ (Allure HTML publish = backlog) |
| FR-10 | CI | `.github/workflows/ci.yml` (5 jobs) + `heal_gate.py` | ✅ (needs your push) |
| FR-11 | benchmark/eval | `tests/eval/*` — precision 0.90 / recall 0.90 / 20 cases | ✅ |
| FR-12 | config + secrets | `config/*.yaml`, `.env*`, gitignore, `safe_load` | ✅ |
| FR-13 | logging | `src/core/logger.py` (loguru + RUN_ID) | ✅ |
| — | MCP / AI operator | `src/mcp_server/server.py` + smoke | ✅ bonus (trendy) |

---

## Part 9 — Study order (if you're reading this repo cold)

1. This file → the whole map without the code.
2. `docs/CODE_WALKTHROUGH.md` §15 — one test traced through every layer.
3. `src/core/config.py` → 60 lines, teaches settings patterns.
4. `src/locators/classifier.py` → 60 lines, teaches triage discipline.
5. `src/locators/registry.py` → JSON as source of truth.
6. `src/locators/heal_resolver.py` → the loop, the budget, the cache.
7. `src/pages/base_page.py` → closures-as-operations heal engine.
8. `tests/unit/test_heal_loop.py` → how each behavior is LOCKED into a test.
9. `scripts/demo_heal.py` → the money-shot demo.
10. `.github/workflows/ci.yml` → how strangers' machines run it identically.
11. `docs/DECISIONS.md` → why the choices look like THIS and not otherwise.

---

## Part 10 — Glossary (the 20 words you'll use in interviews)

| Word | Meaning here |
|---|---|
| **Locator / selector** | the programmatic address of an element ("button[data-qa=login-button]") |
| **Registry** | the JSON address book; single source of truth |
| **intent** | the element's HUMAN purpose — the durable part the AI is asked about |
| **heal / self-healing** | auto-replacing a dead selector with a working one, then persisting |
| **classifier (triage)** | decides failure kind; heal allowed ONLY for LOCATOR_FAILURE |
| **provider** | any class with `propose()` giving ranked locators (mock/openai/ollama) |
| **confidence** | provider's self-scored certainty 0–1; <0.5 candidates discarded |
| **budget guard** | hard per-run cap on LLM calls |
| **cache** | identical (url, selector, intent, action) = no repeat LLM spend |
| **uniqueness validator** | dry-run `count()==1` guard — protects against strict-mode ambiguity |
| **POM (page object)** | class per page; tests read like sentences |
| **smoke** | fast critical-path suite (~3 tests, ~30s) — what runs on every PR |
| **eval benchmark** | 20 offline mutated fixtures; precision/recall vs ground truth |
| **false positive (eval)** | healed to the WRONG element — graded worse than a miss |
| **heal_rate** | healed/(healed+unhealable); CI gate needs ≥ 0.70 |
| **MCP (Model Context Protocol)** | standard letting AI clients call your functions as tools |
| **ADR** | short memo of a major decision (we keep them in docs/DECISIONS.md) |
| **Allure** | test report generator: steps, screenshots, attachments |
| **strict mode** | Playwright: a selector matching N elements throws — ambiguity is bad |
| **pure function** | no I/O → deterministic → trivially unit-testable (classifier) |

---

*Questions this guide should have answered: what → where → why how → how to run → how to extend → how to prove. Anything missing, it's a docs bug — add it here.*
