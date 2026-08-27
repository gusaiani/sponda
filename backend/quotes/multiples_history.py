"""Compute historical multiples (P/L10, P/FCL10) alongside price history.

For tickers whose listing currency differs from their reporting currency
(e.g. NVO is priced in USD on NYSE but files in DKK), every year-end
market cap is translated into the reporting currency using the year-end
FX rate before being divided by earnings/FCF. When historical FX is
unavailable for a given year, falls back to the most recent FX rate and
sets ``currency_warning=True`` so the frontend can display a banner
explaining the limitation.
"""
from datetime import date as date_type
from datetime import datetime, timezone
from decimal import Decimal

from .fx import (
    _resolve_listing_currency,
    _resolve_reported_currency,
    get_fx_rates_for_dates,
)
from .models import FxRate
from .price_history import close_on_or_before, closes_by_date
from .pe10 import get_annual_earnings
from .pfcf10 import get_annual_fcf

ROLLING_WINDOW = 10


def _rolling_avg(by_year: dict[int, float], year: int) -> float | None:
    """Compute rolling 10-year average ending at `year`.

    Returns None if there are no data points in the window or the average is <= 0.
    """
    values = []
    for y in range(year - ROLLING_WINDOW + 1, year + 1):
        v = by_year.get(y)
        if v is not None:
            values.append(v)
    if not values:
        return None
    avg = sum(values) / len(values)
    return avg if avg > 0 else None


def _latest_fx_rate(from_currency: str, to_currency: str) -> Decimal | None:
    """Most recent USD-pivoted rate for the requested pair."""
    if from_currency == to_currency:
        return Decimal("1")
    row = (
        FxRate.objects
        .filter(base_currency="USD", quote_currency=to_currency)
        .order_by("-date")
        .first()
    )
    if not row:
        return None
    if from_currency == "USD":
        return row.rate
    # from_currency != USD: pivot through USD using the latest rate for the base.
    base_row = (
        FxRate.objects
        .filter(base_currency="USD", quote_currency=from_currency)
        .order_by("-date")
        .first()
    )
    if not base_row:
        return None
    return row.rate / base_row.rate


def _fiscal_year_close_dates(*annual_series: list[dict]) -> dict[int, date_type]:
    """When each reported fiscal year closed, across earnings and cash flows.

    Each annual entry carries its periods oldest-first, so the last one is
    the year's close. A year present in one series and not the other still
    gets a date.
    """
    close_by_year: dict[int, date_type] = {}
    for series in annual_series:
        for year_data in series:
            periods = year_data.get("quarterly_detail") or []
            if not periods:
                continue
            close = date_type.fromisoformat(periods[-1]["end_date"])
            known = close_by_year.get(year_data["year"])
            if known is None or close > known:
                close_by_year[year_data["year"]] = close
    return close_by_year


