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
python manage.py refresh_ipca   # fetch IPCA data
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

## Rate Limiting

Free tier allows 3 lookups per day, tracked by session cookie. After the limit, users are prompted to create an account.
