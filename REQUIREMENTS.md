# Project: AI Self-Healing Test Automation Framework

**Version:** 1.0
**Owner:** QA Engineer (2 YoE)
**Target:** Job-ready portfolio project demonstrating AI-driven test maintenance
**Estimated effort:** 3 weeks part-time (≈ 40–50 hours)

---

## 1. Vision
A UI test automation framework where tests that fail because a locator changed are **automatically repaired by an LLM** (OpenAI/Groq/local Ollama), retried, and — on success — the healed locator is persisted and reported. The goal is to prove measurable reduction in maintenance work, e.g. *"broken by UI change X → auto-healed with 90% accuracy, 0 manual intervention."*

## 2. Goals & Success Metrics
| # | Goal | Measurable success |
|---|------|-------------------|
| G1 | Detect locator failures automatically | 100% of `NoSuchElementException` / timeout cases classified as `LOCATOR_FAILURE` vs `APP_FAILURE` |
| G2 | Propose a working replacement locator | ≥ 85% heal rate on a synthetic "broken locator" benchmark suite |
| G3 | Persist & reuse healed locators | Healed locator used on subsequent runs without re-querying the LLM |
| G4 | Reduce flaky/maintenance failures | ≥ 50% reduction vs. baseline run (reported in Allure) |
| G5 | Full traceability | Every heal attempt logged: original, proposed, model, confidence, outcome |
| G6 | CI integration | Runs on GitHub Actions, publishes Allure report |

## 3. Scope

### In scope
- Web UI automation on a public demo app
- Page Object Model with locator registry (JSON)
- Self-healing resolver (LLM proposes CSS/XPath)
- Retry-with-heal loop
- Locator persistence layer (local JSON + optional git-saved)
- Telemetry & metrics dashboard in Allure
- API smoke layer (health/auth)
- Cross-browser (Chrome, Firefox) via config
- Parallel execution
- Config/env management & secrets handling

### Out of scope (v1)
- Mobile (Appium), visual testing, performance
- Autonomous full-app exploration (separate project)
- Self-hosting the model (use Ollama locally only as optional provider)
- Auto-merging healed locators to git without human approval

## 4. Target System Under Test (SUT)
- **Primary:** https://automationexercise.com (public, no login for read-only flows; supports full user flows)
- **Backup:** https://www.saucedemo.com
- Flows to cover (see §6).

## 5. User Personas
- **QA Engineer (me):** authors tests; reviews healed locators in a daily report; approves/rejects.
- **Reviewer / Interviewer:** clones repo, runs `make test`, sees green + Allure report with heal metrics.
- **CI bot:** runs nightly + on PR; posts pass/fail summary.

## 6. Functional Requirements

### FR-01 Locator Registry
- Each page object stores locators in an external JSON file: `{ "loginBtn": {"primary": "css:#login", "strategy": "css", "healed": null, "history": []} }`.
- Locators must be loadable/swappable at runtime (registry pattern), never hard-coded in test code.

### FR-02 Baseline Test Suite
Cover ≥ 6 flows with positive + negative cases:
1. **Login:** valid, invalid password, empty fields, locked user.
2. **Signup:** new user, duplicate email validation.
3. **Product search:** keyword, empty result, pagination.
4. **Cart:** add, remove, quantity update, price recalc.
5. **Checkout (registered user):** place order, view order history.
6. **Contact form:** submit + success message.

### FR-03 Failure Classification
On any element interaction failure, classify:
- `LOCATOR_FAILURE` (element not found / not interactable) → trigger heal
- `ASSERTION_FAILURE` → fail test, no heal
- `APP_FAILURE` (5xx, wrong data) → fail + attach evidence
- `FLAKY_TIMEOUT` (intermittent) → retry without heal

