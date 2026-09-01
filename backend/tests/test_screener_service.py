"""Unit tests for quotes.screener.run_screener — the plain-Python screener
query service, callable in-process without going through HTTP.
"""
from decimal import Decimal

import pytest

from quotes.models import IndicatorSnapshot, Ticker
from quotes.screener import (
    SCREENER_DEFAULT_LIMIT,
    SCREENER_MAX_LIMIT,
    ScreenerError,
    run_screener,
)


@pytest.fixture
def snapshot_universe(db):
    """Three companies with distinct indicator profiles for filter/sort testing."""
    Ticker.objects.create(
        symbol="PETR4", name="Petrobras", display_name="Petrobras",
        sector="Oil", type="stock", logo="https://example.com/petr4.png",
        market_cap=400_000_000_000, country="BR",
    )
    IndicatorSnapshot.objects.create(
        ticker="PETR4",
        pe10=Decimal("6.5"), pfcf10=Decimal("8.0"), peg=Decimal("0.5"),
        debt_to_equity=Decimal("1.2"), liabilities_to_equity=Decimal("2.0"),
        current_ratio=Decimal("1.4"),
        debt_to_avg_earnings=Decimal("3.0"), debt_to_avg_fcf=Decimal("4.5"),
        market_cap=400_000_000_000, current_price=Decimal("35.75"),
    )

    Ticker.objects.create(
        symbol="WEGE3", name="Weg", display_name="WEG",
        sector="Industrial", type="stock", logo="https://example.com/wege3.png",
        market_cap=200_000_000_000, country="BR",
    )
    IndicatorSnapshot.objects.create(
        ticker="WEGE3",
        pe10=Decimal("35.0"), pfcf10=Decimal("40.0"), peg=Decimal("2.5"),
        debt_to_equity=Decimal("0.3"), liabilities_to_equity=Decimal("0.8"),
        current_ratio=Decimal("2.5"),
        debt_to_avg_earnings=Decimal("1.0"), debt_to_avg_fcf=Decimal("1.5"),
        market_cap=200_000_000_000, current_price=Decimal("42.00"),
    )

    Ticker.objects.create(
        symbol="MICRO3", name="Micro", display_name="Micro",
        sector="Retail", type="stock", logo="",
        market_cap=1_000_000_000, country="US",
    )
    IndicatorSnapshot.objects.create(
        ticker="MICRO3",
        pe10=Decimal("12.0"), pfcf10=Decimal("15.0"), peg=Decimal("1.2"),
        debt_to_equity=Decimal("4.0"), liabilities_to_equity=Decimal("6.0"),
        current_ratio=Decimal("0.8"),
        debt_to_avg_earnings=Decimal("10.0"), debt_to_avg_fcf=Decimal("12.0"),
        market_cap=1_000_000_000, current_price=Decimal("2.50"),
    )


