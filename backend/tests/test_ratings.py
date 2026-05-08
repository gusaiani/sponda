"""Tests for the indicator rating engine.

Five-tier scale (1=worst, 5=best). Lower-is-better and higher-is-better
indicators share the same machinery via a per-indicator direction flag.
The exact threshold values are tuned in :mod:`quotes.ratings`; these tests
pin the *behavior* (boundary handling, null fallthrough, sector overrides,
weighted grade math) rather than the exact numbers.
"""
from decimal import Decimal

import pytest

from quotes.ratings import (
    MIN_INDICATORS_FOR_GRADE,
    RATING_THRESHOLDS,
    compute_overall_grade,
    rate_company,
    rate_indicator,
)


class TestRateIndicator:
    def test_returns_none_for_unknown_indicator(self):
        assert rate_indicator("not_an_indicator", Decimal("1")) is None

    def test_returns_none_for_null_value(self):
        assert rate_indicator("pe10", None) is None

    def test_pe10_lower_value_gets_higher_tier(self):
        cheap = rate_indicator("pe10", Decimal("8"))
        expensive = rate_indicator("pe10", Decimal("40"))
        assert cheap is not None and expensive is not None
        assert cheap > expensive

    def test_current_ratio_higher_value_gets_higher_tier(self):
        weak = rate_indicator("current_ratio", Decimal("0.5"))
        strong = rate_indicator("current_ratio", Decimal("3.0"))
        assert weak is not None and strong is not None
        assert strong > weak

    def test_debt_ex_lease_to_equity_lower_is_better(self):
        clean = rate_indicator("debt_ex_lease_to_equity", Decimal("0.1"))
        leveraged = rate_indicator("debt_ex_lease_to_equity", Decimal("5.0"))
        assert clean is not None and leveraged is not None
        assert clean > leveraged

    def test_debt_to_equity_is_no_longer_rated_directly(self):
        # debt_to_equity was dropped from Learning Mode in favour of
        # debt_ex_lease_to_equity (with a value-level fallback handled by
        # rate_company). Asking rate_indicator directly for D/E returns None.
        assert rate_indicator("debt_to_equity", Decimal("0.5")) is None

    def test_returns_integer_in_range_one_to_five(self):
        for indicator in RATING_THRESHOLDS:
            for value in [Decimal("-100"), Decimal("0"), Decimal("1"), Decimal("100")]:
                rating = rate_indicator(indicator, value)
                if rating is not None:
                    assert 1 <= rating <= 5
                    assert isinstance(rating, int)

    def test_accepts_python_float_and_int(self):
        assert rate_indicator("pe10", 8) is not None
        assert rate_indicator("pe10", 8.5) is not None

    def test_extreme_low_value_lower_is_better_caps_at_five(self):
        assert rate_indicator("debt_ex_lease_to_equity", Decimal("0")) == 5

    def test_extreme_high_value_lower_is_better_floors_at_one(self):
        assert rate_indicator("debt_ex_lease_to_equity", Decimal("999")) == 1

    def test_sector_override_used_when_available(self, monkeypatch):
        # Patch in a sector override so we know the lookup path is wired up.
        # Default for D-Lease/E rates 1.0 as average tier; for "Utilities" we set
        # the same value to count as good (utilities run leveraged by design).
        monkeypatch.setitem(
            RATING_THRESHOLDS["debt_ex_lease_to_equity"],
            "Utilities",
            {"direction": "lower", "cuts": [2.0, 3.0, 4.0, 5.0]},
        )
        default_rating = rate_indicator("debt_ex_lease_to_equity", Decimal("1.0"))
        utility_rating = rate_indicator(
            "debt_ex_lease_to_equity", Decimal("1.0"), sector="Utilities",
        )
        assert utility_rating is not None and default_rating is not None
        assert utility_rating > default_rating

    def test_sector_falls_back_to_default_when_no_override(self):
        default_rating = rate_indicator("pe10", Decimal("15"))
        sector_rating = rate_indicator("pe10", Decimal("15"), sector="Some-Sector-No-Override")
        assert sector_rating == default_rating


