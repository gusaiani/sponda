"""BRAPI API client for fetching stock data and IPCA index."""
import re
from datetime import date
from decimal import Decimal

import requests
from django.conf import settings

from .models import BalanceSheet, IPCAIndex, QuarterlyCashFlow, QuarterlyEarnings, Ticker


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


BRAPI_BATCH_SIZE = 20


def fetch_quote(ticker: str) -> dict:
    """Fetch current quote data for a ticker."""
    data = _get(f"/quote/{ticker}")
    results = data.get("results", [])
    if not results:
        raise BRAPIError(f"No results for ticker {ticker}")
    return results[0]


def fetch_quotes_batch(tickers: list[str]) -> dict[str, dict]:
    """Fetch current quote data for multiple tickers.

    BRAPI Pro supports up to 20 tickers per request. Larger lists are split
    into chunks automatically. Returns a dict keyed by uppercase symbol.
    """
    if not tickers:
        return {}
    results: dict[str, dict] = {}
    for chunk_start in range(0, len(tickers), BRAPI_BATCH_SIZE):
        chunk = tickers[chunk_start : chunk_start + BRAPI_BATCH_SIZE]
        data = _get(f"/quote/{','.join(chunk)}")
        for quote in data.get("results", []):
            symbol = (quote.get("symbol") or "").upper()
            if symbol:
                results[symbol] = quote
    return results


def fetch_dividends(ticker: str) -> dict:
    """Fetch dividend history for a ticker.

    Returns a dict with cashDividends and stockDividends lists from BRAPI.
    """
    data = _get(f"/quote/{ticker}", params={"dividends": "true"})
    results = data.get("results", [])
    if not results:
        raise BRAPIError(f"No results for ticker {ticker}")
    dividends_data = results[0].get("dividendsData", {})
    return {
        "cashDividends": dividends_data.get("cashDividends", []),
        "stockDividends": dividends_data.get("stockDividends", []),
    }


def fetch_historical_prices(ticker: str) -> list[dict]:
    """Fetch monthly historical prices (max range) for a ticker.

    Returns the historicalDataPrice list from BRAPI with fields like
    date (unix timestamp), adjustedClose, etc.
    """
    data = _get(f"/quote/{ticker}", params={"range": "max", "interval": "1mo"})
    results = data.get("results", [])
    if not results:
        raise BRAPIError(f"No results for ticker {ticker}")
    return results[0].get("historicalDataPrice", [])


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
    upper_ticker = ticker.upper()
    # Providers occasionally return duplicate endDates (amended filings).
    # Keep the last, matching the prior update_or_create loop semantics,
    # and avoid Postgres ON CONFLICT rejecting the whole batch.
    by_end_date: dict[date, QuarterlyEarnings] = {}

    for stmt in statements:
        end_date_str = stmt.get("endDate", "")[:10]
        if not end_date_str:
            continue

        end_date = date.fromisoformat(end_date_str)

        eps_raw = stmt.get("basicEarningsPerCommonShare")
        eps_value = Decimal(str(eps_raw)) if eps_raw is not None else None

        net_income_raw = stmt.get("netIncome")
        net_income_value = int(net_income_raw) if net_income_raw is not None else None

        revenue_raw = stmt.get("totalRevenue")
        revenue_value = int(revenue_raw) if revenue_raw is not None else None

        by_end_date[end_date] = QuarterlyEarnings(
            ticker=upper_ticker,
            end_date=end_date,
            eps=eps_value,
            net_income=net_income_value,
            revenue=revenue_value,
        )

    if not by_end_date:
        return []

    return QuarterlyEarnings.objects.bulk_create(
        list(by_end_date.values()),
        update_conflicts=True,
        unique_fields=["ticker", "end_date"],
        update_fields=["eps", "net_income", "revenue", "fetched_at"],
    )


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
    upper_ticker = ticker.upper()
    by_end_date: dict[date, QuarterlyCashFlow] = {}

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

        dividends_paid = stmt.get("dividendsPaid")
        if dividends_paid is not None:
            dividends_paid = int(dividends_paid)

        by_end_date[end_date] = QuarterlyCashFlow(
            ticker=upper_ticker,
            end_date=end_date,
            operating_cash_flow=operating_cf,
            investment_cash_flow=investment_cf,
            dividends_paid=dividends_paid,
        )

    if not by_end_date:
        return []

    return QuarterlyCashFlow.objects.bulk_create(
        list(by_end_date.values()),
        update_conflicts=True,
        unique_fields=["ticker", "end_date"],
        update_fields=[
            "operating_cash_flow",
            "investment_cash_flow",
            "dividends_paid",
            "fetched_at",
        ],
    )


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