@pytest.mark.django_db
class TestRunScreenerFilters:
    def test_no_filters_returns_all(self, snapshot_universe):
        count, results = run_screener(
            bounds={}, sectors=[], countries=[], sort="ticker", limit=50, offset=0,
        )
        assert count == 3
        assert {row["ticker"] for row in results} == {"PETR4", "WEGE3", "MICRO3"}

    def test_min_only_bound(self, snapshot_universe):
        count, results = run_screener(
            bounds={"pe10": {"min": Decimal("20")}},
            sectors=[], countries=[], sort="ticker", limit=50, offset=0,
        )
        assert count == 1
        assert results[0]["ticker"] == "WEGE3"

    def test_max_only_bound(self, snapshot_universe):
        count, results = run_screener(
            bounds={"pe10": {"max": Decimal("10")}},
            sectors=[], countries=[], sort="ticker", limit=50, offset=0,
        )
        assert count == 1
        assert results[0]["ticker"] == "PETR4"

    def test_min_and_max_bound(self, snapshot_universe):
        count, results = run_screener(
            bounds={"pe10": {"min": Decimal("10"), "max": Decimal("20")}},
            sectors=[], countries=[], sort="ticker", limit=50, offset=0,
        )
        assert count == 1
        assert results[0]["ticker"] == "MICRO3"

    def test_bound_with_none_min_and_max_is_a_no_op(self, snapshot_universe):
        count, results = run_screener(
            bounds={"pe10": {"min": None, "max": None}},
            sectors=[], countries=[], sort="ticker", limit=50, offset=0,
        )
        assert count == 3

    def test_unknown_bound_field_is_ignored(self, snapshot_universe):
        count, results = run_screener(
            bounds={"market_cap": {"min": Decimal("1")}},
            sectors=[], countries=[], sort="ticker", limit=50, offset=0,
        )
        assert count == 3

    def test_excludes_rows_with_null_filtered_field(self, db):
        Ticker.objects.create(symbol="T1", name="T1", market_cap=100_000_000_000)
        Ticker.objects.create(symbol="T2", name="T2", market_cap=100_000_000_000)
        IndicatorSnapshot.objects.create(
            ticker="T1", pe10=Decimal("5"), market_cap=100_000_000_000,
        )
        IndicatorSnapshot.objects.create(
            ticker="T2", pe10=None, market_cap=100_000_000_000,
        )
        count, results = run_screener(
            bounds={"pe10": {"max": Decimal("10")}},
            sectors=[], countries=[], sort="ticker", limit=50, offset=0,
        )
        assert count == 1
        assert results[0]["ticker"] == "T1"

    def test_sector_filter(self, snapshot_universe):
        count, results = run_screener(
            bounds={}, sectors=["Oil"], countries=[], sort="ticker", limit=50, offset=0,
        )
        assert {row["ticker"] for row in results} == {"PETR4"}

    def test_multiple_sectors_filter(self, snapshot_universe):
        count, results = run_screener(
            bounds={}, sectors=["Oil", "Industrial"], countries=[],
            sort="ticker", limit=50, offset=0,
        )
        assert {row["ticker"] for row in results} == {"PETR4", "WEGE3"}

    def test_country_filter(self, snapshot_universe):
        count, results = run_screener(
            bounds={}, sectors=[], countries=["US"], sort="ticker", limit=50, offset=0,
        )
        assert {row["ticker"] for row in results} == {"MICRO3"}

    def test_sector_and_country_combine(self, snapshot_universe):
        count, results = run_screener(
            bounds={}, sectors=["Oil"], countries=["BR"], sort="ticker",
            limit=50, offset=0,
        )
        assert {row["ticker"] for row in results} == {"PETR4"}

    def test_empty_result_set(self, snapshot_universe):
        count, results = run_screener(
            bounds={}, sectors=["NoSuchSector"], countries=[], sort="ticker",
            limit=50, offset=0,
        )
        assert count == 0
        assert results == []


@pytest.mark.django_db
class TestRunScreenerSort:
    def test_sort_ascending(self, snapshot_universe):
        _, results = run_screener(
            bounds={}, sectors=[], countries=[], sort="pe10", limit=50, offset=0,
        )
        assert [r["ticker"] for r in results] == ["PETR4", "MICRO3", "WEGE3"]

    def test_sort_descending(self, snapshot_universe):
        _, results = run_screener(
            bounds={}, sectors=[], countries=[], sort="-pe10", limit=50, offset=0,
        )
        assert [r["ticker"] for r in results] == ["WEGE3", "MICRO3", "PETR4"]

    def test_default_sort_is_ticker(self, snapshot_universe):
        _, results = run_screener(
            bounds={}, sectors=[], countries=[], sort="ticker", limit=50, offset=0,
        )
        assert [r["ticker"] for r in results] == ["MICRO3", "PETR4", "WEGE3"]

    def test_invalid_sort_field_raises_screener_error(self, snapshot_universe):
        with pytest.raises(ScreenerError, match="Invalid sort field"):
            run_screener(
                bounds={}, sectors=[], countries=[], sort="evil; DROP TABLE",
                limit=50, offset=0,
            )

    def test_nulls_sort_last(self, db):
        Ticker.objects.create(symbol="HASA", name="HasA", market_cap=1)
        Ticker.objects.create(symbol="HASNULL", name="HasNull", market_cap=1)
        Ticker.objects.create(symbol="HASB", name="HasB", market_cap=1)
        IndicatorSnapshot.objects.create(
            ticker="HASA", debt_to_avg_fcf=Decimal("5.0"), market_cap=1,
        )
        IndicatorSnapshot.objects.create(
            ticker="HASNULL", debt_to_avg_fcf=None, market_cap=1,
        )
        IndicatorSnapshot.objects.create(
            ticker="HASB", debt_to_avg_fcf=Decimal("2.0"), market_cap=1,
        )
        _, results = run_screener(
            bounds={}, sectors=[], countries=[], sort="debt_to_avg_fcf",
            limit=50, offset=0,
        )
        assert [r["ticker"] for r in results] == ["HASB", "HASA", "HASNULL"]

    def test_ticker_tiebreaker(self, db):
        Ticker.objects.create(symbol="BBB3", name="BBB", market_cap=1)
        Ticker.objects.create(symbol="AAA3", name="AAA", market_cap=1)
        IndicatorSnapshot.objects.create(
            ticker="BBB3", pe10=Decimal("10.0"), market_cap=1,
        )
        IndicatorSnapshot.objects.create(
            ticker="AAA3", pe10=Decimal("10.0"), market_cap=1,
        )
        _, results = run_screener(
            bounds={}, sectors=[], countries=[], sort="pe10", limit=50, offset=0,
        )
        assert [r["ticker"] for r in results] == ["AAA3", "BBB3"]


