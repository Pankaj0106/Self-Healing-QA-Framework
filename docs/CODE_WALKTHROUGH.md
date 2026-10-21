# Code Walkthrough — every file explained

*Companion doc to `REQUIREMENTS.md`. Written for a Python beginner.*

---

## 0. File map (what each file is, in one line)

```
self_healing_qa_framework/
│
│  PROJECT-LEVEL
├── pyproject.toml ............ project identity + dependency list + pytest config
├── Makefile .................. shortcut commands (setup/test/smoke/eval/report)
├── .env.example .............. TEMPLATE of private settings (real .env never committed)
├── .gitignore ................ files that must never enter version control
├── REQUIREMENTS.md ........... what the product must do (spec)
│
│  SETTINGS
├── config/
│   ├── dev.yaml .............. settings used on YOUR machine (visible browser etc.)
│   └── ci.yaml ............... settings used in GitHub Actions (headless, longer timeouts)
│
│  CORE (foundation)
├── src/core/config.py ........ loads settings: YAML file, optionally overridden by env vars
├── src/core/logger.py ........ every run gets an 8-char ID; all logs carry it
│
│  LOCATORS (the "brain" of self-healing)
├── locators/registry/
│   └── bootstrap.json ........ THE ADDRESS BOOK: every element's current + past selectors
├── src/locators/
│   ├── registry.py ........... reads/writes the address book; apply_heal/rollback logic
│   ├── classifier.py ......... triage nurse: which failure kind? heal allowed or forbidden?
│   ├── heal_resolver.py ...... the healing loop: budget/c cache -> LLM -> persist -> metrics
│   └── providers/
│       ├── base.py ........... the CONTRACT every AI backend must satisfy (Protocol)
│       ├── mock.py ........... free fake AI (regex heuristics) for tests & CI
│       ├── openai_provider.py real AI (OpenAI/compatible), JSON mode, HTML sanitizing
│       └── factory.py ........ picks backend from LLM_PROVIDER env var
│
│  PAGES (the robot's hands)
├── src/pages/
│   ├── base_page.py .......... heal engine: every click/fail/decide/retry happens here
│   ├── home_page.py .......... open site, navigate to Login / Products
│   ├── login_page.py ........ type credentials, submit, assert error
│   └── products_page.py ...... search, assert results
│
│  TESTS
├── tests/
│   ├── conftest.py ........... pytest fixtures: settings, browser, page, failure screenshot
│   ├── unit/
│   │   └── test_heal_loop.py . 11 offline checks of registry/classifier/resolver
│   └── ui/
│       └── test_smoke.py ..... 3 live-site checks (login form, wrong password, search)
│
│  GENERATED (not committed)
├── heal_metrics.json ......... written by HealResolver after every run
└── reports/
    ├── allure-results/ ....... Allure JSON (becomes HTML report)
    └── screenshots/ .......... auto-screenshot when a UI test fails
```

**Dependency direction (who may import whom):**
`pages → locators → core`. Tests import pages + core.
Nothing in `locators/` knows Playwright exists, and nothing in `core/` knows anything else exists — each layer is replaceable.

---

## 1. `pyproject.toml`

**Job:** one file that (a) declares the project name/version, (b) lists what must be installed, (c) configures pytest.

Sections to know:

| Section | Meaning |
|---|---|
| `[project]` `dependencies = [...]` | "Install these toolboxes." `pip install -e ".[dev]"` installs the listed libs **plus** the `dev` extras (ruff, black, mypy, pytest-mock). The `-e` = editable: changes to `src/` take effect instantly, no reinstall. |
| `requires-python = ">=3.11"` | Won't install on Python 3.10 or older (uses newer syntax). Your machine has 3.12 ✔ |
| `[tool.pytest.ini_options]` | Every pytest run automatically uses these: `testpaths=["tests"]` (where tests live), `addopts` = always verbose + always write Allure results. |
| `markers = [...]` | Registers `@pytest.mark.smoke` etc. so `pytest -m smoke` works without "unknown marker" warnings. |
| `[tool.ruff]` / `[tool.black]` | Linter + formatter settings (line length 100). |

**New concept:** TOML is a config format like YAML/JSON — `key = "value"`, sections in `[brackets]`.

---

## 2. `config/dev.yaml` & `config/ci.yaml`

**Job:** environment-specific settings. Same keys, different values.