class TestComputeOverallGrade:
    def test_returns_none_when_too_few_indicators(self):
        ratings = {"pe10": 4, "pfcf10": 5}  # below MIN_INDICATORS_FOR_GRADE
        assert MIN_INDICATORS_FOR_GRADE > 2
        assert compute_overall_grade(ratings) is None

    def test_ignores_null_indicators(self):
        ratings = {"pe10": None, "pfcf10": None, "debt_ex_lease_to_equity": None}
        assert compute_overall_grade(ratings) is None

    def test_average_of_uniform_ratings(self):
        ratings = {f"ind_{i}": 4 for i in range(MIN_INDICATORS_FOR_GRADE)}
        # The overall grade rounds the weighted mean. With all-4 inputs the
        # mean is exactly 4.
        assert compute_overall_grade(ratings) == 4

    def test_rounds_to_nearest_integer(self):
        ratings = {
            "pe10": 5,
            "pfcf10": 4,
            "debt_ex_lease_to_equity": 3,
            "current_ratio": 5,
        }
        # mean = 4.25 → 4
        assert compute_overall_grade(ratings) == 4

    def test_returns_one_when_all_inputs_one(self):
        ratings = {f"ind_{i}": 1 for i in range(MIN_INDICATORS_FOR_GRADE)}
        assert compute_overall_grade(ratings) == 1

    def test_returns_five_when_all_inputs_five(self):
        ratings = {f"ind_{i}": 5 for i in range(MIN_INDICATORS_FOR_GRADE)}
        assert compute_overall_grade(ratings) == 5


class TestRateCompany:
    def test_returns_per_indicator_ratings_and_overall_grade(self):
        result = rate_company(
            {
                "pe10": Decimal("12"),
                "pfcf10": Decimal("15"),
                "debt_ex_lease_to_equity": Decimal("0.5"),
                "current_ratio": Decimal("2.0"),
                "peg": Decimal("0.8"),
            },
            sector="Tech",
        )
        assert "ratings" in result
        assert "overall" in result
        assert result["ratings"]["pe10"] is not None
        assert result["ratings"]["pfcf10"] is not None
        assert result["overall"] is not None
        assert 1 <= result["overall"] <= 5

    def test_handles_partial_data(self):
        result = rate_company({"pe10": Decimal("12")})
        assert result["ratings"]["pe10"] is not None
        assert result["overall"] is None  # too few indicators

    def test_skips_unrated_indicators(self):
        # market_cap, current_price, and debt_to_equity are not rated as
        # standalone indicators (debt_to_equity only feeds the
        # debt_ex_lease_to_equity rating as a fallback value).
        result = rate_company(
            {
                "pe10": Decimal("12"),
                "pfcf10": Decimal("15"),
                "debt_ex_lease_to_equity": Decimal("0.5"),
                "current_ratio": Decimal("2.0"),
                "market_cap": Decimal("1000000000"),
                "current_price": Decimal("35"),
            },
        )
        assert "market_cap" not in result["ratings"]
        assert "current_price" not in result["ratings"]
        assert "debt_to_equity" not in result["ratings"]

    def test_debt_to_equity_falls_back_to_rate_debt_ex_lease(self):
        # When debt_ex_lease_to_equity is missing but debt_to_equity is
        # present, the leverage rating is keyed at debt_ex_lease_to_equity
        # using the D/E value (and the D-Lease/E thresholds).
        result = rate_company(
            {
                "debt_ex_lease_to_equity": None,
                "debt_to_equity": Decimal("0.4"),
            },
        )
        assert "debt_to_equity" not in result["ratings"]
        assert result["ratings"]["debt_ex_lease_to_equity"] is not None
        assert result["ratings"]["debt_ex_lease_to_equity"] == rate_indicator(
            "debt_ex_lease_to_equity", Decimal("0.4"),
        )

    def test_debt_ex_lease_preferred_over_debt_to_equity_fallback(self):
        # When both values are present, the primary debt_ex_lease_to_equity
        # value wins — the D/E fallback is ignored.
        result = rate_company(
            {
                "debt_ex_lease_to_equity": Decimal("0.2"),
                "debt_to_equity": Decimal("5.0"),  # would rate poorly
            },
        )
        assert result["ratings"]["debt_ex_lease_to_equity"] == rate_indicator(
            "debt_ex_lease_to_equity", Decimal("0.2"),
        )
