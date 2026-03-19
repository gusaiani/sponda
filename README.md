# Sponda

Financial indicators for Brazilian stocks. Uses [BRAPI](https://brapi.dev) for financial data and IPCA inflation index.

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

## Stack

- **Backend:** Django 5 + Django REST Framework + PostgreSQL
- **Frontend:** React 19 + TypeScript + Vite + TanStack Query/Router
- **Styling:** Tailwind CSS v4 (`@apply` only — no utility classes in JSX)
- **Deploy:** Docker Compose + Nginx + GitHub Actions → `sponda.poe.ma`

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

A systemd timer (`sponda-refresh.timer`) runs daily at 06:00 UTC to refresh IPCA and ticker data from BRAPI. It is installed automatically on deploy. To check status:

```bash
systemctl status sponda-refresh.timer    # next run time
journalctl -u sponda-refresh.service     # last run logs
```

| Command | Purpose | Frequency |
|---|---|---|
| `refresh_ipca` | Sync IPCA inflation index | Daily |
| `refresh_tickers` | Sync B3 ticker list (~2,300 stocks) | Daily |

## Rate Limiting

Free tier allows 3 lookups per day, tracked by session cookie. After the limit, users are prompted to create an account.
