"""Provider routing layer — picks BRAPI or FMP based on ticker.

Normalizes FMP responses to match BRAPI field names so views work
unchanged regardless of data source.
"""
import re
from datetime import datetime, timezone

from quotes import brapi, fmp


class ProviderError(Exception):
    pass


def is_brazilian_ticker(ticker: str) -> bool:
    """Brazilian tickers end with one or more digits: PETR4, VALE3, SANB11."""
    return bool(re.match(r"^[A-Z]+\d+$", ticker.upper()))


def _route(brazilian_function, us_function, ticker, *args, **kwargs):
    """Call the appropriate provider function and wrap errors as ProviderError."""
    if is_brazilian_ticker(ticker):
        try:
            return brazilian_function(ticker, *args, **kwargs)
        except brapi.BRAPIError as error:
            raise ProviderError(str(error)) from error
    else:
        try:
            return us_function(ticker, *args, **kwargs)
        except fmp.FMPError as error:
            raise ProviderError(str(error)) from error


def _normalize_fmp_quote(raw_quote: dict) -> dict:
    """Normalize FMP quote to BRAPI field names."""
    raw_quote["regularMarketPrice"] = raw_quote.get("price")
    raw_quote["longName"] = raw_quote.get("name", "")
    raw_quote["shortName"] = raw_quote.get("symbol", "")
    return raw_quote


def _normalize_fmp_historical_prices(fmp_prices: list[dict]) -> list[dict]:
    """Normalize FMP historical prices to BRAPI format.

    BRAPI: {"date": <unix_timestamp>, "adjustedClose": float}
    FMP:   {"date": "2025-01-02", "adjClose": float}
    """
    normalized = []
    for point in fmp_prices:
        date_string = point.get("date")
        adj_close = point.get("adjClose")
        if date_string is None or adj_close is None:
            continue
        unix_timestamp = int(datetime.strptime(date_string, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        normalized.append({
            "date": unix_timestamp,
            "adjustedClose": adj_close,
        })
    return normalized


def _normalize_fmp_dividends(fmp_dividends: list[dict]) -> dict:
    """Normalize FMP dividends to BRAPI format.

    BRAPI: {"cashDividends": [...], "stockDividends": [...]}
    FMP:   flat list of dividend records
    """
    cash_dividends = []
    for dividend in fmp_dividends:
        payment_date = dividend.get("paymentDate") or dividend.get("date", "")
        amount = dividend.get("dividend") or dividend.get("adjDividend", 0)
        if payment_date and amount:
            cash_dividends.append({
                "paymentDate": payment_date,
                "value": amount,
                "type": "DIVIDENDO",
            })
    return {
        "cashDividends": cash_dividends,
        "stockDividends": [],
    }


def fetch_quote(ticker: str) -> dict:
    if is_brazilian_ticker(ticker):
        try:
            return brapi.fetch_quote(ticker)
        except brapi.BRAPIError as error:
            raise ProviderError(str(error)) from error
    else:
        try:
            raw = fmp.fetch_quote(ticker)
            return _normalize_fmp_quote(raw)
        except fmp.FMPError as error:
            raise ProviderError(str(error)) from error


def fetch_dividends(ticker: str):
    if is_brazilian_ticker(ticker):
        try:
            return brapi.fetch_dividends(ticker)
        except brapi.BRAPIError as error:
            raise ProviderError(str(error)) from error
    else:
        try:
            raw = fmp.fetch_dividends(ticker)
            return _normalize_fmp_dividends(raw)
        except fmp.FMPError as error:
            raise ProviderError(str(error)) from error


def fetch_historical_prices(ticker: str):
    if is_brazilian_ticker(ticker):
        try:
            return brapi.fetch_historical_prices(ticker)
        except brapi.BRAPIError as error:
            raise ProviderError(str(error)) from error
    else:
        try:
            raw = fmp.fetch_historical_prices(ticker)
            return _normalize_fmp_historical_prices(raw)
        except fmp.FMPError as error:
            raise ProviderError(str(error)) from error


def sync_earnings(ticker: str):
    return _route(brapi.sync_earnings, fmp.sync_earnings, ticker)


def sync_cash_flows(ticker: str):
    return _route(brapi.sync_cash_flows, fmp.sync_cash_flows, ticker)


def sync_balance_sheets(ticker: str):
    return _route(brapi.sync_balance_sheets, fmp.sync_balance_sheets, ticker)
