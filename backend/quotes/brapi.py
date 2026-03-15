"""BRAPI API client for fetching stock data and IPCA index."""
from datetime import date
from decimal import Decimal

import requests
from django.conf import settings

from .models import BalanceSheet, IPCAIndex, QuarterlyCashFlow, QuarterlyEarnings


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


def fetch_cash_flow_statements(ticker: str) -> list[dict]:
    """Fetch cash flow statement history for a ticker.

    Tries quarterly first; falls back to annual if the BRAPI plan
    doesn't include the quarterly module.
    """
    # Try quarterly first
    try:
        data = _get(
            f"/quote/{ticker}",
            params={"modules": "cashflowHistoryQuarterly"},
        )
        if not data.get("error"):
            results = data.get("results", [])
            if results:
                statements = results[0].get("cashflowHistoryQuarterly", [])
                if statements:
                    return statements
    except BRAPIError:
        pass

    # Fall back to annual
    data = _get(
        f"/quote/{ticker}",
        params={"modules": "cashflowHistory"},
    )
    results = data.get("results", [])
    if not results:
        raise BRAPIError(f"No results for ticker {ticker}")
    return results[0].get("cashflowHistory", [])


def sync_cash_flows(ticker: str) -> list[QuarterlyCashFlow]:
    """Fetch and store cash flow data for a ticker from BRAPI."""
    statements = fetch_cash_flow_statements(ticker)
    cash_flows = []

    for stmt in statements:
        end_date_str = stmt.get("endDate", "")[:10]
        if not end_date_str:
            continue

        end_date = date.fromisoformat(end_date_str)

        operating_cf = stmt.get("operatingCashFlow")
        if operating_cf is not None:
            operating_cf = int(operating_cf)

        investment_cf = stmt.get("investmentCashFlow")
        if investment_cf is not None:
            investment_cf = int(investment_cf)

        obj, _ = QuarterlyCashFlow.objects.update_or_create(
            ticker=ticker.upper(),
            end_date=end_date,
            defaults={
                "operating_cash_flow": operating_cf,
                "investment_cash_flow": investment_cf,
            },
        )
        cash_flows.append(obj)

    return cash_flows


def fetch_balance_sheets(ticker: str) -> list[dict]:
    """Fetch balance sheet history for a ticker.

    Tries quarterly first; falls back to annual if the BRAPI plan
    doesn't include the quarterly module.
    """
    # Try quarterly first
    try:
        data = _get(
            f"/quote/{ticker}",
            params={"modules": "balanceSheetHistoryQuarterly"},
        )
        if not data.get("error"):
            results = data.get("results", [])
            if results:
                statements = results[0].get("balanceSheetHistoryQuarterly", [])
                if statements:
                    return statements
    except BRAPIError:
        pass

    # Fall back to annual
    data = _get(
        f"/quote/{ticker}",
        params={"modules": "balanceSheetHistory"},
    )
    results = data.get("results", [])
    if not results:
        raise BRAPIError(f"No results for ticker {ticker}")
    return results[0].get("balanceSheetHistory", [])


def sync_balance_sheets(ticker: str) -> list[BalanceSheet]:
    """Fetch and store balance sheet data for a ticker from BRAPI."""
    statements = fetch_balance_sheets(ticker)
    sheets = []

    for stmt in statements:
        end_date_str = stmt.get("endDate", "")[:10]
        if not end_date_str:
            continue

        end_date = date.fromisoformat(end_date_str)

        # Gross debt: loans + financing (current + non-current) + lease financing
        loans_current = stmt.get("loansAndFinancing")
        loans_long = stmt.get("longTermLoansAndFinancing")
        lease_current = stmt.get("leaseFinancing")
        lease_long = stmt.get("longTermLeaseFinancing")
        debt_parts = [loans_current, loans_long, lease_current, lease_long]
        if any(p is not None for p in debt_parts):
            total_debt = sum(int(p) for p in debt_parts if p is not None)
        else:
            total_debt = None

        # Total liabilities: current + non-current
        # (BRAPI's totalLiab field is unreliable — equals totalAssets)
        current_liab = stmt.get("currentLiabilities")
        noncurrent_liab = stmt.get("nonCurrentLiabilities")
        if current_liab is not None or noncurrent_liab is not None:
            total_liab = int(current_liab or 0) + int(noncurrent_liab or 0)
        else:
            total_liab = None

        equity = stmt.get("shareholdersEquity")
        if equity is not None:
            equity = int(equity)

        obj, _ = BalanceSheet.objects.update_or_create(
            ticker=ticker.upper(),
            end_date=end_date,
            defaults={
                "total_debt": total_debt,
                "total_liabilities": total_liab,
                "stockholders_equity": equity,
            },
        )
        sheets.append(obj)

    return sheets


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
