"""Which fiscal year a statement period belongs to.

Every per-year figure Sponda shows · the Fundamentos table, the annual
earnings and cash flows behind the P/E and P/FCF windows, the multiples
history · has to decide which year a quarter belongs to. Using the calendar
year the quarter ends in is right only for filers that close on 31 December,
and about a quarter of the companies covered do not.

Two wrongs follow from getting it wrong. The audited year-end balance sheet
is overwritten by a later quarter that shares its calendar year and never
appears at all: Salesforce's 31 January 2026 close is buried under its April
and July quarters. And the "annual" income becomes a rolling four quarters
offset from the year the company reported: Starbucks' 2025 row summed its
March, June, September and December quarters, which is the back half of
fiscal 2025 and the front of fiscal 2026.

``fiscal_year_of`` is the single answer to that question. Everything that
groups statements by year goes through it.
"""
from __future__ import annotations

from datetime import date

FIRST_MONTH_OF_THE_YEAR = 1
LAST_MONTH_OF_THE_YEAR = 12


def fiscal_year_of(statement) -> int:
    """Return the fiscal year of one statement row.

    Prefers the figure the provider reported. Falls back to the calendar
    year of the period end, which is correct for every filer that closes on
    31 December and is the best available guess for the rest until the
    backfill reaches them.
    """
    reported = getattr(statement, "fiscal_year", None)
    if reported is not None:
        return reported
    return statement.end_date.year


def fiscal_year_from_year_end_month(end_date: date, year_end_month: int) -> int:
    """Derive a fiscal year from the month a company closes its books in.

    A period ending after the company's close belongs to the fiscal year
    that ends in the *following* calendar year. Salesforce closes in
    January, so its April 2026 quarter is fiscal 2027; its January 2026
    quarter is fiscal 2026. A December filer never rolls, because no month
    falls after December.

    Used by the backfill for the rows stored before the provider's own
    figure was being kept.
    """
    if end_date.month > year_end_month:
        return end_date.year + 1
    return end_date.year


def parse_reported_fiscal_year(value) -> int | None:
    """Read a provider's fiscal-year field, which FMP sends as a string.

    Anything unparseable is treated as absent rather than guessed at: the
    calendar-year fallback is a known quantity, a mangled year is not.
    """
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
