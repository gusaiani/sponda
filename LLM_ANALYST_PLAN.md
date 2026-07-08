# LLM Analyst — Implementation Plan

Natural-language screening over the fundamentals database, with a measured eval
harness. Companion to `LLM_ASSISTANT.md` (the per-company assistant this feature
builds on). Architecture: **tool use, not SQL generation** — the model calls
tools that wrap the existing screener surface; it never composes SQL.

## Requirement → existing module mapping

| Requirement | Existing module | Action |
|---|---|---|
| Screener query surface | `quotes/views.py` `ScreenerView.get` (inline, lines 1638–1746) | **Extract** into `quotes/screener.py::run_screener(filters, sectors, countries, sort, limit, offset)` — plain function, no DRF coupling. `ScreenerView` becomes a thin wrapper. Behavior-preserving refactor, existing tests stay green. |
| `screen_companies` tool | `SCREENER_FILTERABLE_FIELDS` (10 indicators), `run_screener` | New `assistant/tools.py`: JSON schema mirrors the real param surface — per-indicator `min`/`max`, `countries[]`, `sectors[]`, `sort`, `limit`. Executes `run_screener` in-process (no HTTP). |
| `get_company` / `get_fundamentals` tools | `TickerDetailView` internals, `IndicatorSnapshot`, `_compute_quote_payload` | `get_company(symbol)` → Ticker + IndicatorSnapshot row (cheap, precomputed). `get_fundamentals(symbol)` → full `_compute_quote_payload` path incl. stale-while-revalidate provider fetch (decision: completeness over latency; the agent's tool-round bound caps worst-case chaining). |
| `list_available_indicators` tool | `IndicatorSnapshot.INDICATOR_FIELDS`, calculator docstrings | Static catalogue: key, name, definition, direction ("lower is cheaper"), typical range. Zero-cost tool; grounds "cheap" → `pe10` and lets the model decline ROE/dividend-yield asks honestly. |
| Agent loop | none (net-new; `views.py` is single-shot) | New `assistant/agent.py`: OpenAI tool-calling loop, bounded rounds (max 6), streaming final turn. Reuses `get_openai_client()` (timeout 30s, 1 retry). |
| Endpoint | `assistant/views.py` `ask()` SSE pattern | New `POST /api/assistant/screen/`. SSE frames: `meta → filters (interpreted set) → results (ScreenerRow[]) → token* → done`, same `_sse_frame` encoding, same `X-Accel-Buffering: no`. |
| Guardrail | `assistant/guardrail.py` (LLM classifier, structured outputs) | New screening-mode classifier prompt beside `GUARDRAIL_SYSTEM_PROMPT`; same three-way verdict. Unsupported-metric asks are NOT guardrail refusals — they flow to the agent, which answers with what Sponda *can* screen. |
| Prompt-injection boundary | `prompts.py` `SHARED_SYSTEM_PREFIX`, `<COMPANY_DATA>` convention | Same rule extended: tool results wrapped as data blocks; user text stays outside delimiters; adversarial cases added to guardrail tests and the eval set. |
| Conversational refinement | `history.py` (stateless, client resends pairs) | Reuse as-is. The assistant's visible reply always states the full active filter set, so refinement composes from history text — no tool-message persistence needed. |
| Quota + logging | `assistant_quota.py`, `LLMQuery` | Reuse the seam. Wire the documented-but-dead `trial` tier: anonymous per-IP cap via `ASSISTANT_FREE_TRIAL_PER_DAY` + `LLMQuery.ip_hash` (field and index already exist, never populated). Fix the latent `would_exceed_assistant_limit` fall-through for `trial`. |
| Cost accounting | `cost.py` | Reuse. Add `.get()` guard so unknown models raise a clear error, and register any new model used in evals. |
| LLMQuery as eval corpus | `models.py` docstring ("future eval corpus") | Small migration: `feature` discriminator (`ask`/`screen`), `interpreted_filters` JSONField (null), `ticker` allowed blank. Extends the existing table — no parallel logging infra. |
| Frontend input + chips | `screener/page.tsx`, `useAssistantStream.ts`, `useScreener.ts` | New `useScreeningAssistant` hook (same SSE reader patterns, new frame types). Interpreted-filter chips above the existing inline results table; `results` frame rows are `ScreenerRow`-shaped so the existing table markup renders them unchanged. Feature flag: `ASSISTANT_SCREENING_ENABLED` setting enforced server-side + boolean on `/api/auth/me/` for UI gating (the `learning_mode_enabled` pattern). |
| Localization | `src/i18n/types.ts` + 7 locale files | Keys added to `TranslationDictionary`; TypeScript forces all 7 locales, so PT+EN come with es/zh/fr/de/it. |
| E2E | `tests/test_e2e*.py`, `live_server` + `@patch` pattern | Happy path + decline path, patching the agent entry point the way `test_e2e.py` patches `quotes.views.fetch_quote`. |

## Reality check vs. the spec

The spec's example mentions **ROE** and a **timespan** param. Neither exists:
the screener filters exactly 10 indicators (`pe10`, `pfcf10`, `peg`,
`pfcf_peg`, `debt_to_equity`, `debt_ex_lease_to_equity`,
`liabilities_to_equity`, `current_ratio`, `debt_to_avg_earnings`,
`debt_to_avg_fcf`) and has no timespan. Tools mirror the real schema
("mirror the real parameter schema" is the governing instruction). "ROE above
15%" becomes an eval case for honest partial fulfillment: apply the supported
clauses, state that ROE isn't available, suggest the closest supported metric.
"Debt payable from FCF in under 3 years" maps cleanly to `debt_to_avg_fcf < 3`.

## Eval harness (`backend/assistant/evals/`)

- `screening_evals.jsonl` — 60–100 cases: `{id, query, language, category,
  expected_filters | expected_behavior, min_expected_rows |
  expected_symbols_subset}`. Categories: plain filters, direction/unit variants
  ("under", "at most", "single-digit"), PT + EN, composed refinements
  (multi-turn), ambiguous (expect clarification), unsupported (expect decline
  w/ alternatives), adversarial injection (expect safe refusal).
- Runner: `manage.py run_screening_evals [--smoke] [--model X]` — seeds a
  deterministic fixture universe (~16 synthetic companies across BR/US/DE,
  varied sectors, hand-picked indicator values so every eval case has a known
  answer set), executes the real agent, scores: **filter-parse exact match**
  (primary), result-set correctness, refusal correctness, p50/p95 latency,
  cost per query via `cost.calculate_cost`.
- Report: `backend/assistant/evals/latest_report.md` — overall + per-category
  table, five worst failures verbatim, and the model-comparison table
  (`gpt-4o-mini` vs `gpt-4o`: accuracy/cost/latency) for the blog post.
- CI: smoke subset (~10 cases) as a separate job, skipped when
  `OPENAI_API_KEY` secret is absent so forks/PRs don't fail or spend.
- Target: ≥85% filter-parse accuracy on non-adversarial set, 100% refusal on
  injection. Prompt/tool iterations logged in the report (blog narrative).

## PR sequence

1. **PR 1 — foundations**: this plan + `run_screener` extraction (TDD:
   characterization tests on ScreenerView first) + `LLMQuery` migration +
   quota `trial`-tier fix + `cost.py` guard.
2. **PR 2 — tool layer + agent loop**: `tools.py`, `agent.py`, `screen/`
   endpoint, screening guardrail prompt, unit tests (mocked OpenAI, existing
   MagicMock streaming idiom).
3. **PR 3 — evals**: dataset, fixture universe, runner, report; iterate
   prompts/tools to targets.
4. **PR 4 — frontend**: hook, input, chips, table wiring, flag, i18n ×7,
   vitest + 2 Playwright e2e.
5. **PR 5 — report + docs**: final eval report, README section (tool schema,
   why tool-use over SQL-gen, quota model, eval methodology).

## New settings

| Setting | Default | Purpose |
|---|---|---|
| `ASSISTANT_SCREENING_ENABLED` | `False` | Feature flag, server-enforced |
| `ASSISTANT_SCREENING_MODEL` | `gpt-4o` | Agent-loop model |
| `ASSISTANT_MAX_TOOL_ROUNDS` | `6` | Loop bound |
| `ASSISTANT_FREE_TRIAL_PER_DAY` | existing (`0`) | Anonymous per-IP daily cap once wired |
