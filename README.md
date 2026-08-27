# Sponda

Financial indicators and analytics for global public companies. Over 23,000 companies listed across the U.S. and Brazil.

**Live at [sponda.capital](https://sponda.capital)**

![Sponda homepage](docs/screenshot.png)

## Index

**Start here**

- [Architecture](#architecture)
- [Stack](#stack)

**Product**

- [Screener](#screener)
- [Assistant (LLM Q&A)](#assistant-llm-qa)
- [MCP server](#mcp-server)
- [Markdown pages](#markdown-pages)
- [Slack app (BYOK)](#slack-app-byok)
- [Valuation ratios: one definition everywhere](#valuation-ratios-one-definition-everywhere)
- [Cross-currency indicators](#cross-currency-indicators)
- [Comparison chart (expanded indicator view)](#comparison-chart-expanded-indicator-view)
- [Ticker search](#ticker-search)
- [Peer comparison](#peer-comparison)
- [Saved lists](#saved-lists)
- [Learning Mode](#learning-mode)
- [Indicator Alerts](#indicator-alerts)
- [Favorites](#favorites)
- [Social (Sponds)](#social-sponds)
- [Lookup limits](#lookup-limits)
- [Localized account emails](#localized-account-emails)
- [Marketing email opt-out](#marketing-email-opt-out)
- [Logos](#logos)
- [Blog](#blog)

**Engineering**

- [Performance](#performance)
- [Server-side rendering and hydration](#server-side-rendering-and-hydration)
- [Observability](#observability)
- [Seeding a quarter from CVM](#seeding-a-quarter-from-cvm)
- [Measuring CVM publication latency](#measuring-cvm-publication-latency)
- [CVM runbook](CVM_RUNBOOK.md) · what to check, when, and what each answer means
- [Mapping tickers to CVM codes](#mapping-tickers-to-cvm-codes)
- [Ingesting quarters from CVM](#ingesting-quarters-from-cvm)
- [The fourth quarter](#the-fourth-quarter)
- [Ingesting quarters straight from ENET](#ingesting-quarters-straight-from-enet)
- [Scheduled Tasks](#scheduled-tasks)

**Operations**

- [Deployment](#deployment)
- [Local Development](#local-development)

## Architecture

A one-page system architecture overview · stack, apps, data flows, and the reasoning behind each technology choice · lives at [`docs/architecture.html`](docs/architecture.html). GitHub shows HTML as source, so use the [rendered version](https://gusaiani.github.io/sponda/architecture.html) (GitHub Pages, published from `main:/docs`), or open the file locally in a browser.

## Stack

- **Backend:** Django 5 + Django REST Framework + PostgreSQL + Redis + Celery
- **Frontend:** React 19 + TypeScript + Next.js 16 + TanStack Query
- **Styling:** Tailwind CSS v4 (`@apply` only -- no utility classes in JSX)
- **Deploy:** GitHub Actions CI/CD → DigitalOcean VPS (nginx + systemd)

## Screener

The screener page at `/[locale]/screener` lets users filter the whole B3 + US universe (~23K companies) by any of the indicators shown on a company's main page and sort the results. Backed by a dedicated `IndicatorSnapshot` table so filtering and sorting are one DB query instead of recomputing indicators for every ticker on every request.

### Supported filters

All are numeric `min` / `max` bounds (either side optional):

- `pe1` … `pe15` · strict inflation-adjusted P/E windows. `peY` is empty unless the company has the full Y years of earnings history — a PE15 is never quietly a PE8. PE10 is the classic Shiller window.
- `pe_years_available` · widest P/E window a company can honestly fill (max 15). Filter `min=10` to demand a decade of history.
- `pfcf10` · valuation multiple (10-year rolling free cash flow)
- `peg`, `pfcf_peg` · growth-adjusted valuation
- `debt_to_equity`, `debt_ex_lease_to_equity`, `liabilities_to_equity`, `current_ratio` · leverage / liquidity
- `debt_to_avg_earnings`, `debt_to_avg_fcf` · debt vs. cash generation
- `market_cap` · absolute currency amount

### How it works

1. **Snapshot table.** `IndicatorSnapshot` (one row per ticker) stores the latest value of every screened indicator. The table is kept current by a **three-layer refresh strategy** designed to respect BRAPI Pro and FMP Starter monthly budgets:
   - **Persist-on-view.** Any time a user opens a company page, the `PE10View` endpoint writes the freshly computed indicators back into `IndicatorSnapshot` and updates `Ticker.market_cap` as a side-effect (wrapped in `try/except` so a write failure never breaks the page). This keeps actively viewed tickers perpetually fresh without any scheduled work.
   - **Rolling price refresh** (`refresh_snapshot_prices`, every 15 min while B3 or NYSE is open · see [Scheduled Tasks](#scheduled-tasks)). For every ticker with a market cap, fetches the current quote (one API call) and recomputes only the price-dependent indicators — PE10, PFCF10, PEG, P/FCF PEG — against existing DB fundamentals. Leverage and debt-coverage fields are left alone.
   - **Weekly fundamentals refresh** (`refresh_snapshot_fundamentals`, Sunday 06:00 UTC). Resyncs quarterly earnings / cash flows / balance sheets (three API calls per ticker) and then recomputes the full indicator set via `compute_company_indicators` — the same service the company page uses, so the screener and the company page can never disagree.
   - **Bootstrap.** `sync_market_caps` routes Brazilian tickers through BRAPI and US tickers through FMP to backfill `Ticker.market_cap` for rows that are missing it. Run once after adding new tickers; both refresh jobs skip tickers without a market cap.
2. **Query.** `GET /api/screener/` takes `<field>_min` / `<field>_max` params, a `sort` (prefix `-` for descending; nulls always last), `limit` (max 500), and `offset`. Returns `{ count, results[] }`.
3. **Frontend.** The `useScreener` hook (`frontend/src/hooks/useScreener.ts`) wraps the endpoint in React Query with `staleTime: 60s`. The page is `frontend/src/app/[locale]/screener/page.tsx` — sticky filter sidebar + results table with click-to-sort column headers and cursor-based "load more" pagination.

**Example:** `GET /api/screener/?pe10_max=10&debt_to_equity_max=1&sort=-market_cap&limit=50` returns the 50 largest Brazilian companies with PE10 ≤ 10 and D/E ≤ 1.

### Slider scales

Most screener sliders are linear — track position maps directly to value. The leverage filters (`debt_to_equity`, `debt_ex_lease_to_equity`, `liabilities_to_equity`) instead use a piecewise log-like scale defined in `frontend/src/utils/sliderScale.ts` (`LEVERAGE_SCALE`):

- Range `0..100`. The `0..1` band — where most companies sit — gets the first 55% of the track. The `1..100` tail is log-compressed across the remaining 45%, so a few distressed-balance outliers (D/E up to ~100) don't squash the useful resolution out of the slider.
- Snap precision is band-aware: `0.05` below 1, `0.5` between 1 and 20, `5` at 20+. Handle labels track that precision (two decimals below 1, one decimal up to 10, integer above).

`DualRangeSlider` accepts an optional `scale: SliderScale` prop with `toValue` / `toPosition` / `snap`. When supplied, the underlying `<input type="range">` runs in normalized position space (integer stops 0..1000) and the component converts on every change. Without `scale`, behavior is unchanged.

## Assistant (LLM Q&A)

Centered text-area at the bottom of the company page; streaming OpenAI-powered answers,
guardrailed to Sponda's finance domain, with tiered per-day quotas. Superuser-only in v1.
See [LLM_ASSISTANT.md](LLM_ASSISTANT.md).

## MCP server

Sponda's screening tools, exposed to any agent — Claude, Cursor, custom MCP clients —
at `https://sponda.capital/api/mcp/` (Streamable HTTP, stateless, no auth). The tool
surface is `assistant/tools.py` verbatim: the same JSON Schemas and executors the
in-house screening agent uses, so the public MCP surface and the agent can never drift.

### What the server advertises

`initialize` reports `tools` and `prompts`. Every tool carries a human
readable `title` and `readOnlyHint: true`, which is both a hard requirement
for the Anthropic Connectors Directory and the flag clients read to decide
whether a call needs the user to confirm it. Without it a read-only screener
gets treated as potentially destructive.

Nothing on this surface writes. `backend/tests/test_mcp_capabilities.py`
asserts that, so adding a writing tool fails a test rather than silently
inheriting the wrong annotation.

**Prompts** are the menu for someone who does not know the indicator names:
`screen_for_value`, `compare_companies`, `explain_company`. Each expands into
a question phrased the way a person asks it, which the model then answers
using the tools.

**The company count in `instructions` is read, not typed.** It comes from the
same cached symbol list the sitemap uses. The first version said "~23,000",
which was wrong by several thousand, and it matters because registries
generate listings from this text verbatim: Smithery reads it off the wire.

### Using it (any MCP client)

**Claude Code** — one command, then just ask:

```bash
claude mcp add --transport http sponda https://sponda.capital/api/mcp/
```

**Claude (web/desktop):** Settings → Connectors → Add custom connector →
`https://sponda.capital/api/mcp/`.

**Cursor** (`~/.cursor/mcp.json`) or any client that takes a JSON server config:

```json
{
  "mcpServers": {
    "sponda": { "url": "https://sponda.capital/api/mcp/" }
  }
}
```

Then ask things like:

> Brazilian companies with P/E10 under 8 and debt payable from average FCF in under 3 years
>
> Of those, which has the most conservative leverage? Pull WEGE3's full fundamentals.
>
> US companies with at least 15 years of history trading below 10× their 15-year average earnings

The P/E window family is strict: `peY` only exists when the company has the full Y years of earnings history, and `pe_years_available` says the widest window each company can fill — so the agent can explain *why* a PE15 screen excludes a young company instead of quietly averaging fewer years.

Four tools, designed to be called in this order:

| Tool | What it does | Cost |
| --- | --- | --- |
| `list_available_indicators` | Indicator catalogue (keys, definitions, direction), plus live country/sector lists and examples of metrics Sponda does *not* have | cheap |
| `screen_companies` | Filter/sort/rank the ~23k-company universe by indicator bounds, country, sector; returns match count + up to 50 rows | cheap |
| `get_company` | One company's metadata and current indicator values by ticker | cheap |
| `get_fundamentals` | Full fundamentals payload for one company — triggers a live market-data fetch | expensive, tighter cap |

Limits: anonymous per-IP daily caps (see env vars below); over the cap the endpoint
answers HTTP 429 until midnight. Executor failures ("unknown symbol") come back as tool
results with `isError: true`, never protocol errors, so a calling model can read them
and adjust.

### In-app announcement

The frontend announces the MCP server with a centered modal over the page
(`McpAnnouncementModal`): install tabs for Claude Code, Cursor, and the Claude app
(each with a copy button), three example queries, and the usage limits. It opens
automatically on page load for every visitor, logged in or not, until dismissed once;
the dismissal is stored in `localStorage` under `sponda-mcp-announcement-dismissed`
(`useMcpAnnouncement`), so it never auto-opens again on that browser. An outlined
"MCP" pill in the header, next to the Screener link, reopens it on demand
(`McpHeaderButton`). All copy is translated in the seven locales.

**Linking to it: `?mcp=1`.** Any URL carrying the parameter opens the modal even
for a visitor who dismissed it before (`MCP_ANNOUNCEMENT_QUERY_PARAM`). The
announcement email's call-to-action depends on this: without it the link is dead
for precisely the people most likely to click, since anyone who already visited
the site and closed the modal would land on an unchanged homepage. The close
button still outranks the parameter, so a `?mcp=1` visit is not a trap.

The parameter is read through `useSyncExternalStore` rather than
`useSearchParams`, which would opt the whole route into client-side rendering,
and rather than a mount effect, which the codebase avoids (see `useStoredState`
for the same reasoning).

Local testing: run the frontend, load any page, dismiss the modal, reload to confirm
it stays closed, then reopen it via the header pill. Clearing the `localStorage` key
brings the auto-open behavior back. With the key still set, load `/en?mcp=1` and
confirm the modal opens and can be closed.

### Developing it

Implementation: `backend/assistant/mcp.py` — a single stateless JSON-RPC 2.0 view (no
SSE, no sessions; every request is one POST answered with one JSON body). It serves
`initialize` (protocol-version negotiation), `ping`, `tools/list`, and `tools/call`,
and acknowledges notifications with 202. Tool schemas and executors are imported from
`assistant/tools.py` — to add or change a tool, change it there and both the screening
agent and the MCP surface pick it up together.

| Env var | Default | Meaning |
| --- | --- | --- |
| `MCP_ENABLED` | `true` | Serve the endpoint; `false` returns 404 |
| `MCP_TOOL_CALLS_PER_DAY` | `200` | Per-IP daily cap across all `tools/call` requests |
| `MCP_FUNDAMENTALS_CALLS_PER_DAY` | `25` | Per-IP daily sub-cap for `get_fundamentals` |
| `MCP_RECORDED_CALLS_PER_DAY` | `1000` | Per-IP daily cap on `McpCall` audit rows (see [Usage stats](#usage-stats)) |
| `MCP_CALL_RETENTION_DAYS` | `400` | How long `McpCall` rows are kept before the weekly `prune_mcp_calls` timer deletes them |

Rate-limit counters are date-keyed entries in the Redis cache (`mcp:<scope>:<ip_hash>:<day>`),
so caps reset at midnight and need no schema or cron.

Run it locally:

```bash
cd backend && python manage.py runserver
```

Smoke-test with curl:

```bash
# list the tools
curl -s localhost:8000/api/mcp/ -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# run a screen: P/E10 <= 10, cheapest first
curl -s localhost:8000/api/mcp/ -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"screen_companies","arguments":{"filters":{"pe10":{"max":10}},"sort":"pe10"}}}'
```

Or drive it interactively with the MCP inspector
(`npx @modelcontextprotocol/inspector http://localhost:8000/api/mcp/`), or point Claude
Code at your dev server
(`claude mcp add --transport http sponda-dev http://localhost:8000/api/mcp/`).

Tests: `pytest tests/test_mcp_server.py` — transport, lifecycle, schema-sharing,
all four tool paths, and the rate-limit caps.

### Usage stats

Every JSON-RPC message the endpoint answers is recorded as an `McpCall` row
(`assistant/models.py`), and the admin dashboard reports them under **Servidor
MCP**. This is the *only* record of MCP traffic: PostHog is a browser snippet
and MCP clients never load a page, so no product analytics sees this surface at
all, and the rate-limit counters are per-IP cache keys that expire at midnight.
nginx access logs show the hits but not the JSON-RPC body, so they cannot say
which tool was called.

One row per answered message, lifecycle chatter included. Connection volume is
as interesting as tool volume when the question is who actually wired Sponda up:

| Column | Notes |
| --- | --- |
| `method` | `initialize`, `ping`, `tools/list`, `tools/call`, `notifications/*`. Unsupported methods are recorded too, so client probes are visible |
| `tool_name` | `tools/call` only, and set even when the call was rejected, so rate-limit pressure is attributable |
| `client_name` / `client_version` / `protocol_version` | From `initialize`'s `clientInfo`. Blank elsewhere: the server is stateless, so no later request names its caller |
| `user_agent` | The one per-request client signal that is always present |
| `ip_hash` | Same salted SHA-256 as `PageView` and the rate limiter. Raw IPs are never stored |
| `failed` | Protocol errors, executor errors surfaced as `isError`, and rejected calls |
| `rate_limited` | A subset of `failed`: turned away by a daily cap with HTTP 429 |
| `latency_ms` | Server-side time to answer |
| `arguments` | `tools/call` only: the arguments object, verbatim. Size-guarded at 20 KB serialized (stored as `{"_truncated": true}` beyond that, since the sender is unauthenticated); null for lifecycle methods and argument-less calls. Recorded even for rate-limited calls — a turned-away call is still demand |
| `result_count` | `screen_companies` successes only: the total match count, not the page size. Zero flags a screen the data could not answer; null for other tools and for screens that errored |

Writes are best effort. `_record_call` swallows and logs its own failures,
because a statistic is never worth failing a tool call that already succeeded.
Malformed JSON, non-POST requests, and calls served while `MCP_ENABLED=false`
are not recorded: they are not queries.

Recording has a per-IP daily cap of its own (`MCP_RECORDED_CALLS_PER_DAY`,
default 1000, a cache counter alongside the rate-limit ones). The lifecycle
methods are deliberately uncapped so a client can always reconnect, which would
otherwise let an unauthenticated caller grow the table without bound. Past the
cap the endpoint keeps answering normally; only the bookkeeping stops.

The dashboard section (`AdminDashboardView._get_mcp_stats`) adds a fixed number
of queries regardless of traffic: a filtered period aggregate (calls, tool
calls, unique callers, failures, 429s for 24h/7d/30d/1y/all time), the top 10
tools and top 10 clients over 30 days, a 30-day daily series with gaps filled
with zero so a quiet day and a missing day do not look the same, and the query
mining below.

Django admin's static files (its stylesheets, under `/static/`) are served by
WhiteNoise from the Django process itself: every request reaches Django
through the Next.js middleware proxy (`/static/:path*` is an explicit matcher
entry, because the filenames contain dots and the catch-all matcher skips any
path with one), so nginx never gets a chance to serve the files. Production
collects them into `backend/staticfiles/` during deploy (`collectstatic`);
dev and CI serve straight from the app finders (`WHITENOISE_USE_FINDERS`),
so neither needs a build step. Tests: `backend/tests/test_static_files.py`,
`frontend/src/middleware.test.ts`.

Raw rows are browsable in Django admin (`/admin/`, Assistant → Mcp calls;
the left nav shows an "MCP calls" shortcut to superusers): filterable by
method, tool, and outcome, navigable by date, with each call's recorded
`arguments` JSON on the detail page. The page is strictly read-only — the
table is an audit log written by the MCP endpoint, and add, change, and
delete are all denied even for superusers. Viewing is superuser-only:
Django's permission system would let any staff user granted `view_mcpcall`
in, so `McpCallAdmin` requires `is_superuser` outright.

### Query mining

Because `McpCall.arguments` stores what each `tools/call` actually asked for,
the dashboard's **Consultas (30 dias)** block turns the audit log into a
demand signal (`AdminDashboardView._get_mcp_query_stats`):

- **Indicadores mais usados** — which indicator keys screens filtered or
  sorted by (an indicator used both ways in one call counts once). Tells you
  which of Sponda's indicators earn their keep.
- **Países / Setores mais buscados** — where callers point the screener.
  Feeds the country/sector backfill priority.
- **Screens sem resultado** — screens that ran and matched zero companies,
  against all screens that ran. Every zero is a coverage gap or an over-tight
  filter the data could not answer.
- **Símbolos não atendidos** — symbols passed to `get_company` /
  `get_fundamentals` that failed (unknown ticker or no indicator data),
  ranked case-insensitively. A coverage wishlist collected for free.

The screen-arguments aggregation runs in Python over one bounded query — the
interesting shape (keys of a nested JSON object) has no portable SQL
aggregation, and the per-IP recording cap bounds how many rows a 30-day window
can hold. The zero-result and failed-symbol rankings aggregate in SQL.

The tool layer was also hardened so the mined failures are actionable rather
than noise: `screen_companies` now returns corrective errors (naming the valid
values) for unknown indicator keys, non-numeric bounds, and unknown country
codes, instead of silently dropping the filter — the same pattern
`_resolve_sectors` already used. A silently dropped filter means the calling
model believes it screened when it did not.

Retention: the `prune_mcp_calls` management command deletes `McpCall` rows
older than `MCP_CALL_RETENTION_DAYS` (default 400, so year-over-year
comparisons survive). In production it runs weekly via the
`sponda-prune-mcp-calls.timer` systemd unit (Sundays 04:30 UTC), installed by
the deploy workflow like every other timer.

Local testing: run the backend, POST a couple of calls with the curl snippets
above, then sign in as a superuser and open `/admin-dashboard`. The **Chamadas
MCP (24h)** card, the **Servidor MCP** tables, and the **Consultas (30 dias)**
block should reflect them; `python manage.py prune_mcp_calls` reports how many
rows it deleted.

Tests: `pytest tests/test_mcp_analytics.py` (recording, dashboard section,
query mining, pruning), `pytest tests/test_assistant_tools.py` (corrective
errors), and `npm test -- src/app/'[locale]'/admin-dashboard` for the UI.

## Slack app (BYOK)

A Slack bot that answers screening questions in any workspace channel or DM,
running each question on the asker's **own** LLM API key (bring-your-own-key).
Users register an OpenAI or Anthropic key with `/sponda-key`; from then on,
mentioning the bot (`@Sponda cheapest BR banks by P/E10?`) or DMing it runs
the screening agent on their key — their account, their cost. There is no
quota apparatus here because Sponda pays no inference: the only house cost is
the database work the tool layer already bounds.

### How it works

Backend app: `backend/slackbot/`.

- **Tool surface** — identical to the site agent and the public MCP server:
  `assistant/tools.py` executors, shared through
  `assistant.agent.execute_named_tool`, so the three surfaces can never drift.
- **Two agent loops, one event vocabulary** — OpenAI questions reuse
  `assistant.agent.run_screening_agent` with a per-user client injected;
  Anthropic questions run `slackbot/anthropic_agent.py`, a non-streaming
  tool-calling loop over the same prompt, tools, and round bound
  (`ASSISTANT_MAX_TOOL_ROUNDS`). Both yield the same event dataclasses;
  `slackbot/providers.py` folds either stream into one answer.
- **HTTP surface** (`/api/slack/…`, all signature-verified with Slack's v0
  HMAC scheme, replay-bounded to 5 minutes, failing closed when
  unconfigured):
  - `events/` — Events API callback. Acks inside Slack's 3-second window:
    the only inline work is the signature check, `event_id` dedup (Slack
    redelivers events it thinks failed; a cache `add` makes redelivery a
    no-op), and a Celery enqueue. Answers `app_mention` events anywhere and
    plain messages in DMs; ignores bot posts and message edits so it can
    never loop on itself.
  - `commands/` — the `/sponda-key` slash command. Bare → opens a modal
    (provider select + key input); `status` → which provider is registered;
    `delete` → removes the stored key.
  - `interactions/` — the modal submission. The key is liveness-checked
    against the provider's models endpoint (2.5 s budget; an explicit
    401/403 shows an in-modal error, a provider blip stores the key anyway
    rather than locking the user out) and stored Fernet-encrypted.
- **The answer task** (`slackbot/tasks.py`, Celery) — decrypts the asker's
  key, posts a placeholder in the thread, rebuilds conversation memory from
  the thread's prior `SlackQuery` rows (server-side, nothing client-sent is
  trusted), runs the agent, converts the markdown answer to Slack mrkdwn,
  and edits the placeholder into the answer. Errors map to human messages
  (`invalid_api_key` → "re-register with /sponda-key", timeouts, rate
  limits); every outcome lands as a `SlackQuery` audit row with token
  totals and latency. Answer language follows the user's Slack locale
  (`users.info`, cached for a day).
- **Key custody** — keys are encrypted at rest with a dedicated Fernet key
  (`SLACKBOT_KEY_ENCRYPTION_KEY`, deliberately separate from
  `DJANGO_SECRET_KEY`), never logged, never shown in admin (the ciphertext
  is read-only there), and deletable by the user at any time. If the Fernet
  key ever rotates, stored keys fail loudly on decrypt and the bot asks the
  user to re-register.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `SLACK_SIGNING_SECRET` | `""` | Slack app signing secret. Empty → all `/api/slack/` endpoints answer 503. |
| `SLACK_BOT_TOKEN` | `""` | Bot token (`xoxb-…`) for Web API calls (`chat.postMessage`, `views.open`, `users.info`). |
| `SLACKBOT_KEY_ENCRYPTION_KEY` | `""` | Fernet key encrypting stored user API keys. Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Empty → storing a key raises; it never falls back to plaintext. |
| `SLACKBOT_ANTHROPIC_MODEL` | `claude-opus-5` | Model for questions running on an Anthropic key. |

OpenAI questions use the existing `ASSISTANT_SCREENING_MODEL` (default
`gpt-4o`); question/history bounds reuse `ASSISTANT_MAX_QUESTION_CHARS`,
`ASSISTANT_MAX_HISTORY_TURNS`, and `ASSISTANT_MAX_TOOL_ROUNDS`.

### Creating the Slack app

1. <https://api.slack.com/apps> → Create New App → From manifest → paste
   [docs/slack-app-manifest.yml](docs/slack-app-manifest.yml).
2. Install to workspace; copy the **Signing Secret** and **Bot Token** into
   the server's `.env` along with a freshly generated
   `SLACKBOT_KEY_ENCRYPTION_KEY`; restart `sponda` and `sponda-celery`.
3. Slack will verify the events URL (`https://sponda.capital/api/slack/events/`)
   with a `url_verification` challenge — the endpoint answers it once the
   signing secret is configured.

### Local testing

```bash
# Backend up, then simulate Slack (signature required — use the test helper):
cd backend && python -m pytest tests/test_slackbot_views.py -q

# Full slackbot suite (signing, crypto, views, task, both agent loops):
python -m pytest tests/test_slackbot_crypto.py tests/test_slackbot_signing.py \
  tests/test_slackbot_views.py tests/test_slackbot_task.py \
  tests/test_slackbot_providers.py tests/test_slackbot_anthropic_agent.py \
  tests/test_slackbot_settings.py -q
```

Against real Slack from a dev machine, expose the backend with a tunnel
(e.g. `cloudflared tunnel --url http://localhost:8000`) and point the
manifest's URLs at the tunnel host.

## Valuation ratios: one definition everywhere

P/L{N} and P/FCL{N} are computed by a single method across the Indicadores tile, the Fundamentos table, and the Comparar tab (July 2026 unification — the three views previously used three different formulas and disagreed visibly for companies like RIO):

1. **Trailing filings, not calendar years.** An N-year window covers exactly N × periods-per-year trailing filings. When the current year is partial (e.g. only Q1 reported), the window backfills from older periods — a partial year is weighted by what it actually filed, never counted as a full year. Backend: `backend/quotes/pe10.py` / `pfcf10.py`; frontend port: `frontend/src/hooks/deriveForYears.ts` (`trailingQuartersAverage`).
2. **Filing frequency is detected per company** (`backend/quotes/reporting_frequency.py`, mirrored in `deriveForYears.ts`): 4 filings/year for quarterly reporters, 2 for semi-annual ones (Rio Tinto files H1 + full year), 1 for annual-only reporters. The frequency is inferred from the mode of filings per completed calendar year and shipped in the quote payload as `pe10PeriodsPerYear` / `pfcf10PeriodsPerYear`; older cached payloads fall back to client-side inference. This also fixes `maxYearsAvailable` (the PRAZO slider ceiling), which previously divided a semi-annual reporter's history by 4 and halved its horizon.
3. **One FCL definition.** Free cash flow prefers the provider's explicit figure (OCF − CapEx) and falls back to OCF + investing cash flow, both in `backend/quotes/fundamentals.py` and `backend/quotes/pfcf10.py`.
4. **Fundamentos rows are anchored windows.** Each historical year's P/L{N} uses the trailing window ending at that year's last filed period (`computeTrailingRatios` in `frontend/src/components/FundamentalsTab.tsx`), with the year's inflation-adjusted market cap over inflation-adjusted average earnings. Years without enough trailing history show "—" instead of a silently-shrunk average. The Comparar tab reads the same `deriveForYears` values as the Indicadores tile, so the two can never diverge.
5. **Per-year debt coverage columns.** The Fundamentos table's Balance Sheet group also carries Debt/Earn{N} and Debt/FCF{N} — the year's inflation-adjusted ex-lease debt divided by the same anchored trailing averages the P/L{N}/P/FCL{N} columns use, so all four ratios follow the PRAZO slider together. Mirroring the Indicadores debt-coverage tiles (`deriveForYears.ts`), the ratio is only shown when the window average is positive; negative-earnings windows render "—".

No new environment variables. To test locally: open `/pt/RIO` (a semi-annual reporter), check that the PRAZO slider reaches ~13 years and that the P/L and P/FCL values match across Indicadores, Fundamentos (latest row), and Comparar for the same window. For debt coverage, open `/en/DUOL/fundamentals` and check Debt/Earn{N} tracks the slider and blanks out on years whose trailing average earnings are negative.

## Cross-currency indicators

Foreign-domiciled companies (NVO, ASML, TM, BABA, ...) trade in USD on US exchanges but file their financials in their home currency (DKK, EUR, JPY, CNY, ...). Any market-cap-based indicator (PE10, PFCF10, PEG, P/FCF PEG, multiples-history chart) translates the market cap into the **statement currency** before dividing by earnings/FCF, so the ratio is dimensionally coherent.

**Pipeline:**

- `Ticker.reported_currency` is populated by `fmp.sync_earnings` from each statement's `reportedCurrency` (BRL hardcoded for Brazilian tickers).
- `FxRate` stores daily USD↔X close rates from FMP, back to 2010. Refreshed daily by `sync_fx_rates` (timer: `sponda-refresh-fx.timer`).
- `CountryCPIIndex` stores monthly per-country CPI YoY rates from FRED for inflation-adjusting historical fundamentals in non-USD/non-BRL currencies. Currency→FRED-series mapping in `quotes/fred.py::CURRENCY_TO_SERIES_ID`.
- `quotes/fx.py::market_cap_in_reported_currency` is the bridge used by every indicator calculator.
- `quotes/inflation.py::get_inflation_adjustment_factors` dispatches: BRL → IPCA, USD → USCPI, everything else → CountryCPIIndex.

**BRL is a cross-currency case too.** It is tempting to treat BRL as a pure *listing* currency needing no conversion — true for a B3 ticker, which is priced and files in BRL. It is false for US-listed ADRs of Brazilian issuers (SID, PBR, VALE, ABEV, BBD, ...), which are priced in USD and file in BRL. BRL was originally excluded from both `sync_fx_rates` and `audit_currencies`, so no USD→BRL rate ever existed, those ADRs could not translate their market cap, and every market-cap indicator came back empty for them (August 2026 fix). When adding a currency exclusion here, exclude only USD — the base of every stored pair.

**A missing translation is never a fallback to the untranslated cap.** `deriveForYears` (frontend) recomputes the ratios for the year slider. It falls back to `marketCap` when `marketCapInReportedCurrency` is absent, which is correct *only* when listing and reported currency match; for a cross-currency ticker an absent translation means the conversion was impossible, and substituting the listing-currency cap divides (say) a USD market cap by BRL earnings, producing a ratio several times too cheap that then sorts to the top of every value screen. The guard is `listingCurrency !== reportedCurrency → null`, which mirrors what the backend already returns.

**Coverage audit:** `python manage.py audit_currencies` lists every (listing, reported) pair, flags reporting currencies missing FX history, and flags currencies missing a FRED series mapping.

**After a currency-coverage change**, stored data needs rebuilding — the screener reads `IndicatorSnapshot`, not a live calculation:

```bash
python manage.py sync_fx_rates                    # write the missing rates
python manage.py backfill_reported_currency       # one FMP call, stamps reported_currency in bulk
# then recompute snapshots + drop derived caches for cross-currency tickers
#   (invalidate_statement_caches per symbol; see quotes/derived_data.py)
```

Note `refresh_indicator_snapshots` skips tickers whose `Ticker.market_cap` is null, but their `IndicatorSnapshot` rows can still hold a market cap and keep serving stale ratios — recompute those from the snapshot's own market cap.

**Multiples-history chart:** when historical FX is unavailable for any year on the chart, falls back to the latest FX rate uniformly and surfaces `currency_warning=true` in the API; the frontend renders a banner explaining the approximation.

Full design rationale, scope, and the bug it fixes: `docs/cross-currency-fix-plan.md`.

## Comparison chart (expanded indicator view)

Clicking the expand button on any indicator card opens a full-window chart for that single indicator. Beyond the larger view it adds three things:

1. **Term slider** — the same `PRAZO/TERM` slider from the page, rendered inside the modal and bound to the page's `years`. Moving it re-derives the series (for rolling indicators like P/L10 the term is the rolling window, so the curve changes, matching the headline number).
2. **Overlay other companies** — a ticker search adds companies to the chart. Each added company's series is built with the *same* math as the primary (`deriveForYears` → `buildChartData` in `frontend/src/components/CompanyMetricsCard.tsx`), fetched on demand via `useComparisonSeries`.
3. **Indicator-aware normalization** — how series are combined depends on the indicator's kind (`frontend/src/utils/indicatorKinds.ts`):

| Kind | Indicators | Overlay behavior |
|---|---|---|
| `currency-abs-level` | current price | Rebased: arbitrary share-price levels and currency units are neutralized by indexing each series to 100 at a common origin. |
| `currency-abs-size` | market cap | Rebased (growth) or FX-converted to a common currency, then rebased. |
| `ratio` | P/L10, P/FCL10, PEG, D/E, current ratio, debt coverage, … | Overlaid raw — already currency-neutral. Optional log scale for outliers. |
| `percent` | earnings/FCF CAGR | Overlaid raw. |

For currency indicators with two or more companies, a scale toggle offers **Absolute** (single-currency only), **Base 100** (rebased in each company's local currency — price *performance*), and **Base 100 · common currency** (FX-converted to the primary company's listing currency before rebasing — *investor return*). Absolute is disabled when the companies span more than one currency, since a shared currency axis there is misleading. The alignment, rebasing, and FX-conversion math lives in `frontend/src/utils/normalizeSeries.ts`.

The common-currency mode reads a historical FX path from a new endpoint. Dates without an FX anchor fall back to the latest rate, and the chart shows a note when that happens.

**API:** `GET /api/fx/series/?from=<ISO>&to=<ISO>[&start=YYYY-MM-DD]` → `{ from, to, rates: [{ date, rate }] }`, where `rate` is units of `to` per 1 unit of `from`, computed via the USD pivot (see [Cross-currency indicators](#cross-currency-indicators)). Public and currency-only — no ticker, no quota.

No new environment variables. To test locally: open a company page, expand any indicator, drag the term slider, and add a peer (for a cross-currency check, overlay a US ticker on a Brazilian one and switch to Base 100 · common currency).

## Ticker search

The header autocomplete hits `GET /api/tickers/search/?q=<query>` and returns up to 8 rows, ranked in buckets:

1. **Exact symbol** — typing `GM` always surfaces General Motors, even when its market cap is NULL and prefix siblings have one.
2. **Symbol prefix** — `MIC` → MICA, MICB, …, largest market cap first, NULLs last.
3. **Display name or alias contains** — how popular companies surface when obscure tickers hog the prefix (`mic` → Microsoft). Aliases cover former names (`General Electric` → GE).
4. **Formal filed name contains** — fills only the slots the buckets above left empty, so legal boilerplate never displaces a real match. This is the safety net for words that the display name drops: `CIA SANEAMENTO DO PARANA - SANEPAR` displays as *Sanepar*, and `saneamento` still finds it.

Display names are derived from the formal name by `format_display_name()` in `backend/quotes/views.py`, which strips legal suffixes (`S.A.`, `S/A`), expands abbreviations (`BCO` → `Banco`), and prefers a short trade name around a dash. The suffix pattern requires a whole-word match · an earlier version also ate ordinary words beginning with those letters, which reduced Sanepar's display name to `CIA` and made it unsearchable.

Results are cached in Redis for 2 minutes per query; the frontend debounces keystrokes by 300ms.

## Peer comparison

The Compare tab on each company page lists up to 10 peer tickers ranked by how close they are to the source company. Ranking uses four tiers of signal, applied in order:

1. **Subsector within the same sector** — companies whose business line maps to the same subsector as the source (e.g. VALE3 and GGBR4 both map to *Mineração e Siderurgia*, while KLBN4 maps to *Papel e Celulose*).
2. **Other subsectors in the same sector** — fills remaining slots when subsector peers aren't enough.
3. **Adjacent sectors** — only considered when the sector itself has too few candidates (see `ADJACENT_SECTORS` in `backend/quotes/views.py`).
4. **Country, then market cap** — within a tier, same-country peers come first; within same-country, larger market cap comes first.

Subsector inference is pattern-based: a per-sector list of regexes in `SUBSECTOR_RULES` (Finance, Non-Energy Minerals, Process Industries, Retail Trade, Transportation, Utilities, etc.) matches against the company name. Unmatched companies fall back to a default subsector label per sector. No schema change — the subsector is derived at query time.

**API:** `GET /api/tickers/<symbol>/peers/`

## Saved lists

A saved list is a named set of companies and a window, opened at
`/{locale}/{TICKER}/{compare}?listId={id}`. The ticker in that path is an
**address, not an owner**: the comparison table lives on the company route, so
a list is served from one of its members, but the list is not about that
company.

Everything that made it look otherwise is gated on the list being active:

| On a company page | On a saved list |
| --- | --- |
| The company header: logo, ticker, currency, rating | `ListHeader` · the list's name, its size, its window |
| The top row is the company, pinned and not removable | Every row is a peer; any row can be removed, the anchor included |
| Dragging another company to the top navigates to *that company's* page | Reordering is plain state and navigates nowhere |
| Metrics / Fundamentals / Charts / Sponds tabs, the revisit banner, the AI analysis, sector peers, share buttons | None of them · a list is its table |
| The window is capped at the company's own `maxYearsAvailable` | The full range (`LIST_MAX_YEARS`), so a short-history anchor cannot cap the list |

`CompareTab` takes the whole ordered set (`tickers`) plus a `pinnedTicker`
that is `null` for a list, and `resolveReorder` is the one place that decides
between "keep it in state" and "hand the page over to the new top company".

## Learning Mode

A toggleable view that attaches a 1–5 color-coded rating to every fundamental indicator on a company page (P/E10, P/FCF10, PEG, P/FCF-PEG, the four leverage ratios, current ratio, debt/avg-earnings, debt/avg-FCF) plus an overall company grade. Designed for newcomers who can't yet calibrate "is debt/equity of 1 good?". Off by default — when off, pages render exactly as before.

**Available to every visitor.** Authenticated users persist the preference server-side via `/api/auth/preferences/`; anonymous visitors persist it locally via the `sponda-learning-mode` localStorage key.

### How it works

1. **Rating engine** — `backend/quotes/ratings.py` defines `RATING_THRESHOLDS` (per-indicator, optional per-sector overrides) and a `BETTER` direction flag (`lower` for valuation/leverage, `higher` for current ratio). Four cuts produce five tiers. `rate_indicator(indicator, value, sector)` is a pure function; `rate_company({...})` returns `{ ratings, overall, methodology_version }`. An overall grade is only emitted when at least 4 indicators rated (`MIN_INDICATORS_FOR_GRADE`).
2. **API surface** — `PE10View` adds a camelCase `ratings` block to the `/api/quote/<ticker>/` response; `ScreenerView` adds a snake_case `ratings` block to each `/api/screener/` row. Sector lookup feeds into the threshold table. Computed at serialization time (microsecond cost), no migration.
3. **Frontend** — `LearningModeContext` (`frontend/src/learning/LearningModeContext.tsx`) reads `useAuth().user.learning_mode_enabled`, exposes `{ enabled, available, setEnabled }`. `setEnabled` PATCHes `/api/auth/preferences/`. `LearningModeToggle` (header pill, hides itself when `available` is false), `RatingChip` (per-indicator), `CompanyGradeCard` (top of metrics tab) all return `null` when learning mode is off.
4. **Pages affected** — `CompanyMetricsCard` (chips + grade card), `ScreenerView` (chips per cell). The `usePE10` `QuoteResult` and `useScreener` `ScreenerRow` types carry the `ratings` block as an optional field.
5. **i18n** — 35 keys per locale, all 7 supported locales (`pt`, `en`, `es`, `zh`, `fr`, `de`, `it`). Tier labels (`learning.tier.1..5`), per-indicator titles + one-line descriptions, toggle copy, grade card copy.
6. **Color tokens** — `--color-rating-1..5` in `frontend/src/styles/global.css`. Chips use a numeral inside a colored block so the signal is not color-only (works under color-blindness and grayscale).

### Tuning thresholds (follow-up work)

The shipped thresholds are placeholders. Edit `RATING_THRESHOLDS` in `backend/quotes/ratings.py` to adjust cuts; add a sector key under any indicator (e.g. `"Utilities": { "direction": "lower", "cuts": [2.0, 3.0, 4.0, 5.0] }`) to override per sector. `INDICATOR_WEIGHTS` is currently equal-weighted; tune for the overall grade. No migration is needed for any of this — changes ship by deploying.

### Local testing

1. Open any `/<locale>/<ticker>` page; the **Learn** pill sits next to the language toggle in the header.
2. Click it. Each rated indicator gains a colored numeral chip; the company header gains an `Avaliação: [N] Tier` summary. Hover any chip to read the criteria for tiers 1–5.
3. Open the screener — every rated cell shows a chip too.
4. Reload the page. Logged-in users persist via `/api/auth/preferences/`; guests persist via the `sponda-learning-mode` localStorage key.

## Indicator Alerts

Signed-in users can save thresholds on any screened indicator per ticker. When an indicator crosses a threshold, they get an email plus an on-screen entry at `/[locale]/notificacoes`.

### UX

- A small bell button sits next to each indicator label on the company page (`AlertButton` in `frontend/src/components/AlertButton.tsx`). Click it to pick a comparison (`≤` or `≥`) and a threshold value.
- Existing alerts for that (ticker, indicator) pair are listed inline so the popover is the single source of truth — no separate "manage alerts" page. Delete an alert with the `×` button.
- The `/notificacoes` page has a **Triggered alerts** section above the revisit reminders; each row links back to the company and can be dismissed (which deletes the alert).

### Data model

`IndicatorAlert` (in `backend/accounts/models.py`) holds `user`, `ticker`, `indicator`, `comparison` (`lte` / `gte`), `threshold` (Decimal), `active`, and `triggered_at`. The unique constraint `(user, ticker, indicator, comparison)` means a user can set both a floor and a ceiling for the same indicator, but not two overlapping alerts. `model.clean()` validates the indicator against `IndicatorAlert.ALLOWED_INDICATORS` — the same 11 fields the screener supports.

### Evaluation loop

`check_indicator_alerts` (daily 07:30 UTC via `sponda-check-alerts.timer`, right after the snapshot refresh):

1. Batch-loads every active alert's latest snapshot in one query.
2. For each alert, compares the indicator value to the threshold using the stored comparison operator (`None` values are skipped — no snapshot means no evaluation).
3. On a **false → true** transition sets `triggered_at = now()` and sends one email per alert. Re-triggers only happen after a `true → false` reset, so users aren't spammed on consecutive runs while the condition holds.
4. Emails use Django's `send_mail` with a plain + HTML body (`_build_alert_email` in `backend/accounts/tasks.py`); the subject includes the ticker, indicator label, and threshold.

### API

| Method | URL | Purpose |
|---|---|---|
| `GET` | `/api/auth/alerts/` | List current user's alerts. Optional `?ticker=PETR4` filter. |
| `POST` | `/api/auth/alerts/` | Create an alert: `{ ticker, indicator, comparison, threshold }`. 400 on duplicates. |
| `PATCH` | `/api/auth/alerts/<id>/` | Update `active`, `threshold`, or `comparison`. |
| `DELETE` | `/api/auth/alerts/<id>/` | Delete. Scoped to owner — other users get 404. |

Tickers are uppercased on write; thresholds are `DecimalField(max_digits=20, decimal_places=6)` so precision matches the snapshot fields. Auth is session-based with CSRF (`frontend/src/utils/csrf.ts::csrfHeaders`).

## Favorites

Signed-up users can favorite companies to pin them on the home page grid.

- **Unverified users** are capped at 20 favorites total, and the home page renders only the first 8.
- **Verified users** (those who confirmed their email) have no cap — they can add unlimited favorites and every favorite shows on the home page grid.

The backend cap lives in `accounts.views.FavoriteListView` (`MAX_FAVORITES = 20`). The home page render logic lives in `getHomepageTickers` in `frontend/src/components/HomepageGrid.tsx`.

### Resending the verification email

Users whose email is not verified see a notice on the account page (`/[locale]/account`) with a "Resend verification email" button. The button calls `POST /api/auth/resend-verification/` (in `accounts.views.ResendVerificationView`), which re-sends the branded verification link via `_send_verification_email`. The endpoint requires an authenticated session and returns 400 if the email is already verified. The UI lives in `EmailVerificationSection` inside `frontend/src/app/[locale]/account/page.tsx`.

## Social (Sponds)

Users can post short messages — **Sponds** — follow each other, mute, block, and reply to threads. The feature lives under `/api/social/` (backend) and `frontend/src/components/social/` (frontend).

### What it does

- **Compose**: 500-char Sponds with optional `$TICKER` tag and `@handle` mentions. Mentions are extracted server-side and trigger notifications.
- **Engage**: like, reply (one-level threads), edit within 5 minutes, soft-delete with thread tombstones. A Spond and its replies render nested inside one box (`SpondThread`). On the permalink page the reply composer is hidden until "Responder" is clicked; in feeds/sidebar replies are collapsed behind a "show replies" toggle that lazy-loads the thread. The composer opens focused, so "Responder" is a single click to typing.
- **Signed-out engagement**: Like and Responder are live controls for signed-out visitors, not disabled ones. Clicking either opens the `AuthModal` login/signup cycle, and `SpondCard` remembers the intent and replays it on success — the like is submitted, or the reply composer opens focused. Where the card has no inline composer (nested replies, profile pages), the replay navigates to `/<locale>/spond/<id>?reply=1`, which the permalink page reads to open its composer focused (`SpondThread startReplying`). Unverified accounts still pass through the existing email-verification gate, which replays the action after verification.
- **Follow graph**: follow public accounts immediately; follow private accounts via approval (pending → accepted). Mute (one-way) hides someone from the muter's feeds. Block (symmetric) hides each side from the other and removes any existing follows.
- **Feeds**: home page shows `Following | Global` tabs; each company page gets a `Sponds` tab with a locked-ticker composer and per-ticker thread.
- **Profile**: every user gets `@handle`, `display_name`, `bio`, `is_private`, with a public profile at `/<locale>/user/<handle>` and a Spond permalink at `/<locale>/spond/<id>`.
- **Identity**: avatars are initials-on-color circles (no uploads in v1). Handles auto-derive from email on signup; users may change once per 30 days.
- **Notifications**: reply / mention / like / follow / follow-request notifications, polled every 60s in a separate bell next to the existing alerts bell.
- **SEO**: anonymous reads work, but `/user/`, `/spond/`, and `/api/social/` are `Disallow`'d in `robots.txt` and rendered with `<meta name="robots" content="noindex,follow">` until moderation matures.

### Rate limits

Limits are intentionally tight — 5× more stringent than typical defaults. With a small user base we'd rather see a 429 than tolerate a runaway script. They live in `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]` in `backend/config/settings/base.py`.

| Action | Per minute | Per hour | Per day |
|---|---|---|---|
| Compose Spond / reply | 4 | 24 | 80 |
| Like / unlike | 12 | 120 | 600 |
| Follow / unfollow | 6 | 20 | 60 |
| Mute / block / unmute / unblock | 8 | 20 | — |
| Profile edits | — | 6 | — |
| Notifications mark-read | 24 | — | — |
| Anonymous reads (per IP) | 60 | — | — |
| Authenticated reads (per user) | 300 | — | — |

Plus three application-level burst guards: a 5-min duplicate-body check, a hard cap of 8 distinct `@handle`s per Spond, and a rolling 1-hour cap of 20 unique follows per user. Handle changes are limited to once per 30 days, enforced in the serializer.

429 responses include `Retry-After` and a JSON body identifying the scope; the frontend shows a localized toast.

### Data model

Backend app `social/`:
- `Spond` — UUID-keyed posts with author, body, optional ticker, optional parent, soft-delete.
- `SpondMention` / `SpondTickerMention` — denormalized lookup tables populated from the body so per-ticker and per-user feeds stay fast.
- `SpondLike` — unique per `(user, spond)`.
- `Follow` — with `state ∈ {pending, accepted}`; CHECK constraint forbids self-follow.
- `Mute` and `Block` — separate one-way relations; blocking auto-removes any existing follows.
- `Notification` — generic FK to Spond/Follow, with verbs `followed`, `follow_requested`, `replied`, `mentioned`, `liked`.

Profile fields added to the existing `accounts.User`: `handle` (unique, nullable), `display_name`, `bio`, `is_private`, `handle_changed_at`. Migration `accounts/0015_social_profile_fields.py` adds the columns and backfills `handle` from each user's email local-part with collision suffixes.

Visibility filtering for every Spond queryset and every profile lookup is centralized in `social/querysets.py::visible_sponds` and `is_user_visible`.

### Local testing

```bash
# Backend
cd backend
python manage.py migrate
python -m pytest tests/test_social_api.py tests/test_social_models.py tests/test_social_visibility.py tests/test_social_mentions.py tests/test_user_profile.py

# Frontend
cd frontend
npm run test
npm run build
```

### Seeding sample data

`python manage.py seed_social` populates the local DB with 5 users (`alice`, `bruno`, `carla`, `diego`, `elena` — the last is private), 7 supported tickers, 15 Sponds with `$TICKER` and `@handle` mentions, 5 replies, ~20 likes, a small follow graph, and one pending follow request. The command is idempotent; pass `--reset` to wipe seeded users (and their cascaded data) before re-seeding, or `--password=<pw>` to override the default `sponda`.

Login emails: `<handle>@seed.sponda.local`. So you can log in as Alice with `alice@seed.sponda.local` / `sponda` and immediately see the home feed populated. Logging in as Elena (private) lets you accept the pending follow request from Bruno.

Two-account smoke test (after `python manage.py runserver`):
1. Sign up two accounts (`alice@x.com`, `bob@x.com`); verify each via the link in the dev console / mailcatcher.
2. As Alice, click the new initials-circle in the header → "Edit profile" → set a handle and bio.
3. Go to a company page (e.g. `/pt/PETR4`) and click the **Sponds** tab; compose `$PETR4 looks cheap @bob`.
4. Open Bob's session in another browser; the home page **Global** tab shows the post; click the bell to see the mention.
5. As Bob, follow Alice. Switch tab to **Following** — Alice's Spond shows.
6. Toggle Alice's account to **private** in the edit-profile modal; have a third user request to follow — accept/reject from the bell.
7. Mute and block flows: from Bob's view, mute Alice (her Sponds disappear from his feed) → unmute → block (Alice's profile and Sponds disappear, and Bob disappears from Alice's view too).

### Environment variables

No new env vars in v1 (avatars are not uploaded; handles are derived from email). When uploaded avatars ship in v2, an `AVATAR_BACKEND` env var will select between local `MEDIA_ROOT` and S3.

## Lookup limits

A freemium gate on company detail pages (`GET /api/quote/<ticker>/`),
counting **distinct companies viewed per day**. Re-viewing a company
already seen that day is always free, so the cap never traps a user on
content they have already opened.

| Visitor | Daily cap | Scope |
|---|---|---|
| Anonymous | `SPONDA_ANON_LOOKUPS_PER_DAY` (20) | Client IP (SHA-256 hashed) |
| Logged in, email **not** verified | `SPONDA_UNVERIFIED_LOOKUPS_PER_DAY` (50) | User |
| Logged in, email verified | Unlimited | — |

**How it works**

- `quotes.lookup_quota` is the single source of truth. `PE10View`
  (enforcement) and `QuotaView` (the `/api/auth/quota/` meter) call it,
  so the number a user sees can never disagree with the one that blocks
  them.
- The cap guards **every** heavy ticker-payload endpoint, not just the
  main quote page. `PE10View`, `MultiplesHistoryView` (`charts`) and
  `FundamentalsView` (`fundamentals`) share the
  `quotes.lookup_enforcement.LookupQuotaEnforcedView` mixin
  (`enforce_lookup_quota` + `record_lookup`). Without this, a client
  could enumerate the whole catalogue through the data sub-endpoints —
  hammering the providers once per ticker — while never tripping the cap
  on the main page. Loading one ticker's tabs stays free: re-counting a
  company already seen today is a no-op, so the multiple endpoints a page
  fires for the **same** ticker don't multiply the cost. This is
  defense-in-depth against per-IP enumeration; a distributed scraper that
  rotates a fresh IP per ticker is an edge problem (Cloudflare WAF rate
  limit on `CF-Connecting-IP` + Bot Fight Mode), not a per-IP-cap one.
- Anonymous scope is per **IP**, resolved via `CF-Connecting-IP` →
  `X-Forwarded-For` → `REMOTE_ADDR` (`quotes.client_ip`) and stored only
  as a salted hash (`LookupLog.ip_hash`). A cleared session cookie no
  longer resets the cap. Those headers are only worth trusting because
  nginx overwrites them from a Cloudflare-gated `$remote_addr`; see
  [Origin trust](#origin-trust-only-cloudflare-gets-to-name-the-visitor).
- Over-cap requests get `429` with `{"code": "lookup_limit", ...}` and
  `Cache-Control: no-store`; no payload is computed and no quota is
  burned.
- **Server-side renders count against the visitor, not against the
  server.** A Server Component fetching from Django opens a fresh
  connection out of the Node process, so without help Django sees
  `127.0.0.1` and no session, and every server-rendered quote on the site
  shares one anonymous bucket of twenty tickers a day. Past the
  twentieth, `/api/quote/*` answers `429` to the renderer and the ticker
  page ships an empty skeleton to browsers and crawlers alike, all day,
  for every ticker but the first twenty. `lib/requestIdentity.ts`
  forwards the visitor's `Cookie`, `CF-Connecting-IP` and
  `X-Forwarded-For` on every server-side call, which puts the lookup back
  on the visitor's own quota. Counting the same ticker twice costs
  nothing (the cap counts distinct companies), so the page's own
  client-side refetch is free.
- **There is a Cache Rule for `/api/quote/*`, and it does nothing.** A
  Cloudflare Cache Rule (`starts_with(http.request.uri.path,
  "/api/quote/") and http.request.method eq "GET"`, cache eligible, edge
  TTL `bypass_by_default`) marks the path cacheable. It has never produced
  a cache hit. Verified 2026-08-26: a `200` for `/api/quote/PETR4/` comes
  back through the edge as `cf-cache-status: DYNAMIC`, meaning Cloudflare
  declined to store it.
  - The reason is `Vary`. The origin answers with `Vary: origin, Cookie`,
    and Cloudflare only caches responses that vary on `Accept-Encoding`.
    Any other `Vary` value makes a response uncacheable no matter what a
    Cache Rule says.
  - `StripSessionFromPublicCacheMiddleware`
    (`backend/config/middleware/public_cache_strip.py`) exists precisely to
    remove `Cookie` from `Vary` on anonymous `Cache-Control: public` GETs
    so this would work. On `/api/quote/*` it is not doing so. That is a
    bug, not a design choice.
  - So the earlier warning in this section, that the path must be kept off
    any Cache Rule because responses vary by IP and quota state, has never
    been tested in production. Its premise is also weaker than it reads: a
    `429` carries `no-store`, so Cloudflare would not store one even if the
    rule worked, and the `200` payload is identical for every caller.
  - The real trade, if the middleware is ever fixed: a cached payload would
    be served to a visitor who is **over** their daily cap, so the ceiling
    goes porous for 300s per ticker. That is probably worth it, since the
    cap exists to protect the BRAPI and FMP budgets and an edge hit spends
    nothing. But `record_lookup` never runs for an edge hit, so `LookupLog`
    would start undercounting demand. Do not read it as traffic; `PageView`
    is the honest counter.
  - Decide one way or the other. Either delete the rule, or fix
    `StripSessionFromPublicCacheMiddleware` and accept the porous cap.
    Leaving an inert rule in place is the worst of the three, because it
    reads as intent that is not happening.
- Frontend: a `429 lookup_limit` throws `LookupLimitError`. Anonymous
  users get the login/signup modal; logged-in-unverified users get the
  email-verification prompt (they already have an account).

## Localized account emails

Welcome and email-verification messages are rendered in the new user's preferred language. The `User.language` field (`accounts.models.User`, one of `pt`, `en`, `es`, `zh`, `fr`, `de`, `it`, default `en`) drives template selection.

At signup the frontend (`AuthModal.tsx` and `[locale]/login/page.tsx`) sends the current UI locale as `language` in the POST body. If the field is missing, `SignupView._parse_accept_language` picks the highest-q supported locale from the `Accept-Language` header, falling back to `en`. Any later verification resend (`/api/auth/resend-verification/`, change-email flow) reuses the value stored on the user.

Templates live under `backend/accounts/templates/emails/`:

- `welcome_base.html` / `verification_base.html` — shared HTML shell with `{% block %}` placeholders for every translatable string.
- `welcome_<lang>.html` / `verification_<lang>.html` — per-locale overrides (`extends` the base, fills blocks).
- `welcome_<lang>.txt` / `verification_<lang>.txt` — plain-text bodies per locale.

Subjects and localized share-link copy live in `accounts/email_subjects.py`. The sender (`accounts.views._send_welcome_email` / `_send_verification_email`) resolves the language via `accounts.languages.resolve_user_language`, renders the matching templates with `render_to_string`, and passes the localized subject.

To add a new locale: register it in `SUPPORTED_LANGUAGES` (`accounts/models.py`), add a row to both subject dicts and `share_strings` in `email_subjects.py`, and create the four template files (`welcome_<lang>.html`, `welcome_<lang>.txt`, `verification_<lang>.html`, `verification_<lang>.txt`).

## Marketing email opt-out

Any bulk send has to carry a working unsubscribe. Gmail and Outlook require RFC 8058 one-click from bulk senders, and a campaign without it gets filtered on reputation no matter how good the content is. Transactional mail is deliberately out of scope: welcome, verification, password reset and indicator alerts keep flowing after an opt-out, and none of them carry the headers.

Opting out flips `User.allow_contact` to `False`. It is the same flag a signed-in user toggles at `/<locale>/account`.

**The token is signed, not stored.** `accounts/unsubscribe.py::generate_unsubscribe_token` signs `{user_id, email}` with `django.core.signing` under the `accounts.unsubscribe` salt. Nothing is written at send time, so there is no row to expire, exhaust, or clean up, and the link keeps working for as long as the address does. Binding the address into the signature means a token stops resolving the moment the account moves to a different email, so whoever inherits the old address cannot opt out the new one.

**GET never unsubscribes anyone.** Spam filters and corporate link scanners fetch every URL in an email; a mutating GET would empty the list before a human read it. `GET /unsubscribe/<token>/` renders a confirmation page and changes nothing. Only `POST` clears the flag, and it is idempotent.

**POST is CSRF-exempt** because the one-click request arrives from the mail provider with no cookie and no session. The signed link is the credential.

| Piece | Where |
|---|---|
| Token, URL and header builders, the view | `backend/accounts/unsubscribe.py` |
| Per-locale page copy (7 languages) | `backend/accounts/unsubscribe_text.py` |
| Page template | `backend/accounts/templates/unsubscribe/page.html` |
| Route, named `unsubscribe` | `backend/config/urls.py` |
| Proxy rule that gets the request to Django | `frontend/src/middleware.ts` |
| Tests | `backend/tests/test_unsubscribe.py`, `frontend/src/middleware.test.ts` |

**Routing.** In production nginx sends everything except `/api/` (see "The API no longer traverses Next") to Next on `:3100`, so `/unsubscribe/` only reaches Django because the Next middleware proxies that prefix, exactly as it does for `/admin/` and `/static/`. Two details there are load-bearing: `/unsubscribe/:path*` is an explicit matcher entry, because a compressed signing token starts with a dot and the catch-all matcher skips any path containing one; and the prefix is handled before the locale logic, which would otherwise redirect `/unsubscribe/<token>/` to `/en/UNSUBSCRIBE/<token>/` and strand the reader on a 404.

The page answers in the recipient's `User.language` and has four states: confirm, done, already opted out, and invalid link (HTTP 404). An unknown locale falls back to `DEFAULT_LANGUAGE` instead of erroring.

**Headers every marketing send must attach.** `build_unsubscribe_headers(user)` returns both. `send_mail` cannot carry custom headers, so use `EmailMultiAlternatives(..., headers=build_unsubscribe_headers(user))`:

```
List-Unsubscribe: <https://sponda.capital/unsubscribe/<token>/>
List-Unsubscribe-Post: List-Unsubscribe=One-Click
```

**Environment variables**

| Variable | Dev default | Prod value | What it does |
|---|---|---|---|
| `UNSUBSCRIBE_BASE_URL` | `http://localhost:8000` | `https://sponda.capital` | Origin for the unsubscribe link. Django renders the page itself, so in dev this points at the API port, not the Next dev server on `:3000`. |

**Local testing**

```bash
cd backend && .venv/bin/python -m pytest tests/test_unsubscribe.py
```

To open the real page, mint a link for an existing user and paste it in a browser:

```bash
cd backend && ./manage.py shell -c \
  "from accounts.models import User; from accounts.unsubscribe import build_unsubscribe_url; print(build_unsubscribe_url(User.objects.first()))"
```

Adding a locale means one row in `UNSUBSCRIBE_COPY` and one in `HTML_LANG`, both in `unsubscribe_text.py`.

### Sending the MCP announcement

`accounts/management/commands/send_mcp_announcement.py` is the first marketing send, and the shape every later campaign should copy.

```bash
./manage.py send_mcp_announcement --to gustavo@poe.ma        # one address, repeatable
./manage.py send_mcp_announcement --all --dry-run            # list who would get it
./manage.py send_mcp_announcement --all                      # the real campaign
```

Four rules are enforced by the command rather than by the operator remembering them:

- **No target, no send.** Without `--to` or `--all` it raises instead of defaulting to everyone. `--to` and `--all` together is also an error.
- **`allow_contact` is honored.** `--all` only selects opted-in users, and `--to` skips an opted-out address with a message rather than mailing it anyway.
- **Every message carries its own unsubscribe**, in the `List-Unsubscribe` headers and in the footer link, both minted per recipient.
- **Failures are loud.** No `fail_silently`. A campaign that silently drops half its recipients is worse than one that stops and says so.

Templates are `emails/mcp_announcement_<lang>.{html,txt}`, subjects live in `MCP_ANNOUNCEMENT_SUBJECTS` (`accounts/email_subjects.py`). `pt` and `en` exist; `mcp_announcement_language()` falls back to `MARKETING_FALLBACK_LANGUAGE` for any other locale, so a German user gets the Portuguese copy rather than a crash. Both a plain-text and an HTML body go out, because HTML-only mail scores worse with every spam filter.

Adding a language means three things together: a subject in `MCP_ANNOUNCEMENT_SUBJECTS`, and both template files. `TestTemplateCoverage` fails if a subject is added without them, since a missing template raises `TemplateDoesNotExist` partway through a campaign, after some recipients have already been mailed.

The endpoint advertised in the copy comes from `assistant.mcp.MCP_PUBLIC_ENDPOINT_URL`, which is absolute on purpose: the announcement must never go out quoting a localhost URL.

The example questions in each edition are not decorative. Every one of them was run against production before it shipped, so a reader who pastes one gets a populated table rather than an empty result.

### Branding copy in more than one language

`accounts/branding.py` holds the Poema track record and the risk disclaimer. Portuguese is the original and the fallback for every locale; English exists alongside it because the marketing list is roughly half English-speaking, and a risk disclaimer nobody can read is not a disclaimer.

| Helper | Returns |
|---|---|
| `poema_performance_line(language)` | The cumulative-return line, translated |
| `poema_disclaimer(language)` | The past-performance warning, translated |

Both fall back to Portuguese for any language with no translation. `tests/test_branding.py` compares the two editions digit by digit, so updating the figure in one language and forgetting the other fails the build.

Note that the **welcome and verification emails still send the Portuguese footer to every locale** — `welcome_base.html` interpolates the constants directly rather than going through these helpers. That predates this change and is worth fixing, but it is a separate change with its own tests.

## Logos

Company logos are served through `GET /api/logos/<symbol>.png`. The resolution chain is designed so that missing logos are recoverable without code changes:

1. **Manual overrides** (`backend/quotes/logo_overrides.py::LOGO_OVERRIDE_URLS`) — highest priority. Add `"<SYMBOL>": "https://..."` for any ticker whose auto-fetched logo is wrong or missing.
2. **Ticker.logo URL** from the database — skipped entirely if the URL is a known provider placeholder (e.g. BRAPI's generic `BRAPI.svg`). Provider placeholders are also stripped at sync time in `brapi.sync_tickers`.
3. **BRAPI direct URL** — `https://icons.brapi.dev/icons/<SYMBOL>.svg`.
4. **Generated fallback SVG** — colored circle with the ticker's first letter. Never written to disk.

Real logos are cached to disk at `LOGO_CACHE_DIR` for 30 days. When all sources return placeholders or fail, the symbol is added to a 24-hour negative cache (in Redis) so subsequent requests don't re-hit the network.

**Commands:**

| Command | What it does |
|---|---|
| `./manage.py warm_logo_cache [--region ...]` | Pre-warm the disk cache for popular tickers. |
| `./manage.py audit_logos [--limit N] [--symbols ...]` | List tickers whose logo resolution ends in the generated fallback — use the output to populate `LOGO_OVERRIDE_URLS`. |

## Markdown pages

Every public page is also served as plain markdown at the same URL with `.md`
appended. `sponda.capital/en/PETR4` renders its numbers client-side, so the HTML
a crawler receives carries a title, some meta tags and no data at all;
`sponda.capital/en/PETR4.md` carries the table.

The suffix convention is the one Anthropic, Stripe and Mintlify docs use, and
that is the point: a model holding an HTML URL can guess the markdown one
without being told. Every company page also advertises it as
`<link rel="alternate" type="text/markdown">`, and `/llms.txt` documents it.

### What is served

| URL | Contents |
|---|---|
| `/{locale}/{TICKER}.md` | Identity, price, market cap, P/E10, P/FCF10, PEG, PFCF-PEG, leverage, liquidity, debt coverage, and the stored `CompanyAnalysis` when there is one. |
| `/{locale}/{TICKER}/charts.md` | The P/E1..P/E15 term structure, with windows the company cannot fill named as such rather than left blank. |
| `/{locale}/{TICKER}/fundamentals.md` | The per-year revenue / net income / FCF / debt / equity table, inflation-adjusted. |
| `/{locale}/{TICKER}/compare.md` | Sector peers with their own indicators. |
| `/{locale}/screener.md` | The indicator glossary and the screener query API. Every company page links here instead of repeating twenty definitions across 23,000 documents. |
| `/{locale}.md` | What Sponda measures. |
| `/llms.txt` | Generated, not static: what Sponda is, the URL conventions, the indicator list, and how to read data at volume. |
| `blog.sponda.capital/{slug}/index.md` | Each post's own source, shortcodes expanded. |

All seven locales, labels drawn from `frontend/src/i18n/locales/*.ts`. Tab slugs
are localized the same way the HTML routes are, so `/pt/PETR4/graficos.md` works
and `/en/PETR4/graficos.md` is a 404. A URL with no locale prefix, such as
`/PETR4.md`, is served in English rather than redirected: a crawler that guessed
the URL should not pay for a hop.

### Why it is not built on `/api/quote/`

This is the load-bearing decision. `PE10View` syncs statements and fetches a
live quote from BRAPI or FMP on a cache miss, which is exactly why it sits
behind `LookupQuotaEnforcedView` and its cap of `SPONDA_ANON_LOOKUPS_PER_DAY`
(20) distinct companies per IP per day. Pointing 23,000 crawlable pages at it
would exhaust the monthly provider budget and then start answering 429s.

So the markdown pages read from `IndicatorSnapshot` instead, through a new
endpoint that is deliberately **not** quota-enforced because it can never reach
a provider:

```
GET /api/tickers/{SYMBOL}/indicators/            # one company
GET /api/tickers/{SYMBOL}/indicators/?symbols=A,B,C   # bulk, for the peer table
GET /api/tickers/{SYMBOL}/indicators/?analysis=1      # + the stored analysis, or null
GET /api/tickers/{SYMBOL}/indicators/?fundamentals=1  # + the per-year table
```

Two indexed reads and no provider call, so a full page render is cheap enough
to serve on demand with no pre-generation and no new scheduled job. The
accessors live in `backend/quotes/company_snapshot.py`, and
`assistant.tools.execute_get_company` (the `get_company` MCP tool) was rewired
to call the same functions so the two surfaces cannot drift.

`?analysis=1` returns `200` with a null analysis rather than `404` on purpose:
most companies have none, and a 404 is not storable in the Next data cache, so
a 404 here would mean one Django round trip per markdown page view for the
whole catalogue, forever.

The invariant is pinned by
`backend/tests/test_company_snapshot.py::TestNoProviderCalls`, which asserts
that no function in `quotes.providers` is called on any path. Measured on a
cold cache: 150 markdown page renders (50 companies × 3 locales) produced 50
Django requests, zero `/api/quote/` calls, and zero `LookupLog` rows.

### How it fits together

```
GET /en/PETR4.md
  -> middleware.ts rewrites to /md/en/PETR4
  -> src/app/md/[...slug]/route.ts
       -> GET /api/tickers/PETR4/indicators/?analysis=1   (Next data cache, 15 min)
  -> src/lib/company-markdown.ts renders
  -> text/markdown; charset=utf-8
     Cache-Control: public, max-age=900, s-maxage=86400, stale-while-revalidate=604800
```

The rewrite lives in `frontend/src/middleware.ts` rather than in a
`next.config.ts` rewrite: all the other URL shaping is there, it has a test
harness, and path-to-regexp's treatment of a `.md` literal after a greedy
`:param` is the kind of thing that fails silently in production. The middleware
matcher needs an explicit `.md` entry because the catch-all excludes any path
containing a dot. A `.md` URL we do not publish, such as `/en/login.md`, is
answered with a `404` there rather than falling through to the ticker-case rule,
which would redirect it to `/en/LOGIN.MD` and get a 200 HTML shell.

Because the indicators URL does not vary by locale, all seven locales of one
company share a single Django request per 15-minute window.

### Telling machines the data is here

Four signals, cheapest for a client to find first:

| Signal | Where | Who sees it |
|---|---|---|
| `Link:` response header | `middleware.ts`, on every page with a twin | A crawler doing `HEAD`, which never parses a body |
| `<link rel="alternate" type="text/markdown">` | `generateTickerMetadata`, plus the `for-ai` page | Anything parsing the document head |
| `Dataset.distribution` in JSON-LD | `lib/metadata.ts` | Anything already reading our structured data. `distribution` is schema.org's own vocabulary for "the machine-readable version lives here", so this needs no convention of ours |
| `/llms.txt` and `/{locale}/for-ai` | Generated routes | A human wiring Sponda into a program, and whatever they point at it |

`/{locale}/for-ai` and its markdown twin both render from
`frontend/src/lib/ai-access-copy.ts`. A page whose subject is machine-readable
access would be a poor advertisement for itself if its two versions disagreed.
It is English only on purpose: the audience is whoever is writing the client,
and every identifier on the page is English regardless of their locale.

`llms.txt` derives its company count from `/api/tickers/symbols/` rather than
stating one. The first version said "roughly 23,000 listed companies" and was
wrong by nearly 5,000, which is what a generated file that hand-types its one
important number gets you.

**Still to do, outside the code.** Discovery is a distribution problem, and
the in-page signals above are the cheap half:

- Resubmit `sitemap.xml` in Google Search Console and Bing Webmaster Tools.
  It changed shape from ~1,240 URLs to an index over every company.
- List the MCP server in the registries. That channel puts Sponda inside the
  assistant rather than hoping the assistant crawls us, and it is the highest
  leverage of anything here.
- Submit the site in Bing Webmaster Tools. The one-click import from Google
  Search Console handles verification and pulls the sitemap across. See
  "IndexNow" above for the faster channel once that is done.
- `PerplexityBot` was answering `403` through Cloudflare on 2026-08-26 while
  GPTBot, ClaudeBot, Claude-User and Googlebot all got `200`. Same IP, same
  request, only the User-Agent differed. `docs/seo-checklist.md` claims none
  are blocked. Check the bot settings.

### IndexNow

Pushes changed URLs to Bing, DuckDuckGo, Yandex, Seznam and Naver instead of
waiting to be crawled. Google does not participate, which matters less than it
sounds: Bing's index feeds DuckDuckGo and Microsoft Copilot, so this is a
direct route to the assistants the markdown pages were built for.

```bash
./manage.py submit_indexnow --dry-run       # what would be sent
./manage.py submit_indexnow                 # send it
./manage.py submit_indexnow --resubmit      # include companies already sent
```

Runs daily at 07:00 from `sponda-indexnow.timer`, after the 06:00 ticker
refresh, so a company onboarded overnight is pushed the same morning. A run
with nothing new is a no-op.

**One submission per company, on purpose.** Prices move every fifteen minutes,
and resubmitting 17,000 companies on every tick is how a host gets
deprioritised for abuse. A price tick is not a content change.
`IndexNowSubmission` records what has been sent; `--resubmit` overrides it
after something that genuinely rewrites the pages.

**What gets submitted:** the HTML company page, per sitemap locale, for
companies that have indicator data. Not the markdown twins, which are for
direct readers rather than search results, and not the tab pages, which are
detail views of a page already being submitted.

| Setting | Purpose |
|---|---|
| `INDEXNOW_KEY` | 8 to 128 characters of `a-z A-Z 0-9 -`. Must equal the name and the contents of the key file. |

**The key is public by design.** It is served at
`https://sponda.capital/<key>.txt` from `frontend/public/`, and its only power
is to submit URLs for a host you already control. There is nothing to keep
secret and no registration step: ownership is proved by the file, not by
anything in Bing Webmaster Tools.

**The failure this guards against is silence.** A key file that drifts from
`INDEXNOW_KEY` makes every submission a `403` and nothing anywhere says so.
`submit_indexnow` fetches the live key file and compares before sending, so
the drift is a `CommandError` rather than a quiet nothing. A test also pins
that the committed file is named after its own contents, which catches it in
CI for free.

**Rotating the key:** add the new file, deploy, change `INDEXNOW_KEY`, then
delete the old file. In that order, or the pre-flight check will refuse.

### Setup: the Cloudflare Cache Rule

`.md` is **not** in Cloudflare's default cacheable-extension list. `/og/*.png`
is edge-cached today only because `.png` is on that list. Without a rule, every
markdown request reaches the 2-core origin.

In the Cloudflare dashboard, Caching → Cache Rules, add:

| Field | Value |
|---|---|
| Match | `ends_with(http.request.uri.path, ".md") and not starts_with(http.request.uri.path, "/api/")` |
| Cache eligibility | Eligible for cache |
| Edge TTL | Use cache-control header from origin |

Note that Cloudflare rewrites `max-age` to 4 hours on cacheable responses.
`verify_edge_cache` now carries three `.md` canaries (`/en.md`,
`/pt/screener.md`, `/en/AAPL.md`) alongside the Open Graph ones, so a deploy
that breaks the rewrite is caught before anyone notices. Two of the three
cannot 404 on a data gap, deliberately: the markdown route 404s a company with
no `IndicatorSnapshot` row, so a delisted canary ticker would fail the deploy
gate for a reason that is not a cache problem.

Blog markdown is static, served by nginx from `blog/public/`. It needs
`default_type text/markdown` in a `location ~* \.md$` block, which
`nginx/blog.sponda.capital.conf` now has. A `types` block would collide with
the `mime.types` already included at the http level; because `.md` has no entry
there, naming the default type is enough.

## Blog

The blog at [blog.sponda.capital](https://blog.sponda.capital) is a [Hugo](https://gohugo.io/) static site living in `blog/` in this repo. It serves flat HTML from nginx — no runtime, no database, no JavaScript.

### Writing a post

```bash
cd blog
hugo new content/posts/2026-04-15-my-post.md
```

Frontmatter supports `tags`, `categories`, and an explicit `slug` (recommended when the title has accents):

```yaml
---
title: "Exemplo"
slug: "exemplo"
date: 2026-04-15
tags: ["petrobras", "dividendos"]
categories: ["análise"]
---

Markdown goes here. YouTube embeds use Hugo's built-in shortcode:

{{< youtube dQw4w9WgXcQ >}}
```

Commit and push to `main`; the deploy workflow builds the site on the server.

### Local preview

```bash
cd blog
hugo server
# open http://localhost:1313/
```

### Layout

- `blog/content/posts/` · Markdown posts.
- `blog/layouts/` · custom DF-minimal HTML templates (no theme dependency).
- `blog/assets/css/main.css` · site CSS (fingerprinted and minified at build).
- `blog/static/` · favicon and fonts, copied verbatim to the output.
- `blog/hugo.toml` · site config.
- `blog/layouts/_default/single.md` · the markdown twin of a post, built alongside `index.html`.
- `blog/layouts/shortcodes/youtube.md` · renders the embed as a plain URL for markdown readers.

Tags and categories auto-generate index pages at `/tags/*` and `/categories/*`. RSS feed is auto-generated at `/index.xml`.

Every post is also written out as plain markdown at `{slug}/index.md`, via the
`Markdown` output format in `blog/hugo.toml`. The template uses
`.RenderShortcodes`, not `.RawContent`, so a reader gets the prose as written
with a real URL where the video embed was instead of a literal shortcode tag.

### One-time server setup

Before `blog.sponda.capital` is reachable, the droplet needs:

1. DNS: `A` record `blog.sponda.capital → 159.203.108.19`.
2. `certbot --nginx -d blog.sponda.capital` (after DNS propagates).
3. `ln -sf /etc/nginx/sites-available/blog.sponda.capital.conf /etc/nginx/sites-enabled/`.
4. `nginx -t && systemctl reload nginx`.

Hugo itself is auto-installed by the deploy workflow if missing — no manual `apt install` needed.

Every subsequent `git push` to `main` rebuilds and publishes automatically.

## Performance

### Database

- **Trigram indexes** (pg_trgm) on `Ticker.display_name`, `name` and `symbol` for sub-millisecond ILIKE search across 23K+ tickers
- **Composite indexes** on `CompanyAnalysis(ticker, -generated_at)`, `LookupLog(user, timestamp)`, `LookupLog(session_key, timestamp)`
- **PostgreSQL tuning** for SSD + 2 GB RAM: `shared_buffers=512MB`, `work_mem=8MB`, `random_page_cost=1.1`
- **pg_stat_statements** enabled for query performance monitoring

### Query counts that must not grow with the data

Three endpoints were doing per-row work that Sentry caught as N+1s. Each fix is
pinned by a test that fails if the cost starts scaling again, because that is
the only property worth asserting: adding rows must not add queries.

| Endpoint | Was | Now |
|---|---|---|
| `/api/social/feed/global/` | 10 + 4 per Spond (110 for a 25-row page) | 10, flat |
| `/api/quote/{ticker}/multiples-history/` | 2 per year (64 for 30 years) | 4, flat |
| `/api/quote/{ticker}/fundamentals/` | 1 per year | flat |

**The social feed** had `_annotate_sponds` in place already, and the serializer
was throwing the annotations away four different ways:

- `get_like_count` and `get_reply_count` read the annotation through
  `getattr(spond, "annotated_like_count", spond.likes.count())`. Python
  evaluates arguments before the call, so the fallback COUNT ran on every row
  even though its result was discarded in favour of the annotation. This is the
  trap to remember: a `getattr` default that is a query is a query.
- `get_viewer_has_liked` ran an `EXISTS` per row. It now reads an
  `annotated_viewer_has_liked` annotation, which is why `_annotate_sponds` takes
  the viewer.
- `get_handle_mentions` called `.select_related()` on the related manager, which
  builds a fresh queryset and ignores the `prefetch_related` the view had
  already paid for. Only `.all()` reads the prefetch cache.

**The FX translation** behind multiples history and the fundamentals table
resolved one year at a time, and multiples history did it twice over (once per
multiple). `quotes.fx.get_fx_rates_for_dates` loads each non-USD leg once and
resolves every date against it with `bisect`, so the cost is one query per leg
regardless of how many years a company has. `fx_series` uses it too, where the
old loop was one query per anchor date.

### Caching (Redis)

Three-layer caching strategy eliminates redundant external API calls:

**Layer 1 · Provider cache** (in `providers.py`): raw external API responses (BRAPI/FMP) are cached at the routing layer, so multiple views that need the same data (e.g. `fetch_quote`, `fetch_historical_prices`) share a single external call.

| Provider call | TTL |
|---|---|
| `fetch_quote` | 15 min |
| `fetch_historical_prices` | 1 hour |
| `fetch_dividends` | 1 hour |

**Layer 2 · View cache**: computed results for each API endpoint.

| Endpoint | TTL | Cache key | What it avoids |
|---|---|---|---|
| Ticker list (27K rows) | 1 hour | `ticker_list` | Full table scan on every page load |
| Search results | 2 min | `search:<md5>` | Trigram query + sorting per keystroke |
| PE10 metrics | 24 hours | `pe10:<T>` | 6+ DB queries + external API call + inflation adjustment |
| Fundamentals | 24 hours | `fundamentals:<T>` | All balance sheets, earnings, cash flows + IPCA table + external API |
| Multiples history | 24 hours | `multiples_history:<T>` | 2 sequential external API calls (was 8s uncached) |

**Layer 3 · Cache warming**: `python manage.py warm_cache` pre-populates all three endpoints for the top 50 most-queried tickers. Run every 4 hours via cron so popular tickers are always served from cache.

### Invalidation on statement writes

The bottom three entries above are computed from quarterly statements, so a 24 hour TTL used to mean a newly written quarter stayed invisible for a day. `quotes/derived_data.py` closes that: every path that writes statements calls it, and it recomputes the screener's `IndicatorSnapshot` and then drops the three cached payloads.

| Writer | Calls | Why |
|---|---|---|
| `quotes.tasks.refresh_provider_data` (Celery) | `refresh_derived_data` | Stale-while-revalidate cannot revalidate anything if the payload stays cached |
| `seed_quarter_from_cvm` | `refresh_derived_data` | A seeded quarter is useless behind a day-old payload |
| `refresh_snapshot_fundamentals` (weekly) | `invalidate_statement_caches` | It already recomputed the snapshot from a fresh quote |
| `_ensure_fresh_data` cold path | `invalidate_statement_caches` | Caches only · ten years of arithmetic does not belong on a request thread |

Snapshot first, caches second. A request arriving in the gap either hits a cache that is still warm or rebuilds from a snapshot that is already correct; the reverse order would let it repopulate the cache from a snapshot that has not caught up.

Company metadata (`ticker_detail_<T>`) and peer lists (`ticker_peers_<T>`) are deliberately **not** invalidated · they hold names, sectors and logos, none of which a filing changes.

### Edge cache TTL for statement-derived endpoints

With the server-side caches dropped on write, the `Cache-Control` header became the only remaining staleness between a filing and the page. It was `max-age=3600`, which put a one hour floor under how fresh the site could ever be no matter how fast ingestion got. `/api/quote/<T>/`, `/api/quote/<T>/fundamentals/` and `/api/quote/<T>/multiples-history/` now send `public, max-age=300`.

Two measurements made that safe:

- **Quota is unaffected.** `lookup_quota` counts *distinct tickers per day*, not requests, so extra origin hits cannot exhaust an allowance. Repeat views of the same ticker add duplicate `LookupLog` rows and nothing else.
- **Load is negligible.** Origin traffic for these three endpoints is ~48 requests/hour. Even the theoretical 12x worst case stays well under one request per second, and each is a Redis read.

Sub-minute freshness would need a Cloudflare purge on write. The credentials for that now exist (see "Cloudflare cache purge" below); the purge-on-write call itself is not wired up.

#### Cloudflare cache purge

`/opt/sponda/.env` holds `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ZONE_ID` (added 2026-08-17). The token is scoped to exactly one permission, `Zone · Cache Purge · Purge` on the `sponda.capital` zone, so a leaked copy can flush caches and nothing else. It is read by the services through the existing systemd `EnvironmentFile`, and the deploy script runs on the box, so anything that needs to purge can source it directly.

```bash
set -a; . /opt/sponda/.env; set +a
curl -sS -X POST "https://api.cloudflare.com/client/v4/zones/$CLOUDFLARE_ZONE_ID/purge_cache" \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"files":["https://sponda.capital/og/pt/VULC3.png"]}'
```

Purge **by URL** works on every Cloudflare plan, up to 30 URLs per call. Purge by prefix, hostname, or cache tag is Enterprise only, so "drop everything under `/og/`" is not available. `{"purge_everything": true}` works on all plans but dumps the entire edge cache and sends every subsequent request to the origin, so keep it out of routine deploys.

##### Deploy edge gate

The deploy's existing health check polls `http://127.0.0.1:3100/` and rolls `.next` back if the frontend won't come up. It cannot see a stale edge, because it never crosses Cloudflare. `python manage.py verify_edge_cache` runs last in the deploy script and closes that gap:

1. Fetch each canary in `backend/quotes/management/commands/verify_edge_cache.py` through Cloudflare and compare the content-type (a non-200 or a transport error counts as a mismatch).
2. Purge anything that disagrees, using the credentials above.
3. Re-check. Exit non-zero only if a URL is *still* wrong, which means the problem was never the cache.

The canary list is deliberately tiny: one rendered card per URL shape and one static file, i.e. one per *kind* of asset whose route could change hands, not one per asset. It is a tripwire, not coverage. The card canaries use fixed tickers, which is safe because the route renders a card for unknown symbols too, so a delisting cannot make the check flaky.

Run it by hand any time: `cd /opt/sponda/backend && python manage.py verify_edge_cache`.

**Why this matters beyond convenience.** Cloudflare rewrites `max-age` to 14400 (4h) on cacheable responses. Any URL fetched *before* a deploy keeps serving its pre-deploy body for four hours afterwards, wrong content-type included, and CF ignores client `Cache-Control: no-cache`. That is exactly how a `/og/` path ended up serving HTML with a `200` to crawlers after the card route shipped. When a deploy changes what a URL returns, purge that URL or verify against the origin directly (`ssh root@poe.ma "curl http://127.0.0.1:3100<path>"`), because the edge will lie to you for hours.

The cache keys are defined once in `derived_data.py` and imported by the views, `warm_cache`, and the invalidator. An invalidator that clears a key nobody sets fails silently, which is the worst way for this to break, so the shared definition is load-bearing rather than tidiness.

### Home page fanout (May 2026 rewrite)

The home page renders ~30 tickers (favorites + saved lists). Before this rewrite each visit fired ~60 parallel HTTP requests (PE10 + Fundamentals × ticker), and every request whose data was older than 24h paid for ~3 sequential provider syncs inside the user's request thread. End result: the first paint waited on a long tail of cold-cache calls, and "warming the cache" took ages.

The current architecture, in the order each layer fires:

1. **Server-rendered shell** — `app/[locale]/page.tsx` is an async Server Component (`force-dynamic`). It forwards the user's session cookie to Django, prefetches favorites + saved lists + the batch quote endpoint, and dehydrates the React Query cache into a `<HydrationBoundary>`. The browser receives populated cards in the first byte; no spinner.
2. **`POST /api/quotes/batch/`** — one request returns every ticker the home page needs. Server fans out internally over a `ThreadPoolExecutor`. Replaces the 30-way client-side fanout. Capped at 100 tickers per request. Defined in `quotes/views.py::BatchQuotesView`; consumed via `useQuotesBatch`.
3. **Stale-while-revalidate refresh** — `_ensure_fresh_data` returns immediately when stale data exists and enqueues `quotes.tasks.refresh_provider_data` (Celery) to re-pull from BRAPI/FMP in the background. Only outright cold tickers pay the synchronous provider cost.
4. **Persisted React Query cache** — `@tanstack/react-query-persist-client` mirrors the cache to `localStorage` with a 24h `maxAge`. Returning visitors paint from disk instantly while a soft revalidation runs in the background.
5. **Cache warming, favorites-aware** — `python manage.py warm_cache` now sources tickers from every active user's favorites + saved lists (in addition to LookupLog popularity), runs across 8 worker threads, and skips tickers whose `pe10:<T>` cache is already warm. The 0.5s `time.sleep` per ticker is gone.
6. **Provider circuit breakers + tight timeouts** — every BRAPI/FMP/FRED call goes through `quotes.circuit_breaker.CircuitBreaker` with `(connect, read) = (3, 8)` timeouts. After N consecutive failures the breaker opens for ~60s, short-circuiting subsequent calls instead of pinning a worker for 30s on each one.
7. **`Cache-Control`** so repeat-tab visits skip the round-trip entirely. The batch endpoint keeps `public, max-age=3600` (it is a POST, so no edge caches it and the header only governs the client's own reuse). The three statement-derived GETs use `public, max-age=300` · see below. Logos are `max-age=31536000, stale-while-revalidate=604800` since they rotate at most once a year.
8. **DB connection pooling** — `CONN_MAX_AGE=600` + `CONN_HEALTH_CHECKS=True` in `production.py` so 30 parallel batch workers reuse the same pool of warm Postgres connections.
9. **Redis pool** — `CONNECTION_POOL_KWARGS={"max_connections": 50}` on the cache backend, sized for the peak fanout.
10. **`LookupLog(ticker, timestamp)` index** — added because `warm_cache` filters by ticker + recent timestamp on every run.

### Real-user monitoring

The frontend Sentry init (`instrumentation-client.ts`) now uses `browserTracingIntegration({ enableInp: true, enableLongAnimationFrame: true })`. Web Vitals (LCP / INP / CLS / FCP / TTFB) ship automatically; INP replaced FID as the responsiveness signal in March 2024 and is the most useful number on this page. `tracesSampler` keeps the home page and company-detail routes at 1.0 sampling and drops everything else to 0.2 to keep quota in check. `tracePropagationTargets` is wired so frontend transactions stitch to backend spans on the Sentry timeline.

Backend custom spans (`sentry_sdk.start_span(op="db.calc", description=...)`) now wrap each PE10 sub-step (`pe10`, `pfcf10`, `leverage`, `peg`, `pfcf_peg`) plus the `_ensure_fresh_data` and `fetch_quote` calls. A `Server-Timing` middleware (`config.middleware.server_timing.ServerTimingMiddleware`) emits per-request `app`, `cache hit/miss`, and `calc` marks so DevTools and Sentry's Resource Timing capture both surface backend wall-clock without bespoke client code.

#### Configuration

| Variable | Default | What it does |
|---|---|---|
| `SENTRY_TRACES_SAMPLE_RATE` | `1.0` (dev), set as needed in prod | Backend Django/Celery span sampling rate. |
| `NEXT_PUBLIC_SENTRY_DSN` | unset | Enables frontend Sentry. When unset, the SDK is a no-op. |
| `NEXT_PUBLIC_SENTRY_ENVIRONMENT` | `development` | Sentry environment tag. |
| `NEXT_PUBLIC_SENTRY_RELEASE` | unset | Optional release tag (commit SHA in production). |
| `DJANGO_API_URL` | `http://localhost:8710` | Used by the Next.js Server Component shell to prefetch from Django. Already used by `middleware.ts` for the `/api/*` proxy. |

#### Local testing

1. **Server-rendered home page** — `make backend && make frontend`, then visit `http://localhost:5174/`. View source: cards should be present in the initial HTML, not just a `<div id="__next">` placeholder.
2. **Batch endpoint** — `curl -sX POST http://localhost:8710/api/quotes/batch/ -H 'Content-Type: application/json' -d '{"tickers": ["PETR4", "VALE3"]}' | jq '.results | keys'`. Server-Timing header on the response shows `app;dur=...`, `cache;dur=...;desc="hit|miss"`, and `calc;dur=...`.
3. **Async refresh** — start a Celery worker (`celery -A config worker -l info`) and re-hit `/api/quote/PETR4/` after manually backdating its `QuarterlyEarnings.fetched_at` by 48h. The view returns immediately; the worker logs `refresh_provider_data` running.
4. **Warm cache** — `python manage.py warm_cache --limit=50 --workers=8`. Output reports cached / failed / skipped-already-warm counts.

### Frontend

- **Search debounce** at 300ms to reduce API calls during typing
- **Dynamic imports** via `next/dynamic` for CompanyMetricsCard, MultiplesChart (Recharts), CompareTab, FundamentalsTab, and CompanyAnalysis. Recharts (~100KB) only loads when the Charts tab is opened.
- **Prefetch on hover**: hovering over Fundamentos or Graficos tabs triggers `queryClient.prefetchQuery()`, so data is ready before the user clicks
- **Self-hosted Satoshi font**: eliminates the 1.15s Fontshare external request
- **30-minute staleTime** on React Query hooks; SSR revalidation at 1 hour
- **Lazy-loaded images** on all company logos; footer logo served via Next.js `<Image>` with WebP optimization
- **useMemo** on frequently recomputed derived state (excludeSet, sectorPeerLinks)

### International SEO

Locale-prefixed URLs serve region-specific metadata to search engines across all 7 supported locales (`pt`, `en`, `es`, `zh`, `fr`, `de`, `it`):

- `/pt/PETR4/fundamentos` · Portuguese metadata, `<html lang="pt-BR">`, OG locale `pt_BR`
- `/en/PETR4/fundamentals` · English metadata, `<html lang="en">`, OG locale `en_US`
- `/fr/PETR4/fondamentaux`, `/de/PETR4/fundamentaldaten`, etc. follow the same shape
- Bare URLs (`/PETR4`) 302-redirect to the locale-prefixed version based on `sponda-lang` cookie, then `Accept-Language`
- Every page includes `<link rel="alternate" hreflang>` cross-links between the **indexable** locales plus `x-default` (English)
- Tab URL paths are localized per locale (see `CANONICAL_TO_LOCALE_SLUG` in `frontend/src/middleware.ts`)

#### Noindex locales

Some locales are served but excluded from search indexing. `NOINDEX_LOCALES` in `frontend/src/lib/i18n-config.ts` is the single source of truth; `zh` is currently in it (its traffic was overwhelmingly automated scraping, not a real audience — see the June 2026 scraper incident). The helpers built on it:

- `robotsForLocale(locale)` → `"noindex, follow"` for noindex locales, `"index, follow"` otherwise. Used by the locale layout's `generateMetadata` (`frontend/src/app/[locale]/layout.tsx`), so it cascades to every page under that locale, including ticker pages.
- `INDEXABLE_LOCALES` (every supported locale minus the noindex set) drives the hreflang alternates in both the layout and the sitemap (`frontend/src/lib/sitemap.ts`), so a noindexed locale is never advertised as a crawlable alternate.

`noindex` only affects compliant search engines — it does not stop scrapers (they ignore robots directives). To add or remove a noindex locale, edit `NOINDEX_LOCALES` and the unit tests in `frontend/src/lib/i18n-config.test.ts`.

#### OG images

There are two kinds: a rendered card per company, and a static JPEG for everything else.

##### Per-company cards · `/og/<locale>/<TICKER>.png`

Every company page advertises its own image, rendered on demand by `frontend/src/app/og/[locale]/[ticker]/route.tsx` using `ImageResponse` from `next/og`. The card shows the company name, ticker, translated sector, the four headline indicators, and the locale's tagline:

```
GET /og/pt/VULC3.png   → 1200×630 PNG, ~43 KB
GET /og/en/AAPL.png    → the same card in English
```

- **Data.** `fetchOgCardData(ticker)` in `frontend/src/lib/og-card.ts` hits `/api/tickers/<t>/` and `/api/quote/<t>/` in parallel, each with `revalidate: 3600`. Neither is allowed to reject: a card with a company name and no numbers still beats a broken image, and a ticker the API has never heard of still gets a branded card with `N/A` in every slot.
- **Indicator labels come from the API, not from us.** The quote endpoint returns `pe10Label` / `pfcf10Label`, which say `PE15` or `PE20` when that much history exists. The card prints whatever window was actually used.
- **Formatting is locale-aware** via the existing `formatNumber`, so `/og/pt/` shows `22,8` and `/og/en/` shows `22.8`.
- **`zh` renders its wording in English.** The card is drawn by satori with the Geist Regular face bundled inside `next/og`, which covers Latin only; Chinese would come out as tofu boxes. `ogCardTextLocale()` owns that fallback. Adding real CJK means shipping a CJK font file and passing it to `ImageResponse` via `fonts`.
- **Only `<TICKER>.png` is served.** `tickerFromOgImageParam` requires the extension and validates the symbol, so one card has exactly one URL — which matters because social networks key their image caches by URL. Anything else 404s.
- **Caching.** `public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800`. Cold render is ~500 ms, warm ~20 ms.
- **Routing.** `src/middleware.ts` lets `/og/` through untouched. It used to proxy `/og/` to Django, which has no routes there — its catch-all answered with the legacy SPA shell, i.e. HTML with a `200` to a crawler asking for an image.

##### Static fallback · `frontend/public/images/`

- `sponda-og-v2.jpg` · Portuguese tagline, used for `/pt/*` URLs
- `sponda-og-en-v2.jpg` · English tagline, used for every other locale

Used by pages with no single company to render (homepage, screener). `getOgImageUrl(locale)` selects the image and `buildOgImageDescriptor(locale)` wraps it with width, height, MIME type and alt text; `buildTickerOgImageDescriptor(locale, ticker, name)` is the per-company equivalent. All live in `frontend/src/lib/metadata.ts`.

**Why the `-v2` suffix.** X (Twitter) rendered every sponda.capital card with the correct title and description but no image, while Twitterbot fetched the unsuffixed image roughly 100 times a day — about seven times more often than it crawled the pages themselves. A crawler that ingested the image successfully would not re-fetch it that hard, so the entry in X's image cache was stuck in a failed state. Everything on our side verified clean (HTTP 200 in ~210 ms, `image/jpeg`, baseline JPEG, 1200×630, ~57 KB, absolute HTTPS URL, allowed by `robots.txt`), and X exposes no way to purge its cache, so the only lever is a new URL. The `-v2` files are byte-distinct copies of the originals (a JPEG `COM` comment segment inserted after `APP0`; pixels untouched) so the new URL cannot be content-deduplicated back onto the stuck entry. The unsuffixed files stay in `public/images/` so previews already cached by other networks keep resolving.

Per-company cards make that failure mode survivable rather than fatal: with one image URL per company, a single stuck cache entry can no longer take every preview on the domain down with it.

X caches a card per page URL for about seven days, so an already-shared link keeps its old imageless card. To verify a fix, share a URL X has not seen before (append a throwaway query string, e.g. `?v=2`).

**Testing a card locally.** `npm run build && DJANGO_API_URL=https://sponda.capital npx next start -p 3199`, then open `http://localhost:3199/og/pt/VULC3.png`. Pointing `DJANGO_API_URL` at production is the quickest way to render against real numbers.

#### Sitemaps

A sitemap **index** at `/sitemap.xml`, pointing at paginated children under
`/sitemaps/`. Every entry carries `xhtml:link rel="alternate" hreflang="..."` alternates
across the indexable locales (noindex locales such as `zh` are omitted from
the alternates, see "Noindex locales" above).

| URL | Contents |
|---|---|
| `/sitemap.xml` | The index. Lists `pages.xml` and one `companies-{n}.xml` per chunk |
| `/sitemaps/pages.xml` | Home and screener, per sitemap locale |
| `/sitemaps/companies-{n}.xml` | One slice of the universe: company root plus the charts, fundamentals and compare tabs |

Generated by `frontend/src/app/sitemap.xml/route.ts` and
`frontend/src/app/sitemaps/[file]/route.ts`, both rendering through
`frontend/src/lib/sitemap.ts`. Symbols come from
`GET /api/tickers/symbols/`, which returns strings and nothing else, about
150KB for the whole catalogue.

**What this replaced, and why.** The old `frontend/src/app/sitemap.ts`
enumerated `CURATED_TICKERS`, roughly 155 hand-picked symbols across two
locales: **under 1% of the catalogue**. Django's `SitemapView` did enumerate
everything, but built 600k `<url>` entries in one uncompressed document,
past the 50,000-URL protocol limit, and was unreachable in production anyway
because `/sitemap.xml` contains a dot and Next's middleware skips dotted
paths. So neither one was pointing crawlers at the company pages, and by
extension neither was pointing them at the markdown twins.

**Sizing.** `MAX_URLS_PER_SITEMAP` is 20,000, not the protocol's 50,000. The
binding limit is bytes, not URLs: each entry carries up to six `xhtml:link`
alternates, and a full 20,000-URL file measures about 17MB against the 50MB
ceiling. `SYMBOLS_PER_SITEMAP` is derived from it in `lib/sitemap.ts` so the
index and the children cannot disagree about which chunk holds what.

**Only companies with data are listed.** `/api/tickers/symbols/` requires an
`IndicatorSnapshot` row. 768 of the 18,400 listed tickers had none when this
was built, and a company page with no numbers is a thin page; a few hundred
of them in a sitemap invites a soft-404 judgement across the whole domain.

`/sitemap.xml` is `force-dynamic` on purpose. The symbol list comes from
Django, which is not reachable from the CI runner where `next build` runs, so
a prerendered index would be baked empty. The underlying fetches are cached
for an hour, so being dynamic costs one Redis-backed call.

Django's `SitemapView` at `/api/sitemap.xml` still exists for API consumers.
It is not what production serves and it still exceeds the protocol limits.

### Deploys reload gunicorn, they do not restart it

`systemctl restart` closes the listening socket, and for the couple of
seconds before the new master binds, nginx answers every request with a
`502`. `ExecReload=/bin/kill -s HUP $MAINPID` lets the deploy send `reload`
instead: the master keeps the socket while its workers re-fork, so nothing is
refused and nothing in flight is cut off.

That window was not theoretical. On 2026-08-26 a registry crawler probing
`/api/mcp` walked into it during a deploy and recorded the server as having
no capabilities at all:

```
23:05:54  Stopping Sponda Gunicorn...
23:05:55  nginx: recv() failed (104) reading response header from upstream
23:05:56  nginx: connect() failed (111) connecting to upstream
23:05:56  Started Sponda Gunicorn.
```

Workers re-import the application on `HUP`, so deployed code does take
effect. That holds only while gunicorn runs without `--preload`; adding that
flag would silently stop reloads from picking up new code, and the deploy
would have to go back to `restart`. The deploy falls back to `restart` if
`reload` fails, because a brief `502` window is bad and a deploy that aborts
halfway is worse.

### The API no longer traverses Next

nginx routes `/api/` straight to Django on :8710. It used to go to Next on
:3100, which rewrote it to Django in `middleware.ts`, so every API call on the
site crossed an extra Node process.

That hop was not just slow, it was broken for `HEAD`. gunicorn's sync workers
do not support keep-alive and close the connection on every response; Node's
HTTP client cannot reliably parse a bodyless response that ends that way, and
throws `HPE_CLOSED_CONNECTION` ("Data after `Connection: close`"), which Next
answers as a **500**. Measured 2026-08-26 through the edge:

| Request | Result |
|---|---|
| `HEAD /api/health/` x15 | 13 x 500, 2 x 200 |
| `HEAD /api/tickers/PETR4/` x15 | 14 x 500, 1 x 200 |
| `HEAD /api/tickers/NOPE99/` x15 | 15 x 500 |
| `HEAD /api/quote/T{1..20}/` | 7 x 500, 13 x 429 |
| `GET` on all of the above | no failures |

Every status code, not just errors. GET was unaffected, which is why browsers
never hit it and monitors, link checkers and anything doing a cheap existence
probe did. If UptimeRobot is pointed at an `/api/` path with `HEAD`, it was
seeing roughly 90% failure and reporting flapping downtime that was not real.

`/api/logos/` and `/api/assistant/ask` already had their own direct blocks for
related reasons. nginx matches the longest prefix, so they still win over the
general `/api/` one.

The rewrite stays in `frontend/src/middleware.ts` because local development
has no nginx. In production that branch is now dead.

**Next still calls Django directly** for server-rendered pages, the markdown
twins, the sitemap and the Open Graph cards, and those calls can still hit the
same parser bug. They go through `frontend/src/lib/django-fetch.ts`, which
retries once on a transport failure: a second attempt gets a fresh socket. It
never retries an HTTP error status, because a `429` is an answer rather than a
failure, and never retries a non-idempotent method.

### Origin trust: only Cloudflare gets to name the visitor

`sponda.capital` is Cloudflare-proxied, and the origin is a DigitalOcean VPS on
a public address. Cloudflare reaches it over TLS on 443 (the port-80 block only
redirects, so a `Flexible` zone setting would have redirect-looped years ago),
but encryption is not authentication: nginx had no way to tell a Cloudflare
connection from anyone who had learned the origin IP from a Certificate
Transparency log or old DNS.

That mattered because `quotes.client_ip.client_ip` trusts `CF-Connecting-IP` to
identify the anonymous visitor behind the [lookup cap](#lookup-limits), and
nothing enforced where the header came from. nginx passes unknown request
headers through untouched, so a direct request could carry its own
`CF-Connecting-IP`, mint a fresh identity per ticker, and walk the catalogue
with the cap intact but useless. `X-Forwarded-For` was the same hole with a
second door: it was built with `$proxy_add_x_forwarded_for`, which **appends**
to whatever chain the peer sent, and `client_ip()` reads the leftmost entry.

Two layers now stand in the way.

**Layer one, on by default.** `nginx/cloudflare-real-ip.conf` lists Cloudflare's
published ranges and sets `real_ip_header CF-Connecting-IP`, so nginx resolves
`$remote_addr` from that header **only** for connections opening from those
ranges. A direct connection keeps its real peer address no matter what it sends.
`sponda.capital.conf` then rebuilds `X-Real-IP`, `X-Forwarded-For` and
`CF-Connecting-IP` from `$remote_addr`, so the value Django reads is nginx's in
both cases. The list is committed rather than fetched at reload time: nginx has
to start when Cloudflare is unreachable, and a list that silently came back
empty would collapse every visitor into one shared rate-limit bucket. Cloudflare
changes the ranges about once a year; run `./nginx/update-cloudflare-ips.sh`,
read the diff, commit it.

The include sits at **server** scope, not in `conf.d/`. That box fronts eighteen
sites and only `sponda.capital` is behind Cloudflare, so trusting these ranges
globally would rewrite `$remote_addr` for the other seventeen too. The
`proxy_set_header` directives moved to server scope for the opposite reason:
they were copy-pasted into four locations, and the newest one had to remember
all four lines. Note the inheritance rule if you add a location: nginx inherits
`proxy_set_header` from the enclosing level only when the location declares
**none** of its own, so one header inside a location silently drops all five.

One side effect worth knowing: the default `combined` log format writes
`$remote_addr`, so `/var/log/nginx/sponda.capital-access.log` now records the
visitor rather than the Cloudflare edge node that relayed them. Counting unique
IPs in that file finally means something. Log lines from before this shipped are
not comparable. (`$realip_remote_addr` still holds the edge address if a log
format ever needs both.) No fail2ban jail reads these logs, so nothing bans on
the new values.

**Layer two, opt-in.** Authenticated Origin Pulls is mTLS against Cloudflare's
client certificate: nginx refuses a direct connection during the handshake
rather than merely distrusting its headers. It needs a CA file on the box *and*
a zone setting in the dashboard, and enabling either without the other is an
outage, so the deploy cannot own it. `sponda.capital.conf` carries a **wildcard**
include for it, because `include` of a literal missing path is a hard `nginx -t`
failure that would redden every deploy until someone installed the CA, while a
mask matching no files is simply empty.

To turn it on:

```bash
ssh root@poe.ma
/opt/sponda/nginx/enable-cloudflare-origin-pull.sh
```

The script installs the CA, verifies it really is `origin-pull.cloudflare.net`,
makes you confirm the dashboard toggle before it writes anything nginx reads,
runs `nginx -t`, and removes its own snippet if the test fails. Roll back by
deleting `/etc/nginx/snippets/sponda-origin-pull.conf` and reloading.

While you are in that dashboard, check SSL/TLS → Overview reads **Full
(strict)**, not **Full**. Plain `Full` accepts any origin certificate, expired
or self-signed included, so the hop is encrypted against a passive listener but
not against an active one. There is a valid Let's Encrypt certificate on the
box, so there is no reason to be on the weaker setting.

### Provider zeros that are not zeros

BRAPI and FMP both encode a missing net income as a literal `0` on some
filings rather than omitting the field. Stored as-is it is indistinguishable
from a real result and gets averaged into the inflation-adjusted earnings
behind every P/E window that covers it, dragging the average down and
inflating the multiple.

BBAS3 reported roughly R$31bn of revenue per quarter and precisely R$0 of
profit for every quarter from 2013 to 2019. Corpus-wide when found: **2,801
quarters across 565 companies**, from both providers plus older rows with no
recorded source.

The tell is revenue. `quotes/statement_quality.py::normalize_net_income`
treats a zero as missing when revenue is positive, and keeps it when there is
no revenue, because a pre-revenue company can genuinely earn nothing. Both
`brapi.sync_earnings` and `fmp.sync_earnings` apply it at ingestion.

For rows already stored:

```bash
./manage.py repair_zero_net_income --dry-run   # report only
./manage.py repair_zero_net_income             # null them, invalidate caches
```

It drops the derived caches for every company it touches. `IndicatorSnapshot`
rows are recomputed by the usual refresh jobs; run
`refresh_snapshot_fundamentals` if you want it sooner.

### Debt that vanishes without the liabilities to match

FMP publishes a quarterly balance sheet within hours of the filing, and on
that first pass it sometimes mis-tags the debt lines while getting the totals
right. Salesforce's Q2 FY2027, filed 2026-08-26, is the clean example: $39.3bn
of senior notes landed in `otherNonCurrentLiabilities`, so `totalDebt` came
back as **$2.46bn against $71.2bn of total liabilities**, the quarter after
$41.9bn against $72.4bn. The company had just issued $25bn of notes and drawn
a $6bn term loan to fund a $27.4bn buyback. Stored as-is it produced a
debt/equity of 0.06, a debt/EARN10 of 0.74 and a debt/FCF10 of 0.32, ranking
CRM as unlevered at the exact moment it levered up.

This is the dangerous direction of wrong. An overstated debt makes a company
look worse than it is; an understated one hides leverage from precisely the
screens someone uses to avoid it.

The tell is the accounting identity. Debt can fall by any amount for real
reasons, but the cash that retired it has to show up somewhere, so total
liabilities fall with it. `quotes/statement_quality.py::is_implausible_debt_collapse`
distrusts a quarter only when three things hold together:

| Condition | Threshold | Why |
| --- | --- | --- |
| The debt nearly vanished | at most **25%** of the prior quarter's debt survives | partial paydowns and refinancings are routine; near-total disappearance in one quarter is not |
| The amount was material | the drop is at least **25%** of prior total liabilities | a company can clear a small facility without moving its totals |
| Liabilities did not absorb it | they shed less than **50%** of the drop | a genuine repayment takes total liabilities down with it |

`discard_implausible_debt_collapses` applies that walk to a whole history in
date order, and never lets a quarter it has already rejected become the
baseline for the next one. Both `brapi.sync_balance_sheets` and
`fmp.sync_balance_sheets` run it before writing, so the next successful sync
restores the figure once the provider corrects the filing.

Corpus-wide when found: **31,483 quarters across 6,307 companies**, of which
**1,372 were a company's most recent quarter** and so were driving its live
ratios. Honda and BMW were reporting zero debt against trillions of yen and
billions of euros of liabilities.

Orange is the clearest case, because it shows the rule discriminating rather
than just firing:

| Quarter end | Debt (M) | Liabilities (M) | Distrusted |
| --- | --- | --- | --- |
| 2025-06-30 | 7,508 | 68,999 | yes |
| 2024-12-31 | 42,666 | 68,713 | no |
| 2024-06-30 | 7,404 | 69,936 | yes |
| 2023-12-31 | 52,650 | 83,579 | no |

FMP mis-tags Orange's interim filings and gets its annuals right. Each
annual restores the trusted baseline, so the walk flags exactly the interims
and does not run away.

Note the shape of that walk when reading these numbers. It compares each
quarter against the last one whose debt it still *trusts*, not against the
row immediately before, so a mis-tag sustained across several quarters is
caught for its whole span. A naive `lag()` query sees only the quarter where
debt drops and undercounts by roughly 3x · it was what produced the 9,716
and 458 first reported here.

For rows already stored:

```bash
./manage.py repair_collapsed_debt --dry-run       # report only
./manage.py repair_collapsed_debt --ticker CRM    # one company
./manage.py repair_collapsed_debt --latest-only   # just the live ratios (1,372)
./manage.py repair_collapsed_debt --limit 5000    # one tranche
./manage.py repair_collapsed_debt                 # all of it
```

**No provider is called.** Every figure the repair needs is already stored,
so it costs no API budget however it is run. `--latest-only` takes the
quarter each company's live ratios and screener row are computed from, which
is the visible damage. `--limit` takes a tranche of any size: a nulled
quarter no longer looks like a collapse, so successive runs pick up where the
last one stopped rather than redoing it.

Nulling drops debt/equity, debt/EARN10 and debt/FCF10 from the company's
rating rather than scoring them on a fiction. The rating still forms from the
remaining indicators as long as at least four survive
(`MIN_INDICATORS_FOR_GRADE`), so a repaired company keeps a grade, just an
honest one.

### Fiscal years, which are not calendar years

Roughly a quarter of the companies covered close their books somewhere other
than 31 December. Salesforce closes on 31 January, Starbucks in late
September, Microsoft in June. Grouping their quarters by the calendar year
the quarter happens to end in gets two things wrong at once:

- **The audited year-end never appears.** Salesforce's 31 January 2026 close
  lands in calendar 2026 and is then overwritten by its April and July
  quarters. Starbucks' 2025 row showed the 28 December 2025 balance sheet
  (the first quarter of fiscal 2026, $33.5bn of debt) instead of the audited
  28 September 2025 close ($26.6bn): a 26% overstatement on a row labelled
  with a year it does not describe.
- **The "annual" income is a rolling four quarters** offset from the year the
  company reported, so it never equals the figure in the filing.

FMP reports `fiscalYear` on all three statement endpoints and we now store it
(`QuarterlyEarnings.fiscal_year`, `QuarterlyCashFlow.fiscal_year`,
`BalanceSheet.fiscal_year`). `quotes/fiscal_year.py::fiscal_year_of` is the
single answer to "which year is this period in", and everything that groups
statements by year goes through it: the Fundamentos table, `get_annual_earnings`
and `get_annual_fcf` behind every P/E and P/FCF window, PEG, and the multiples
chart. BRAPI and CVM report no fiscal year and need none, because Brazilian
filers close on 31 December; the fallback to the end date's calendar year is
correct for them.

Three things had to move with it, each of which would have been a silent
regression on its own:

| What | Why |
| --- | --- |
| The frontend's year join | `FundamentalsTab` joins its rows to `pe10CalculationDetails` by year. Had one side moved and not the other, every trailing ratio on an off-calendar filer would have gone blank. |
| The inflation key | The CPI series is calendar time; a fiscal label is not. A filer's 2027 is already open in 2026, so looking the factor up under 2027 finds nothing and quietly adjusts by 1. Each annual entry carries an `inflation_year` (the calendar year it closed in) and every lookup uses that. |
| The year-end price | A year is valued on the day it closed. Pricing Salesforce's fiscal 2026 at the previous 31 December carries a month of price movement into that year's multiples. `quotes/price_history.py` indexes closes by date so both the table and the chart can ask for the close on or before a given day. |

`calculate_pe_windows` itself was never affected: it sums trailing periods,
so the year label only ever picked its CPI factor. It had to stay that way.

For rows stored before the field existed:

```bash
./manage.py backfill_fiscal_year --ticker CRM              # one company
./manage.py backfill_fiscal_year --limit 40 --dry-run      # sample, no writes
./manage.py backfill_fiscal_year --limit 2000              # one tranche
./manage.py backfill_fiscal_year --limit 2000 --after CRM  # the next one
```

It asks each company's **annual** statement which month it closes in, once,
and derives the label for every row that company already has. That is one FMP
call per ticker (~25,000 companies) rather than re-pulling twenty years of
quarterly statements across three endpoints (~75,000). Rows the provider
already labelled are skipped, so it is safe to re-run and safe to run
alongside the ordinary sync. Companies whose closing month cannot be learned
are reported and left on the calendar-year fallback rather than guessed at.

**Run it in tranches**, because one call per company is real API budget.
`--limit` sets the size, `--after` resumes past the last company done, and
each run prints the cursor for the next:

```
1500 companies this run, 23507 still queued after it
9 companies skipped, closing month unknown: AAC-UN, AACPU, ...
labelled 141032 rows across 1491 companies
next tranche: --after BLDP (23507 companies left)
```

The cursor is not a convenience. A company whose closing month can never be
learned stays unlabelled, so without it that company would head every later
tranche and burn a call on each one.

**A provider that cannot answer says nothing about a company.** The first
production run pushed 2,000 companies with no gap between calls, FMP's
circuit breaker opened (`failure_threshold=8`, `cool_down_seconds=60`), and
every call for the next minute raised. Each one was recorded as a company
whose closing month could not be learned: **1,611 of 2,000 "skipped"**,
American Airlines among them, and the cursor would have stepped past every
one. Nothing was corrupted, since a skipped company keeps a null
`fiscal_year`, but ~1,600 calls bought nothing.

Three things follow from that, all of them now covered by tests:

| | |
| --- | --- |
| `ProviderUnavailable` is separate from a null closing month | Only an empty answer from a *healthy* provider is a fact about the company, and only that earns a skip |
| A refusal is waited out, not counted | `RETRY_WAITS_SECONDS = (5, 20, 65)`, the last outlasting a full breaker cool-down |
| A run that still cannot reach the provider stops | And reports the cursor at the last company it actually **reached**, so everything unreached stays queued |

`--pause` (default 0.2s) keeps a long run from tripping the breaker in the
first place.

`--dry-run` still makes the call per company, because the closing month is
the thing it has to fetch to know what it would write. Bound it with
`--limit` rather than dry-running the universe.

Until the backfill reaches a company, `fiscal_year_of` falls back to the
calendar year, so deploying this changes nothing on its own.

## Server-side rendering and hydration

Every page is server-rendered, so the browser's **first** render has to
produce exactly the markup the server sent. Two house rules keep it that
way; both were learned from Sentry issues that ran for months.

**Never gate markup on React Query's `isLoading`.** The persisted cache
(`@tanstack/react-query-persist-client`) restores from `localStorage` in an
effect, and while it is restoring React Query reports a pending query with
`fetchStatus: "idle"`, so `isLoading` is `false`. Only the browser restores
anything: the server has no persister. A query with no `initialData`
therefore reports `isLoading: true` on the server and `isLoading: false` on
the browser's first pass, and anything gated on it renders two different
trees before a single effect has run. React then throws error #418, and
sometimes takes a `removeChild` `NotFoundError` down with it while it
rebuilds the DOM it no longer trusts.

Gate on the data instead. `[locale]/[ticker]/ticker-client.tsx` derives a
single `company` value and every section reads it, so server and browser
agree by construction: both start from exactly what the server fetched.
`ticker-client.hydration.test.tsx` pins the invariant by rendering the page
twice, once with `IsRestoringProvider` set the way the browser reports it
and once the way the server does, and asserting the two strings are equal.

**Never render auth-dependent markup on the first pass.** The server has no
session, so it cannot know the answer. `AccountButton` renders a placeholder
until `useIsHydrated` (`hooks/useIsHydrated.ts`, a `useSyncExternalStore`
wrapper) says the browser has taken over. Use that hook rather than a
`useState` + `useEffect` mount flag, which trips
`react-hooks/set-state-in-effect`.

## Observability

Unified error, performance, and cron monitoring through Sentry (free tier) plus UptimeRobot for external health checks. Full plan and rollout status: `docs/observability-plan.md`.

**How it works**

- **Django + Celery.** `config.observability.init_sentry` runs from `settings/base.py`. It is a no-op when `SENTRY_DSN` is unset, so dev and tests stay quiet. `before_send` scrubs `Authorization`, `Cookie`, `Set-Cookie`, `DATABASE_URL`, and `SECRET_KEY` from events. Integrations: `DjangoIntegration`, `CeleryIntegration`, `LoggingIntegration` (INFO breadcrumbs, ERROR-level events).
- **Systemd-timer commands.** Subclass `config.monitored_command.MonitoredCommand` and implement `run()` instead of `handle()`. The base class captures any unhandled exception to Sentry and re-raises (so systemd still marks the unit as failed). Setting `sentry_monitor_slug` wraps execution in `sentry_sdk.crons.monitor`, so Sentry Crons alerts you when a timer misses or fails. All six timer-invoked commands (`refresh_ipca`, `refresh_tickers`, `refresh_snapshot_prices`, `refresh_snapshot_fundamentals`, `check_indicator_alerts`, `send_revisit_reminders`) use this base.
- **Next.js.** `@sentry/nextjs` is wired up via `sentry.client.config.ts`, `sentry.server.config.ts`, `sentry.edge.config.ts`, all delegating to `src/lib/sentry.ts`. `withSentryConfig` in `next.config.ts` handles source-map upload at build time. Session Replay: 10% of sessions + 100% of error sessions (within free-tier quota).
- **Request IDs.** `config.middleware.request_id.RequestIDMiddleware` attaches a UUID to every request (or honors an inbound `X-Request-ID`, capped at 128 chars). The ID is echoed back in the `X-Request-ID` response header, tagged on the Sentry scope, and included in every JSON log line emitted during the request.
- **Structured logging.** `config.logging_formatter.JSONLogFormatter` emits one JSON object per log record (`timestamp`, `level`, `logger`, `message`, `request_id`, `exception`). Writes to stderr → captured by journald on production. No external log shipping yet; when we want it, point Promtail/Vector at the journal.
- **External uptime.** UptimeRobot (free) hits `https://sponda.capital/` and `https://sponda.capital/api/health/` every 5 minutes. Setup is manual, outside the repo.
- **Interactive shells are not reported.** `init_sentry` returns early for `manage.py shell`, `shell_plus` and `dbshell` (see `is_interactive_shell_session`). A traceback at a REPL is an operator mistyping a model name, not the service failing, and five such typos were sitting in the inbox looking like production errors. Skipping init also drops the two-second Sentry flush that every shell exit was paying. Gunicorn, Celery, pytest and all timer-driven management commands are untouched, which is the part the tests pin.
- **Third-party browser noise is dropped.** `src/lib/sentry.ts` ships a default `ignoreErrors` list covering wallet extensions (`Failed to connect to MetaMask`, `window.ethereum`), iOS in-app webviews reaching for Safari-only handlers (`window.webkit.messageHandlers`), and extension bootstraps (`ext:core/`, `<name:bootstrap>`). None of it is code we ship. A caller can pass its own `ignoreErrors` to replace the defaults.
- **A DFP archive the CVM has not published is not an error.** `download_dfp_archive` raises `DfpArchiveNotPublished` on a 404 and `sync_cvm_fourth_quarters` reports it and stops. Any other HTTP failure still raises. The job necessarily runs for a reporting year before the CVM publishes it, so without this the same page fires every year.

**Environment variables**

| Name | Where | Purpose |
|---|---|---|
| `SENTRY_DSN` | backend `.env` | Django + Celery DSN. Unset → Sentry is inactive. |
| `SENTRY_ENVIRONMENT` | backend | `production` / `development`. Defaults to `development`. |
| `SENTRY_RELEASE` | backend | Git SHA for release-tagged events. Optional. |
| `SENTRY_TRACES_SAMPLE_RATE` | backend | Perf trace sampling. Defaults to `1.0`; lower when traffic grows. |
| `NEXT_PUBLIC_SENTRY_DSN` | frontend build | Browser DSN. Baked into the client bundle at build time. |
| `NEXT_PUBLIC_SENTRY_ENVIRONMENT` | frontend | Same semantics as backend, but client-side. |
| `NEXT_PUBLIC_SENTRY_RELEASE` | frontend | Client release tag. |
| `SENTRY_DSN_NEXTJS` | frontend runtime | DSN used by the Next.js Node + edge runtimes. Separate from Django's `SENTRY_DSN` so server-rendered and API-route errors reach the `javascript-nextjs` project. Falls back to `SENTRY_DSN` when unset. |
| `SENTRY_AUTH_TOKEN` | frontend build / CI | Source-map upload. Build succeeds without it, source maps just aren't uploaded. |
| `SENTRY_ORG`, `SENTRY_PROJECT` | frontend build | Target for source-map upload. |

**Local testing**

```bash
# Backend: tests run green with no DSN (init is a no-op).
cd backend && .venv/bin/pytest tests/test_observability.py tests/test_monitored_command.py tests/test_request_id_middleware.py tests/test_json_log_formatter.py

# Frontend: vitest covers the initSentry helper.
cd frontend && npx vitest run src/lib/sentry.test.ts

# End-to-end smoke (optional): export SENTRY_DSN=<dev-dsn> before running
# the dev server and trigger a 500 from any view to verify delivery.
```

## Seeding a quarter from CVM

BRAPI is the only provider of Brazilian quarterly statements, and it lags the filing. Measured on 2026-08-10, BRAPI carried 2Q26 for every issuer that reported by ~30 July (ABEV3, VALE3, WEGE3, USIM5, VIVT3) and none that reported from 4 August on (GGBR3/4, PETR3/4, ITUB4, BBAS3, CSNA3, EMBR3, JBSS3, LREN3, RENT3, SUZB3). During earnings season that lag lands exactly when the Fundamentos tab is worth opening.

The CVM publishes the same filings as open data within days. `seed_quarter_from_cvm` reads that archive and writes one quarter of `QuarterlyEarnings`, `QuarterlyCashFlow`, and `BalanceSheet` rows, ahead of BRAPI.

```bash
cd backend
python manage.py seed_quarter_from_cvm --quarter 2026-06-30 \
    --ticker GGBR3 --ticker GGBR4 --ticker PETR3 --ticker PETR4

# Parse and print the figures without touching the database
python manage.py seed_quarter_from_cvm --quarter 2026-06-30 --ticker GGBR3 --dry-run
```

| Flag | Meaning |
|---|---|
| `--quarter` | Quarter end, ISO format. Must be 03-31, 06-30 or 09-30 · Q4 is filed as a DFP, not an ITR, and is rejected. |
| `--ticker` | Ticker to seed. Repeat the flag for several. Rejected up front if absent from `TICKER_TO_CVM_CODE` in the command module. |
| `--dry-run` | Parse and report, write nothing. |

No new environment variables · the CVM archive (`dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_<year>.zip`, ~13 MB) is public and unauthenticated. It is downloaded once per invocation and shared across every requested ticker.

### Why the seed is safe to overwrite

The write is deliberately BRAPI-compatible, not a replacement. `sync_earnings` / `sync_cash_flows` / `sync_balance_sheets` upsert on `(ticker, end_date)`, so BRAPI silently replaces these rows once it catches up. Nothing needs undoing.

Compatibility is not assumed, it is calibrated: `quotes/cvm.py` reproduces BRAPI's own stored 2026-03-31 values for Gerdau and Petrobras across all ten fields, exactly. Two fields are left unset on purpose · `free_cash_flow`, because BRAPI never reports it and `fundamentals.py` derives FCF as operating + investing for exactly that case, and `eps`, because a differenced year-to-date EPS would misstate the quarter's weighted share count (nothing reads the field).

### Period arithmetic

Three filing conventions, three treatments:

| Statement | CVM files | Command does |
|---|---|---|
| Income (DRE) | Both a year-to-date and a standalone three-month column | Reads the three-month column directly; differences YTD only if it is missing |
| Cash flow (DFC, indirect or direct) | Year-to-date only | Differences against the previous quarter's filing in the same annual archive |
| Balance sheet (BPA/BPP) | Point-in-time snapshot | Reads as filed |

Restatements are handled by keeping the highest `VERSAO` per document, and prior-year comparatives (`ORDEM_EXERC = PENÚLTIMO`) are discarded.

### Account mapping

An account number is only trusted when the line's own label agrees with it. The chart of accounts is sector-specific, so the number alone does not identify the concept · see below.

| Field | CVM account | Required label |
|---|---|---|
| `revenue` | 3.01 | · |
| `net_income` | 3.11 (consolidated, including minority interest · matches BRAPI) | · |
| `operating_cash_flow` | 6.01 | · |
| `investment_cash_flow` | 6.02 | · |
| `dividends_paid` | 6.03.* lines whose description names dividends or interest on equity | · |
| `total_debt` | 2.01.04 + 2.02.01 | Empréstimos e Financiamentos |
| `total_lease` | 2.01.04.03 + 2.02.01.03 | Financiamento por Arrendamento |
| `total_liabilities` | total (2) − equity, falling back to 2.01 + 2.02 | Passivo Circulante / Não Circulante |
| `stockholders_equity` | whichever account carries the label | Patrimônio Líquido Consolidado |
| `current_assets` | 1.01 | Ativo Circulante |
| `current_liabilities` | 2.01 | Passivo Circulante |

### Why the label, not the number

The same account numbers hold different quantities depending on the filer's sector:

| Account | Industrial filer | Banco do Brasil |
|---|---|---|
| `1.01` | Ativo Circulante | Caixa e Equivalentes de Caixa |
| `2.01` | Passivo Circulante | Passivos Financeiros a Valor Justo |
| `2.02.01` | Empréstimos e Financiamentos | **Depósitos** |
| `2.03` | Patrimônio Líquido | **Provisões** |

Read by number alone, a bank's customer deposits become debt and its provisions become equity · R$39.11bn where the real figure is R$196.91bn. These are not mislabelled fields but different quantities, and they feed `debtToEquity`, `liabilitiesToEquity` and `currentRatio`. Every one is a plausible wrong number, which is the kind that survives review.

Across the 416 consolidated filers of 2026, equity sits at `2.03` for 404, `2.07` for 7 and `2.08` for 5 · but **all 416** carry a line labelled "Patrimônio Líquido Consolidado". The label is the reliable key.

Label checking also catches cases a sector rule would miss: three filers publish "Capitalização" at the borrowings account, one publishes "Depósitos Interfinanceiros" at the lease account, and the two insurers *do* report current/non-current, so branching on sector would have wrongly discarded their figures.

`total_liabilities` is taken as the balance-sheet total less equity. That agrees with `2.01 + 2.02` for all 404 industrial filers and, unlike that sum, is also meaningful for a bank whose `2.01`/`2.02` are a fair-value/amortised-cost split rather than a maturity one.

### Validation gates

Both refuse the write rather than log a warning, because what they catch is a plausible wrong number rather than an obvious one.

| Gate | Rule | Basis |
|---|---|---|
| Balance identity | Total assets must equal liabilities plus equity, within 0.1% | Held for all 414 filers of 2026 publishing both totals, so a violation means the parse is wrong |
| Equity ambiguity | Two lines claiming to be equity is refused | Guessing silently halves or doubles every leverage ratio |
| Equity continuity | Equity must stay within an order of magnitude of the prior quarter | Checked in the writer, where prior quarters exist |

Measured over the full 2026 archive: **416 of 416 filers parse, none refused.** Equity and total liabilities resolve for 415, current assets/liabilities for 403 (the 12 financial filers correctly report neither), debt and leases for 401.

### Local testing

```bash
cd backend
.venv/bin/pytest tests/test_cvm.py tests/test_seed_quarter_from_cvm.py
```

The suites use synthetic in-memory archives, so they never touch the network.

## Measuring CVM publication latency

> Operational checks, decision rules and known gaps live in [`CVM_RUNBOOK.md`](CVM_RUNBOOK.md).

How quickly a filing can appear on Sponda is capped by something outside our control: how long the CVM takes to publish it. `snapshot_cvm_filings` records the evidence, `report_cvm_lag` summarises it.

### Why it is polled hourly

The CVM does not publish its filing index (`itr_cia_aberta_<year>.csv`) as a standalone file · it exists only as the first entry inside the 12 MB annual archive. Two properties of CVM's server make polling cheap anyway:

| Property | Used for |
|---|---|
| `Last-Modified` / `ETag` on the archive | A HEAD request says whether anything was rebuilt, transferring no payload. An unchanged poll downloads **0 bytes**. |
| `Accept-Ranges: bytes` | When it *has* changed, a 256 KB ranged read covers the index alone, which is inflated directly from the first zip entry. Measured: the full 859-row index recovered from 0.7% of the archive. |

The command falls back to the full download whenever the archive's layout is not the one this shortcut assumes, so an unexpected layout costs bandwidth rather than correctness.

Hourly rather than daily because a daily poll would only locate a rebuild to within 24 hours, and the rebuild cadence is the very thing being measured.

### What is recorded

| Model | Row per | Purpose |
|---|---|---|
| `CvmArchiveBuild` | Distinct `Last-Modified` seen for an archive year | Successive rows are the rebuild history; the gaps are the cadence |
| `CvmFiling` | `(cvm_code, reference_date, version)` | Who filed what, when CVM received it (`DT_RECEB`), and which build first carried it |

`CvmFiling.publication_lag_days` measures against the build's own timestamp rather than our poll time, so the figure does not move if the polling interval changes. A restatement is a new `version`, hence its own row and its own lag.

### Backfill is not a measurement

The first poll records every filing published so far that year, all attributed to whichever build was current. Those filings were not watched into existence · one received in April and first recorded in August may well have been published in April. Counting that gap as lag invents months of latency that never happened.

A lag therefore counts as measured only when the filing was received *after* the earliest recorded build, so an earlier observation exists that could have carried it and did not. Everything else is reported as `already published when polling began`, and the report prints `not enough observations yet` rather than a number.

```bash
cd backend
python manage.py snapshot_cvm_filings          # hourly via timer; safe to run by hand
python manage.py report_cvm_lag --year 2026
python manage.py report_cvm_lag --reference-date 2026-06-30   # one earnings season
```

### What is already known

Measured 2026-08-11, before any observation window had opened:

- Every CVM document dataset (ITR, DFP, FCA, IPE, VLMO, FRE) carried the same `Last-Modified` of Sunday 2026-08-09, 10:00–11:40 GMT · one batch rebuild across the whole tree. The company registry (`cad_cia_aberta.csv`) is rebuilt separately and daily.
- That archive was untouched through Monday and Tuesday, which suggests a **weekly Sunday** cadence. Inferred from a single 2-day gap, so it is a hypothesis · confirming or refuting it is what the timer is for.
- Within a build, the newest filing was 2 days old (`DT_RECEB` 2026-08-07 in an 2026-08-09 build), with 52 filings each at 3 and 4 days.

If the weekly hypothesis holds, filing-to-live is roughly 1 day at best and 7 at worst, median around 3.5 · better than BRAPI's measured 7–21 days, but a halving rather than the near-elimination a 2-day publication lag on its own would imply. The rebuild cadence, not the publication lag, is the binding constraint.

## Mapping tickers to CVM codes

CVM identifies companies by `CD_CVM` and CNPJ and never by ticker, so nothing can be read from CVM for a given company until this bridge exists. `map_tickers_to_cvm` builds it from published data and stores it on `Ticker`.

### Where the mapping comes from

Three sources of evidence, strongest first. Each declines on ambiguity rather than guessing · a ticker attached to the wrong company produces a plausible wrong number, which survives review far longer than a missing one.

| Method | Evidence | Covers |
|---|---|---|
| `ticker` | The FCA securities table publishes `Codigo_Negociacao` (the B3 code) against a CNPJ; the registry maps CNPJ to `CD_CVM` | 361 |
| `root` | B3 gives one company one four-letter root, and the FCA sometimes lists only the unit (`KLBN11` recovers `KLBN3`/`KLBN4`) | 12 |
| `name` | Company name against the registry, normalised for how the two datasets differ | 14 |
| `manual` | Set by hand with `--set`; never overwritten by the automated pass | 2 |

`Ticker.cvm_match_method` records which produced a mapping, so a disputed figure can be traced back to the evidence behind it.

### The published field is dirty

Of the values CVM publishes as `Codigo_Negociacao`, 61 are not tickers at all: zeros, a debenture code (`1545-8`), and for CSN the company's own CVM code (`4030`) sitting in the ticker column. Every candidate is checked against the B3 ticker shape (`^[A-Z]{4}\d{1,2}$`) before use. Reading the field unvalidated attaches real tickers to whichever company published the string.

CSN is the instructive case: its FCA entry is rejected as a ticker, then recovered correctly by name.

### Coverage

358 of 361 Brazilian tickers resolve from published data alone (99.2%). The three that do not (`MBRF3`, `CTAX3`, `WDCN3`) are exactly the three with no company name stored, so the name fallback has nothing to work with. Two were identified from the registry and set by hand; `WDCN3` matches no registered company and remains unmapped.

```bash
cd backend
python manage.py map_tickers_to_cvm --dry-run     # report without writing
python manage.py map_tickers_to_cvm
python manage.py map_tickers_to_cvm --set MBRF3=20788 --set CTAX3=19100
```

`--set` validates the code against the registry before writing and refuses one no company holds, since a typo there puts another company's accounts on a real company's page.

### What is deliberately not mapped

BDRs (`XPBR31`, `PRXB31`, `INBR32` and around a dozen others) match the B3 ticker shape but are receipts over foreign issuers that CVM never registers. They can never be mapped. The unmapped report therefore lists only tickers **with a market cap**, so permanent BDR noise cannot bury the one new listing that needs attention.

Known limitation: a BDR sharing a four-letter root with a Brazilian issuer (`JBSS32` over JBS N.V. against `JBSS3` for JBS S.A.) will root-match to the Brazilian entity. Distinct companies, similar figures. The `root` provenance is what flags it for audit; none are currently in the ticker universe.

## Ingesting quarters from CVM

`sync_cvm_filings` turns what the hourly poll recorded into statement rows. It is the first place in the pipeline where a parsing mistake reaches a company's page rather than a report, so the defaults are conservative.

### Precedence: CVM fills gaps, it does not compete

BRAPI's rows are the ten-year baseline every P/E10 denominator is built from. A quarter already held by another source is left alone — including one whose provenance predates the `source` column, since absence of a label is not permission to overwrite. When BRAPI catches up it overwrites the CVM row on `(ticker, end_date)` and restamps the source, which is the intended end state rather than something to undo.

| `source` | Meaning |
|---|---|
| `brapi` | Written by the BRAPI sync (Brazilian tickers) |
| `fmp` | Written by the FMP sync (everything else) |
| `cvm` | Written from CVM open data ahead of BRAPI |
| *(empty)* | Written before provenance was tracked |

Existing rows are deliberately **not** backfilled. Their origin is inferable but not known — some were seeded from CVM by hand — and labelling them from a guess would make the audit trail assert something false. Empty means unrecorded, which is what actually happened.

**A writer stamps its own source.** Adding the column without adding it to BRAPI's `bulk_create(update_fields=...)` would have let BRAPI overwrite the figures while leaving the row still claiming `cvm`, which is worse than having no provenance at all.

### What it costs when there is nothing to do

The work list is derived from `CvmFiling` rows the poll already recorded, so deciding there is nothing to write is one query rather than a 12 MB download. That is the normal state between earnings seasons. The archive is fetched once per run and parsed once per company, then written to every ticker sharing that CVM code (ON and PN share one filing).

### Written once, not on every run

A quarter is rewritten only when a **later filing** exists for it. Holding a quarter is not a reason to rewrite it: every rewrite re-parses the company, recomputes ten years of indicators and drops three caches to arrive back where it started. Four runs a day over a season is a great deal of work for no change · and it churns the timestamp that answers "when did this go live".

`filed_at` (CVM's `DT_RECEB`) is stored on each row for that comparison. It also makes a row self-describing: it says which filing produced it without depending on the ticker mapping still resolving the same way.

### Filing to live: the goal as a number

`report_cvm_lag` publishes the metric the whole plan exists to move · **median days from the CVM receiving a filing to the row being live**. Unlike the publication-lag figures above, which measure CVM, this measures the whole path we control: CVM's publication lag, its rebuild cadence, our poll interval and the sync cadence together.

Rows from other providers are excluded rather than counted as zero. They carry no filing date, and their latency is a property of that provider rather than of this pipeline.

So are quarters filed before ingestion could reach them. The first sync wrote quarters filed months earlier, because that is when the feature shipped · counting those reported `p90 89d, max 99d`, figures describing when ingestion began rather than how long it takes. A row counts only once its filing arrived after the archive was first observed, which is the same window the publication-lag report uses. The excluded rows are reported as `filed before ingestion began, not measurable`.

Without it, "as near their quarterly publishing dates as possible" is an aspiration rather than something that can regress and be noticed.

### Failure is kept local

During earnings season a single unparseable filing must not cost the batch. A company that fails to parse, or whose figures are refused by the continuity gate, is reported and skipped; the rest are written. Q4 filings are ignored entirely — ITR covers Q1 to Q3, and Q4 lives in the annual DFP.

```bash
cd backend
python manage.py sync_cvm_filings --dry-run    # list the work, download nothing
python manage.py sync_cvm_filings
```

### When the continuity gate is wrong

The gate refuses equity that moved by an order of magnitude in a quarter, because that is what reading the wrong line looks like. It cannot tell that from a real corporate event, and sometimes it is one: SAUD3's equity moved 13x when Bradesco's health business was folded into Odontoprev, with Capital Social going from R$851m to R$14.90bn.

The threshold stays where it is · a false positive costs a visibly missing quarter, a false negative puts a wrong number on a page nobody checks. But the automated path rejects such a quarter identically on every run, so without an override it could never be ingested at all.

```bash
python manage.py seed_quarter_from_cvm --quarter 2026-06-30 --ticker SAUD3 --force
```

`--force` overrides the continuity check only, and is logged at warning level. The parser's own gates are not overridable: a balance sheet that does not balance is a parse fault whoever is asking. The scheduled sync never forces.

## The fourth quarter

ITR covers Q1 to Q3. **Nobody files Q4 as a standalone period** · the annual DFP carries the calendar year and nothing else, so Q4 is derived as the audited year minus the nine months already reported.

### The difference lands in Q4

The year is audited and the quarters are not, so any adjustment the auditors made to an earlier quarter is charged wholly to Q4. That is deliberate: the four quarters then sum to the audited year, and the alternative · rewriting Q1 to Q3 from the DFP · would displace BRAPI's series, which the whole ingestion path treats as the baseline. Not a trade worth making for a quarter BRAPI itself publishes within weeks.

### What can and cannot be checked

| Refused | Why |
|---|---|
| The annual reports no net income | Three 2025 filers published a zero annual against quarters summing to billions; differencing that derives a large false loss |
| Q1, Q2 or Q3 is missing | Two quarters is not nine months |
| The balance sheet does not balance, or equity moved an order of magnitude | The same gates the quarterly path uses |

**A bound on the size of the implied quarter would be dead code** and is deliberately absent. The implied value is the year minus the nine months, so its magnitude can never exceed their sum; any threshold loose enough to permit a genuine collapse is already unreachable. A check that cannot fire reads as protection without being any.

So a year that quietly disagrees with its own quarters is **not** detectable here. AUAU3 and BOBR4 differ from theirs by 63% and 36%, and with only the year and the nine months in hand, a Q4 absorbing that is arithmetically indistinguishable from a terrible quarter. It shows up only against a Q4 from another source, which is what `source` makes auditable after the fact.

### Measured against 2025

Of 279 companies where a Q4 could be derived, **277 (99.3%) matched the Q4 BRAPI eventually published**, within 1%. Three were refused by the gate. The two that differed are exactly the pair above.

```bash
cd backend
python manage.py sync_cvm_fourth_quarters --dry-run
python manage.py sync_cvm_fourth_quarters --year 2025
```

## Ingesting quarters straight from ENET

The archive path above is bounded by CVM's batch rebuild, which the latency
evidence puts at roughly weekly. A company that files the day after a rebuild
waits most of a week before `sync_cvm_filings` can see it — during earnings
season, exactly when the Fundamentos tab matters most. `sync_cvm_enet_filings`
closes that gap by reading ENET (rad.cvm.gov.br), the system companies
actually file into, whose public search lists a filing within minutes of
delivery. Filing-to-live drops from days to about an hour.

### A second discovery mechanism, not a second set of rules

ENET only changes how a filing is *found and fetched*. Everything after that
is the shared pipeline: the package's statements are converted into the same
account-row vocabulary the archive CSVs use and handed to
`cvm.build_quarter_statements`, so the account mapping, the label guards, the
balance validation and the equity continuity gate apply identically. Writes go
through the same `is_writable`/`write_quarter` pair, so BRAPI is never
displaced, an unchanged quarter is never rewritten, and when the weekly
archive catches up it finds these rows already written with the same filing
date and leaves them alone.

### How a filing is found

`ListarDocumentos`, the JSON endpoint behind ENET's public search page,
filtered to category `EST_3` (structured quarterly filings) and a delivery
window of the last `--days` days (default 7). The endpoint needs the search
page's session cookie and a browser User-Agent — without the latter the WAF
resets multi-megabyte downloads partway through. Restatements appear as new
versions; only the highest version per company and quarter is ingested.

### The cash flow needs one extra download

A filing package carries the income statement with a standalone three-month
column and the balance sheet as a snapshot, but the cash flow year-to-date
only. In the annual archive the previous quarter's filing sits alongside and
the differencing arithmetic finds it; a single ENET package travels alone. So
for second and third quarters the previous quarter's package is downloaded
too, keeping the delta pure CVM arithmetic rather than mixing sources. First
quarters need nothing: their year-to-date is the quarter. When the previous
filing cannot be found the cash flow fields stay `None` rather than wrong.

Verified against BRAPI on ALLD3's 2026-06-30 filing: the operating and
investment cash flow deltas implied by the two ENET packages reproduce
BRAPI's stored first quarter exactly.

```bash
cd backend
python manage.py sync_cvm_enet_filings --dry-run   # list the work, download nothing
python manage.py sync_cvm_enet_filings             # ingest the last 7 days
python manage.py sync_cvm_enet_filings --days 30   # widen the window
```

No new environment variables · ENET's search and downloads are public and
unauthenticated.

## Scheduled Tasks

Systemd timers run periodic jobs. Each timer is installed and enabled automatically on deploy. To inspect:

```bash
systemctl list-timers --all              # all timers, next/last run
journalctl -u sponda-refresh.service     # last run logs for a unit
```

| Command | Timer | Purpose | Frequency |
|---|---|---|---|
| `refresh_ipca` + `refresh_tickers` | `sponda-refresh.timer` | Sync IPCA inflation index and the B3 + US ticker lists from BRAPI / FMP | Daily 06:00 UTC |
| `refresh_snapshot_prices` (+ `check_indicator_alerts` post-run) | `sponda-refresh-snapshots.timer` | Rolling 15-minute refresh while either B3 or NYSE is open. Updates market cap + current price and recomputes PE10 / PFCF10 / PEG / P/FCF PEG against existing fundamentals, then re-evaluates alert thresholds. The command short-circuits with "No exchange open" outside market hours, so off-hours ticks are cheap no-ops. | Every 15 min Mon-Fri |
| `refresh_snapshot_fundamentals` | `sponda-refresh-fundamentals.timer` | Full refresh: resyncs quarterly earnings, cash flows, balance sheets, then recomputes the entire `IndicatorSnapshot` row. Four API calls per ticker. | Weekly Sun 06:00 UTC |
| `check_indicator_alerts` | `sponda-check-alerts.timer` | Daily safety-net pass over user alerts (the in-market 15-min run already covers weekday hours) | Daily 07:30 UTC |
| `send_revisit_reminders` | `sponda-revisit-reminders.timer` | Email users whose scheduled company revisits are due or overdue | Daily 11:00 UTC |
| `sync_fx_rates` + `sync_country_cpi` | `sponda-refresh-fx.timer` | Pull daily USD↔X FX rates from FMP and per-country CPI from FRED, for every reporting currency in the universe. Required by the cross-currency indicator pipeline. | Daily 05:30 UTC |
| `snapshot_cvm_filings` | `sponda-snapshot-cvm.timer` | Record which quarterly filings the CVM has published and when, to measure how fast a filing can reach the site. Costs one HEAD request when the archive is unchanged. | Hourly |
| `map_tickers_to_cvm` | `sponda-map-cvm-tickers.timer` | Resolve Brazilian tickers to the CVM codes their filings are keyed by. The recurring pass is how a new listing surfaces rather than silently never being ingested. | Monthly, 1st 04:00 UTC |
| `sync_cvm_filings` | `sponda-sync-cvm.timer` | Write newly filed quarters that no other source holds. One query when there is nothing to write. | 4x daily |
| `sync_cvm_fourth_quarters` | `sponda-sync-cvm-q4.timer` | Derive Q4 from the annual DFP for companies lacking it. DFPs arrive across February and March. | Daily 05:40 UTC |
| `sync_cvm_enet_filings` | `sponda-sync-cvm-enet.timer` | Write ITRs delivered to ENET in the last week, ahead of the weekly archive rebuild. One search request when nothing new was delivered. | Hourly at :35 |
| `sync_country` | `sponda-sync-country.timer` | Backfill `Ticker.country` from FMP company profiles for tickers still missing it (new listings arrive without a country). One profile call per missing ticker, largest market cap first; a no-op once the universe is labeled. | Daily 05:17 UTC |

#### Which source may delete a ticker

`refresh_tickers` runs two list syncs against two disjoint sources: BRAPI lists B3 instruments, FMP lists the US universe. Each reaps rows that vanished from its own source, so each must first decide which rows it owns · a symbol absent from BRAPI is not delisted, it is simply American. Ownership is decided by symbol shape in `quotes/ticker_symbols.py`: `BRAZILIAN_SYMBOL_REGEX` (`^[A-Z]+\d+$`) matches `PETR4` and `VALE3` but never `AAPL`. `sync_tickers` deletes only what matches; `refresh_us_tickers` deletes only what does not. The regex has one home because the two guards are only reviewable as a pair.

Getting this wrong is silent rather than loud. `sync_tickers` originally deleted every unmatched row, so each daily run dropped all ~18K US tickers and `refresh_us_tickers` re-inserted them seconds later as fresh rows with an empty `sector` and `country`. The universe count stayed right and no job errored; what leaked was the backfilled metadata, which `sync_us_sectors` then repurchased from FMP every morning without ever converging. `country` fared worse · `sync_country` runs at 05:17, before the 06:00 wipe, so its work never survived to be seen and the screener's country list offered only BR.

The reminder service is `Type=oneshot` with `Restart=on-failure` (up to 3 retries 120s apart) so a transient SMTP error doesn't silently drop a day of notifications. The timer is `Persistent=true`, so a missed run (e.g. server reboot) catches up on next boot. Long-running services (`sponda`, `sponda-frontend`) use `Restart=always`.

`StartLimitIntervalSec` and `StartLimitBurst` must sit in `[Unit]`. systemd parses them nowhere else · under `[Service]` they are ignored with a log warning, leaving `Restart=on-failure` with no ceiling, so a unit whose dependency is down retries forever instead of giving up. That is a silent defeat of the configuration rather than a degradation, so `tests/test_deploy_config.py` asserts the placement for every unit and that anything declaring `Restart=on-failure` still carries a `StartLimitBurst`.

## Deployment

Pushes to `main` trigger a GitHub Actions workflow that runs all test suites, builds the Next.js bundle in CI, then SSHs to `poe.ma`: pulls the latest code, installs backend deps into the venv (`uv pip install`), runs `npm ci` against the prebuilt bundle, migrates, installs the systemd units and timers, reloads nginx, and restarts `sponda`, `sponda-celery`, and `sponda-frontend`. There is no Docker anywhere · every environment runs the code directly in a Python virtualenv (prod under gunicorn + systemd, local dev via `make dev`).

### Manual Deploy

```bash
ssh root@poe.ma
cd /opt/sponda
git pull
source venv/bin/activate && uv pip install -r backend/requirements.txt
cd backend && python manage.py migrate --noinput && cd ..
cd frontend && npm ci && npm run build && cd ..
systemctl restart sponda sponda-celery sponda-frontend
```

## Local Development

### Prerequisites

- Python 3.12+
- Node.js 20+
- A [BRAPI](https://brapi.dev) API key (Brazilian tickers)
- An [FMP](https://site.financialmodelingprep.com) API key (US tickers)

There is no Docker · everything runs directly in a Python virtualenv. Once the one-time setup below is done, `make dev` is the everyday command: it starts Django (`runserver 8710`) and the Next.js dev server (`next dev --turbopack`) together and opens `http://localhost:3000`.

### Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create .env from template (edit with your BRAPI key)
cp ../.env.example ../.env

# Run migrations and start server
python manage.py migrate
python manage.py refresh_ipca     # fetch IPCA data
python manage.py refresh_tickers  # fetch B3 ticker list
python manage.py runserver 8710   # port the frontend proxies to (see below)
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The Next.js dev server runs on `localhost:3000`. Browser `/api/*` calls are proxied to Django by Next.js middleware (`frontend/src/middleware.ts`), which rewrites them to `DJANGO_API_URL` (default `http://localhost:8710`). The browser only ever talks to Next.js · Django is never exposed directly.

### Backend linting

```bash
cd backend
ruff check .          # what CI runs
ruff check . --fix    # apply the safe autofixes
```

Ruff, configured in `backend/ruff.toml`, running in CI as a step in the `unit-tests` job. **There is no baseline: `ruff check .` passes clean**, so anything it reports is genuinely new.

That is possible because the ruleset is deliberately narrow — pyflakes (`F`) plus the pycodestyle error groups that catch real mistakes (`E4` imports, `E7` statements, `E9` syntax/IO). Ruff 0.16's own defaults report ~735 problems on this codebase, almost all stylistic. The narrow set found 46, small enough to fix outright rather than suppress:

- 40 auto-fixed, mostly unused imports and `f`-strings with no placeholders
- 6 by hand: a `.screener` import that had drifted below a module constant, three lambda assignments (the sitemap path builders and one test helper), an unused variable in the dismiss-all test, and a `# noqa: F405` for a `BASE_DIR` reference in the star-imported dev settings

Each removed import was checked against Django's side-effect import patterns before trusting the autofix. Nothing in `__init__.py`, `apps.py`, signals, `conftest.py` or settings was touched; the three production removals (`assistant/admin.py`, `social/views.py`) were verified unreferenced by hand.

Migrations are excluded — they are generated files.

Ruleset expansion is deliberately left as follow-up work, one group per PR, since each has a real cost today: `I` (89 unsorted imports, auto-fixable but import order can matter in Django), `B` (~20 bugbear findings), `DJ` (13 Django-specific, 6 of which need migrations). `E501` is intentionally absent: this codebase runs long lines with intent and reflowing them would bury real history in `git blame`.

`backend/tests/test_deploy_config.py` guards that both linters still run in CI, that ruff stays pinned in `requirements.txt`, and that `ruff.toml` exists — without the config file CI would silently fall back to ruff's 735-problem defaults.

### Frontend linting

```bash
cd frontend
npm run lint          # eslint src --max-warnings 0
npx eslint src --fix  # apply the auto-fixable subset
```

ESLint 9 with flat config (`frontend/eslint.config.mjs`), extending `next/core-web-vitals` and `next/typescript`. It runs in CI as its own step in the `frontend-tests` job, before the test run. `.next/`, `dist/` (the retired Vite bundle Django still serves as a fallback shell) and `public/` are ignored.

**Warnings are errors here.** `--max-warnings 0` is what keeps the count at zero rather than letting it drift back up: a zero-warning state nobody enforces lasts about a week.

**Two rules are off**, both with the reasoning in `eslint.config.mjs` rather than here:

- `@next/next/no-img-element` — every `<img>` in the app is a 14–40px company logo or avatar, sized by a CSS class, with an `onError` fallback, coming from the `/api/logos/` Django proxy that already normalises and caches. `next/image` wants explicit dimensions the stylesheets currently own, does not map onto the hide-or-swap fallback, and would put a second image pipeline in front of a 14px PNG. None of them is an LCP image, which is what the rule protects. Turn it back on the day a real content image lands.
- `@next/next/no-page-custom-font` — written for the Pages Router; it warns that a font link outside `pages/_document.js` "will only load for a single page". There is no `pages/` directory here, and the link is in the App Router root layout, which wraps every route.

**The suppressions baseline.** Linting was introduced to an existing codebase, which surfaced 40 errors and 34 warnings. The warnings are now all gone (see above and the git history of this section). The errors are a different matter: rewriting 25 `react-hooks/set-state-in-effect` violations across the auth, locale and Learning Mode contexts is a behavioural change, not a lint fix, so it is not something to do blind. Those are recorded in `frontend/eslint-suppressions.json` (`eslint src --suppress-all`), which means:

- **New violations fail CI.** Verified: a fresh `any` in a new file exits 1, and so does exceeding a suppressed count in a file already listed.
- **Existing debt is visible and burn-downable**, not hidden behind disabled rules. The rules stay on at full strength.

What is in the baseline:

| Count | Rule |
|---|---|
| 6 | `@next/next/no-html-link-for-pages` |
| 4 | `react-hooks/refs` |
| 4 | `@typescript-eslint/no-explicit-any` |
| 1 | `react-hooks/purity` |

To burn one down: fix the violations in a file, then `npx eslint src --prune-suppressions` to drop the stale entries.

#### The set-state-in-effect burndown

The baseline started with 25 `react-hooks/set-state-in-effect` entries and now has none. That rule is worth knowing about because chasing it found **three real bugs**, not just style problems:

- **`CompanySearchInput` added the wrong company.** Its keyboard highlight reset was keyed on `results.length`, so typing a new query that happened to return the same number of rows left the old index highlighted, pointing at an unrelated ticker. Enter added that one.
- **`AddFavoriteCard`'s arrow keys did not work at all.** `useFavorites` returned `favorites.map(...)` unmemoised, so a fresh array every render invalidated `excludeSet`, then `results`, then fired the highlight reset — wiping the selection on the render that followed each keypress.
- **`ScreenerFilterPresets` synced state to a prop that never changes**, in a modal that unmounts on close. Pure dead code.

Sixteen were fixed. The recurring shapes and their replacements:

| Shape | Replacement |
|---|---|
| `mounted` flag from an empty effect, to gate a portal | `useIsHydrated()` |
| Read localStorage on mount and `setState` | `useStoredState()` |
| Read a client-only constant (timezone) on mount | `useSyncExternalStore` directly, as in `useRegion` |
| Reset state when a prop or list changes | Adjust state during render, keyed on a **value** not an identity |
| `fetch` in an effect with hand-synced loading/error/data | `useQuery` |

**Keying on a value, not an identity, is the part that matters.** Both dropdown bugs came from an effect watching an array whose identity churned (or whose length did not). Comparing a joined string of symbols cannot go wrong in either direction.

The remaining nine are deliberate and carry their reasoning inline at the call site rather than in the suppressions file, because in each the effect genuinely is the right primitive: one-shot token exchanges driven by a URL (`verify-email`, the Google callback), seeding state from a query that resolves later (`ticker-client`), reacting to an external change (`EmailVerificationGate`), or starting an operation the effect itself owns (`useTickerSearch`). Read the comment above any `// eslint-disable-next-line react-hooks/set-state-in-effect` before removing it.

**Two `exhaustive-deps` disables are deliberate**, each with its reasoning inline:

- `CompareTab.tsx` auto-save — `allTickers` and `existingList` are fresh objects every render and `updateList` is a mutation whose identity changes as it runs, so listing them would re-arm the 1s debounce continuously and the list would save in a loop. The effect keys off `tickersKey` (the joined composition) instead.
- `shared/[token]/page.tsx` fetch — `t` is memoised per locale, so listing it would re-run the whole fetch on a language switch, a network round trip for identical data, when `t` is only used there for error copy.

The other two missing dependencies were real and are now listed: `locale` in the login page's Escape handler (which navigates to `/${locale}` and would otherwise close over a stale one) and `t` in `HomepageGrid`'s save-layout callback.

One quirk worth knowing. Suppressions are counted per file per rule, so adding a *sixth* `any` to a file with five suppressed ones reports all six, not one. Confusing the first time; it fails safe, which is the right direction.

The 34 warnings are mostly `@next/next/no-img-element` (18 raw `<img>` tags that could be `next/image`) plus unused variables and `react-hooks/exhaustive-deps`.

### Environment Variables

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Django secret key |
| `BRAPI_API_KEY` | BRAPI pro API key (Brazilian tickers) |
| `FMP_API_KEY` | FMP API key (US tickers + FX rates) |
| `FRED_API_KEY` | FRED API key (per-country CPI; free at fred.stlouisfed.org) |
| `SPONDA_ANON_LOOKUPS_PER_DAY` | Anonymous per-IP daily company-lookup cap (default `20`) |
| `SPONDA_UNVERIFIED_LOOKUPS_PER_DAY` | Per-user daily cap for logged-in but email-unverified accounts (default `50`) |
| `DATABASE_URL` | PostgreSQL connection string (production only) |
| `REDIS_URL` | Redis for the cache layers and the Celery broker (default `redis://127.0.0.1:6379/0`) |
| `OPENAI_API_KEY` | OpenAI key for the LLM assistant (unset disables the feature) |
| `RESEND_API_KEY` | Resend SMTP key for transactional email |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts |
| `DEBUG` | `True` for development, `False` for production |