@pytest.mark.django_db
class TestRunScreenerPagination:
    def test_count_reflects_total_not_page(self, snapshot_universe):
        count, results = run_screener(
            bounds={}, sectors=[], countries=[], sort="pe10", limit=2, offset=0,
        )
        assert count == 3
        assert len(results) == 2
        assert [r["ticker"] for r in results] == ["PETR4", "MICRO3"]

    def test_offset_skips_rows(self, snapshot_universe):
        _, results = run_screener(
            bounds={}, sectors=[], countries=[], sort="pe10", limit=5, offset=1,
        )
        assert [r["ticker"] for r in results] == ["MICRO3", "WEGE3"]

    def test_limit_clamped_to_at_least_one(self, snapshot_universe):
        _, results = run_screener(
            bounds={}, sectors=[], countries=[], sort="ticker", limit=0, offset=0,
        )
        assert len(results) == 1

    def test_negative_limit_clamped_to_one(self, snapshot_universe):
        _, results = run_screener(
            bounds={}, sectors=[], countries=[], sort="ticker", limit=-5, offset=0,
        )
        assert len(results) == 1

    def test_negative_offset_clamped_to_zero(self, snapshot_universe):
        _, with_negative = run_screener(
            bounds={}, sectors=[], countries=[], sort="pe10", limit=50, offset=-5,
        )
        _, baseline = run_screener(
            bounds={}, sectors=[], countries=[], sort="pe10", limit=50, offset=0,
        )
        assert with_negative == baseline

    def test_limit_capped_at_max(self, db):
        tickers = [
            Ticker(symbol=f"T{i:04d}", name=f"T{i}", market_cap=1)
            for i in range(SCREENER_MAX_LIMIT + 5)
        ]
        Ticker.objects.bulk_create(tickers)
        snapshots = [
            IndicatorSnapshot(ticker=f"T{i:04d}", pe10=Decimal("1.0"), market_cap=1)
            for i in range(SCREENER_MAX_LIMIT + 5)
        ]
        IndicatorSnapshot.objects.bulk_create(snapshots)
        count, results = run_screener(
            bounds={}, sectors=[], countries=[], sort="ticker",
            limit=SCREENER_MAX_LIMIT + 100, offset=0,
        )
        assert count == SCREENER_MAX_LIMIT + 5
        assert len(results) == SCREENER_MAX_LIMIT

    def test_defaults_when_omitted(self, snapshot_universe):
        count, results = run_screener()
        assert count == 3
        assert len(results) <= SCREENER_DEFAULT_LIMIT


