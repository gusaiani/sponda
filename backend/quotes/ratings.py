"""Indicator rating engine — Learning Mode v1.

Maps a numeric indicator value to a 1-5 tier (1 = worst, 5 = best). The
exact thresholds here are placeholders (methodology v1) and will be tuned
with sector-aware overrides in follow-up data-only changes; the *shape*
of the engine is what matters now: every indicator declares a direction
('lower' or 'higher' is better) plus four cuts that split the real line
into five tiers, with optional per-sector overrides.

Overall company grade is a rounded mean of the available per-indicator
ratings, returned only when at least :data:`MIN_INDICATORS_FOR_GRADE`
indicators could be rated.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping, Optional, Sequence

DEFAULT_SECTOR_KEY = "__default__"
MIN_INDICATORS_FOR_GRADE = 4
METHODOLOGY_VERSION = "v1"

# Per-indicator thresholds. Each entry is keyed by sector (or the default
# fallback) and maps to a direction + four numeric cuts. The cuts split
# values into five tiers; see :func:`rate_indicator` for the exact mapping.
RATING_THRESHOLDS: dict[str, dict[str, dict]] = {
    "pe10": {
        DEFAULT_SECTOR_KEY: {"direction": "lower", "cuts": [10, 15, 20, 30]},
    },
    "pfcf10": {
        DEFAULT_SECTOR_KEY: {"direction": "lower", "cuts": [12, 18, 25, 35]},
    },
    "peg": {
        DEFAULT_SECTOR_KEY: {"direction": "lower", "cuts": [0.5, 1.0, 1.5, 2.5]},
    },
    "pfcf_peg": {
        DEFAULT_SECTOR_KEY: {"direction": "lower", "cuts": [0.5, 1.0, 1.5, 2.5]},
    },
    "debt_to_equity": {
        DEFAULT_SECTOR_KEY: {"direction": "lower", "cuts": [0.3, 0.7, 1.5, 3.0]},
    },
    "debt_ex_lease_to_equity": {
        DEFAULT_SECTOR_KEY: {"direction": "lower", "cuts": [0.2, 0.5, 1.0, 2.0]},
    },
    "liabilities_to_equity": {
        DEFAULT_SECTOR_KEY: {"direction": "lower", "cuts": [0.5, 1.5, 3.0, 5.0]},
    },
    "current_ratio": {
        DEFAULT_SECTOR_KEY: {"direction": "higher", "cuts": [0.8, 1.2, 1.6, 2.5]},
    },
    "debt_to_avg_earnings": {
        DEFAULT_SECTOR_KEY: {"direction": "lower", "cuts": [2, 4, 6, 10]},
    },
    "debt_to_avg_fcf": {
        DEFAULT_SECTOR_KEY: {"direction": "lower", "cuts": [3, 5, 8, 12]},
    },
}

# Equal-weighted v1. A future revision can downweight redundant indicators
# (e.g. PE10 vs PFCF10 measure similar things) once we have data on which
# combinations correlate with realized returns.
INDICATOR_WEIGHTS: dict[str, float] = {indicator: 1.0 for indicator in RATING_THRESHOLDS}


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _tier_for_lower_better(value: float, cuts: Sequence[float]) -> int:
    if value <= cuts[0]:
        return 5
    if value <= cuts[1]:
        return 4
    if value <= cuts[2]:
        return 3
    if value <= cuts[3]:
        return 2
    return 1


def _tier_for_higher_better(value: float, cuts: Sequence[float]) -> int:
    if value <= cuts[0]:
        return 1
    if value <= cuts[1]:
        return 2
    if value <= cuts[2]:
        return 3
    if value <= cuts[3]:
        return 4
    return 5


def rate_indicator(
    indicator: str,
    value,
    sector: Optional[str] = None,
) -> Optional[int]:
    """Map a single indicator value to a 1-5 tier.

    Returns ``None`` when the indicator is unknown or the value is null.
    Sector overrides take precedence over the default thresholds.
    """
    if indicator not in RATING_THRESHOLDS:
        return None
    numeric_value = _to_float(value)
    if numeric_value is None:
        return None

    sector_table = RATING_THRESHOLDS[indicator]
    threshold = sector_table.get(sector or "", sector_table[DEFAULT_SECTOR_KEY])
    cuts = threshold["cuts"]
    direction = threshold["direction"]

    if direction == "lower":
        return _tier_for_lower_better(numeric_value, cuts)
    return _tier_for_higher_better(numeric_value, cuts)


def compute_overall_grade(ratings: Mapping[str, Optional[int]]) -> Optional[int]:
    """Round the weighted mean of available per-indicator ratings to 1-5.

    Returns ``None`` when fewer than :data:`MIN_INDICATORS_FOR_GRADE`
    indicators were rated — a half-graded company would mislead more than
    inform.
    """
    available = [(name, tier) for name, tier in ratings.items() if tier is not None]
    if len(available) < MIN_INDICATORS_FOR_GRADE:
        return None

    weighted_sum = 0.0
    total_weight = 0.0
    for name, tier in available:
        weight = INDICATOR_WEIGHTS.get(name, 1.0)
        weighted_sum += tier * weight
        total_weight += weight

    if total_weight == 0:
        return None
    mean = weighted_sum / total_weight
    return max(1, min(5, round(mean)))


def rate_company(
    indicator_values: Mapping[str, object],
    sector: Optional[str] = None,
) -> dict:
    """Rate every indicator we know how to rate, then compute the overall grade.

    Indicators not in :data:`RATING_THRESHOLDS` (e.g. ``market_cap``,
    ``current_price``) are silently skipped — they are stored in the
    snapshot but are not part of Learning Mode.
    """
    ratings: dict[str, Optional[int]] = {}
    for indicator in RATING_THRESHOLDS:
        if indicator in indicator_values:
            ratings[indicator] = rate_indicator(
                indicator, indicator_values[indicator], sector=sector,
            )
    overall = compute_overall_grade(ratings)
    return {
        "ratings": ratings,
        "overall": overall,
        "methodology_version": METHODOLOGY_VERSION,
    }
