"""BRAPI API client for fetching stock data and IPCA index."""
from datetime import date
from decimal import Decimal

import requests
from django.conf import settings

from .models import IPCAIndex, QuarterlyEarnings


class BRAPIError(Exception):
    pass


def _get(endpoint: str, params: dict | None = None) -> dict:
    params = params or {}
    params["token"] = settings.BRAPI_API_KEY
    url = f"{settings.BRAPI_BASE_URL}{endpoint}"
    response = requests.get(url, params=params, timeout=30)
    if response.status_code != 200:
        raise BRAPIError(
            f"BRAPI returned {response.status_code}: {response.text[:200]}"
        )
    return response.json()


def fetch_quote(ticker: str) -> dict:
    """Fetch current quote data for a ticker."""
    data = _get(f"/quote/{ticker}")
    results = data.get("results", [])
    if not results:
        raise BRAPIError(f"No results for ticker {ticker}")
    return results[0]


def fetch_income_statements(ticker: str) -> list[dict]:
    """Fetch quarterly income statement history for a ticker."""
    data = _get(
        f"/quote/{ticker}",
        params={"modules": "incomeStatementHistoryQuarterly"},
    )
    results = data.get("results", [])
    if not results:
        raise BRAPIError(f"No results for ticker {ticker}")

    statements = (
        results[0]
        .get("incomeStatementHistoryQuarterly", {})
        .get("incomeStatementHistory", [])
    )
    return statements


def sync_quarterly_earnings(ticker: str) -> list[QuarterlyEarnings]:
    """Fetch and store quarterly earnings for a ticker from BRAPI."""
    statements = fetch_income_statements(ticker)
    earnings = []

    for stmt in statements:
        end_date_raw = stmt.get("endDate", {})
        if isinstance(end_date_raw, dict):
            fmt = end_date_raw.get("fmt")
        else:
            fmt = str(end_date_raw)[:10]

        if not fmt:
            continue

        end_date = date.fromisoformat(fmt)
        eps_raw = stmt.get("basicEarningsPerCommonShare", {})
        eps_value = None
        if isinstance(eps_raw, dict):
            raw = eps_raw.get("raw")
            if raw is not None:
                eps_value = Decimal(str(raw))
        elif eps_raw is not None:
            eps_value = Decimal(str(eps_raw))

        net_income_raw = stmt.get("netIncome", {})
        net_income_value = None
        if isinstance(net_income_raw, dict):
            raw = net_income_raw.get("raw")
            if raw is not None:
                net_income_value = int(raw)
        elif net_income_raw is not None:
            net_income_value = int(net_income_raw)

        obj, _ = QuarterlyEarnings.objects.update_or_create(
            ticker=ticker.upper(),
            end_date=end_date,
            defaults={
                "eps": eps_value,
                "net_income": net_income_value,
            },
        )
        earnings.append(obj)

    return earnings


def fetch_ipca_data() -> list[dict]:
    """Fetch IPCA accumulated index from BRAPI."""
    data = _get("/v2/inflation/prime-rate/historical")
    return data.get("primeRate", [])


def sync_ipca() -> int:
    """Fetch IPCA data from BRAPI and store in DB. Returns number of records synced."""
    records = fetch_ipca_data()
    count = 0
    for record in records:
        record_date = record.get("date", "")[:10]
        value = record.get("value")
        if not record_date or value is None:
            continue

        IPCAIndex.objects.update_or_create(
            date=date.fromisoformat(record_date),
            defaults={"accumulated_index": Decimal(str(value))},
        )
        count += 1
    return count
