"""FMP (Financial Modeling Prep) API client for fetching US stock data."""
from datetime import date
from decimal import Decimal

import requests
from django.conf import settings

from .models import BalanceSheet, QuarterlyCashFlow, QuarterlyEarnings, USCPIIndex


class FMPError(Exception):
    pass


def _get(endpoint: str, params: dict | None = None) -> dict | list:
    params = params or {}
    params["apikey"] = settings.FMP_API_KEY
    url = f"{settings.FMP_BASE_URL}{endpoint}"
    response = requests.get(url, params=params, timeout=30)
    if response.status_code != 200:
        raise FMPError(
            f"FMP returned {response.status_code}: {response.text[:200]}"
        )
    return response.json()


def fetch_etf_symbols() -> set[str]:
    """Fetch all ETF symbols from FMP to use as an exclusion set."""
    data = _get("/stable/etf-list")
    if not isinstance(data, list):
        return set()
    return {
        (entry.get("symbol") or "").upper()
        for entry in data
        if entry.get("symbol")
    }


def fetch_quote(ticker: str) -> dict:
    """Fetch current quote data for a US ticker."""
    data = _get("/stable/quote", params={"symbol": ticker})
    if not data:
        raise FMPError(f"No results for ticker {ticker}")
    return data[0]


FMP_BATCH_SIZE = 100


def fetch_quotes_batch(tickers: list[str]) -> dict[str, dict]:
    """Fetch current quote data for multiple US tickers.

    FMP accepts comma-separated symbols: /stable/quote?symbol=AAPL,MSFT,...
    Large lists are chunked to avoid URL length limits. Returns a dict
    keyed by uppercase symbol.
    """
    if not tickers:
        return {}
    results: dict[str, dict] = {}
    for chunk_start in range(0, len(tickers), FMP_BATCH_SIZE):
        chunk = tickers[chunk_start : chunk_start + FMP_BATCH_SIZE]
        data = _get("/stable/quote", params={"symbol": ",".join(chunk)})
        if not isinstance(data, list):
            continue
        for quote in data:
            symbol = (quote.get("symbol") or "").upper()
            if symbol:
                results[symbol] = quote
    return results


def fetch_income_statements(ticker: str) -> list[dict]:
    """Fetch quarterly income statements for a US ticker."""
    return _get(
        "/stable/income-statement",
        params={"symbol": ticker, "period": "quarter", "limit": 80},
    )


def fetch_cash_flow_statements(ticker: str) -> list[dict]:
    """Fetch quarterly cash flow statements for a US ticker."""
    return _get(
        "/stable/cash-flow-statement",
        params={"symbol": ticker, "period": "quarter", "limit": 80},
    )


def fetch_balance_sheets(ticker: str) -> list[dict]:
    """Fetch quarterly balance sheets for a US ticker."""
    return _get(
        "/stable/balance-sheet-statement",
        params={"symbol": ticker, "period": "quarter", "limit": 80},
    )


def fetch_historical_prices(ticker: str) -> list[dict]:
    """Fetch historical daily prices for a US ticker.

    Requests data from 2000-01-01 onward so that historical market cap
    can be estimated for all years with fundamental data available.
    Without the 'from' parameter, FMP returns only the last ~5 years.
    """
    data = _get("/stable/historical-price-eod/full", params={"symbol": ticker, "from": "2000-01-01"})
    if not isinstance(data, list) or not data:
        raise FMPError(f"No historical price data for ticker {ticker}")
    return data


def fetch_profile(ticker: str) -> dict | None:
    """Fetch company profile (sector, industry) for a US ticker.

    Returns the profile dict, or None if no data is available.
    """
    data = _get("/stable/profile", params={"symbol": ticker})
    if not isinstance(data, list) or not data:
        return None
    return data[0]


def fetch_dividends(ticker: str) -> list[dict]:
    """Fetch dividend history for a US ticker."""
    data = _get("/stable/dividends-company", params={"symbol": ticker})
    if not isinstance(data, list):
        return []
    return data


def sync_earnings(ticker: str) -> list[QuarterlyEarnings]:
    """Fetch and store earnings for a US ticker from FMP."""
    statements = fetch_income_statements(ticker)
    upper_ticker = ticker.upper()
    records: list[QuarterlyEarnings] = []

    for statement in statements:
        end_date_string = (statement.get("date") or "")[:10]
        if not end_date_string:
            continue

        end_date = date.fromisoformat(end_date_string)

        eps_raw = statement.get("eps")
        eps_value = Decimal(str(eps_raw)) if eps_raw is not None else None

        net_income_raw = statement.get("netIncome")
        net_income_value = int(net_income_raw) if net_income_raw is not None else None

        revenue_raw = statement.get("revenue")
        revenue_value = int(revenue_raw) if revenue_raw is not None else None

        records.append(
            QuarterlyEarnings(
                ticker=upper_ticker,
                end_date=end_date,
                eps=eps_value,
                net_income=net_income_value,
                revenue=revenue_value,
            )
        )

    if not records:
        return []

    return QuarterlyEarnings.objects.bulk_create(
        records,
        update_conflicts=True,
        unique_fields=["ticker", "end_date"],
        update_fields=["eps", "net_income", "revenue", "fetched_at"],
    )


