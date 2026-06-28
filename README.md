# Sponda

Financial indicators and analytics for global public companies. Over 23,000 companies listed across the U.S. and Brazil. Live at
<a href="https://sponda.capital" target="_blank" rel="noopener noreferrer">sponda.capital</a>.
.

![Sponda homepage](docs/screenshot.png)

## Performance

### Database

- **Trigram indexes** (pg_trgm) on `Ticker.display_name` and `symbol` for sub-millisecond ILIKE search across 23K+ tickers
- **Composite indexes** on `CompanyAnalysis(ticker, -generated_at)`, `LookupLog(user, timestamp)`, `LookupLog(session_key, timestamp)`
- **PostgreSQL tuning** for SSD + 2 GB RAM: `shared_buffers=512MB`, `work_mem=8MB`, `random_page_cost=1.1`
- **pg_stat_statements** enabled for query performance monitoring

### Caching (Redis)

Three-layer caching strategy eliminates redundant external API calls:

**Layer 1 · Provider cache** (in `providers.py`): raw external API responses (BRAPI/FMP) are cached at the routing layer, so multiple views that need the same data (e.g. `fetch_quote`, `fetch_historical_prices`) share a single external call.

| Provider call | TTL |
|---|---|
| `fetch_quote` | 15 min |
| `fetch_historical_prices` | 1 hour |
| `fetch_dividends` | 1 hour |

**Layer 2 · View cache**: computed results for each API endpoint.

| Endpoint | TTL | What it avoids |
|---|---|---|
| Ticker list (27K rows) | 1 hour | Full table scan on every page load |
| Search results | 2 min | Trigram query + sorting per keystroke |
| PE10 metrics | 4 hours | 6+ DB queries + external API call + inflation adjustment |
| Fundamentals | 6 hours | All balance sheets, earnings, cash flows + IPCA table + external API |
| Multiples history | 6 hours | 2 sequential external API calls (was 8s uncached) |

**Layer 3 · Cache warming**: `python manage.py warm_cache` pre-populates all three endpoints for the top 50 most-queried tickers. Run every 4 hours via cron so popular tickers are always served from cache.

### Home page fanout (May 2026 rewrite)

The home page renders ~30 tickers (favorites + saved lists). Before this rewrite each visit fired ~60 parallel HTTP requests (PE10 + Fundamentals × ticker), and every request whose data was older than 24h paid for ~3 sequential provider syncs inside the user's request thread. End result: the first paint waited on a long tail of cold-cache calls, and "warming the cache" took ages.

The current architecture, in the order each layer fires:

1. **Server-rendered shell** — `app/[locale]/page.tsx` is an async Server Component (`force-dynamic`). It forwards the user's session cookie to Django, prefetches favorites + saved lists + the batch quote endpoint, and dehydrates the React Query cache into a `<HydrationBoundary>`. The browser receives populated cards in the first byte; no spinner.
2. **`POST /api/quotes/batch/`** — one request returns every ticker the home page needs. Server fans out internally over a `ThreadPoolExecutor`. Replaces the 30-way client-side fanout. Capped at 100 tickers per request. Defined in `quotes/views.py::BatchQuotesView`; consumed via `useQuotesBatch`.
3. **Stale-while-revalidate refresh** — `_ensure_fresh_data` returns immediately when stale data exists and enqueues `quotes.tasks.refresh_provider_data` (Celery) to re-pull from BRAPI/FMP in the background. Only outright cold tickers pay the synchronous provider cost.
4. **Persisted React Query cache** — `@tanstack/react-query-persist-client` mirrors the cache to `localStorage` with a 24h `maxAge`. Returning visitors paint from disk instantly while a soft revalidation runs in the background.
5. **Cache warming, favorites-aware** — `python manage.py warm_cache` now sources tickers from every active user's favorites + saved lists (in addition to LookupLog popularity), runs across 8 worker threads, and skips tickers whose `pe10:<T>` cache is already warm. The 0.5s `time.sleep` per ticker is gone.
6. **Provider circuit breakers + tight timeouts** — every BRAPI/FMP/FRED call goes through `quotes.circuit_breaker.CircuitBreaker` with `(connect, read) = (3, 8)` timeouts. After N consecutive failures the breaker opens for ~60s, short-circuiting subsequent calls instead of pinning a worker for 30s on each one.
7. **`Cache-Control: public, max-age=3600`** on PE10View + the batch endpoint, so repeat-tab visits skip the round-trip entirely. Logos bumped to `max-age=31536000, stale-while-revalidate=604800` since they rotate at most once a year.
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
- `INDEXABLE_LOCALES` (every supported locale minus the noindex set) drives the hreflang alternates in both the layout and the sitemap (`frontend/src/app/sitemap.ts`), so a noindexed locale is never advertised as a crawlable alternate.