### FR-04 Self-Healing Resolver
When `LOCATOR_FAILURE`:
1. Capture: page URL, page HTML snippet (trimmed to relevant region), screenshot, failed locator, action intent (e.g., "login button"), element's expected tag/type.
2. Build a structured prompt (JSON schema for response) asking the model to return up to 3 candidate locators (css then xpath) with confidence 0–1 and short rationale.
3. Parse & validate candidates (syntax + dry-run `querySelector`/XPath eval) → keep only computable ones.
4. Try candidates in order, each with the original action + timeout.
5. On first success → promote to primary, append original to `history`, mark `healed=true`, log telemetry.
6. If none succeed → mark `UNHEALABLE`, attach prompt+response to report, fail test with a clear reason (no silent pass).

### FR-05 Persistence
- Healed locator saved to registry JSON immediately on success.
- Optional: write a pending-update file `healed_locators PR` for human review (diff of original vs new), so repo history stays clean.
- Manual override always possible via JSON edit.

### FR-06 Telemetry / Metrics
Track per run (export to `heal_metrics.json` + Allure):
- `failures_total`, `locator_failures`, `healed_success`, `healed_failed`, `heal_rate`, `model_latency_ms`, `cost_tokens`
- Per-locator: attempt count, success/fail history (rolling window).
- Flaky rate comparison: baseline vs. healed.

### FR-07 Provider Abstraction
- LLM provider interface with adapters: OpenAI (gpt-4o-mini), Groq (free), Ollama (local).
- Switch via env var `LLM_PROVIDER` + `LLM_MODEL`.
- Cost guard: `MAX_HEAL_CALLS_PER_RUN` (default 20) and `MAX_TOKENS_PER_CALL`.
- Caching: identical (url + failed locator + intent) → cached suggestion (in-memory + file) to avoid repeat calls.

### FR-08 Prompt Engineering & Safety
- Prompts version-controlled in `/prompts/*.md` with placeholders.
- Response enforced to JSON via schema (use function calling / json mode).
- Red-team: prompts must not leak PII from HTML; HTML is sanitized (strip scripts, inputs values, tokens) before sending.
- Model must never be allowed to execute arbitrary code — only propose selectors.

### FR-09 Reporting
- Allure report with: test steps, screenshots (on failure + heal), LLM prompt/response attachments, heal status badges.
- `heal_metrics.json` published as artifact.
- README contains a "Last run" badge + link to GitHub Pages report.

### FR-10 CI/CD
- GitHub Actions: matrix (Chrome, Firefox) × (smoke, regression).
- Triggers: push to main, PR, nightly cron.
- Secrets: `OPENAI_API_KEY` via repo secrets; fallback to Groq if absent.
- Upload Allure report as artifact + deploy to GitHub Pages.
- Fail job if `heal_rate < threshold` (configurable, default 0.7) **during benchmark suite**.

### FR-11 Benchmark / Evaluation Suite (critical for interview credibility)
A separate test module `eval/` that:
- Contains 20 hand-mutated "broken locator" variants of real pages (saved HTML fixtures).
- Runs the healing resolver offline (no network).
- Computes precision/recall of heal suggestions + false-positive rate (healed to wrong element).
- Produces `eval_report.html` + JSON.
- This is the proof point you demo.

### FR-12 Configuration & Secrets
- `config.yaml` per env (dev/staging/prod-like demo).
- `.env` for secrets; `.env.example` committed.
- No secrets in git (pre-commit secret scan: gitleaks).

### FR-13 Logging
- Structured JSON logs (structlog/loguru) with run_id, test_id, step.
- Configurable level.

## 7. Non-Functional Requirements
| Category | Requirement |
|---|---|
| Language | Python 3.11+ (primary) — *alt: TS/Playwright if you prefer; must justify* |
| Test framework | pytest + playwright (sync) |
| Parallelism | `pytest-xdist`, 4 workers |
| Runtime | Full regression ≤ 15 min (cloud CI), smoke ≤ 3 min |
| Determinism | Seeded faker; reproducible test data |
| Resilience | Retries: 2 on flakiness, 1 on heal; exponential backoff for API |
| Security | Sanitize HTML before LLM; never send credentials/tokens |
| Cost | <$2 per full run on OpenAI-mini; $0 option via Ollama/Groq |
| Code quality | ruff + black + mypy (typed), pre-commit hooks |
| Coverage | ≥ 70% unit test coverage on resolver/registry modules |
| Docs | README, ARCHITECTURE.md, CONTRIBUTING.md, ADRs |