@pytest.mark.django_db
class TestRunScreenerRowShape:
    def test_row_includes_ticker_metadata(self, snapshot_universe):
        _, results = run_screener(
            bounds={}, sectors=[], countries=[], sort="ticker", limit=50, offset=0,
        )
        row = next(r for r in results if r["ticker"] == "PETR4")
        assert row["name"] == "Petrobras"
        assert row["sector"] == "Oil"
        assert row["logo"] == "https://example.com/petr4.png"
        assert Decimal(str(row["pe10"])) == Decimal("6.5")
        assert row["market_cap"] == 400_000_000_000

    def test_row_includes_ratings_block(self, snapshot_universe):
        _, results = run_screener(
            bounds={}, sectors=[], countries=[], sort="ticker", limit=50, offset=0,
        )
        for row in results:
            assert "ratings" in row
            assert "overall" in row["ratings"]
            assert "methodology_version" in row["ratings"]


@pytest.mark.django_db
class TestRunScreenerPEWindows:
    """The strict P/E window family is filterable and sortable."""

    @pytest.fixture
    def pe_window_universe(self, snapshot_universe):
        IndicatorSnapshot.objects.filter(ticker="PETR4").update(
            pe5=Decimal("5.0"), pe15=Decimal("7.5"), pe_years_available=15,
        )
        IndicatorSnapshot.objects.filter(ticker="WEGE3").update(
            pe5=Decimal("30.0"), pe_years_available=8,
        )

    def test_filters_by_a_short_window(self, pe_window_universe):
        count, results = run_screener(
            bounds={"pe5": {"max": Decimal("10")}},
            sectors=[], countries=[], sort="ticker", limit=50, offset=0,
        )
        assert count == 1
        assert results[0]["ticker"] == "PETR4"

    def test_null_windows_are_excluded_by_bounds(self, pe_window_universe):
        # WEGE3 has only 8 years of history: its pe15 is NULL, so a pe15
        # bound can never match it.
        count, results = run_screener(
            bounds={"pe15": {"max": Decimal("100")}},
            sectors=[], countries=[], sort="ticker", limit=50, offset=0,
        )
        assert count == 1
        assert results[0]["ticker"] == "PETR4"

    def test_filters_by_years_available(self, pe_window_universe):
        count, results = run_screener(
            bounds={"pe_years_available": {"min": Decimal("10")}},
            sectors=[], countries=[], sort="ticker", limit=50, offset=0,
        )
        assert count == 1
        assert results[0]["ticker"] == "PETR4"

    def test_sorts_by_a_window_with_nulls_last(self, pe_window_universe):
        _, results = run_screener(
            bounds={}, sectors=[], countries=[], sort="-pe5", limit=50, offset=0,
        )
        tickers = [row["ticker"] for row in results]
        assert tickers[0] == "WEGE3"
        assert tickers[1] == "PETR4"
        assert tickers[2] == "MICRO3"  # NULL pe5 sorts last

    def test_rows_carry_window_values(self, pe_window_universe):
        _, results = run_screener(
            bounds={}, sectors=[], countries=[], sort="ticker", limit=50, offset=0,
        )
        row = next(r for r in results if r["ticker"] == "PETR4")
        assert Decimal(str(row["pe5"])) == Decimal("5.0")
        assert row["pe_years_available"] == 15


@pytest.fixture
def debt_window_universe(db):
    """Two companies whose loose and strict debt-coverage values disagree.

    LONG3 has fifteen years of history, so every window is filled and the
    strict windows drift away from the loose figure. YOUNG3 has three years:
    the loose pair is filled (averaged over what exists) but any window
    wider than three years is None.
    """
    Ticker.objects.create(
        symbol="LONG3", name="Long", display_name="Long", sector="Oil",
        type="stock", market_cap=100, country="BR",
    )
    IndicatorSnapshot.objects.create(
        ticker="LONG3", market_cap=100,
        debt_to_avg_earnings=Decimal("4.0"), debt_to_avg_fcf=Decimal("5.0"),
        debt_to_avg_earnings_3=Decimal("2.0"), debt_to_avg_fcf_3=Decimal("2.5"),
        debt_to_avg_earnings_5=Decimal("9.0"), debt_to_avg_fcf_5=Decimal("8.0"),
        debt_to_avg_earnings_15=Decimal("6.0"), debt_to_avg_fcf_15=Decimal("7.0"),
    )
    Ticker.objects.create(
        symbol="YOUNG3", name="Young", display_name="Young", sector="Retail",
        type="stock", market_cap=50, country="BR",
    )
    IndicatorSnapshot.objects.create(
        ticker="YOUNG3", market_cap=50,
        debt_to_avg_earnings=Decimal("1.0"), debt_to_avg_fcf=Decimal("1.5"),
        debt_to_avg_earnings_3=Decimal("1.0"), debt_to_avg_fcf_3=Decimal("1.5"),
    )


