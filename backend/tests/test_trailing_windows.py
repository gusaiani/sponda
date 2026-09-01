"""Unit tests for quotes.trailing_windows — the strict per-window average
shared by the P/E windows and the debt-coverage windows."""
from decimal import Decimal

from quotes.trailing_windows import strict_window_averages


class TestStrictWindowAverages:
    def test_every_window_within_history_averages_its_own_periods(self):
        # Newest first: four quarters of 8, then four quarters of 4.
        values = [Decimal(8)] * 4 + [Decimal(4)] * 4
        result = strict_window_averages(values, periods_per_year=4, max_years=3)
        assert result["years_available"] == 2
        assert result["average_by_years"] == {
            1: Decimal(32),
            2: Decimal(24),
            3: None,
        }

    def test_semi_annual_reporter_needs_two_periods_per_year(self):
        values = [Decimal(10)] * 6
        result = strict_window_averages(values, periods_per_year=2, max_years=5)
        assert result["years_available"] == 3
        assert result["average_by_years"][3] == Decimal(20)
        assert result["average_by_years"][4] is None

    def test_partial_year_is_never_counted_as_a_year(self):
        values = [Decimal(5)] * 7
        result = strict_window_averages(values, periods_per_year=4, max_years=2)
        assert result["years_available"] == 1
        assert result["average_by_years"] == {1: Decimal(20), 2: None}

    def test_no_periods_means_no_windows(self):
        result = strict_window_averages([], periods_per_year=4, max_years=2)
        assert result["years_available"] == 0
        assert result["average_by_years"] == {1: None, 2: None}

    def test_years_available_is_capped_at_max_years(self):
        values = [Decimal(1)] * 40
        result = strict_window_averages(values, periods_per_year=4, max_years=3)
        assert result["years_available"] == 3