## 8. Architecture (high level)

```
self_healing_qa_framework/
├── src/
│   ├── pages/                  # Page objects (no locators here)
│   ├── locators/               # registry loader + healer
│   │   ├── registry.py
│   │   ├── classifier.py       # failure classifier
│   │   ├── heal_resolver.py    # LLM propose + validate + retry
│   │   ├── cache.py
│   │   └── providers/          # openai, groq, ollama
│   ├── core/                   # base page, driver, config, logger
│   ├── api/                    # smoke client
│   ├── data/                   # test data factories
│   ├── reporting/              # metrics, heal report builder
│   └── cli.py                  # `heal` CLI (re-run unhealable, review)
├── tests/
│   ├── ui/                     # pytest tests
│   ├── unit/                   # resolver, classifier, registry
│   └── eval/                   # benchmark suite
├── locators/registry/*.json   # source of truth
├── fixtures/html/              # saved HTML for eval + offline
├── prompts/                   # versioned prompts
├── config/ (dev.yaml, ci.yaml)
├── .github/workflows/
├── docker-compose.yml          # optional: local runner
├── Makefile
└── README.md
```

## 9. Key User Stories
- **US-1** As a test author, I run `pytest -m smoke` and get a green Allure report.
- **US-2** As the framework, when `#login` becomes `#sign-in-btn`, the next run auto-heals and logs the change.
- **US-3** As a reviewer, I open `healed_locators.patch`, diff old vs new, approve via PR.
- **US-4** As CI, on PR I see a comment with heal_rate and flaky-rate delta.
- **US-5** As an evaluator, I run `make eval` and get precision/recall + HTML report.

## 10. Acceptance Criteria (demo-ready)
- [ ] Smoke suite (≥6 flows) green on CI against AutomationExercise.
- [ ] At least 1 documented "heal event" in README with before/after screenshot.
- [ ] Eval report shows ≥85% heal accuracy on ≥20 mutated fixtures.
- [ ] Allure report published to GitHub Pages.
- [ ] Zero secrets in git; `.env.example` present.
- [ ] `make setup && make test` works on a clean machine in <5 min.
- [ ] ARCHITECTURE.md explains design decisions + tradeoffs.

## 11. Timeline (3 weeks, part-time)
- **W1:** Scaffolding, POM, registry, baseline suite green, CI.
- **W2:** Classifier, heal resolver, providers, caching, unit tests.
- **W3:** Telemetry, Allure polish, eval suite, docs, synthetic "break & heal" demo, portfolio polish.

## 12. Risks & Mitigations
| Risk | Mitigation |
|---|---|
| LLM suggests wrong element (false positive) | Dry-run + assertion re-check; confidence threshold; history rollback; human review gate |
| Flaky tests blamed on "AI" | Separate flaky classification; retry without heal first |
| API cost/latency in CI | Caching, call cap, Ollama/Groq fallback; mock provider for unit tests |
| Demo site changes break everything | Pin to known HTML fixtures for eval; SUT swapped via config |
| "Just marketing" perception | Eval suite with measurable metrics is the proof |

## 13. Portfolio Deliverables (what you link in resume/LinkedIn)
1. GitHub repo URL with CI badge green.
2. 2-min Loom/GIF: breaking a locator → auto-heal → report.
3. README "Results" section with metrics table.
4. Blog post (optional): "How I cut test maintenance by X% with an LLM resolver."
5. Interview story: design decisions, failure modes, why caching & cost guard.

## 14. Stretch (if time)
- MCP server exposing `run_tests` / `get_failures` to Claude → "Claude fixes my tests" demo (very trendy, +1 on resume).
- Mutation testing (mutmut) to prove test quality.
- Jira/Slack notifier for heal events.

---

**Next step:** reply with (1) language (Python/Playwright vs Java/Selenium vs TS), (2) provider (OpenAI/Groq/Ollama), (3) SUT (AutomationExercise/SauceDemo), and I'll scaffold the repo.