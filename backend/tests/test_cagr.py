"""Tests for the robust CAGR calculation module."""
import pytest

from quotes.cagr import compute_cagr


class TestEndpointCAGR:
    def test_simple_growth(self):
        values = [(2020, 100.0), (2021, 110.0), (2022, 121.0)]
        result = compute_cagr(values)
        assert result["method"] == "endpoint"
        assert result["cagr"] == pytest.approx(10.0, abs=0.1)
        assert result["excluded_years"] == []

    def test_no_growth(self):
        values = [(2020, 100.0), (2025, 100.0)]
        result = compute_cagr(values)
        assert result["method"] == "endpoint"
        assert result["cagr"] == pytest.approx(0.0, abs=0.01)

    def test_decline(self):
        values = [(2020, 100.0), (2025, 50.0)]
        result = compute_cagr(values)
        assert result["method"] == "endpoint"
        assert result["cagr"] is not None
        assert result["cagr"] < 0


class TestRegressionCAGR:
    def test_negative_start_year(self):
        """When the oldest year is negative, should fall back to regression."""
        values = [
            (2016, -13_000_000_000),
            (2017, 5_000_000_000),
            (2018, 10_000_000_000),
            (2019, 15_000_000_000),
            (2020, 20_000_000_000),
        ]
        result = compute_cagr(values)
        assert result["method"] == "regression"
        assert result["cagr"] is not None
        assert result["cagr"] > 0
        assert 2016 in result["excluded_years"]
        assert result["positive_years"] == 4

    def test_negative_end_year(self):
        """When the newest year is negative, should fall back to regression."""
        values = [
            (2018, 10_000_000_000),
            (2019, 15_000_000_000),
            (2020, 20_000_000_000),
            (2021, -5_000_000_000),
        ]
        result = compute_cagr(values)
        assert result["method"] == "regression"
        assert result["cagr"] is not None
        assert 2021 in result["excluded_years"]

    def test_multiple_negative_years(self):
        """Multiple negative years excluded, regression on the rest."""
        values = [
            (2016, -5_000),
            (2017, 100),
            (2018, -3_000),
            (2019, 200),
            (2020, 300),
        ]
        result = compute_cagr(values)
        assert result["method"] == "regression"
        assert set(result["excluded_years"]) == {2016, 2018}
        assert result["positive_years"] == 3


class TestEdgeCases:
    def test_single_value(self):
        result = compute_cagr([(2020, 100.0)])
        assert result["cagr"] is None
        assert result["method"] is None

    def test_empty_list(self):
        result = compute_cagr([])
        assert result["cagr"] is None

    def test_same_year(self):
        result = compute_cagr([(2020, 100.0), (2020, 200.0)])
        assert result["cagr"] is None

    def test_all_negative(self):
        result = compute_cagr([(2020, -100.0), (2021, -200.0)])
        assert result["cagr"] is None
        assert result["excluded_years"] == [2020, 2021]

    def test_only_one_positive(self):
        result = compute_cagr([(2020, -100.0), (2021, 200.0)])
        assert result["cagr"] is None
        assert result["positive_years"] == 1

    def test_zero_values_excluded(self):
        values = [(2020, 0.0), (2021, 100.0), (2022, 200.0)]
        result = compute_cagr(values)
        assert 2020 in result["excluded_years"]

    def test_unsorted_input(self):
        """Input doesn't need to be sorted — compute_cagr sorts internally."""
        values = [(2022, 121.0), (2020, 100.0), (2021, 110.0)]
        result = compute_cagr(values)
        assert result["method"] == "endpoint"
        assert result["cagr"] == pytest.approx(10.0, abs=0.1)
