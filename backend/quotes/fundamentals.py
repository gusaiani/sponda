"""Per-year fundamentals aggregation for the Fundamentos tab."""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from .models import BalanceSheet, QuarterlyCashFlow, QuarterlyEarnings
from .pe10 import get_ipca_adjustment_factors


def _aggregate_balance_sheets(ticker: str) -> dict[int, dict]:
    """Return the latest balance sheet per year, keyed by year.

    For each year, picks the quarter with the latest end_date.
    """
    sheets = BalanceSheet.objects.filter(ticker=ticker.upper()).order_by("end_date")

    by_year: dict[int, dict] = {}
    for sheet in sheets:
        year = sheet.end_date.year
        entry = {
            "endDate": sheet.end_date.isoformat(),
            "totalDebt": sheet.total_debt,
            "totalLease": sheet.total_lease,
            "totalLiabilities": sheet.total_liabilities,
            "stockholdersEquity": sheet.stockholders_equity,
            "currentAssets": sheet.current_assets,
            "currentLiabilities": sheet.current_liabilities,
        }
        # Always overwrite — ordered by end_date asc, so last write = latest quarter
        by_year[year] = entry

    return by_year


def _aggregate_earnings(ticker: str) -> dict[int, dict]:
    """Sum quarterly earnings and revenue per year."""
    quarters = QuarterlyEarnings.objects.filter(ticker=ticker.upper()).order_by("end_date")

    yearly: dict[int, dict] = defaultdict(
        lambda: {"netIncome": Decimal("0"), "revenue": Decimal("0"), "quarters": 0,
                 "hasRevenue": False, "hasNetIncome": False}
    )
    for quarter in quarters:
        year = quarter.end_date.year
        if quarter.net_income is not None:
            yearly[year]["netIncome"] += quarter.net_income
            yearly[year]["hasNetIncome"] = True
        if quarter.revenue is not None:
            yearly[year]["revenue"] += quarter.revenue
            yearly[year]["hasRevenue"] = True
        yearly[year]["quarters"] += 1

    return dict(yearly)


def _aggregate_cash_flows(ticker: str) -> dict[int, dict]:
    """Sum quarterly cash flows per year: operating CF, FCF, dividends."""
    quarters = QuarterlyCashFlow.objects.filter(ticker=ticker.upper()).order_by("end_date")

    yearly: dict[int, dict] = defaultdict(
        lambda: {"operatingCashFlow": Decimal("0"), "fcf": Decimal("0"),
                 "dividendsPaid": Decimal("0"), "quarters": 0,
                 "hasOperatingCF": False, "hasDividends": False}
    )
    for quarter in quarters:
        year = quarter.end_date.year
        if quarter.operating_cash_flow is not None:
            operating = Decimal(str(quarter.operating_cash_flow))
            investment = Decimal(str(quarter.investment_cash_flow or 0))
            yearly[year]["operatingCashFlow"] += operating
            yearly[year]["fcf"] += operating + investment
            yearly[year]["hasOperatingCF"] = True
        if quarter.dividends_paid is not None:
            yearly[year]["dividendsPaid"] += quarter.dividends_paid
            yearly[year]["hasDividends"] = True
        yearly[year]["quarters"] += 1

    return dict(yearly)


def _safe_float(value) -> float | None:
    """Convert Decimal/int to float, returning None for None."""
    if value is None:
        return None
    return float(value)


