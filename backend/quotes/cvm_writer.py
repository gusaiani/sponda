"""Write one parsed CVM quarter into the statement tables.

Shared by the manual seeder and the scheduled sync so both go through the same
checks. The parser's own gates establish that a filing is internally
consistent; what survives to here is a plausible wrong value, and this is the
last place to refuse it.

Precedence is BRAPI's. Its rows are the ten-year baseline that every P/E10
denominator is built from, so CVM fills gaps rather than competing: a quarter
that already has a row from another provider is left alone. Once BRAPI catches
up it overwrites the CVM row on ``(ticker, end_date)`` and restamps the source,
which is the intended end state rather than something to undo.
"""
from __future__ import annotations

import logging

from django.db import transaction

from .derived_data import refresh_derived_data
from .models import (
    SOURCE_CVM,
    BalanceSheet,
    QuarterlyCashFlow,
    QuarterlyEarnings,
)

logger = logging.getLogger(__name__)

FREE_CASH_FLOW_IS_DERIVED_DOWNSTREAM = None
EPS_IS_UNUSED = None

# Equity may legitimately swing on a large write-down, a rights issue or a
# spin-off, so the band is wide: it guards against reading the wrong line, not
# against unusual quarters. The bounds are exclusive, so a move of exactly an
# order of magnitude is refused rather than admitted.
EQUITY_CONTINUITY_MIN_RATIO = 0.1
EQUITY_CONTINUITY_MAX_RATIO = 10.0


class StatementRejected(Exception):
    """The parsed quarter did not survive validation and was not written."""


def existing_source(ticker: str, quarter_end) -> str | None:
    """Which provider already holds this quarter, or None if nobody does."""
    row = QuarterlyEarnings.objects.filter(
        ticker=ticker, end_date=quarter_end,
    ).first()
    return None if row is None else row.source


def is_writable(ticker: str, quarter_end) -> bool:
    """True when CVM may write this quarter without displacing another source."""
    source = existing_source(ticker, quarter_end)
    return source is None or source == SOURCE_CVM


def check_equity_continuity(ticker: str, statements) -> None:
    """Refuse equity that moved by an order of magnitude in one quarter.

    A company's equity does not move tenfold in three months. A parse that says
    it did has read the wrong line, and the figure it produces is plausible
    enough to reach a page and stay there.
    """
    equity = statements.stockholders_equity
    if equity is None:
        return

    previous = (
        BalanceSheet.objects
        .filter(ticker=ticker, end_date__lt=statements.quarter_end)
        .exclude(stockholders_equity=None)
        .order_by("-end_date")
        .first()
    )
    if previous is None or not previous.stockholders_equity:
        return

    ratio = abs(equity) / abs(previous.stockholders_equity)
    if not EQUITY_CONTINUITY_MIN_RATIO < ratio < EQUITY_CONTINUITY_MAX_RATIO:
        raise StatementRejected(
            f"{ticker}: equity moved from {previous.stockholders_equity:,} at "
            f"{previous.end_date} to {equity:,} at {statements.quarter_end} "
            f"({ratio:.2f}x). Refusing to write · this is a parse fault, not "
            f"a corporate event."
        )


@transaction.atomic
def write_quarter(ticker: str, statements) -> None:
    """Write one quarter and bring every derived artifact back in line."""
    check_equity_continuity(ticker, statements)

    QuarterlyEarnings.objects.update_or_create(
        ticker=ticker,
        end_date=statements.quarter_end,
        defaults={
            "revenue": statements.revenue,
            "net_income": statements.net_income,
            "eps": EPS_IS_UNUSED,
            "source": SOURCE_CVM,
        },
    )
    QuarterlyCashFlow.objects.update_or_create(
        ticker=ticker,
        end_date=statements.quarter_end,
        defaults={
            "operating_cash_flow": statements.operating_cash_flow,
            "investment_cash_flow": statements.investment_cash_flow,
            "free_cash_flow": FREE_CASH_FLOW_IS_DERIVED_DOWNSTREAM,
            "dividends_paid": statements.dividends_paid,
            "source": SOURCE_CVM,
        },
    )
    BalanceSheet.objects.update_or_create(
        ticker=ticker,
        end_date=statements.quarter_end,
        defaults={
            "total_debt": statements.total_debt,
            "total_lease": statements.total_lease,
            "total_liabilities": statements.total_liabilities,
            "stockholders_equity": statements.stockholders_equity,
            "current_assets": statements.current_assets,
            "current_liabilities": statements.current_liabilities,
            "source": SOURCE_CVM,
        },
    )
    refresh_derived_data(ticker)
    logger.info("Wrote %s %s from CVM ITR", ticker, statements.quarter_end)
