# Sponda

PE10 (Shiller P/E) calculator for Brazilian stocks. Uses [BRAPI](https://brapi.dev) for financial data and IPCA inflation index.

## What is PE10?

PE10 (also known as CAPE or Shiller P/E) smooths earnings volatility by averaging 10 years of inflation-adjusted earnings per share (EPS). This makes it more reliable than single-year P/E ratios for identifying overvalued or undervalued companies.

```
PE10 = Current Price / Average Inflation-Adjusted Annual EPS (10 years)
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
