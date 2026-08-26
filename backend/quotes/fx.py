"""FX rate lookup helper.

All rates are persisted as USD-pivoted (base=USD, quote=X). Cross-rates
are computed at lookup time. The lookup uses "latest available rate ≤
requested date", so weekend/holiday dates resolve to the previous trading
day. When no historical anchor exists, returns None and the caller decides
how to degrade (e.g. apply current FX with a warning, skip the indicator).
"""
from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable
from datetime import date as date_type
from decimal import Decimal

from .models import FxRate, Ticker
from .providers import is_brazilian_ticker


def get_fx_rate(
    on_date: date_type, from_currency: str, to_currency: str,
) -> Decimal | None:
    """Return how many units of `to_currency` equal 1 unit of `from_currency`
    on `on_date` (or the most recent available date ≤ on_date).

    Returns Decimal("1") when from_currency == to_currency.
    Returns None when no historical anchor exists (e.g. requested date is
    earlier than the oldest stored rate, or the currency is unknown).
    """
    if from_currency == to_currency:
        return Decimal("1")

    if from_currency == "USD":
        return _lookup_usd_to(on_date, to_currency)
    if to_currency == "USD":
        rate = _lookup_usd_to(on_date, from_currency)
        return Decimal("1") / rate if rate else None

    # Non-USD pair: pivot through USD.
    usd_to_quote = _lookup_usd_to(on_date, to_currency)
    usd_to_base = _lookup_usd_to(on_date, from_currency)
    if usd_to_quote is None or usd_to_base is None:
        return None
    return usd_to_quote / usd_to_base


def _lookup_usd_to(on_date: date_type, quote_currency: str) -> Decimal | None:
    """Return the latest USD→quote_currency rate with date ≤ on_date."""
    row = (
        FxRate.objects
        .filter(base_currency="USD", quote_currency=quote_currency, date__lte=on_date)
        .order_by("-date")
        .first()
    )
    return row.rate if row else None


def get_fx_rates_for_dates(
    dates: Iterable[date_type], from_currency: str, to_currency: str,
) -> dict[date_type, Decimal | None]:
    """Resolve many dates at once, with one query per non-USD leg.

    Same contract as :func:`get_fx_rate`, applied to a whole set of dates:
    each entry is the rate on the most recent anchor at or before that
    date, or ``None`` when no anchor is old enough. Identical currencies
    resolve to 1 without touching the database.

    Callers that translate a value per year (multiples history, the
    fundamentals table) were previously issuing one query per year, which
    Sentry reported as an N+1 on both endpoints. Loading each leg's series
    once and searching it in memory keeps the cost flat in the number of
    dates.
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    requested_dates = list(dates)
    if not requested_dates:
        return {}
    if from_currency == to_currency:
        return {on_date: Decimal("1") for on_date in requested_dates}

    newest_requested = max(requested_dates)
    legs = {
        currency: _load_usd_anchor_series(currency, newest_requested)
        for currency in {from_currency, to_currency}
        if currency != "USD"
    }

    resolved: dict[date_type, Decimal | None] = {}
    for on_date in requested_dates:
        resolved[on_date] = _cross_rate_from_series(
            legs, on_date, from_currency, to_currency,
        )
    return resolved


def _load_usd_anchor_series(
    quote_currency: str, newest_requested: date_type,
) -> tuple[list[date_type], list[Decimal]]:
    """Every USD -> quote_currency anchor that any requested date could use.

    Anchors later than the newest requested date can never be the answer
    to "latest rate at or before this date", so they are left in the
    database. Everything older is kept, because the oldest requested date
    may have to reach a long way back for its anchor. Two parallel lists
    (dates ascending, rates in the same order) is the shape
    :func:`bisect_right` wants.
    """
    anchor_dates: list[date_type] = []
    anchor_rates: list[Decimal] = []
    rows = (
        FxRate.objects
        .filter(
            base_currency="USD",
            quote_currency=quote_currency,
            date__lte=newest_requested,
        )
        .order_by("date")
        .values_list("date", "rate")
    )
    for anchor_date, rate in rows:
        anchor_dates.append(anchor_date)
        anchor_rates.append(rate)
    return anchor_dates, anchor_rates


def _rate_from_series(
    series: tuple[list[date_type], list[Decimal]], on_date: date_type,
) -> Decimal | None:
    """The latest rate in ``series`` at or before ``on_date``."""
    anchor_dates, anchor_rates = series
    position = bisect_right(anchor_dates, on_date)
    if position == 0:
        return None
    return anchor_rates[position - 1]


def _cross_rate_from_series(
    legs: dict[str, tuple[list[date_type], list[Decimal]]],
    on_date: date_type,
    from_currency: str,
    to_currency: str,
) -> Decimal | None:
    """Mirror of :func:`get_fx_rate`'s pivot logic, over preloaded series."""
    if from_currency == "USD":
        return _rate_from_series(legs[to_currency], on_date)

    usd_to_base = _rate_from_series(legs[from_currency], on_date)
    if to_currency == "USD":
        return Decimal("1") / usd_to_base if usd_to_base else None

    usd_to_quote = _rate_from_series(legs[to_currency], on_date)
    if usd_to_quote is None or usd_to_base is None:
        return None
    return usd_to_quote / usd_to_base