def _fetch_annual_lease_data(ticker: str) -> dict[str, tuple[int | None, int | None]]:
    """Fetch lease fields from annual balance sheets (keyed by endDate).

    The quarterly BRAPI module often omits leaseFinancing fields, but the
    annual module includes them.  Returns {end_date_str: (lease_current, lease_long)}.
    """
    try:
        data = _get(
            f"/quote/{ticker}",
            params={"modules": "balanceSheetHistory"},
        )
        results = data.get("results", [])
        if not results:
            return {}
        stmts = results[0].get("balanceSheetHistory", [])
    except BRAPIError:
        return {}

    out: dict[str, tuple[int | None, int | None]] = {}
    for stmt in stmts:
        ed = stmt.get("endDate", "")[:10]
        lc = stmt.get("leaseFinancing")
        ll = stmt.get("longTermLeaseFinancing")
        if lc is not None or ll is not None:
            out[ed] = (lc, ll)
    return out


def fetch_financial_data(ticker: str) -> dict:
    """Fetch BRAPI's financialData module.

    Returns dict with totalDebt, debtToEquity, ebitda, totalCash, etc.
    BRAPI computes these from the underlying DFP/ITR data and often
    produces non-zero values even when balanceSheetHistory reports
    loansAndFinancing=0 (common on mid/small caps and banks).
    """
    try:
        data = _get(f"/quote/{ticker}", params={"modules": "financialData"})
    except BRAPIError:
        return {}
    results = data.get("results", [])
    if not results:
        return {}
    return results[0].get("financialData") or {}


