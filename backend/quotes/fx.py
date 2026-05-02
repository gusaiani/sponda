"""FX rate lookup helper.

All rates are persisted as USD-pivoted (base=USD, quote=X). Cross-rates
are computed at lookup time. The lookup uses "latest available rate ≤
requested date", so weekend/holiday dates resolve to the previous trading
day. When no historical anchor exists, returns None and the caller decides
how to degrade (e.g. apply current FX with a warning, skip the indicator).
"""
from __future__ import annotations

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
