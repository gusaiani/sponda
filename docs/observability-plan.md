# Observability Plan — Sponda

Greenfield observability setup. Low traffic today; pick free tiers, but structure the code so shipping to paid tools later is a config change, not a refactor.

## Stack recap

Django 5 + Celery (systemd timers, not Beat) + Next.js 16 static-exported into Django, single DO droplet (poe.ma), Postgres 15, Redis. Starting point: zero error tracking, default Django stderr logging, `/api/health/` already exists.

## Strategy

Lean on **Sentry** as the hub — one SDK family covers Django, Celery, Next.js, browser, perf, replay, crons. Supplement with purpose-built free tools only where Sentry is weak. Defer log aggregation and metrics stacks until pain appears — structure the logs now so that day is a config change, not a refactor.

---

## Phase 1 — Error + perf tracking (Sentry) — ✅ done

**Backend** (`backend/requirements.txt` + `config/settings/base.py`)
- Add `sentry-sdk[django,celery]`
- Init in `base.py` with `DjangoIntegration`, `CeleryIntegration`, `LoggingIntegration`
- `traces_sample_rate=1.0` at current traffic; drop later
- `environment` from `DJANGO_ENV`, `release` from git SHA injected at build
- `send_default_pii=False`, scrub `Authorization`, `Cookie`, `DATABASE_URL`
- DSN via `SENTRY_DSN` env var; **no-op when unset** (so dev + tests stay clean)

**Frontend** (`frontend/`)
- Add `@sentry/nextjs`
- `sentry.client.config.ts`, `sentry.server.config.ts`, `sentry.edge.config.ts`
- Session Replay at 10% sessions / 100% on error (free tier = 50/mo, safe at current traffic)
- Web Vitals auto-captured
- Source maps uploaded in build step (`next build`)

**Management commands & Celery tasks**
- Sentry's Celery integration auto-wraps tasks
- Management commands invoked by systemd timers: wrap `handle()` with `sentry_sdk.init` check + explicit `capture_exception` on failure (management commands don't go through middleware)

---

## Phase 2 — Structured logging (local only, ship-ready) — ✅ done

- Add `python-json-logger`
- Centralized `LOGGING` dict in `base.py`:
  - JSON formatter with `timestamp, level, logger, message, request_id, user_id, trace_id`
  - `django`, `django.request`, `celery`, app loggers all routed through it
- Request ID middleware: generate UUID per request, attach to log context + Sentry scope + response header `X-Request-ID`
- Still writes to stderr → journald captures it. No external shipping yet.
- **Why now**: free, and when we later add Grafana Loki / Axiom / BetterStack, it's `journalctl | promtail` with zero app changes.

---

## Phase 3 — Cron & uptime monitoring — ✅ done (code)

**Sentry monitor slugs wired** (set on `sentry_monitor_slug` of each `MonitoredCommand`):

| Command | Slug | Systemd unit |
|---|---|---|
| `send_revisit_reminders` | `sponda-revisit-reminders` | `sponda-revisit-reminders.timer` |
| `check_indicator_alerts` | `sponda-check-alerts` | `sponda-check-alerts.timer` |
| `refresh_ipca` | `sponda-refresh-ipca` | `sponda-refresh.timer` |
| `refresh_tickers` | `sponda-refresh-tickers` | `sponda-refresh.timer` |
| `refresh_snapshot_prices` | `sponda-refresh-snapshot-prices` | `sponda-refresh-snapshots.timer` |
| `refresh_snapshot_fundamentals` | `sponda-refresh-snapshot-fundamentals` | `sponda-refresh-fundamentals.timer` |

**Manual setup remaining** (one-time, outside the repo):
1. Create the Sentry project + obtain `SENTRY_DSN` and `NEXT_PUBLIC_SENTRY_DSN`.
2. In Sentry → Crons, confirm each monitor appears on first run and set expected schedules.
3. UptimeRobot free account → two monitors, 5-min interval: `https://sponda.capital/` and `https://sponda.capital/api/health/`.

**Systemd timers** (`sponda-refresh*`, `sponda-check-alerts`, `sponda-revisit-reminders`)
- **Decision**: Sentry Crons (one dashboard, one vendor). Check-in via `sentry_sdk.crons.monitor` decorator on the management command `handle()`.
- Alternative considered: Healthchecks.io — rejected to avoid a second dashboard.

**External uptime**
- **UptimeRobot free**: 5-min checks on `https://sponda.capital/` and `https://sponda.capital/api/health/`
- `/api/health/` already checks ticker + IPCA staleness — good signal

---

## Phase 4 — Server & DB (deferred, sketch only) — ⬜ not started

When traffic or cost justifies it:
- **Grafana Cloud free** (10k series, 50GB logs, 14d retention): run `grafana-agent` on the droplet, scrape node_exporter + nginx log + postgres_exporter + ship journald
- `pg_stat_statements` is already on — wire it to a Grafana dashboard later
- Not worth the config effort today at current traffic

---

## What we won't do (yet)

- No Datadog / New Relic (paid, overkill)
- No self-hosted Prometheus (ops burden)
- No log shipping (journald is fine at this volume)
- No Celery Beat migration (systemd timers are working)

## Env vars introduced

| Name | Where | Purpose |
|---|---|---|
| `SENTRY_DSN` | backend `.env` | Django + Celery Sentry DSN |
| `NEXT_PUBLIC_SENTRY_DSN` | frontend build | browser Sentry DSN |
| `SENTRY_AUTH_TOKEN` | CI/build only | source-map upload |
| `SENTRY_ENVIRONMENT` | both | `production` / `development` |
| `SENTRY_RELEASE` | both | git SHA |

## TDD approach (per project standards)

- Unit tests for: request-ID middleware, JSON log formatter output shape, Sentry init no-op when DSN unset, scrubbing hook redacts expected fields
- Not tested (third-party surface): that Sentry actually delivers — verified manually by triggering a test error in staging

## Rollout order

1. Phase 1 backend (smallest blast radius, highest ROI)
2. Phase 1 frontend
3. Phase 2 structured logging
4. Phase 3 crons + uptime
5. README doc update (per global instructions)

## Status legend

- ⬜ not started
- ⏳ in progress
- ✅ done
