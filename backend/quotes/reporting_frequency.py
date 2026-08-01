"""Infer how many financial statements a company files per year.

Most companies file quarterly (4 periods/year), but some file
semi-annually (e.g. Rio Tinto: H1 + full year) and some annually
(BRAPI tickers without quarterly modules). Window math that hard-codes
"4 filings = 1 year" halves the usable history of a semi-annual
reporter and quadruples an annual one's.
"""
from collections import Counter

ANNUAL_PERIODS_PER_YEAR = 1
SEMI_ANNUAL_PERIODS_PER_YEAR = 2
QUARTERLY_PERIODS_PER_YEAR = 4


def infer_periods_per_year(annual_data: list[dict]) -> int:
    """
    Infer the filing frequency (1, 2, or 4 periods per year) from
    per-calendar-year filing counts, newest year first.

    The most recent year is excluded from the inference — it may still
    be in progress. When no complete prior year exists the frequency is
    unknowable, so assume quarterly: that way a partial year is never
    presented as a full one. Counts of 3+ (a quarterly reporter with a
    missing filing, or calendar bucketing of an off-quarter fiscal
    year) resolve to quarterly.
    """
    prior_year_counts = [year_data["quarters"] for year_data in annual_data[1:]]
    if not prior_year_counts:
        return QUARTERLY_PERIODS_PER_YEAR

    count_frequencies = Counter(prior_year_counts)
    most_common_count = max(
        count_frequencies.items(),
        key=lambda item: (item[1], item[0]),
    )[0]

    if most_common_count >= 3:
        return QUARTERLY_PERIODS_PER_YEAR
    if most_common_count == SEMI_ANNUAL_PERIODS_PER_YEAR:
        return SEMI_ANNUAL_PERIODS_PER_YEAR
    return ANNUAL_PERIODS_PER_YEAR