def sync_balance_sheets(ticker: str) -> list[BalanceSheet]:
    """Fetch and store balance sheet data for a ticker from BRAPI."""
    statements = fetch_balance_sheets(ticker)
    upper_ticker = ticker.upper()
    by_end_date: dict[date, BalanceSheet] = {}

    # Pre-fetch annual lease data in case quarterly doesn't have it
    annual_lease: dict[str, tuple[int | None, int | None]] | None = None

    for stmt in statements:
        end_date_str = stmt.get("endDate", "")[:10]
        if not end_date_str:
            continue

        end_date = date.fromisoformat(end_date_str)

        # Gross debt: loansAndFinancing already includes leasing in BRAPI
        # (BRAPI's loansAndFinancing = financiamentos + arrendamentos)
        loans_current = stmt.get("loansAndFinancing")
        loans_long = stmt.get("longTermLoansAndFinancing")
        lease_current = stmt.get("leaseFinancing")
        lease_long = stmt.get("longTermLeaseFinancing")

        # If quarterly has no lease fields, try annual for the same date
        if lease_current is None and lease_long is None:
            if annual_lease is None:
                annual_lease = _fetch_annual_lease_data(ticker)
            if end_date_str in annual_lease:
                lease_current, lease_long = annual_lease[end_date_str]

        lease_parts = [lease_current, lease_long]
        if any(p is not None for p in lease_parts):
            total_lease = sum(int(p) for p in lease_parts if p is not None)
        else:
            total_lease = None

        # total_debt = loans (which already include leases) — do NOT add lease again
        debt_parts = [loans_current, loans_long]
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

        current_assets = stmt.get("totalCurrentAssets") or stmt.get("currentAssets")
        if current_assets is not None:
            current_assets = int(current_assets)

        by_end_date[end_date] = BalanceSheet(
            ticker=upper_ticker,
            end_date=end_date,
            total_debt=total_debt,
            total_lease=total_lease,
            total_liabilities=total_liab,
            stockholders_equity=equity,
            current_assets=current_assets,
            current_liabilities=int(current_liab) if current_liab is not None else None,
        )

    if not by_end_date:
        return []

    sheets = BalanceSheet.objects.bulk_create(
        list(by_end_date.values()),
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

    _patch_latest_total_debt_from_financial_data(ticker, sheets)
    return sheets


def _patch_latest_total_debt_from_financial_data(
    ticker: str, sheets: list[BalanceSheet]
) -> None:
    """Fill in the most recent balance sheet's total_debt from BRAPI's
    financialData.totalDebt only when the balance sheet itself reports
    no debt.

    BRAPI's balanceSheetHistory often reports loansAndFinancing=0 for
    mid/small caps and banks even when the company has real debt; the
    financialData module is derived differently and usually carries the
    correct figure in that case.  When the balance sheet already reports
    real loansAndFinancing, trust it — BRAPI's financialData.totalDebt is
    sometimes inflated (observed on VALE3: 203.6B vs the correct 103.5B),
    which would otherwise push our D/E ratio ~2x above the ADR.
    """
    if not sheets:
        return
    latest = max(sheets, key=lambda s: s.end_date)

    if latest.total_debt not in (None, 0):
        return

    financial_data = fetch_financial_data(ticker)
    reported_debt = financial_data.get("totalDebt") if financial_data else None

    if reported_debt is None:
        if latest.total_debt == 0:
            latest.total_debt = None
            latest.save(update_fields=["total_debt"])
        return

    latest.total_debt = int(reported_debt)
    latest.save(update_fields=["total_debt"])


def fetch_ipca_data() -> list[dict]:
    """Fetch IPCA historical data from BRAPI."""
    data = _get("/v2/inflation", params={"country": "ipca", "historical": "true"})
    return data.get("inflation", [])


def sync_ipca() -> int:
    """Fetch IPCA data from BRAPI and store in DB. Returns number of records synced."""
    records = fetch_ipca_data()
    objects = []
    for record in records:
        date_str = record.get("date", "")
        value = record.get("value")
        if not date_str or value is None:
            continue

        # BRAPI returns dates as "dd/mm/yyyy"
        day, month, year = date_str.split("/")
        record_date = date(int(year), int(month), int(day))

        objects.append(IPCAIndex(date=record_date, annual_rate=Decimal(str(value))))

    if objects:
        IPCAIndex.objects.bulk_create(
            objects,
            update_conflicts=True,
            unique_fields=["date"],
            update_fields=["annual_rate"],
        )
    return len(objects)


def fetch_ticker_list() -> list[dict]:
    """Fetch all tickers from BRAPI quote list (paginated)."""
    all_stocks = []
    for page in range(1, 5):  # Safety cap at 4 pages
        data = _get("/quote/list", params={"page": page, "limit": 1000})
        stocks = data.get("stocks", [])
        if not stocks:
            break
        all_stocks.extend(stocks)
        if not data.get("hasNextPage", False):
            break
    return all_stocks


def sync_tickers() -> int:
    """Fetch all tickers from BRAPI and upsert into the Ticker model."""
    from .logo_overrides import is_placeholder_logo_url
    from .views import format_display_name

    stocks = fetch_ticker_list()
    objects = []
    for stock in stocks:
        symbol = (stock.get("stock") or "").strip().upper()
        if not symbol:
            continue
        # Only keep standard stock tickers (e.g. PETR4, VALE3)
        # Skip fractional (F), BDRs (34), receipts (39), funds/ETFs (11),
        # and units/other instruments (10, 31, 32, 33, 35)
        if re.search(r"(F|\d{2})$", symbol):
            continue
        # Only keep actual stocks
        ticker_type = stock.get("type") or ""
        if ticker_type and ticker_type != "stock":
            continue
        formal_name = stock.get("name") or ""
        logo_url = stock.get("logo") or ""
        # BRAPI returns its generic branding SVG for tickers it has no logo
        # for. Persisting that URL would just cause repeated rejected fetches.
        if is_placeholder_logo_url(logo_url):
            logo_url = ""
        objects.append(Ticker(
            symbol=symbol,
            name=formal_name,
            display_name=format_display_name(formal_name),
            sector=stock.get("sector") or "",
            type=stock.get("type") or "",
            logo=logo_url,
        ))

    if objects:
        Ticker.objects.bulk_create(
            objects,
            update_conflicts=True,
            unique_fields=["symbol"],
            update_fields=["name", "display_name", "sector", "type", "logo"],
        )
        synced_symbols = {ticker.symbol for ticker in objects}
        Ticker.objects.exclude(symbol__in=synced_symbols).delete()
    return len(objects)