def sync_cash_flows(ticker: str) -> list[QuarterlyCashFlow]:
    """Fetch and store cash flow data for a US ticker from FMP."""
    statements = fetch_cash_flow_statements(ticker)
    upper_ticker = ticker.upper()
    records: list[QuarterlyCashFlow] = []

    for statement in statements:
        end_date_string = (statement.get("date") or "")[:10]
        if not end_date_string:
            continue

        end_date = date.fromisoformat(end_date_string)

        operating_cash_flow = statement.get("operatingCashFlow")
        if operating_cash_flow is not None:
            operating_cash_flow = int(operating_cash_flow)

        investing_cash_flow = statement.get("netCashProvidedByInvestingActivities")
        if investing_cash_flow is not None:
            investing_cash_flow = int(investing_cash_flow)

        dividends_paid = statement.get("commonDividendsPaid")
        if dividends_paid is not None:
            dividends_paid = int(dividends_paid)

        records.append(
            QuarterlyCashFlow(
                ticker=upper_ticker,
                end_date=end_date,
                operating_cash_flow=operating_cash_flow,
                investment_cash_flow=investing_cash_flow,
                dividends_paid=dividends_paid,
            )
        )

    if not records:
        return []

    return QuarterlyCashFlow.objects.bulk_create(
        records,
        update_conflicts=True,
        unique_fields=["ticker", "end_date"],
        update_fields=[
            "operating_cash_flow",
            "investment_cash_flow",
            "dividends_paid",
            "fetched_at",
        ],
    )


def sync_balance_sheets(ticker: str) -> list[BalanceSheet]:
    """Fetch and store balance sheet data for a US ticker from FMP."""
    statements = fetch_balance_sheets(ticker)
    upper_ticker = ticker.upper()
    records: list[BalanceSheet] = []

    for statement in statements:
        end_date_string = (statement.get("date") or "")[:10]
        if not end_date_string:
            continue

        end_date = date.fromisoformat(end_date_string)

        total_debt = statement.get("totalDebt")
        if total_debt is not None:
            total_debt = int(total_debt)

        total_liabilities = statement.get("totalLiabilities")
        if total_liabilities is not None:
            total_liabilities = int(total_liabilities)

        stockholders_equity = statement.get("totalStockholdersEquity")
        if stockholders_equity is not None:
            stockholders_equity = int(stockholders_equity)

        current_assets = statement.get("totalCurrentAssets")
        if current_assets is not None:
            current_assets = int(current_assets)

        current_liabilities = statement.get("totalCurrentLiabilities")
        if current_liabilities is not None:
            current_liabilities = int(current_liabilities)

        records.append(
            BalanceSheet(
                ticker=upper_ticker,
                end_date=end_date,
                total_debt=total_debt,
                total_lease=None,
                total_liabilities=total_liabilities,
                stockholders_equity=stockholders_equity,
                current_assets=current_assets,
                current_liabilities=current_liabilities,
            )
        )

    if not records:
        return []

    return BalanceSheet.objects.bulk_create(
        records,
        update_conflicts=True,
        unique_fields=["ticker", "end_date"],
        update_fields=[
            "total_debt",
            "total_lease",
            "total_liabilities",
            "stockholders_equity",
            "current_assets",
            "current_liabilities",
            "fetched_at",
        ],
    )


def sync_us_cpi() -> int:
    """Fetch US CPI data from FMP and store as year-over-year rates.

    FMP returns absolute CPI index values (e.g. 327.46). We convert to
    YoY percentage change so the inflation module can compound them the
    same way it handles IPCA rates.
    """
    records = _get("/stable/economic-indicators", params={"name": "CPI", "from": "2010-01-01"})

    # Build a map of (year, month) -> index value
    index_by_date: dict[tuple[int, int], Decimal] = {}
    for record in records:
        date_string = (record.get("date") or "")[:10]
        value = record.get("value")
        if not date_string or value is None:
            continue
        record_date = date.fromisoformat(date_string)
        index_by_date[(record_date.year, record_date.month)] = Decimal(str(value))

    # Compute YoY rate for each month: (index_now / index_12mo_ago - 1) * 100
    objects = []
    for (year, month), current_value in index_by_date.items():
        prior_value = index_by_date.get((year - 1, month))
        if prior_value is None or prior_value == 0:
            continue
        yoy_rate = (current_value / prior_value - 1) * 100
        record_date = date(year, month, 1)
        objects.append(USCPIIndex(date=record_date, annual_rate=round(yoy_rate, 4)))

    if objects:
        USCPIIndex.objects.bulk_create(
            objects,
            update_conflicts=True,
            unique_fields=["date"],
            update_fields=["annual_rate"],
        )
    return len(objects)