def _safe_ratio(numerator, denominator) -> float | None:
    """Compute numerator/denominator, returning None if impossible."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return round(float(numerator) / float(denominator), 2)


def _extract_year_end_prices(historical_prices: list[dict]) -> dict[int, float]:
    """Extract the last adjusted close per year from historical price data.

    Iterates through all data points and keeps the last adjustedClose seen
    for each calendar year — effectively the year-end (or most recent) price.
    """
    year_end_prices: dict[int, float] = {}
    for point in historical_prices:
        timestamp = point.get("date")
        adjusted_close = point.get("adjustedClose")
        if timestamp is None or adjusted_close is None:
            continue
        point_date = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        year_end_prices[point_date.year] = adjusted_close
    return year_end_prices


def compute_fundamentals(
    ticker: str,
    market_cap: float | None,
    current_price: float | None,
    historical_prices: list[dict] | None = None,
) -> list[dict]:
    """Compute per-year fundamental data for a ticker.

    Returns a list of year objects sorted by year descending, each containing:
    - Balance sheet data (debt, liabilities, equity, current ratio)
    - Income data (revenue, earnings, IPCA-adjusted)
    - Cash flow data (FCF, operating CF, dividends, IPCA-adjusted)
    - Computed ratios (debt/equity, liabilities/equity, current ratio)
    - Partial-year flag (quarters < 4)
    """
    balance_by_year = _aggregate_balance_sheets(ticker)
    earnings_by_year = _aggregate_earnings(ticker)
    cash_flow_by_year = _aggregate_cash_flows(ticker)

    all_years = sorted(
        set(balance_by_year.keys()) | set(earnings_by_year.keys()) | set(cash_flow_by_year.keys()),
        reverse=True,
    )

    if not all_years:
        return []

    # IPCA adjustment factors
    ipca_factors = get_ipca_adjustment_factors(all_years)

    # Estimate shares outstanding for historical market cap approximation
    shares_outstanding = None
    if market_cap and current_price and current_price > 0:
        shares_outstanding = market_cap / current_price

    year_end_prices = _extract_year_end_prices(historical_prices or [])

    results = []
    for year in all_years:
        balance = balance_by_year.get(year, {})
        earnings = earnings_by_year.get(year, {})
        cash_flow = cash_flow_by_year.get(year, {})

        # Determine how many quarters of data we have
        earnings_quarters = earnings.get("quarters", 0)
        cash_flow_quarters = cash_flow.get("quarters", 0)
        max_quarters = max(earnings_quarters, cash_flow_quarters)

        # Balance sheet values
        total_debt = balance.get("totalDebt")
        total_lease = balance.get("totalLease")
        total_liabilities = balance.get("totalLiabilities")
        equity = balance.get("stockholdersEquity")
        current_assets = balance.get("currentAssets")
        current_liabilities = balance.get("currentLiabilities")

        # Debt ex-leasing
        debt_ex_lease = None
        if total_debt is not None:
            debt_ex_lease = total_debt - (total_lease or 0)

        # Income values
        net_income = earnings.get("netIncome") if earnings.get("hasNetIncome") else None
        revenue = earnings.get("revenue") if earnings.get("hasRevenue") else None

        # Cash flow values
        fcf = cash_flow.get("fcf") if cash_flow.get("hasOperatingCF") else None
        operating_cf = cash_flow.get("operatingCashFlow") if cash_flow.get("hasOperatingCF") else None
        dividends_paid = cash_flow.get("dividendsPaid") if cash_flow.get("hasDividends") else None

        # IPCA adjustment
        ipca_factor = ipca_factors.get(year, Decimal("1"))

        revenue_adjusted = float(revenue * ipca_factor) if revenue is not None else None
        net_income_adjusted = float(net_income * ipca_factor) if net_income is not None else None
        fcf_adjusted = float(fcf * ipca_factor) if fcf is not None else None
        operating_cf_adjusted = float(operating_cf * ipca_factor) if operating_cf is not None else None
        dividends_adjusted = float(dividends_paid * ipca_factor) if dividends_paid is not None else None
        debt_ex_lease_adjusted = float(debt_ex_lease * ipca_factor) if debt_ex_lease is not None else None
        total_liabilities_adjusted = float(total_liabilities * ipca_factor) if total_liabilities is not None else None
        equity_adjusted = float(equity * ipca_factor) if equity is not None else None

        # Ratios
        debt_to_equity = _safe_ratio(debt_ex_lease, equity)
        liabilities_to_equity = _safe_ratio(total_liabilities, equity)
        current_ratio = _safe_ratio(current_assets, current_liabilities)

        # Market cap: current snapshot for latest year, historical estimate for others
        if year == all_years[0]:
            year_market_cap = market_cap
        elif shares_outstanding and year in year_end_prices:
            year_market_cap = round(year_end_prices[year] * shares_outstanding, 2)
        else:
            year_market_cap = None

        market_cap_adjusted = float(year_market_cap * float(ipca_factor)) if year_market_cap is not None else None

        year_data = {
            "year": year,
            "quarters": max_quarters,
            "balanceSheetDate": balance.get("endDate"),
            "marketCap": year_market_cap,
            "marketCapAdjusted": market_cap_adjusted,
            # Balance sheet (in original currency)
            "totalDebt": total_debt,
            "totalLease": total_lease,
            "debtExLease": debt_ex_lease,
            "debtExLeaseAdjusted": debt_ex_lease_adjusted,
            "totalLiabilities": total_liabilities,
            "totalLiabilitiesAdjusted": total_liabilities_adjusted,
            "stockholdersEquity": _safe_float(equity),
            "stockholdersEquityAdjusted": equity_adjusted,
            "currentAssets": current_assets,
            "currentLiabilities": current_liabilities,
            # Ratios
            "debtToEquity": debt_to_equity,
            "liabilitiesToEquity": liabilities_to_equity,
            "currentRatio": current_ratio,
            # Income
            "revenue": _safe_float(revenue),
            "revenueAdjusted": revenue_adjusted,
            "netIncome": _safe_float(net_income),
            "netIncomeAdjusted": net_income_adjusted,
            # Cash flow
            "fcf": _safe_float(fcf),
            "fcfAdjusted": fcf_adjusted,
            "operatingCashFlow": _safe_float(operating_cf),
            "operatingCashFlowAdjusted": operating_cf_adjusted,
            "dividendsPaid": _safe_float(dividends_paid),
            "dividendsAdjusted": dividends_adjusted,
            # IPCA
            "ipcaFactor": round(float(ipca_factor), 6),
        }

        results.append(year_data)

    return results
