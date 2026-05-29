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

`POST /api/assistant/ask/` with `{"ticker","tab","locale","question"}`. The client sends only a
context **descriptor** — never financial data. The view, in order:

1. Permission check (`IsAssistantAllowed`) — superuser-only in v1; backend-enforced, not a UI hide.
2. Daily quota check (`assistant_quota.would_exceed_assistant_limit`) — returns 429 before any OpenAI call.
3. **Context assembly** — reuses `quotes.views._compute_quote_payload` for the same numbers the user sees,
   plus the `Ticker` row, plus (if authed) the latest `accounts.CompanyVisit.note` and active
   `accounts.IndicatorAlert` rows. Wrapped in `<COMPANY_DATA>…</COMPANY_DATA>` delimiters so
   user-authored notes cannot be interpreted as instructions.
4. **Guardrail** — GPT-4o-mini with Pydantic structured output classifies `on_topic | off_topic | jailbreak`.
   Non-`on_topic` → one `off_topic` SSE frame, log row, done.
5. **Answer** — GPT-4o streaming (`stream=True`, `include_usage=True`), strong localized system prompt.
6. Emit SSE events `meta → token* → done` (or `error` on upstream failure).
7. `finally:` write the `LLMQuery` row with tokens, cost, latency, classification, status.

Streaming requires the SSE route to **bypass Next.js middleware** (`NextResponse.rewrite` buffers)
and **nginx proxy buffering** (`X-Accel-Buffering: no`, `proxy_buffering off`) — same pattern as
`/api/logos/`. See deploy step.

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
| `ASSISTANT_MAX_QUESTION_CHARS` | `1000` | Per-request input cap, enforced before OpenAI is called. |
| `ASSISTANT_GLOBAL_DAILY_USD_CAP` | `10.0` | Global per-day USD kill-switch across all tiers. |

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
