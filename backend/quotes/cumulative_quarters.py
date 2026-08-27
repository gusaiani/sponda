"""Undo BRAPI differencing a quarter that was already a single quarter.

A Brazilian ITR reports the income statement twice: once for the three months
just ended and once for the year to date. Turning the second into discrete
quarters means subtracting the previous filing. For some companies BRAPI
applies that subtraction to the first column instead of the second, so what it
publishes as Q2 is really Q2 minus Q1, and Q3 is Q3 minus Q2.

Q1 survives because there is nothing before it to subtract, and Q4 survives
because nobody files it: BRAPI derives it from the audited annual less the
nine months, which is the one place its arithmetic uses a real year-to-date
figure. Only the two quarters in between are wrong.

The damage hides, because the annual then telescopes:

    Q1 + (Q2-Q1) + (Q3-Q2) + Q4  =  Q3 + Q4

Kepler Weber's 2025 came out as R$822m against R$1,490m filed, and reads as a
company that lost half its revenue. Petrobras understates 2025 revenue by 49%
and net income by 56%. In a part-year the same identity collapses further:
2026 to date reads as Q2 alone, so the first quarter appears to be missing
when in fact it cancelled.

Nothing here is a heuristic about plausible numbers. The company's own audited
annual filing decides, and it decides per year: BRAPI's pipeline broke during
2025, so the same company can be clean in 2024 and differenced in 2025. Where
the annual settles nothing, the figures are left exactly as filed. That
matters more than repairing every case, because the defect is far from
universal · of the eight largest B3 companies on this path, five are affected
and three are perfectly correct, and a blanket correction would break those
three as badly as the bug breaks the others.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

AS_REPORTED = "as-reported"
RUNNING_SUM = "running-sum"
UNDECIDED = "undecided"

# The provider rounds its own quarters: Kepler's restated 2025 revenue misses
# the audited annual by R$80 in R$1.49bn. A tolerance this loose is still
# nowhere near able to confuse the two readings, which differ by 46 points at
# the closest measured.
RECONCILIATION_TOLERANCE = Decimal("0.005")

QUARTERS_IN_A_YEAR = 4
LAST_DIFFERENCED_QUARTER = 3

# Fields restated together. EPS is net income over a share count, so it
# carries the same defect and would otherwise contradict the net income
# beside it.
RESTATED_FIELDS = ("revenue", "net_income", "eps")


@dataclass(frozen=True)
class AnnualIncome:
    """What the audited annual filing reports for one year."""

    revenue: int | None = None
    net_income: int | None = None

    @property
    def is_empty(self) -> bool:
        return self.revenue is None and self.net_income is None


def running_sum_restatement(reported: dict[int, object]) -> dict[int, object] | None:
    """Rebuild true quarters from ones differenced against their predecessor.

    ``reported[n]`` is Qn minus Q(n-1) for the second and third quarters, so
    the original is recovered by accumulating from the first. The fourth is
    taken whole.

    Returns ``None`` rather than a partial answer when the run cannot be
    rebuilt: the accumulation is only anchored by a first quarter, and a hole
    anywhere inside it would make every later quarter an invention. The fourth
    quarter is exempt, since nothing is accumulated through it.
    """
    if not reported or 1 not in reported:
        return None
    if sorted(reported) != list(range(1, len(reported) + 1)):
        return None

    accumulated_so_far = None
    restated: dict[int, object] = {}
    for quarter in sorted(reported):
        value = reported[quarter]
        if quarter > LAST_DIFFERENCED_QUARTER:
            restated[quarter] = value
            continue
        if value is None:
            return None
        accumulated_so_far = value if accumulated_so_far is None else accumulated_so_far + value
        restated[quarter] = accumulated_so_far
    return restated


def choose_restatement(
    reported_revenue: dict[int, object],
    reported_net_income: dict[int, object],
    annual: AnnualIncome,
) -> str:
    """Ask the audited annual which reading of the quarters is the real one.

    Revenue and net income are asked separately and must not contradict each
    other, since a provider cannot difference one line of a statement without
    differencing the one below it. A contradiction means something other than
    this bug is wrong, and nothing is touched.
    """
    verdicts = {
        _verdict_from_total(reported_revenue, annual.revenue),
        _verdict_from_total(reported_net_income, annual.net_income),
    }
    verdicts.discard(UNDECIDED)
    if len(verdicts) != 1:
        return UNDECIDED
    return verdicts.pop()


def _verdict_from_total(reported: dict[int, object], annual_total) -> str:
    """Which reading of a full year sums to the total the company filed."""
    if annual_total in (None, 0):
        return UNDECIDED
    if len(reported) != QUARTERS_IN_A_YEAR or any(v is None for v in reported.values()):
        return UNDECIDED

    restated = running_sum_restatement(reported)
    if restated is None:
        return UNDECIDED

    reported_ties = _ties_to(sum(reported.values()), annual_total)
    restated_ties = _ties_to(sum(restated.values()), annual_total)
    if reported_ties and not restated_ties:
        return AS_REPORTED
    if restated_ties and not reported_ties:
        return RUNNING_SUM
    # Neither reading works, or a year small enough that both do. Either way
    # the annual has not chosen, and guessing is what this module exists to
    # avoid.
    return UNDECIDED


def _ties_to(candidate, annual_total) -> bool:
    gap = abs(Decimal(candidate) - Decimal(annual_total)) / abs(Decimal(annual_total))
    return gap <= RECONCILIATION_TOLERANCE


def restate_quarterly_earnings(quarters: list, annual_by_year: dict[int, AnnualIncome]) -> list:
    """Correct every year the company's own annual filings condemn.

    Years are walked oldest first so a verdict can be carried forward into the
    year still in progress, which has no annual of its own yet and is the year
    a reader is most likely looking at. The verdict is a property of the
    provider's pipeline rather than of the quarter, so the most recent
    measurement is the best evidence available for the open year · but only
    evidence, so a carried verdict is still sanity-checked before it is
    applied. A year that has an annual and is not condemned by it is left
    alone, and does not inherit anything.

    Mutates and returns the objects it was given, because ingestion passes
    them straight to ``bulk_create``.
    """
    quarters_by_year = _grouped_by_year(quarters)
    carried_verdict = AS_REPORTED

    for year in sorted(quarters_by_year):
        by_quarter = quarters_by_year[year]
        annual = annual_by_year.get(year)

        if annual is not None and not annual.is_empty:
            verdict = choose_restatement(
                _field_values(by_quarter, "revenue"),
                _field_values(by_quarter, "net_income"),
                annual,
            )
            if verdict == UNDECIDED:
                continue
            carried_verdict = verdict
            if verdict == RUNNING_SUM:
                _apply_running_sum(by_quarter)
            continue

        if carried_verdict == RUNNING_SUM and _running_sum_is_plausible(by_quarter):
            _apply_running_sum(by_quarter)

    return quarters


def _grouped_by_year(quarters: list) -> dict[int, dict[int, object]]:
    """Index quarters by calendar year and quarter number.

    Calendar year rather than fiscal year deliberately: this path serves B3
    only, where the CVM requires a 31 December year end, and the fourth
    quarter's exemption is a fact about 31 December filings.

    A year holding two statements for the same quarter is dropped rather than
    silently resolved, since the accumulation depends on each step being one
    quarter wide.
    """
    grouped: dict[int, dict[int, object]] = {}
    duplicated: set[int] = set()
    for quarter in quarters:
        year = quarter.end_date.year
        number = (quarter.end_date.month - 1) // 3 + 1
        if number in grouped.setdefault(year, {}):
            duplicated.add(year)
        grouped[year][number] = quarter
    for year in duplicated:
        del grouped[year]
    return grouped


def _field_values(by_quarter: dict[int, object], field: str) -> dict[int, object]:
    return {number: getattr(quarter, field) for number, quarter in by_quarter.items()}


def _apply_running_sum(by_quarter: dict[int, object]) -> None:
    """Rewrite each restatable field, independently of the others.

    Independently because a company may report EPS on some quarters and not
    others, and a hole in one field is no reason to leave the rest differenced.
    """
    for field in RESTATED_FIELDS:
        restated = running_sum_restatement(_field_values(by_quarter, field))
        if restated is None:
            continue
        for number, value in restated.items():
            setattr(by_quarter[number], field, value)


def _running_sum_is_plausible(by_quarter: dict[int, object]) -> bool:
    """Reject a carried verdict that would drive revenue below zero.

    A carried verdict is the one place this module acts without the annual
    having spoken, so it gets the one check the annual would otherwise
    provide. If BRAPI repairs its pipeline mid-year the carried verdict
    becomes wrong, and subtracting a real quarter from a real quarter is what
    produces a negative. No company earns negative revenue, so that reading is
    refused and the year waits for its own annual.
    """
    restated = running_sum_restatement(_field_values(by_quarter, "revenue"))
    if restated is None:
        return False
    return all(value is None or value >= 0 for value in restated.values())