```yaml
base_url: "https://automationexercise.com"
browser: "chromium"
headless: true          # dev can flip to false to SEE the browser
timeout_ms: 10000
heal_enabled: true
max_heal_calls: 20      # spending guard
llm_provider: "mock"    # mock = zero cost
llm_model: "mock-1"
```

**Rules:**
- `ENV=dev|ci` (env var) picks the file. Default `dev`.
- CI overrides values via environment variables — see next file.

---

## 3. `src/core/config.py` — the settings loader

**Flow:** `.env` file → env vars → choose YAML (`dev` or `ci`) → load JSON → env vars override YAML values → build immutable `Settings` object.

Line by line (the interesting ones):

| Line | Code | Meaning |
|---|---|---|
| 11 | `load_dotenv()` | Read a local `.env` file and put its contents into environment variables. (CI has no `.env`; it uses GitHub Secrets.) |
| 13 | `ROOT = Path(__file__).resolve().parents[2]` | `Path(__file__)` = path of this file. `.parents[2]` climbs 2 levels: `src/core/config.py` → project root. Using an absolute path means the app finds config no matter which folder you run pytest from. Beginner trap: relative paths like `"config/dev.yaml"` break when run from elsewhere. |
| 16-25 | `@dataclass(frozen=True)` | Dataclass: auto-generates `__init__` from the field list. `frozen=True` = cannot be modified after creation (prevents `settings.base_url = "..."` bugs mid-run). |
| 28-31 | `_as_bool()` | Env vars are always **strings** (`"false"` is truthy as a string!) — this converts `"1"/"true"/"yes"` to real booleans. Classic Py bug avoided. |
| 34-37 | `load_settings()` | Reads `ENV` (default "dev"), builds path `config/{env}.yaml`, `yaml.safe_load` parses it into a **dict** — like a Python dictionary/map: `{key: value}`. `safe_load` (not `load`) = never execute anything embedded in the YAML file (security). |
| 40-46 | env overrides | Priority: **env var beats YAML**. This is how CI changes provider/URL/headless without editing files — and why the API key can live in GitHub Secrets instead of the repo. |
| 48 | `Settings(**{k: data[k] for k in Settings.__dataclass_fields__})` | Dict **comprehension** filtering the loaded YAML to only the keys Settings knows about (extra YAML keys silently ignored). `**dict` unpacking: turns `{"a":1}` into keyword args `a=1`. |

---

## 4. `src/core/logger.py`

```python
RUN_ID = uuid.uuid4().hex[:8]           # e.g. "1b366ad3" — fresh per process
logger.remove()                          # throw away default handler
logger.add(sys.stderr, level="INFO", format="...| run={extra[run_id]} | {message}")
logger = logger.bind(run_id=RUN_ID)      # every future line carries the ID
```

**Why:** 4 parallel pytest workers all print logs — without a run ID their lines interleave unreadably. With it: `grep run=1b366ad3` extracts one run cleanly.

---

## 5. `locators/registry/bootstrap.json` — the address book

One entry per element the robot touches:

```json
"login_submit": {
  "primary": "button[data-qa=login-button]",   // original address (never overwritten)
  "strategy": "css",                            // css | text | xpath | role
  "intent": "Submit login form",                // human description — the AI's clue!
  "healed": null,                               // set when LLM replaces primary
  "history": []                                 // past heal addresses (rollback trail)
}
```

**The `intent` field is the key insight of the whole architecture:** the AI is not shown "fix `button[data-qa=login-button]`" — it's shown "**find 'Submit login form'**". Descriptions of *purpose* survive UI redesigns; concrete selectors don't.

Currently 12 entries: signup/login link, email + password fields, submit buttons, signup fields, products nav, search box + button, first product title, add-to-cart.

---

## 6. `src/locators/registry.py` — registry reader/writer

**Public surface:**

| Piece | What it does |
|---|---|
| `LocatorEntry` (dataclass) | One address-book row in Python form. |
| `entry.active` (`@property`) | `healed` if present else `primary` **— the single source of truth** for "what selector should I use right now". Property = method that reads like an attribute. |
| `LocatorRegistry(path)` | Constructor: loads JSON → dict of `LocatorEntry`. `dict[str, LocatorEntry]` = typed annotation, nothing else. |
| `get(key)` | Fetch entry; unknown key → friendly `KeyError` with the file path in the message (`from None` suppresses the confusing chained traceback). |
| `apply_heal(key, new)` | Set `healed=new`, append old heal to `history`, **write JSON to disk immediately** — so a crash mid-run never loses a fix. |
| `rollback(key)` | Set `healed=None` (append removed one to history) → back to original. |
| `_save()` | Rebuild dict → `json.dumps(..., indent=2)` → `path.write_text`. Encodings always explicit (`utf-8`) — Windows default encodings bite beginners. |
| `get_registry()` (**singleton**) | `global _registry` + create-once pattern → whole test process shares ONE registry instance, so 4 pytest-xdist workers each get their own but inside one worker it's consistent. |

