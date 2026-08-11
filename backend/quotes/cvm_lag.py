"""Turn recorded CVM builds and filings into a latency measurement.

Two quantities decide whether ingesting from the CVM is worth building on:

* **Publication lag** — days from the CVM receiving a filing to publishing it.
* **Rebuild interval** — how often the archive is republished at all.

The second dominates. A one-day publication lag buys nothing if the archive is
only rebuilt weekly, because a filing received the day after a rebuild waits
for the next one no matter how often it is polled.

Every figure here is derived from observations, never assumed. Filings whose
lag cannot be measured are excluded from the distribution rather than counted
as zero, and a single build is reported as no cadence at all rather than as a
cadence of one.

The subtle one is backfill. The first poll records every filing published so
far that year, all attributed to the build that happened to be current. Those
filings were not watched into existence — one received in April and first
recorded in August may well have been published in April — so treating the
gap as lag invents months of latency. A lag is only a measurement when an
earlier build was observed that could have carried the filing and did not,
which is to say when the filing was received after observation began.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime

from django.utils import timezone

from .models import SOURCE_CVM, CvmArchiveBuild, CvmFiling, QuarterlyEarnings

SECONDS_PER_DAY = 86_400
NINETIETH_PERCENTILE = 0.9


@dataclass(frozen=True)
class LagReport:
    """What the recorded observations say about CVM's publication latency."""

    year: int
    build_count: int
    filing_count: int
    observation_start: datetime | None = None
    rebuild_interval_days: list[float] = field(default_factory=list)
    publication_lag_days: list[int] = field(default_factory=list)
    backfilled_filing_count: int = 0

    @property
    def measured_filing_count(self) -> int:
        """Filings whose lag is known, which is what the distribution covers."""
        return len(self.publication_lag_days)

    @property
    def median_rebuild_interval_days(self) -> float | None:
        return _median(self.rebuild_interval_days)

    @property
    def max_rebuild_interval_days(self) -> float | None:
        return max(self.rebuild_interval_days, default=None)

    @property
    def median_publication_lag_days(self) -> int | None:
        median = _median(self.publication_lag_days)
        return None if median is None else int(round(median))

    @property
    def p90_publication_lag_days(self) -> int | None:
        return _percentile(self.publication_lag_days, NINETIETH_PERCENTILE)

    @property
    def max_publication_lag_days(self) -> int | None:
        return max(self.publication_lag_days, default=None)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2


def _percentile(values: list[int], fraction: float) -> int | None:
    """Nearest-rank percentile — the smallest observed value at or above it.

    Nearest-rank rather than interpolated so the figure is always a lag that
    actually happened, which is what a worst-case claim should rest on.
    """
    if not values:
        return None
    ordered = sorted(values)
    rank = min(len(ordered), max(1, math.ceil(len(ordered) * fraction)))
    return ordered[rank - 1]


def _rebuild_intervals(year: int) -> list[float]:
    stamps = list(
        CvmArchiveBuild.objects.filter(year=year)
        .order_by("last_modified")
        .values_list("last_modified", flat=True)
    )
    return [
        (later - earlier).total_seconds() / SECONDS_PER_DAY
        for earlier, later in zip(stamps, stamps[1:])
    ]


def build_lag_report(year: int, reference_date: date | None = None) -> LagReport:
    """Summarize publication latency for one archive year.

    ``reference_date`` narrows to a single reported quarter, which is how a
    single earnings season is inspected without the previous one's long-settled
    filings flattening the distribution.
    """
    filings = CvmFiling.objects.filter(
        first_seen_in__year=year,
    ).select_related("first_seen_in")
    if reference_date is not None:
        filings = filings.filter(reference_date=reference_date)
    filings = list(filings)

    earliest_build = _earliest_build(year)
    lags, backfilled = _partition_by_measurability(filings, earliest_build)
    observation_start = earliest_build.last_modified if earliest_build else None

    return LagReport(
        year=year,
        build_count=CvmArchiveBuild.objects.filter(year=year).count(),
        filing_count=len(filings),
        observation_start=observation_start,
        rebuild_interval_days=_rebuild_intervals(year),
        publication_lag_days=lags,
        backfilled_filing_count=backfilled,
    )


