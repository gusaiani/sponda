# Assistant (LLM Q&A)

A centered text-area fixed to the bottom of the company page lets the user ask questions about
the company they are looking at. Answers stream token-by-token. The assistant is **harnessed**:
a cheap GPT-4o-mini classifier rejects off-topic / jailbreak attempts before any GPT-4o call,
so users cannot turn it into a general-purpose chatbot and costs stay bounded.

## What it does

- Answers finance / Sponda-domain questions about the **company in context** (the ticker in the URL).
- Off-topic, jailbreak, or empty questions get a fixed redirect — no expensive model call.
- Streams the answer via SSE; aborting the request stops billing mid-stream.
- Logs every query (`assistant.models.LLMQuery`) for quota counting, cost dashboards, and the future eval corpus.

## How it works

`POST /api/assistant/ask/` with `{"ticker","tab","locale","question","history","years"}`. The client sends
only a context **descriptor** (plus its rolling memory and the current PRAZO window) — never financial
data; the server recomputes the numbers itself. The view, in order:

1. Permission check (`IsAssistantAllowed`) — superuser-only in v1; backend-enforced, not a UI hide.
2. Daily quota check (`assistant_quota.would_exceed_assistant_limit`) — returns 429 before any OpenAI call.
3. **Context assembly** (`assistant/context.py`) — an **allowlist** of named fields is emitted (so verbose
   `*CalculationDetails` blocks can never leak into the prompt): an always-present base set
   (`display_name`, `current_price`, `pe10`, `pfcf10`, `peg`) plus a **tab-specific** set driven by the
   open tab — e.g. `fundamentals` adds the leverage/balance-sheet numbers (`debt_to_equity`,
   `current_ratio`, `total_debt`…), `metrics` adds `pfcf_peg` / CAGRs. So the model sees what's on screen
   without every prompt carrying the whole payload. **Window-aware** (see below): the multiples are
   recomputed for the user's `years` window. Plus (if authed) the latest `accounts.CompanyVisit.note` and
   active `accounts.IndicatorAlert` rows. Wrapped in `<COMPANY_DATA>…</COMPANY_DATA>` delimiters so
   user-authored notes cannot be interpreted as instructions.
4. **Guardrail** — GPT-4o-mini with Pydantic structured output classifies `on_topic | off_topic | jailbreak`.
   Non-`on_topic` → one `off_topic` SSE frame, log row, done.
5. **Answer** — GPT-4o streaming (`stream=True`, `include_usage=True`), strong localized system prompt.
6. Emit SSE events `meta → token* → done` (or `error` on upstream failure).
7. `finally:` write the `LLMQuery` row with tokens, cost, latency, classification, status.

Streaming requires the SSE route to **bypass Next.js middleware** (`NextResponse.rewrite` buffers)
and **nginx proxy buffering** (`X-Accel-Buffering: no`, `proxy_buffering off`) — same pattern as
`/api/logos/`. See deploy step.

## Conversation memory

Follow-ups work: "Is it cheap?" → "And on PFCF10?" keeps context. Memory is **bounded by design** so a
long session can't balloon prompt cost.

- **Client** (`useAssistantStream`) keeps a rolling per-company list of `{question, answer}` turns in a
  ref. It resends the list on each `ask`, appends a turn only when the stream ends on a genuine
  `on_topic` answer (off-topic redirects and errors are not remembered), caps it to the last
  `MAX_HISTORY_TURNS` (4, newest-wins), and **clears it when the ticker changes** (a PETR4 thread never
  bleeds into AAPL).
- **Server** never trusts the client to bound itself: `assistant/history.py::build_history_messages`
  re-clamps the incoming list — drops incomplete/malformed entries, keeps the last
  `ASSISTANT_MAX_HISTORY_TURNS` pairs, truncates each question to `ASSISTANT_MAX_QUESTION_CHARS` and each
  answer to `ASSISTANT_MAX_HISTORY_ANSWER_CHARS`. The clamped turns are interleaved as lean
  `user`/`assistant` messages **between the system prompt and the current question**, in both the
  guardrail call (so short follow-ups classify as on-topic) and the answer call. Only the current turn
  carries the fresh `<COMPANY_DATA>` block — history stays plain text, so memory is cheap and the data
  always reflects the page the user is on *now*.

## Window-aware data (the numbers must match the screen)

The company page's multiples (PE10, PFCF10, PEG, PFCLG, debt-coverage, CAGRs) are **windowed by the PRAZO
year slider** and computed **client-side** in `deriveForYears` (trailing N×4 quarters, IPCA-adjusted). The
quote payload's raw scalars use the all-history window (`max_years=50`), so they do **not** match what's on
screen — feeding them to the assistant produced *"PE10 66.66"* while the page showed *49,9* for WEG.

The fix threads the live window end to end:

- **Client**: the slider's value lives in `ticker-client` (page) but the `AssistantBar` lives in the layout
  shell (a sibling). `AssistantWindowContext` bridges them — the page pushes its `effectiveYears` up, the
  bar reads it and sends `years` with each question.
- **Server**: `build_company_context(…, years)` recomputes the window-dependent multiples by calling the
  **same canonical** `calculate_pe10/pfcf10/peg/pfcf_peg` functions with `max_years=years` — reusing the
  one implementation rather than porting a second one (the drift between two implementations is exactly
  what caused the 66.66-vs-49,9 mismatch). Leverage/balance-sheet fields are point-in-time and pass
  through unchanged. The window is clamped to 1..20 server-side; out-of-range or absent ⇒ no recompute
  (falls back to the canonical scalars).

