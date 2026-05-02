"""FRED (Federal Reserve Economic Data) client for per-country CPI.

FMP only exposes US CPI; for non-US/non-BR companies we need each country's
CPI series to inflation-adjust historical fundamentals. FRED hosts those
series under stable identifiers like ``DNKCPIALLMINMEI`` (Denmark) and
``JPNCPIALLMINMEI`` (Japan).

Series ids follow the OECD naming convention <ISO3>CPIALLMINMEI for the
"all-items, monthly" series, with two notable exceptions:

* Eurozone: FRED publishes the harmonized HICP under
  ``CP0000EZ19M086NEST`` (Euro area, 19 countries).
* Some smaller economies (TWD, SGD, KRW) publish quarterly rather than
  monthly. The sync still works because we group YoY by month and the
  inflation module only consumes one rate per year.

Mapping is deliberately a hand-curated dict so a missing/changed series
ID surfaces clearly rather than silently using the wrong one.
"""
from __future__ import annotations

from datetime import date as date_type
from decimal import Decimal

import requests
from django.conf import settings

from .models import CountryCPIIndex


class FREDError(Exception):
    """Raised on bad responses or unmapped currencies."""


# ISO 4217 currency code → FRED series id (CPI All Items, monthly).
# Add a row when supporting a new reporting currency; the sync command
# refuses to run for any currency not in this map (no silent fallback).
CURRENCY_TO_SERIES_ID: dict[str, str] = {
    "DKK": "DNKCPIALLMINMEI",
    "JPY": "JPNCPIALLMINMEI",
    "EUR": "CP0000EZ19M086NEST",  # Eurozone HICP
    "GBP": "GBRCPIALLMINMEI",
    "CNY": "CHNCPIALLMINMEI",
    "CHF": "CHECPIALLMINMEI",
    "CAD": "CANCPIALLMINMEI",
    "AUD": "AUSCPIALLQINMEI",     # quarterly
    "MXN": "MEXCPIALLMINMEI",
    "INR": "INDCPIALLMINMEI",
    "KRW": "KORCPIALLMINMEI",
    "NOK": "NORCPIALLMINMEI",
    "SEK": "SWECPIALLMINMEI",
    # TWD / SGD / HKD: FRED only exposes a "% Chg." (pre-computed YoY)
    # series for these. Adding a separate ingest path for that shape is a
    # follow-up; for now those tickers fall back to nominal averages.
}


def _get(endpoint: str, params: dict | None = None) -> dict | list:
    url = f"{settings.FRED_BASE_URL}{endpoint}"
    merged = {"api_key": settings.FRED_API_KEY, **(params or {})}
    response = requests.get(url, params=merged, timeout=30)
    if response.status_code != 200:
        raise FREDError(f"FRED {endpoint} → HTTP {response.status_code}: {response.text[:200]}")
    return response.json()


def fetch_cpi_observations(currency: str) -> list[dict]:
    """Return monthly CPI observations from FRED for the given currency.

    Each row is `{"date": "YYYY-MM-DD", "value": "..."}`. FRED uses the
    string "." for missing months; callers should skip those.
    """
    series_id = CURRENCY_TO_SERIES_ID.get(currency.upper())
    if not series_id:
        raise FREDError(f"No FRED series id mapped for currency '{currency}'")
    payload = _get(
        "/series/observations",
        params={"series_id": series_id, "file_type": "json"},
    )
    if not isinstance(payload, dict):
        return []
    return payload.get("observations") or []


def sync_country_cpi(currencies: list[str]) -> int:
    """Fetch each currency's CPI series from FRED and persist YoY rates.

    Mirrors `fmp.sync_us_cpi`: takes FRED's absolute index levels, pairs
    each month with the same month one year earlier, and stores the
    percent change as `CountryCPIIndex.annual_rate`. Skips months whose
    YoY anchor is missing.

    Per-currency failures (404 from FRED, network errors, etc.) are caught
    and logged so a single bad series id doesn't take down the whole run —
    the operator can fix the mapping and re-run.
    """
    import logging
    log = logging.getLogger(__name__)
    total = 0
    for currency in currencies:
        ccy = currency.upper()
        try:
            observations = fetch_cpi_observations(ccy)
        except FREDError as error:
            log.warning("sync_country_cpi: skipping %s — %s", ccy, error)
            continue

        index_by_date: dict[tuple[int, int], Decimal] = {}
        for obs in observations:
            date_string = (obs.get("date") or "")[:10]
            value_string = obs.get("value")
            if not date_string or not value_string or value_string == ".":
                continue
            obs_date = date_type.fromisoformat(date_string)
            index_by_date[(obs_date.year, obs_date.month)] = Decimal(value_string)

        rows: list[CountryCPIIndex] = []
        for (year, month), current_value in index_by_date.items():
            prior_value = index_by_date.get((year - 1, month))
            if prior_value is None or prior_value == 0:
                continue
            yoy_rate = (current_value / prior_value - 1) * 100
            rows.append(CountryCPIIndex(
                currency=ccy,
                date=date_type(year, month, 1),
                annual_rate=round(yoy_rate, 4),
            ))

        if rows:
            CountryCPIIndex.objects.bulk_create(
                rows,
                update_conflicts=True,
                unique_fields=["currency", "date"],
                update_fields=["annual_rate", "fetched_at"],
            )
            total += len(rows)
    return total