def _run(**overrides):
    arguments = dict(
        bounds={}, sectors=[], countries=[], sort="ticker", limit=50, offset=0,
    )
    arguments.update(overrides)
    return run_screener(**arguments)


@pytest.mark.django_db
class TestRunScreenerDebtWindow:
    """``debt_window_years`` swaps the loose debt-coverage pair for the strict
    N-year window everywhere the screener touches them: bounds, sort, and
    the values each row reports."""

    def test_omitted_window_keeps_the_loose_values(self, debt_window_universe):
        count, results = _run(bounds={"debt_to_avg_earnings": {"max": Decimal("3")}})
        assert count == 1
        assert results[0]["ticker"] == "YOUNG3"
        assert results[0]["debt_to_avg_earnings"] == Decimal("1.0")

    def test_bound_applies_to_the_requested_window(self, debt_window_universe):
        count, results = _run(
            bounds={"debt_to_avg_earnings": {"max": Decimal("3")}},
            debt_window_years=3,
        )
        assert {row["ticker"] for row in results} == {"LONG3", "YOUNG3"}
        count, results = _run(
            bounds={"debt_to_avg_earnings": {"max": Decimal("3")}},
            debt_window_years=5,
        )
        assert count == 0

    def test_rows_report_the_windowed_value_under_the_plain_key(
        self, debt_window_universe,
    ):
        _, results = _run(debt_window_years=5)
        by_ticker = {row["ticker"]: row for row in results}
        assert by_ticker["LONG3"]["debt_to_avg_earnings"] == Decimal("9.0")
        assert by_ticker["LONG3"]["debt_to_avg_fcf"] == Decimal("8.0")
        assert by_ticker["YOUNG3"]["debt_to_avg_earnings"] is None
        assert by_ticker["YOUNG3"]["debt_to_avg_fcf"] is None

    def test_window_beyond_a_company_history_excludes_it_from_bounds(
        self, debt_window_universe,
    ):
        count, results = _run(
            bounds={"debt_to_avg_fcf": {"min": Decimal("0")}}, debt_window_years=15,
        )
        assert count == 1
        assert results[0]["ticker"] == "LONG3"

    def test_sort_uses_the_windowed_column_with_nulls_last(
        self, debt_window_universe,
    ):
        _, results = _run(sort="-debt_to_avg_earnings", debt_window_years=3)
        assert [row["ticker"] for row in results] == ["LONG3", "YOUNG3"]
        _, results = _run(sort="debt_to_avg_earnings", debt_window_years=5)
        assert [row["ticker"] for row in results] == ["LONG3", "YOUNG3"]

    def test_other_indicators_are_untouched_by_the_window(self, debt_window_universe):
        IndicatorSnapshot.objects.filter(ticker="YOUNG3").update(pe10=Decimal("7"))
        count, results = _run(
            bounds={"pe10": {"max": Decimal("10")}}, debt_window_years=15,
        )
        assert count == 1
        assert results[0]["ticker"] == "YOUNG3"

    @pytest.mark.parametrize("window", [0, 16, -1, "5", 2.5, True])
    def test_invalid_window_raises_screener_error(self, debt_window_universe, window):
        with pytest.raises(ScreenerError):
            _run(debt_window_years=window)

    def test_ratings_follow_the_windowed_value(self, debt_window_universe):
        _, loose = _run(sort="ticker")
        _, strict = _run(sort="ticker", debt_window_years=5)
        long_loose = next(row for row in loose if row["ticker"] == "LONG3")
        long_strict = next(row for row in strict if row["ticker"] == "LONG3")
        assert long_loose["ratings"]["debt_to_avg_earnings"] != long_strict["ratings"]["debt_to_avg_earnings"]