def _earliest_build(year: int) -> CvmArchiveBuild | None:
    """The first build recorded, i.e. when we began watching this archive."""
    return (
        CvmArchiveBuild.objects.filter(year=year).order_by("last_modified").first()
    )


def _partition_by_measurability(
    filings: list[CvmFiling], earliest_build: CvmArchiveBuild | None,
) -> tuple[list[int], int]:
    """Split filings into measured lags and backfill that only looks like lag.

    The test is whether a filing first appeared in a build later than the
    earliest one recorded. If it did, an observation exists that could have
    carried it and did not, which is what dates its publication. If it was
    already present in the very first build we saw, it arrived unwatched.

    Deliberately not a test on the receipt date: a filing received before
    polling began but absent from the first observed build was still watched
    into existence, and it is exactly the slow filings that fall in that gap.
    Excluding them would bias the distribution toward flattering the CVM.
    """
    if earliest_build is None:
        return [], 0

    lags: list[int] = []
    backfilled = 0
    for filing in filings:
        lag = filing.publication_lag_days
        if lag is None:
            continue
        if filing.first_seen_in_id == earliest_build.id:
            backfilled += 1
            continue
        lags.append(lag)
    return lags, backfilled


# --- Filing to live ---------------------------------------------------------
#
# The goal stated as a number. "As near their quarterly publishing dates as
# possible" is an aspiration until something can regress and be noticed, and
# this is the thing that can.
#
# Measured per row from the date CVM received the filing (DT_RECEB, stored on
# the row so it does not depend on the ticker mapping still resolving the same
# way) to when the row was written. It therefore includes every hop we control
# — CVM's publication lag, its rebuild cadence, our poll interval and the sync
# cadence — which is what a reader of the site actually experiences.


@dataclass(frozen=True)
class FreshnessReport:
    """How long CVM-sourced quarters took to go from filed to live."""

    row_count: int
    days_to_live: list[int] = field(default_factory=list)
    caught_up_row_count: int = 0

    @property
    def median_days_to_live(self) -> int | None:
        median = _median(self.days_to_live)
        return None if median is None else int(round(median))

    @property
    def p90_days_to_live(self) -> int | None:
        return _percentile(self.days_to_live, NINETIETH_PERCENTILE)

    @property
    def max_days_to_live(self) -> int | None:
        return max(self.days_to_live, default=None)


def build_freshness_report(reference_date: date | None = None) -> FreshnessReport:
    """Days from filing to live across every CVM-sourced quarter.

    Rows from other providers are excluded rather than counted as zero: they
    carry no filing date, and their latency is a property of that provider
    rather than of this pipeline.

    So are quarters filed before we could ingest them. The first sync wrote
    quarters filed months earlier, because that is when the feature shipped ·
    counting those reported a p90 of 89 days and a max of 99, figures that
    describe when ingestion began rather than how long it takes. A row counts
    only when its filing arrived after the archive was first observed, which
    is the same window the publication-lag report uses.
    """
    rows = QuarterlyEarnings.objects.filter(
        source=SOURCE_CVM,
    ).exclude(filed_at=None).only("filed_at", "fetched_at", "end_date")
    if reference_date is not None:
        rows = rows.filter(end_date=reference_date)
    rows = list(rows)

    watched_from = _watching_since()
    days, caught_up = [], 0
    for row in rows:
        if watched_from is None or row.filed_at <= watched_from:
            caught_up += 1
            continue
        days.append((timezone.localtime(row.fetched_at).date() - row.filed_at).days)

    return FreshnessReport(
        row_count=len(rows),
        days_to_live=days,
        caught_up_row_count=caught_up,
    )


def _watching_since() -> date | None:
    """The earliest archive build recorded, in the filing dates' own timezone."""
    earliest = (
        CvmArchiveBuild.objects.order_by("last_modified")
        .values_list("last_modified", flat=True)
        .first()
    )
    return None if earliest is None else timezone.localtime(earliest).date()