`noindex` only affects compliant search engines — it does not stop scrapers (they ignore robots directives). To add or remove a noindex locale, edit `NOINDEX_LOCALES` and the unit tests in `frontend/src/lib/i18n-config.test.ts`.

#### OG images

OG images are static JPEGs under `frontend/public/images/`:

- `sponda-og.jpg` · Portuguese tagline, used for `/pt/*` URLs
- `sponda-og-en.jpg` · English tagline, used for every other locale

`getOgImageUrl(locale)` in `frontend/src/lib/metadata.ts` selects the right image; both the homepage layout and `generateTickerMetadata` go through it. Only PT and EN images exist today because most crawlers cache a single OG image per URL and maintaining one per-locale wasn't worth the churn. If you need a new localized image, drop `sponda-og-<locale>.jpg` into `public/images/` and extend the helper.

#### Sitemaps

Two sitemaps are emitted; both advertise URLs with full `xhtml:link rel="alternate" hreflang` alternates across the indexable locales (noindex locales such as `zh` are omitted from the alternates — see "Noindex locales" above):

- `/sitemap.xml` · Next.js, generated by `frontend/src/app/sitemap.ts` (production source of truth — Nginx routes the root `/sitemap.xml` to Next.js on port 3100)
- `/api/sitemap.xml` · Django, generated by `SitemapView` in `backend/quotes/views.py` (fallback / API consumers)

Both use shared constants: canonical tab keys (`charts`, `fundamentals`, `compare`) map to localized slugs in `SITEMAP_TAB_SLUGS` (backend) and `tabSlugForLocale` (frontend). Keep these in sync when adding a new locale.

## Peer comparison

The Compare tab on each company page lists up to 10 peer tickers ranked by how close they are to the source company. Ranking uses four tiers of signal, applied in order:

1. **Subsector within the same sector** — companies whose business line maps to the same subsector as the source (e.g. VALE3 and GGBR4 both map to *Mineração e Siderurgia*, while KLBN4 maps to *Papel e Celulose*).
2. **Other subsectors in the same sector** — fills remaining slots when subsector peers aren't enough.
3. **Adjacent sectors** — only considered when the sector itself has too few candidates (see `ADJACENT_SECTORS` in `backend/quotes/views.py`).
4. **Country, then market cap** — within a tier, same-country peers come first; within same-country, larger market cap comes first.

Subsector inference is pattern-based: a per-sector list of regexes in `SUBSECTOR_RULES` (Finance, Non-Energy Minerals, Process Industries, Retail Trade, Transportation, Utilities, etc.) matches against the company name. Unmatched companies fall back to a default subsector label per sector. No schema change — the subsector is derived at query time.

**API:** `GET /api/tickers/<symbol>/peers/`

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
  longer resets the cap.
- Over-cap requests get `429` with `{"code": "lookup_limit", ...}` and
  `Cache-Control: no-store`; no payload is computed and no quota is
  burned. Because the response now varies by IP/quota state,
  `/api/quote/*` is **not** edge-cacheable — keep it off any Cloudflare
  Cache Rule.
- Frontend: a `429 lookup_limit` throws `LookupLimitError`. Anonymous
  users get the login/signup modal; logged-in-unverified users get the
  email-verification prompt (they already have an account).

## Assistant (LLM Q&A)

Centered text-area at the bottom of the company page; streaming OpenAI-powered answers,
guardrailed to Sponda's finance domain, with tiered per-day quotas. Superuser-only in v1.
See [LLM_ASSISTANT.md](LLM_ASSISTANT.md).

## Stack

- **Backend:** Django 5 + Django REST Framework + PostgreSQL + Redis
- **Frontend:** React 19 + TypeScript + Next.js 15 + TanStack Query
- **Styling:** Tailwind CSS v4 (`@apply` only -- no utility classes in JSX)
- **Deploy:** GitHub Actions CI/CD → DigitalOcean VPS

## Local Development

### Prerequisites