def compute_multiples_history(
    ticker: str,
    historical_prices: list[dict],
    market_cap: float,
    current_price: float,
) -> dict:
    """Build price history + year-end rolling P/L10 and P/FCL10 multiples.

    Shares outstanding is approximated as market_cap / current_price.
    This is a common approximation — share count changes over time are
    not accounted for, but the resulting multiples are directionally correct.

    For each year Y, the multiple is:
        P/L10  = (year_end_price x shares, in reporting currency) / avg(net_income from Y-9..Y)
        P/FCL10 = same with FCF

    Returns:
        {
          "prices": [{"date": "2015-01-31", "adjustedClose": 12.34}, ...],
          "multiples": {
            "pl": [{"year": 2015, "value": 8.5}, ...],
            "pfcl": [{"year": 2015, "value": 10.2}, ...]
          },
          "currency_warning": bool   # True if any historical year fell back to current FX
        }
    """
    if not current_price or current_price <= 0:
        return {
            "prices": [], "multiples": {"pl": [], "pfcl": []},
            "currency_warning": False,
        }

    shares_outstanding = market_cap / current_price

    listing_currency = _resolve_listing_currency(ticker)
    reported_currency = _resolve_reported_currency(ticker)
    needs_fx_translation = listing_currency != reported_currency
    latest_fx_fallback: Decimal | None = None
    if needs_fx_translation:
        latest_fx_fallback = _latest_fx_rate(listing_currency, reported_currency)
    currency_warning = False

    # Convert prices: unix timestamp → ISO date, keep adjustedClose
    prices = []
    for point in historical_prices:
        ts = point.get("date")
        adj_close = point.get("adjustedClose")
        if ts is None or adj_close is None:
            continue
        iso_date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        prices.append({"date": iso_date, "adjustedClose": round(adj_close, 2)})

    # Normalize to oldest-first; FMP returns newest-first while BRAPI returns
    # oldest-first, and the frontend plots whatever order it receives.
    prices.sort(key=lambda p: p["date"])

    # Fetch annual earnings and FCF from DB (reuses existing logic)
    earnings_data = get_annual_earnings(ticker, max_years=50)
    fcf_data = get_annual_fcf(ticker, max_years=50)

    earnings_by_year = {d["year"]: float(d["net_income"]) for d in earnings_data}
    fcf_by_year = {d["year"]: float(d["fcf"]) for d in fcf_data}

    # Each year is priced on the day that year closed. For a filer that does
    # not close on 31 December, taking the December price puts the price
    # three months late against the year's earnings, and labels a different
    # period "2026" here than the Fundamentos table does.
    #
    # Years the price series covers but the filer never reported still get a
    # point, priced at the calendar year end. They carry a null multiple, as
    # they always have, so the chart keeps its gaps instead of shortening.
    closes = closes_by_date(historical_prices)
    year_close_dates = _fiscal_year_close_dates(earnings_data, fcf_data)
    plotted_years = set(year_close_dates) | {close_date.year for close_date, _ in closes}

    year_end_prices: dict[int, float] = {}
    for year in plotted_years:
        price = close_on_or_before(
            closes, year_close_dates.get(year) or date_type(year, 12, 31),
        )
        if price is not None:
            year_end_prices[year] = price

    # Both multiple loops below translate the same set of year ends, so the
    # rates are resolved once here instead of per year per loop. That repeated
    # single-date lookup was the N+1 Sentry reported on this endpoint.
    fx_by_year: dict[int, Decimal | None] = {}
    if needs_fx_translation:
        year_end_by_year = {
            year: year_close_dates.get(year) or date_type(year, 12, 31)
            for year in year_end_prices
        }
        rate_by_date = get_fx_rates_for_dates(
            year_end_by_year.values(), listing_currency, reported_currency,
        )
        fx_by_year = {
            year: rate_by_date.get(year_end)
            for year, year_end in year_end_by_year.items()
        }

    def _market_cap_in_reported(year: int, year_end_price: float) -> float | None:
        """Translate a year-end market cap from listing into reported currency.
        Sets `currency_warning` when we fall back to the latest FX rate."""
        nonlocal currency_warning
        listing_cap = year_end_price * shares_outstanding
        if not needs_fx_translation:
            return listing_cap
        fx = fx_by_year.get(year)
        if fx is None:
            if latest_fx_fallback is None:
                return None
            currency_warning = True
            fx = latest_fx_fallback
        return float(Decimal(str(listing_cap)) * fx)

    # Compute P/L10 per year
    pl_multiples = []
    for year, price in sorted(year_end_prices.items()):
        avg_income = _rolling_avg(earnings_by_year, year)
        market_cap_at_year = _market_cap_in_reported(year, price)
        if avg_income is not None and market_cap_at_year is not None:
            pl = round(market_cap_at_year / avg_income, 2)
            pl_multiples.append({"year": year, "value": pl})
        else:
            pl_multiples.append({"year": year, "value": None})

    # Compute P/FCL10 per year
    pfcl_multiples = []
    for year, price in sorted(year_end_prices.items()):
        avg_fcf = _rolling_avg(fcf_by_year, year)
        market_cap_at_year = _market_cap_in_reported(year, price)
        if avg_fcf is not None and market_cap_at_year is not None:
            pfcl = round(market_cap_at_year / avg_fcf, 2)
            pfcl_multiples.append({"year": year, "value": pfcl})
        else:
            pfcl_multiples.append({"year": year, "value": None})

    return {
        "prices": prices,
        "multiples": {
            "pl": pl_multiples,
            "pfcl": pfcl_multiples,
        },
        "currency_warning": currency_warning,
    }