**Tested by:** `test_registry_reads_active_selector`, `test_apply_heal_persists_and_keeps_history` (reloads from disk to prove real persistence), `test_rollback_restores_original`.

---

## 7. `src/locators/classifier.py` — the triage nurse

```python
class FailureKind(str, Enum):
    LOCATOR_FAILURE, ASSERTION_FAILURE, APP_FAILURE, FLAKY_TIMEOUT, UNKNOWN
```

`classify(message, *, element_exists=None, status_code=None)` — pure function, **no I/O** (that's why its 4 tests run in milliseconds):

| Input signal | Verdict | Rationale |
|---|---|---|
| `status_code ≥ 500` | `APP_FAILURE` | outage is a bug, first |
| message contains "no element found / not found / timeout waiting..." | see below | Playwright locator errors |
| & element_exists=True | `FLAKY_TIMEOUT` | element present but slow → retry (no LLM) |
| & element_exists=False | `LOCATOR_FAILURE` | gone for real → heal |
| & unknown | `FLAKY_TIMEOUT` | retry first, heal last (safe default) |
| message contains "assert / expected / to equal..." | `ASSERTION_FAILURE` | wrong data = real bug, never heal |
| element_exists=True (no locator error) | `FLAKY_TIMEOUT` | e.g. network hiccup |

**The `*` in the signature** = keyword-only args: `classify(msg, element_exists=False)` — impossible to accidentally swap boolean/int arguments.

**Meta-note:** tests caught a real bug here — first version returned `LOCATOR_FAILURE` when `element_exists=True`; fixed in source, not the test.

---

## 8. `src/locators/providers/` — the AI consultancies

### 8a. `base.py` — the contract
```python
class LLMProvider(Protocol):
    name: str
    def propose(*, intent, failed_selector, url, html_snippet, max_suggestions=3) -> HealResponse: ...
```
- **Protocol** = "structural typing": *any* class having these members IS an LLMProvider — no inheritance needed (Java would demand `implements`).
- Two frozen dataclasses: `LocatorSuggestion` (selector/strategy/confidence/rationale) and `HealResponse` (suggestions + model + latency_ms + tokens_used).

### 8b. `mock.py` — the free fake
Reads the HTML with regex looking for (1) `data-qa`/`id`/`name` attributes, (2) intent keywords in visible button/link text. Emits ranked `LocatorSuggestion`s. `time.perf_counter()` timing recorded as latency. Zero network, zero cost, deterministic → same input = same output, ideal for unit tests and CI.

Concepts: `re.finditer` (iterate matches), list slicing `[:max_suggestions]`, `int((t2-t1)*1000)` ms timing.

### 8c. `openai_provider.py` — the real one
- `sanitize_html()` FIRST: strips `<script>...</script>`, replaces every `value="..."` (form content = potentially private input), redacts JWTs (`eyJ...`) and `password=`/`api_key=` patterns, then slices to 12,000 chars. **Security requirement FR-08; resume sentence: "PII/secret redaction before outbound LLM calls".**
- `SYSTEM_PROMPT` (module constant, caps strings): exact role + rules ("only selectors, never code") + demands STRICT JSON.
- Call: `temperature=0` (fully deterministic), `response_format={"type":"json_object"}` (model *must* output valid JSON — no markdown-blob parsing), `max_tokens=400` (cost cap), lazy import (`from openai import OpenAI` inside `__init__`) so mock-only machines never need the package installed.
- Defensive parse: `try json.loads except json.JSONDecodeError → empty list` (model side-errors don't crash the robot).

### 8d. `factory.py` — the switchboard
```python
LLM_PROVIDER=mock    → MockProvider()          (default, free)
LLM_PROVIDER=openai  → OpenAIProvider("gpt-4o-mini")
LLM_PROVIDER=ollama  → OpenAIProvider(model="qwen2.5:3b", api_key="ollama")  # local, free
```
Lazy imports again (only import what you actually use). Unknown name → loud `ValueError` (fail fast, fail clear).

---

## 9. `src/locators/heal_resolver.py` — the healing loop (the engine room)

### `HealAttempt` (dataclass) — one healing event as a record: which element, what URL, what failed, outcome (`healed|unhealable|skipped_budget|cache_hit`), chosen selector, confidence, model, latency, tokens, timestamp.

### `HealResolver.heal(key, url, html_snippet)` — THE algorithm:

```
① healing disabled?            → record "skipped_budget", return
② calls_used >= max_calls?     → record "skipped_budget", return  ← cost guard FR-07
③ cache miss?
     yes → calls_used += 1
           provider.propose(...)            ← THE AI CALL (money spent here)
           store suggestions in cache keyed by (url, primary, intent)
     no  → rebuild suggestions from cache          ← zero cost
④ filter candidates: confidence >= MIN_CONFIDENCE (0.5)
⑤ sort by confidence descending
⑥ for each candidate (non-empty):
       registry.apply_heal(key, cand.selector) ← saved to disk FOREVER
       record "healed" + log line + return
⑦ nothing survived filtering     → record "unhealable"  ← test will FAIL loudly
```

**Key design decisions encoded here:**
- Budget **before** cache check (disabled/broke both never touch the LLM).
- Cache **before** filter — an identical failure later in the same run is free.
- Cheap sanity check only (non-empty string); the *real* validation (does this selector resolve?) happens back in `base_page._recover()` when the healed selector is actually retried — separation: resolver decides **what to try**, page decides **whether it works**.
- Never returns `None`; every path returns a `HealAttempt` and every path is recorded.

### `flush()` — writes `heal_metrics.json`:
- `heal_rate = healed / (healed + unhealable)` (rounded 3dp; `None` when no attempts)
- totals per outcome, `llm_calls`, token spend, active model
- full per-attempt list + registry snapshot
- Written after **every** attempt (via `_record → flush`), so even a killed run keeps history.

### `get_resolver()` — same singleton pattern as registry; reads settings lazily (`from src.core.config import load_settings` *inside* the function: import-time literature — avoids circular imports and means unit tests can construct resolver objects without env deps).

---

## 10. `src/pages/base_page.py` — where browser meets brain

### The public action API (what page objects call)
```python
def click(self, key, *, timeout=None):   self._act(key, lambda sel: self.page.click(sel, timeout=timeout))
def fill(self, key, value, ...):         self._act(key, lambda sel: self.page.fill(sel, value, timeout=timeout))
def text_of(self, key, ...):             self._act(key, lambda sel: self.page.text_content(sel, timeout=timeout) or "")
```
- **Closure + Callable trick:** `lambda sel: ...` is a tiny function capturing `value`/`timeout` from the enclosing scope. `Callable[[str], Any]` type = "function taking a selector string". Result: **one** heal engine serves *all* action types — the heal logic exists in exactly one place (DRY). Without closures you'd copy the engine 3×.
- `locator(key)` → Playwright `Locator` built from `entry.active` — used for assertions (never healed).

### `_act()` — the single gateway
```python
try:    return operation(entry.active)
except (PlaywrightTimeoutError, PlaywrightError) as exc:
        return self._recover(key, exc, operation)
```
Catches **both** Playwright exceptions: `TimeoutError` (element missing/slow) and `Error` (invalid selector syntax) — both are healable classes. Everything else (crashed browser etc.) propagates normally.

### `_recover()` — the decision tree
```
classify(str(exc), element_exists=self._exists(key))
│
├── LOCATOR_FAILURE → resolver.heal(key, url, page.content()[:12000])
│        ├ outcome=="healed" → operation(new active selector)   ← one retry
│        └ else              → raise exc   (loud fail, FR-04.6)
│
├── FLAKY_TIMEOUT   → operation(same selector)  ← one plain retry, 0 LLM spend
│
└── ASSERTION / APP / UNKNOWN → raise exc      ← never hide a real bug
```
- `str(exc)` = string version of the exception for the classifier.
- `self.page.content()` = full page HTML (the AI's "snapshot"), sliced to 12,000 chars — cost cap matched to `sanitize_html`'s cap.
- **Critical rule:** *validating* the healed selector happens by **actually retrying the action**. No extra dry-run clutter; if the AI's guess is wrong, the retry throws and the test fails with full context.

### `_exists()`
`.count() > 0` — instantaneous presence probe (does **not** wait), used only to inform the classifier. Wrapped in broad `except Exception` because a torn-down page must yield `False`, not an error.

---

## 11. Page objects

### `home_page.py`
```python
def open(self):
    self.page.goto(self.base_url, wait_until="domcontentloaded", timeout=45_000)
    return self                       # fluent chaining
```
- `wait_until="domcontentloaded"`: the demo site fires ads; full `load` may never settle → historically caused a timeout (real bug we fixed).
- `45_000` = digit-separator syntax, read "45 thousand" ms.
- `return self` / `return LoginPage(...)` = **fluent API**: tests read like sentences.

### `login_page.py`
`login_with(email, pwd)` = fill + fill + click (all registry-keyed, heal-eligible).
`expect_error(fragment)` = `expect(page.get_by_text(fragment))` — **free-text Playwright assertion, deliberately NOT registry-driven** (assertions are never healed).
`expect_form_visible()` = two `expect(locator(key)).to_be_visible()` checks.

### `products_page.py`
`open_products()` (nav click), `search(term)` (fill + click), `expect_results()` (asserts "Searched Products" heading visible). Results assertion is text-based, not selector-based, on purpose: product grids change hourly on demo sites.

---

## 12. `tests/conftest.py` — fixtures + evidence

**conftest.py** is pytest's magic file: fixtures defined here are visible to every test below it — zero imports needed.

```python
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)      # stores rep_setup/rep_call/rep_teardown
```
pytest doesn't hand fixtures the pass/fail result by default — this classic hookwrapper records it on the test item so the `page` fixture can read it later.

| Fixture | Scope | What it does |
|---|---|---|
| `settings()` | session | `load_settings()` once per run |
| `browser` | session | `sync_playwright()` context manager → `getattr(p, settings.browser)` picks `p.chromium` dynamically → `launch(headless=...)`; yielded object closed after all tests |
| `page` | function | fresh `browser.new_context(...)` per test = clean cookies/localStorage = no cross-test pollution; `set_default_timeout(settings.timeout_ms)`; **on failure** (`request.node.rep_call.failed`): full-page screenshot → `reports/screenshots/<test>-<ts>.png` + log line; `context.close()` always runs |

**Why session browser / function page:** launching a browser ≈ 1s; N tests × 4 workers would waste it. But state isolation demands per-test contexts. Both goals met.

**Verified live:** during a genuinely failed run this machinery captured `reports/screenshots/test_login_form_visible-*.png`.

---

## 13. Unit tests — `tests/unit/test_heal_loop.py` (11 checks)

| Group | Tests | What it proves |
|---|---|---|
| classifier | 4 | correct verdicts per failure type (incl. the fixed bug) |
| registry | 3 | reads active selector; heal persists to real disk (`tmp_path` + reload!); rollback works |
| resolver | 3 | heal loop offline via MockProvider (asserts `calls_used == 1`); budget=0 blocks LLM call; metrics file written with correct `heal_rate` |
| factory | 1 | default provider = mock |

**Test-side Python concepts:**
- `@pytest.fixture` — setup/injected-value; `tmp_path` (built-in) gives a per-test throwaway directory → real `bootstrap.json` never polluted.
- `class TinyRegistry(LocatorRegistry)` — inheritance to override `_save()` (no-op): a hand-rolled test double, no mocking library.
- Path-relative fixture file read: `Path("locators/registry/bootstrap.json")` run from project root.
- pytest's assertion magic: bare `assert x == y` auto-generates an "actual vs expected" diff on failure (saw it live when the classifier bug surfaced).

---

## 14. UI tests — `tests/ui/test_smoke.py`

```python
pytestmark = [pytest.mark.smoke]     # marker applies to ALL tests in this module
```

| Test | Flow | Design notes |
|---|---|---|
| `test_login_form_visible` | open → Signup/Login → assert email+password visible | cheapest full trip through the heal-aware stack |
| `test_login_invalid_password_shows_error` | open → login with guaranteed-nonexistent email → assert exact error text | deterministic: fake email means no account state, ever |
| `test_product_search_returns_results` | open → Products → search "top" → assert results heading | exercises nav/fill/click + text assertion |

Run: `pytest tests/ui -m smoke` (16s). Known artifice: first navigation cold-start is slow — handled at `goto` level.

---

## 15. End-to-end trace — follow ONE test through EVERYTHING

`pytest tests/ui -m smoke` → `test_login_form_visible`:

1. pytest reads `pyproject.toml` (path/marker config), imports `conftest.py`.
2. `settings` fixture → `load_settings()` → reads `.env` + `config/dev.yaml` → frozen `Settings`.
3. `browser` fixture → Chromium launches (headless, 1440×900 default).
4. `page` fixture → fresh context + page; 10s default timeout.
5. Incident module `test_smoke.py` → `pytestmark` registers smoke.
6. `HomePage(page, base_url)` → `__init__` asks `get_registry()` (singleton; first caller loads bootstrap.json) and `get_resolver()` (singleton; resolves provider = **mock**).
7. `.open()` → `goto(..., wait_until="domcontentloaded", 45s)` → returns self.
8. `.go_to_signup_login()` → `click("signup_login_btn")`:
   a. `_act` → registry entry → active selector `text=Signup / Login` → `page.click(...)` ✔ (no heal; 0 LLM calls).
9. `.expect_form_visible()` → registry lookups + Playwright auto-retrying `expect()`.
10. Test passes → pytest records result → hook stores `rep_call` → `page` fixture noticed `failed=False` → no screenshot → `context.close()`.
11. `browser.close()` after session.

### And now the failure path (the money shot). Suppose the site renames the login button:

9'. `click("login_submit")` → `page.click("button[data-qa=login-button]")` → **TimeoutError after 10s**.
10'. `_recover` → `classify("timeout waiting...", element_exists=False)` → `LOCATOR_FAILURE`.
11'. `resolver.heal("login_submit", url, page.content()[:12000])`:
     - budget 0/20 ✔ → cache miss → `calls_used = 1` → provider = MockProvider.propose:
       - sanitize (no secrets) → regex finds `data-qa="login-button"` → suggestion `[data-qa="login-button"]`, confidence 0.7.
     - filter 0.7 ≥ 0.5 ✔ → sort → `registry.apply_heal("login_submit", '[data-qa="login-button"]')` → **bootstrap.json updates `healed` on disk** → record "healed" → flush → heal_metrics.json gains attempt #1.
12'. back in `_recover`: `operation(registry.get("login_submit").active)` → the NEW selector → click ✔ → test PASSES.
13'. Even a killed run leaves everything recorded; **all future test runs use the healed selector automatically** (registry persists).

If instead the click had failed because the site returned a 500 → verdict `APP_FAILURE` → **no AI call**, test fails with the true cause. If it had been merely slow (`element_exists=True`) → `FLAKY_TIMEOUT` → one plain retry, zero cost. **This branching is precisely the story you tell in interviews.**

---

## 16. Python-for-testers glossary (everything used so far)

| Syntax | Means |
|---|---|
| `def f(a, /, b, *, c)` | positional-only / normal / **keyword-only** args |
| `str \| None` (PEP 604) | union type — "or None" (`Optional[str]` pre-3.10) |
| `@dataclass` | auto-`__init__` from fields; `frozen=True` = immutable |
| `field(default_factory=list)` | per-instance default list (avoids shared-mutable-default bug) |
| `@property` | method disguised as attribute, computed on access |
| `from __future__ import annotations` | all type hints become lazy strings (no import-order headaches) |
| `Protocol` | structural interface: shape is the contract, no inheritance |
| Enum (`class K(str, Enum)`) | fixed legal values; str-mixin prints nicely |
| dict/set/list comprehension `{k: v for ...}` | build collections inline |
| `**dict` unpacking | dict → keyword arguments |
| `getattr(obj, "x", default)` | safe attribute fetch, default if missing |
| `global X` | mutate module-level variable (singletons) |
| `with` / context manager | guaranteed cleanup (`sync_playwright`, files) |
| `yield` in fixture | split setup/teardown at the yield line |
| `try/except/raise ... from None` | catch, decide, or re-raise with a clean traceback |
| `lambda` + closure | tiny function capturing surrounding variables |
| `Callable[[str], Any]` | type of "function taking a string" |
| `re.finditer / re.search / re.sub` | iterate / find / replace in text |
| slicing `s[:12000]` | first N chars/items |
| `45_000` | digit separator — 45000 |
| `f"{expr}"` | interpolated string |
| `simple variable = uuid4().hex[:8]` | trim a random ID string |
| `time.perf_counter()` | high-resolution timer for latency measurement |