- Python 3.12+
- Node.js 20+
- A [BRAPI](https://brapi.dev) API key (Brazilian tickers)
- An [FMP](https://site.financialmodelingprep.com) API key (US tickers)

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
python manage.py runserver
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` requests to Django on `localhost:8000`.

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
| `ALLOWED_HOSTS` | Comma-separated allowed hosts |
| `DEBUG` | `True` for development, `False` for production |

## Deployment

Pushes to `main` trigger a GitHub Actions workflow that SSHs to `poe.ma`, pulls the latest code, rebuilds Docker containers, runs migrations, and restarts services.

### Manual Deploy

```bash
ssh root@poe.ma
cd /opt/sponda
git pull
docker compose build
docker compose run --rm web python manage.py migrate --noinput
docker compose up -d
```

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

Tags and categories auto-generate index pages at `/tags/*` and `/categories/*`. RSS feed is auto-generated at `/index.xml`.

### One-time server setup

Before `blog.sponda.capital` is reachable, the droplet needs:

1. DNS: `A` record `blog.sponda.capital → 159.203.108.19`.
2. `certbot --nginx -d blog.sponda.capital` (after DNS propagates).
3. `ln -sf /etc/nginx/sites-available/blog.sponda.capital.conf /etc/nginx/sites-enabled/`.
4. `nginx -t && systemctl reload nginx`.

Hugo itself is auto-installed by the deploy workflow if missing — no manual `apt install` needed.

Every subsequent `git push` to `main` rebuilds and publishes automatically.

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

The reminder service is `Type=oneshot` with `Restart=on-failure` (up to 3 retries 120s apart) so a transient SMTP error doesn't silently drop a day of notifications. The timer is `Persistent=true`, so a missed run (e.g. server reboot) catches up on next boot. Long-running services (`sponda`, `sponda-frontend`) use `Restart=always`.

## Cross-currency indicators

Foreign-domiciled companies (NVO, ASML, TM, BABA, ...) trade in USD on US exchanges but file their financials in their home currency (DKK, EUR, JPY, CNY, ...). Any market-cap-based indicator (PE10, PFCF10, PEG, P/FCF PEG, multiples-history chart) translates the market cap into the **statement currency** before dividing by earnings/FCF, so the ratio is dimensionally coherent.

**Pipeline:**

- `Ticker.reported_currency` is populated by `fmp.sync_earnings` from each statement's `reportedCurrency` (BRL hardcoded for Brazilian tickers).
- `FxRate` stores daily USD↔X close rates from FMP, back to 2010. Refreshed daily by `sync_fx_rates` (timer: `sponda-refresh-fx.timer`).
- `CountryCPIIndex` stores monthly per-country CPI YoY rates from FRED for inflation-adjusting historical fundamentals in non-USD/non-BRL currencies. Currency→FRED-series mapping in `quotes/fred.py::CURRENCY_TO_SERIES_ID`.
- `quotes/fx.py::market_cap_in_reported_currency` is the bridge used by every indicator calculator.
- `quotes/inflation.py::get_inflation_adjustment_factors` dispatches: BRL → IPCA, USD → USCPI, everything else → CountryCPIIndex.

**Coverage audit:** `python manage.py audit_currencies` lists every (listing, reported) pair, flags reporting currencies missing FX history, and flags currencies missing a FRED series mapping.

**Multiples-history chart:** when historical FX is unavailable for any year on the chart, falls back to the latest FX rate uniformly and surfaces `currency_warning=true` in the API; the frontend renders a banner explaining the approximation.

Full design rationale, scope, and the bug it fixes: `docs/cross-currency-fix-plan.md`.

## Observability

Unified error, performance, and cron monitoring through Sentry (free tier) plus UptimeRobot for external health checks. Full plan and rollout status: `docs/observability-plan.md`.

**How it works**

- **Django + Celery.** `config.observability.init_sentry` runs from `settings/base.py`. It is a no-op when `SENTRY_DSN` is unset, so dev and tests stay quiet. `before_send` scrubs `Authorization`, `Cookie`, `Set-Cookie`, `DATABASE_URL`, and `SECRET_KEY` from events. Integrations: `DjangoIntegration`, `CeleryIntegration`, `LoggingIntegration` (INFO breadcrumbs, ERROR-level events).
- **Systemd-timer commands.** Subclass `config.monitored_command.MonitoredCommand` and implement `run()` instead of `handle()`. The base class captures any unhandled exception to Sentry and re-raises (so systemd still marks the unit as failed). Setting `sentry_monitor_slug` wraps execution in `sentry_sdk.crons.monitor`, so Sentry Crons alerts you when a timer misses or fails. All six timer-invoked commands (`refresh_ipca`, `refresh_tickers`, `refresh_snapshot_prices`, `refresh_snapshot_fundamentals`, `check_indicator_alerts`, `send_revisit_reminders`) use this base.
- **Next.js.** `@sentry/nextjs` is wired up via `sentry.client.config.ts`, `sentry.server.config.ts`, `sentry.edge.config.ts`, all delegating to `src/lib/sentry.ts`. `withSentryConfig` in `next.config.ts` handles source-map upload at build time. Session Replay: 10% of sessions + 100% of error sessions (within free-tier quota).
- **Request IDs.** `config.middleware.request_id.RequestIDMiddleware` attaches a UUID to every request (or honors an inbound `X-Request-ID`, capped at 128 chars). The ID is echoed back in the `X-Request-ID` response header, tagged on the Sentry scope, and included in every JSON log line emitted during the request.
- **Structured logging.** `config.logging_formatter.JSONLogFormatter` emits one JSON object per log record (`timestamp`, `level`, `logger`, `message`, `request_id`, `exception`). Writes to stderr → captured by journald on production. No external log shipping yet; when we want it, point Promtail/Vector at the journal.
- **External uptime.** UptimeRobot (free) hits `https://sponda.capital/` and `https://sponda.capital/api/health/` every 5 minutes. Setup is manual, outside the repo.

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

## Screener

The screener page at `/[locale]/screener` lets users filter the whole B3 universe by any of the indicators shown on a company's main page and sort the results. Backed by a dedicated `IndicatorSnapshot` table so filtering and sorting are one DB query instead of recomputing indicators for every ticker on every request.

### Supported filters

All are numeric `min` / `max` bounds (either side optional):

- `pe10`, `pfcf10` · valuation multiples (10-year rolling)
- `peg`, `pfcf_peg` · growth-adjusted valuation
- `debt_to_equity`, `debt_ex_lease_to_equity`, `liabilities_to_equity`, `current_ratio` · leverage / liquidity
- `debt_to_avg_earnings`, `debt_to_avg_fcf` · debt vs. cash generation
- `market_cap` · absolute currency amount

### How it works

1. **Snapshot table.** `IndicatorSnapshot` (one row per ticker) stores the latest value of every screened indicator. The table is kept current by a **three-layer refresh strategy** designed to respect BRAPI Pro and FMP Starter monthly budgets:
   - **Persist-on-view.** Any time a user opens a company page, the `PE10View` endpoint writes the freshly computed indicators back into `IndicatorSnapshot` and updates `Ticker.market_cap` as a side-effect (wrapped in `try/except` so a write failure never breaks the page). This keeps actively viewed tickers perpetually fresh without any scheduled work.
   - **Daily price refresh** (`refresh_snapshot_prices`, 07:00 UTC). For every ticker with a market cap, fetches the current quote (one API call) and recomputes only the price-dependent indicators — PE10, PFCF10, PEG, P/FCF PEG — against existing DB fundamentals. Leverage and debt-coverage fields are left alone.
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

## Localized account emails

Welcome and email-verification messages are rendered in the new user's preferred language. The `User.language` field (`accounts.models.User`, one of `pt`, `en`, `es`, `zh`, `fr`, `de`, `it`, default `en`) drives template selection.

At signup the frontend (`AuthModal.tsx` and `[locale]/login/page.tsx`) sends the current UI locale as `language` in the POST body. If the field is missing, `SignupView._parse_accept_language` picks the highest-q supported locale from the `Accept-Language` header, falling back to `en`. Any later verification resend (`/api/auth/resend-verification/`, change-email flow) reuses the value stored on the user.

Templates live under `backend/accounts/templates/emails/`:

- `welcome_base.html` / `verification_base.html` — shared HTML shell with `{% block %}` placeholders for every translatable string.
- `welcome_<lang>.html` / `verification_<lang>.html` — per-locale overrides (`extends` the base, fills blocks).
- `welcome_<lang>.txt` / `verification_<lang>.txt` — plain-text bodies per locale.

Subjects and localized share-link copy live in `accounts/email_subjects.py`. The sender (`accounts.views._send_welcome_email` / `_send_verification_email`) resolves the language via `_resolve_language`, renders the matching templates with `render_to_string`, and passes the localized subject.

To add a new locale: register it in `SUPPORTED_LANGUAGES` (`accounts/models.py`), add a row to both subject dicts and `share_strings` in `email_subjects.py`, and create the four template files (`welcome_<lang>.html`, `welcome_<lang>.txt`, `verification_<lang>.html`, `verification_<lang>.txt`).

## Social (Sponds)

Users can post short messages — **Sponds** — follow each other, mute, block, and reply to threads. The feature lives under `/api/social/` (backend) and `frontend/src/components/social/` (frontend).

### What it does

- **Compose**: 500-char Sponds with optional `$TICKER` tag and `@handle` mentions. Mentions are extracted server-side and trigger notifications.
- **Engage**: like, reply (one-level threads), edit within 5 minutes, soft-delete with thread tombstones. A Spond and its replies render nested inside one box (`SpondThread`). On the permalink page the reply composer is hidden until "Responder" is clicked; in feeds/sidebar replies are collapsed behind a "show replies" toggle that lazy-loads the thread.
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