Result: the assistant reasons over the exact numbers the user is looking at, whatever the slider is set to.

## Error handling

The endpoint fails loudly, never silently. Three layers:

1. **Pre-stream HTTP errors** — returned *before* any `200`/SSE is committed, so
   the client gets a real status it can branch on:
   - `403` superuser/tier gate · `429` daily quota · `400` empty/oversized question
   - `503 {"code": "assistant_not_configured"}` when `OPENAI_API_KEY` is unset.
     Without this guard the guardrail call would throw mid-generator *after* a
     `200` was already sent, leaving the client hanging on a dead stream.
2. **Mid-stream SSE `error` frames** — once streaming, upstream failures surface
   as an `error` event with a stable code (`upstream_timeout`, `rate_limited`,
   `internal`) rather than a broken connection.
3. **Client-side resilience** (`useAssistantStream`):
   - Any non-OK status → error state; a JSON `code` in the body wins over the
     status map (so `assistant_not_configured` reaches the UI).
   - A stream that closes with no terminal frame (`done`/`off_topic`/`error`) →
     `assistant_interrupted`, keeping any partial answer visible.
   - A failed `fetch` → `network`; an `AbortError` (Stop button / unmount) is
     treated as deliberate, not an error.

User-facing messages are localized in all seven locales; config-level causes
(`assistant_not_configured`) show a neutral "unavailable" message to users while
a **developer hint** (rendered only when `NODE_ENV !== "production"`) names the
real cause, e.g. *"OPENAI_API_KEY is not set on the backend."*

## Access tiers

| Tier | When | Daily cap |
|---|---|---|
| `superuser` | `is_superuser=True` | unlimited |
| `paying` | `is_paying_user(user)` *(stub returns False until a Subscription model lands)* | `ASSISTANT_PAYING_PER_DAY` (200) |
| `trial` | `ASSISTANT_FREE_TRIAL_PER_DAY > 0` (off by default in v1) | `ASSISTANT_FREE_TRIAL_PER_DAY` |
| `denied` | anonymous or no tier matches | 0 |

The tier resolver (`assistant.assistant_quota.assistant_access_tier`) is the single seam — flipping the
free trial on is one env var; adding paying users is one function body once billing exists.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | *(empty)* | OpenAI API key. Empty ⇒ endpoint degrades to 503 (no crash). |
| `ASSISTANT_ANSWER_MODEL` | `gpt-4o` | Model for the streamed answer. |
| `ASSISTANT_GUARD_MODEL` | `gpt-4o-mini` | Cheap classifier for the topic guardrail. |
| `ASSISTANT_PAYING_PER_DAY` | `200` | Per-day quota for the `paying` tier (when billing lands). |
| `ASSISTANT_FREE_TRIAL_PER_DAY` | `0` | Per-day free-trial quota. `0` ⇒ trial disabled. |
| `ASSISTANT_MAX_QUESTION_CHARS` | `1000` | Per-request input cap, enforced before OpenAI is called. Also caps each remembered question. |
| `ASSISTANT_GLOBAL_DAILY_USD_CAP` | `10.0` | Global per-day USD kill-switch across all tiers. |
| `ASSISTANT_MAX_HISTORY_TURNS` | `4` | Max remembered Q&A pairs per session (oldest dropped first). The per-session cost ceiling. |
| `ASSISTANT_MAX_HISTORY_ANSWER_CHARS` | `2000` | Truncates each remembered answer before it re-enters the prompt. |

## Local testing

```bash
# Backend tests for the assistant app
cd backend && pytest tests/test_assistant_models.py tests/test_assistant_settings.py -q

# Smoke-import the OpenAI SDK
python -c "from openai import OpenAI; print(OpenAI)"

# Set a key in your .env (one-time)
echo "OPENAI_API_KEY=sk-..." >> ../.env

# End-to-end (once the view ships in Plan Step 4):
#   1. Log in as a superuser
#   2. Open /pt/PETR4 and use the bar at the bottom
#   3. Ask "what's the weather" → fixed off-topic redirect, no GPT-4o call
```

## Status

Backend (Steps 1–5) is feature-complete for v1 and fully tested — 31 passing
tests across the assistant app (`backend/tests/test_assistant_*.py`).

- ✅ Step 1 — app scaffold, `LLMQuery` model + migration, settings, URL include, env example
- ✅ Step 2 — server-side context assembly (`assistant/context.py`)
- ✅ Step 3 — guardrail, Pydantic structured output (`assistant/guardrail.py`)
- ✅ Step 4 — SSE streaming answer endpoint, superuser-gated (`assistant/views.py`)
- ✅ Step 5 — tiered quota enforcement (`assistant/assistant_quota.py`), wired into the
  view as a 429 before any OpenAI call. The resolver/cap logic supports the `paying`
  tier; the `ask` gate stays superuser-only in v1, so the quota check is a no-op for
  superusers (always under cap) and pre-wired for when the gate broadens.
- ⏳ Step 6 — frontend `AssistantBar` + SSE consumer
- ⏳ Step 7 — wire into `layout-shell`, gated
- ⏳ Step 8 — nginx bypass + middleware-matcher exclusion (SSE through CDN)

Full design plan: `~/.claude/plans/in-this-branch-i-kind-kay.md`.
