# Architecture Decision Records (ADR)

Short, numbered memos of *why the project is built the way it is*.
Format: Context → Decision → Consequences. New decisions append, never rewrite history.

## ADR-001 — Auto-heal LLM provider: **Ollama (local), qwen2.5:3b**

**Date:** 2026-10-20
**Status:** Accepted

### Context
The self-heal loop needs a "consultant" that turns (intent, sanitized HTML) into
ranked replacement locators. Options evaluated:

| Option | Cost | Privacy/offline | Quality (benchmarks vs 20-case eval suite) | Ops |
|---|---|---|---|---|
| Mock heuristic | $0 | fully offline | 0.90 precision, 0.90 recall; fails 2 lexical traps | zero |
| OpenAI gpt-4o-mini | ~$0.001/heal | HTML leaves the machine | expected ≥ mock; clears the 2 lexical FPs | needs API key in CI or dev |
| Ollama (local) | $0 | fully offline, HTML never leaves laptop | model-dependent (qwen2.5:3b ≈ mock-to-mid) | install once per dev machine |

### Decision
**Use Ollama as the standard heal provider for development and research runs.**

- Provider: `LLM_PROVIDER=ollama`
- Model: `qwen2.5:3b` (default; `LLM_MODEL` can override)
- Endpoint: `OLLAMA_BASE_URL`, default `http://localhost:11434/v1`
  (Ollama exposes an OpenAI-compatible API, so `openai_provider.py` serves it
  with a dummy key — one client library, two brains)
- **Mock stays the CI default** (`ci.yml` sets `LLM_PROVIDER=mock`): CI heals must
  be free, key-less, and deterministic; the eval suite stays reproducible.
- **OpenAI stays available** for comparison runs: same eval suite is the
  apples-to-apples instrument for provider quality.
- Requires the same guards as any provider: HTML sanitizing (FR-08),
  budget cap, cache, uniqueness validation (FR-04), heal-rate gate (FR-10).

### Consequences
1. **Positive:** $0 healing anywhere; no secrets needed for local runs; HTML with
   customer data never leaves the device (privacy win worth stating aloud).
2. **Positive:** the provider Protocol + one env var keeps all downstream
   behavior identical (cache/budget/persistence/reporting don't change).
3. **Trade-off:** local 3B model may rank candidates differently than gpt-4o-mini;
   the eval benchmark (`pytest tests/eval`) must be re-run per provider and its
   `reports/eval_report.json` attached whenever a heal claim is repeated.
4. **Trade-off:** first call is slow (model load ≈ seconds); acceptable — heal
   calls are rare by design (budget + cache), and Ollama keeps the model warm.
5. **Note:** laptop without Ollama (e.g. clean CI machine) degrades gracefully:
   provider errors surface as `unhealable` attempts, tests fail loudly —
   no silent false passes (FR-04.6).

### Verification commands (per provider runs)
```bash
# Ollama (local, free) — the default research provider
ollama pull qwen2.5:3b
LLM_PROVIDER=ollama python scripts/demo_heal.py      # live break-and-heal
LLM_PROVIDER=ollama pytest tests/eval -q             # benchmark on qwen2.5:3b

# Mock (CI baseline, free, deterministic)
pytest tests/eval -q

# OpenAI (paid comparison, optional)
LLM_PROVIDER=openai OPENAI_API_KEY=... pytest tests/eval -q
```
Attach each provider's `eval_report.json` to the provider-change PR; CI gate
(`heal_rate ≥ 0.70`) still applies to live healing.
