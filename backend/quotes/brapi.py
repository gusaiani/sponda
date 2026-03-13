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
    """Fetch income statement history for a ticker.

    Tries quarterly first; falls back to annual if the BRAPI plan
    doesn't include the quarterly module.
    """
    # Try quarterly first
    try:
        data = _get(
            f"/quote/{ticker}",
            params={"modules": "incomeStatementHistoryQuarterly"},
        )
        if not data.get("error"):
            results = data.get("results", [])
            if results:
                statements = results[0].get("incomeStatementHistoryQuarterly", [])
                if statements:
                    return statements
    except BRAPIError:
        pass

    # Fall back to annual
    data = _get(
        f"/quote/{ticker}",
        params={"modules": "incomeStatementHistory"},
    )
    results = data.get("results", [])
    if not results:
        raise BRAPIError(f"No results for ticker {ticker}")
    return results[0].get("incomeStatementHistory", [])


def sync_earnings(ticker: str) -> list[QuarterlyEarnings]:
    """Fetch and store earnings for a ticker from BRAPI.

    Works with both quarterly and annual income statements.
    """
    statements = fetch_income_statements(ticker)
    earnings = []

    for stmt in statements:
        end_date_str = stmt.get("endDate", "")[:10]
        if not end_date_str:
            continue

        end_date = date.fromisoformat(end_date_str)

        eps_value = None
        eps_raw = stmt.get("basicEarningsPerCommonShare")
        if eps_raw is not None:
            eps_value = Decimal(str(eps_raw))

        net_income_value = None
        net_income_raw = stmt.get("netIncome")
        if net_income_raw is not None:
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
    """Fetch IPCA historical data from BRAPI."""
    data = _get("/v2/inflation", params={"country": "ipca", "historical": "true"})
    return data.get("inflation", [])


def sync_ipca() -> int:
    """Fetch IPCA data from BRAPI and store in DB. Returns number of records synced."""
    records = fetch_ipca_data()
    count = 0
    for record in records:
        date_str = record.get("date", "")
        value = record.get("value")
        if not date_str or value is None:
            continue

        # BRAPI returns dates as "dd/mm/yyyy"
        day, month, year = date_str.split("/")
        record_date = date(int(year), int(month), int(day))

        IPCAIndex.objects.update_or_create(
            date=record_date,
            defaults={"annual_rate": Decimal(str(value))},
        )
        count += 1
    return count
