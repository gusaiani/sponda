# Sponda

Financial indicators and analytics for global public companies. Live at [sponda.capital](https://sponda.capital).

![Sponda homepage](docs/screenshot.png)

## Indicators

### PE10 (Shiller P/E)

Smooths earnings volatility by averaging 10 years of inflation-adjusted net income. More reliable than single-year P/E for identifying overvalued or undervalued companies.

```
PE10 = Market Cap / Average Inflation-Adjusted Annual Net Income (10 years)
```

### PFCF10 (Price/Free Cash Flow 10-year)

Same 10-year averaging approach, but using free cash flow instead of earnings. Reveals whether reported profits translate into real cash generation.

```
PFCF10 = Market Cap / Average Inflation-Adjusted Annual FCF (10 years)
FCF = Operating Cash Flow + Investing Cash Flow
```

### Dívida Bruta / PL (Gross Debt to Equity)

Point-in-time ratio measuring how much of the company's capital structure is financed by debt relative to shareholders' equity. Uses the most recent balance sheet.

```
Dívida Bruta / PL = Total Debt / Stockholders' Equity
```

**Debt source (Brazilian tickers):** historical debt per balance sheet comes from BRAPI's `balanceSheetHistory` (`loansAndFinancing + longTermLoansAndFinancing`). For the most recent quarter, we additionally query BRAPI's `financialData.totalDebt` — a broader figure that also includes debentures, financial leases, and other interest-bearing obligations. When `financialData.totalDebt` is larger (or when balance-sheet loans are zero because BRAPI's raw fields are incomplete, as happens on many mid/small caps and banks), we override the latest row's `total_debt` with it. We never downgrade. If `financialData` reports `totalDebt=None` (typical of banks, whose liabilities are deposits rather than loans) the leverage card shows "not available" instead of a misleading zero.

### Passivo / PL (Liabilities to Equity)

Broader measure that considers all obligations (not just financial debt) relative to equity. Includes suppliers, taxes, provisions, etc.

```
Passivo / PL = Total Liabilities / Stockholders' Equity
```

### Multiples History Chart

Dual-panel chart showing historical adjusted prices alongside year-end P/L (Price/Earnings) and P/FCL (Price/Free Cash Flow) multiples. Helps visualize how a company's valuation has evolved over time relative to its stock price.

**How it works:**
- Fetches monthly historical prices from BRAPI (`range=max&interval=1mo`)
- Approximates shares outstanding as `market_cap / current_price`
- For each year with earnings/FCF data, calculates the year-end multiple: `(year_end_price × shares) / net_income` (or FCF)
- Years with negative earnings or FCF show as gaps in the chart
- Top panel shows adjusted prices (monthly); bottom panel shows the selected multiple (annual)
- Toggle between P/L and P/FCL with pill buttons

**API endpoint:** `GET /api/quote/<ticker>/multiples-history/`

## Performance

### Database

- **Trigram indexes** (pg_trgm) on `Ticker.display_name` and `symbol` for sub-millisecond ILIKE search across 27K+ tickers
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

### Frontend

- **Search debounce** at 300ms to reduce API calls during typing
- **Dynamic imports** via `next/dynamic` for CompanyMetricsCard, MultiplesChart (Recharts), CompareTab, FundamentalsTab, and CompanyAnalysis. Recharts (~100KB) only loads when the Charts tab is opened.
- **Prefetch on hover**: hovering over Fundamentos or Graficos tabs triggers `queryClient.prefetchQuery()`, so data is ready before the user clicks
- **Self-hosted Satoshi font**: eliminates the 1.15s Fontshare external request
- **30-minute staleTime** on React Query hooks; SSR revalidation at 1 hour
- **Lazy-loaded images** on all company logos; footer logo served via Next.js `<Image>` with WebP optimization
- **useMemo** on frequently recomputed derived state (excludeSet, sectorPeerLinks)

### International SEO

Locale-prefixed URLs serve region-specific metadata to search engines:

- `/pt/PETR4/fundamentos` · Portuguese metadata, `<html lang="pt-BR">`, OG locale `pt_BR`
- `/en/PETR4/fundamentals` · English metadata, `<html lang="en">`, OG locale `en_US`
- Bare URLs (`/PETR4`) 301-redirect to the locale-prefixed version based on `Accept-Language`
- Every page includes `<link rel="alternate" hreflang>` cross-links between locales
- Tab URL paths are localized: fundamentos/fundamentals, comparar/compare, graficos/charts
- Auto-generated sitemap with both locale variants for every ticker and tab
- `x-default` hreflang points to English

### Query optimization

- **N+1 fix** in AdminDashboard: replaced per-user loops with `annotate(Count(...))` (1,200+ queries down to 1)
- **CompanyAnalysisView**: 3 queries reduced to 1 with `.values()`

## Stack

- **Backend:** Django 5 + Django REST Framework + PostgreSQL + Redis
- **Frontend:** React 19 + TypeScript + Next.js 15 + TanStack Query
- **Styling:** Tailwind CSS v4 (`@apply` only -- no utility classes in JSX)
- **Deploy:** GitHub Actions CI/CD → DigitalOcean VPS

## Local Development

### Prerequisites

- Python 3.12+
- Node.js 20+
- A [BRAPI](https://brapi.dev) API key

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
| `BRAPI_API_KEY` | BRAPI pro API key |
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

## Scheduled Tasks

Systemd timers run periodic jobs. Each timer is installed and enabled automatically on deploy. To inspect:

```bash
systemctl list-timers --all              # all timers, next/last run
journalctl -u sponda-refresh.service     # last run logs for a unit
```

| Command | Timer | Purpose | Frequency |
|---|---|---|---|
| `refresh_ipca` + `refresh_tickers` | `sponda-refresh.timer` | Sync IPCA inflation index and B3 ticker list (~2,300 stocks) from BRAPI | Daily 06:00 UTC |
| `send_revisit_reminders` | `sponda-revisit-reminders.timer` | Email users whose scheduled company revisits are due or overdue | Daily 11:00 UTC |

The reminder service is `Type=oneshot` with `Restart=on-failure` (up to 3 retries 120s apart) so a transient SMTP error doesn't silently drop a day of notifications. The timer is `Persistent=true`, so a missed run (e.g. server reboot) catches up on next boot. Long-running services (`sponda`, `sponda-frontend`) use `Restart=always`.

## Rate Limiting

Free tier allows 3 lookups per day, tracked by session cookie. After the limit, users are prompted to create an account.
