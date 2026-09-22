"""Which archive years the scheduled CVM commands cover.

The poll and the sync have to agree: the sync can only write a quarter the
poll has recorded, so a window that differs between them leaves filings
listed and never ingested.
"""
from django.utils import timezone

# How many archive years a scheduled run covers. One is not enough: a quarter
# can go unwritten for reasons that only surface later · a provider that
# quietly stops publishing a company, a ticker remapped after a merger, a
# restatement · and on 1 January a window of one stops looking at the year
# that holds it. Natura's Q3 2025 was published by CVM in November 2025 and
# sat unread until it was found by hand.
SCHEDULED_YEARS_COVERED = 2


def scheduled_years(named_year: int | None, *, newest_offset: int = 0) -> list[int]:
    """The archive years a run covers · newest first.

    A named year is taken literally, and is how an operator reaches further
    back than the routine window.

    ``newest_offset`` moves the window back for a command whose newest usable
    year is not the current one. The annual DFP is the case: a reporting year
    is not published until the following March, so the Q4 derivation starts
    from last year rather than this one.
    """
    if named_year:
        return [named_year]
    newest_year = timezone.localdate().year - newest_offset
    return [newest_year - offset for offset in range(SCHEDULED_YEARS_COVERED)]