def fx_series(
    from_currency: str,
    to_currency: str,
    start: date_type | None = None,
) -> list[tuple[date_type, Decimal]]:
    """Return the ``from_currency → to_currency`` rate at every date we hold an
    FX anchor for, on or after ``start`` (ascending by date).

    Each rate is units of ``to_currency`` per 1 unit of ``from_currency``,
    computed via the same USD pivot as :func:`get_fx_rate`. The candidate dates
    come from the stored USD-pivoted rows for the non-USD legs of the pair, so a
    consumer can step-sample the result to translate a dated value series.

    Returns an empty list when the currencies are identical (the caller treats
    that as the identity conversion).
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    if from_currency == to_currency:
        return []

    non_usd_legs = {c for c in (from_currency, to_currency) if c != "USD"}
    anchor_dates = (
        FxRate.objects
        .filter(base_currency="USD", quote_currency__in=non_usd_legs)
    )
    if start is not None:
        anchor_dates = anchor_dates.filter(date__gte=start)
    dates = sorted(set(anchor_dates.values_list("date", flat=True)))

    # One resolution pass for the whole series. Asking date by date meant a
    # query per anchor, which for a daily currency pair is thousands.
    rate_by_date = get_fx_rates_for_dates(dates, from_currency, to_currency)
    return [
        (on_date, rate_by_date[on_date])
        for on_date in dates
        if rate_by_date[on_date] is not None
    ]


def _resolve_listing_currency(ticker: str) -> str:
    """The currency the *quote* (price, market cap) is denominated in.
    BRL for B3 tickers, USD for everything else (FMP)."""
    return "BRL" if is_brazilian_ticker(ticker) else "USD"


def _resolve_reported_currency(ticker: str) -> str:
    """The currency the company *files* its statements in. Read from
    ``Ticker.reported_currency`` when populated; otherwise fall back to the
    listing currency (legacy/test paths)."""
    row = Ticker.objects.filter(symbol=ticker.upper()).only("reported_currency").first()
    if row and row.reported_currency:
        return row.reported_currency
    return _resolve_listing_currency(ticker)


def _latest_fx_date(quote_currency: str) -> date_type | None:
    """Most recent date for which we have a USD→quote_currency rate."""
    row = (
        FxRate.objects
        .filter(base_currency="USD", quote_currency=quote_currency)
        .order_by("-date")
        .first()
    )
    return row.date if row else None


def market_cap_in_reported_currency(
    market_cap: Decimal | int | float | None,
    ticker: str,
    on_date: date_type | None = None,
) -> Decimal | None:
    """Translate a market cap from the listing currency into the company's
    reported (statement) currency, using FX on ``on_date``.

    When ``on_date`` is None, uses the most recent available rate (the
    standard behaviour for snapshot indicators like PE10/PFCF10/peg).
    Historical-multiples callers should pass the year-end date for each
    point and apply their own warning when FX falls back.

    Returns None when the conversion cannot be made (no FX data for the
    requested currency/date, or the market cap itself is None). Callers
    should treat None as "indicator unavailable".
    """
    if market_cap is None:
        return None

    listing_currency = _resolve_listing_currency(ticker)
    reported_currency = _resolve_reported_currency(ticker)
    if listing_currency == reported_currency:
        return Decimal(market_cap) if not isinstance(market_cap, Decimal) else market_cap

    lookup_date = on_date or _latest_fx_date(reported_currency) or date_type.today()
    rate = get_fx_rate(lookup_date, listing_currency, reported_currency)
    if rate is None:
        return None
    market_cap_decimal = Decimal(market_cap) if not isinstance(market_cap, Decimal) else market_cap
    return market_cap_decimal * rate
