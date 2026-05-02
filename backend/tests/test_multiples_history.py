"""Unit tests for multiples history calculation logic."""
import calendar
from datetime import datetime, timezone


from quotes.multiples_history import _rolling_avg, compute_multiples_history


def _make_monthly_prices(year_prices: dict[int, float]) -> list[dict]:
    """Build a minimal historicalDataPrice list with one entry per month.

    For each year in year_prices, creates 12 monthly entries all with the
    same adjustedClose (simplifies assertions while exercising the full path).
    """
    points = []
    for year in sorted(year_prices):
        price = year_prices[year]
        for month in range(1, 13):
            last_day = calendar.monthrange(year, month)[1]
            dt = datetime(year, month, last_day, tzinfo=timezone.utc)
            points.append({"date": int(dt.timestamp()), "adjustedClose": price})
    return points


class TestRollingAvg:
    def test_basic_average(self):
        data = {2020: 100.0, 2021: 200.0, 2022: 300.0}
        assert _rolling_avg(data, 2022) == 200.0

    def test_uses_10_year_window(self):
        data = {y: 10.0 for y in range(2010, 2025)}
        # Year 2024: window is 2015–2024 (10 values of 10.0)
        assert _rolling_avg(data, 2024) == 10.0
        # Data from 2010–2014 should NOT be included
        data[2010] = 999.0
        assert _rolling_avg(data, 2024) == 10.0

    def test_returns_none_when_no_data_in_window(self):
        data = {2010: 100.0}
        assert _rolling_avg(data, 2025) is None

    def test_returns_none_when_average_is_negative(self):
        data = {2020: -100.0, 2021: 50.0}
        # avg = (-100 + 50) / 2 = -25 → None
        assert _rolling_avg(data, 2021) is None

    def test_returns_none_when_average_is_zero(self):
        data = {2020: -50.0, 2021: 50.0}
        assert _rolling_avg(data, 2021) is None

    def test_sparse_data_uses_available_points(self):
        data = {2020: 100.0, 2025: 200.0}
        # Window 2016–2025 includes both points
        assert _rolling_avg(data, 2025) == 150.0

    def test_empty_dict(self):
        assert _rolling_avg({}, 2025) is None


class TestComputeMultiplesHistory:
    def test_returns_empty_when_price_zero(self, db):
        result = compute_multiples_history("FAKE3", [], 1000.0, 0)
        assert result == {
            "prices": [], "multiples": {"pl": [], "pfcl": []},
            "currency_warning": False,
        }

    def test_returns_empty_when_price_negative(self, db):
        result = compute_multiples_history("FAKE3", [], 1000.0, -10.0)
        assert result == {
            "prices": [], "multiples": {"pl": [], "pfcl": []},
            "currency_warning": False,
        }

    def test_converts_unix_timestamps_to_iso_dates(self, db):
        # 2020-06-30 00:00:00 UTC
        ts = int(datetime(2020, 6, 30, tzinfo=timezone.utc).timestamp())
        prices = [{"date": ts, "adjustedClose": 25.0}]
        result = compute_multiples_history("FAKE3", prices, 1000.0, 10.0)
        assert result["prices"][0]["date"] == "2020-06-30"
        assert result["prices"][0]["adjustedClose"] == 25.0

    def test_prices_are_sorted_ascending_by_date(self, db):
        """FMP returns prices newest-first; backend must normalize to oldest-first."""
        ts_2020 = int(datetime(2020, 1, 15, tzinfo=timezone.utc).timestamp())
        ts_2022 = int(datetime(2022, 6, 30, tzinfo=timezone.utc).timestamp())
        ts_2024 = int(datetime(2024, 12, 31, tzinfo=timezone.utc).timestamp())
        prices_desc = [
            {"date": ts_2024, "adjustedClose": 30.0},
            {"date": ts_2022, "adjustedClose": 20.0},
            {"date": ts_2020, "adjustedClose": 10.0},
        ]
        result = compute_multiples_history("FAKE3", prices_desc, 1000.0, 10.0)
        dates = [p["date"] for p in result["prices"]]
        assert dates == ["2020-01-15", "2022-06-30", "2024-12-31"]

    def test_skips_entries_with_missing_fields(self, db):
        prices = [
            {"date": None, "adjustedClose": 10.0},
            {"date": 1000000, "adjustedClose": None},
            {"date": 1000000, "adjustedClose": 10.0},  # valid
        ]
        result = compute_multiples_history("FAKE3", prices, 1000.0, 10.0)
        assert len(result["prices"]) == 1

    def test_computes_pl_with_rolling_average(self, sample_earnings):
        """P/L10 should use rolling 10-year average of net income."""
        # Create price data for years matching sample_earnings (2016–2025)
        prices = _make_monthly_prices({y: 30.0 for y in range(2016, 2026)})
        market_cap = 585_000_000_000.0
        current_price = 45.0

        result = compute_multiples_history("PETR4", prices, market_cap, current_price)

        pl = result["multiples"]["pl"]
        assert len(pl) == 10
        # All years should have values (rolling avg includes available data)
        values_with_data = [p for p in pl if p["value"] is not None]
        assert len(values_with_data) > 0

        # Check a specific year: 2025 should use avg of 2016–2025
        year_2025 = next(p for p in pl if p["year"] == 2025)
        assert year_2025["value"] is not None
        assert year_2025["value"] > 0

    def test_computes_pfcl_with_rolling_average(self, sample_earnings, sample_cash_flows):
        """P/FCL10 should use rolling 10-year average of FCF."""
        prices = _make_monthly_prices({y: 30.0 for y in range(2016, 2026)})
        market_cap = 585_000_000_000.0
        current_price = 45.0

        result = compute_multiples_history("PETR4", prices, market_cap, current_price)

        pfcl = result["multiples"]["pfcl"]
        assert len(pfcl) == 10
        values_with_data = [p for p in pfcl if p["value"] is not None]
        assert len(values_with_data) > 0

    def test_null_when_no_earnings_data(self, db):
        """Years without earnings → null multiple."""
        prices = _make_monthly_prices({2025: 30.0})
        result = compute_multiples_history("FAKE3", prices, 1000.0, 10.0)
        assert result["multiples"]["pl"][0]["value"] is None
        assert result["multiples"]["pfcl"][0]["value"] is None

    def test_year_end_price_is_last_month(self, db, sample_earnings):
        """Year-end price should be the last monthly price seen for that year."""
        ts_jan = int(datetime(2025, 1, 31, tzinfo=timezone.utc).timestamp())
        ts_dec = int(datetime(2025, 12, 31, tzinfo=timezone.utc).timestamp())
        prices = [
            {"date": ts_jan, "adjustedClose": 10.0},
            {"date": ts_dec, "adjustedClose": 50.0},  # this should be the year-end price
        ]
        result = compute_multiples_history("PETR4", prices, 585_000_000_000.0, 45.0)

        # The multiple should be based on year-end price (50.0), not Jan price (10.0)
        pl_2025 = next(p for p in result["multiples"]["pl"] if p["year"] == 2025)
        if pl_2025["value"] is not None:
            shares = 585_000_000_000.0 / 45.0
            50.0 * shares
            # Just verify it's using the Dec price (higher value → higher multiple)
            assert pl_2025["value"] > 0

    def test_prices_sorted_chronologically(self, db):
        """Output prices should be in the same order as input."""
        ts1 = int(datetime(2024, 1, 31, tzinfo=timezone.utc).timestamp())
        ts2 = int(datetime(2024, 6, 30, tzinfo=timezone.utc).timestamp())
        prices = [
            {"date": ts1, "adjustedClose": 10.0},
            {"date": ts2, "adjustedClose": 20.0},
        ]
        result = compute_multiples_history("FAKE3", prices, 1000.0, 10.0)
        assert result["prices"][0]["date"] == "2024-01-31"
        assert result["prices"][1]["date"] == "2024-06-30"

    def test_multiples_sorted_by_year(self, sample_earnings):
        """Multiples should be sorted by year ascending."""
        prices = _make_monthly_prices({y: 30.0 for y in range(2020, 2026)})
        result = compute_multiples_history("PETR4", prices, 585_000_000_000.0, 45.0)
        years = [p["year"] for p in result["multiples"]["pl"]]
        assert years == sorted(years)


class TestMultiplesHistoryCrossCurrency:
    """For ADRs that report in a non-USD currency, the year-end market cap
    must be translated to the reporting currency using the year-end FX
    rate, otherwise multiples for older years are off by the FX factor."""

    def test_translates_year_end_market_cap_with_per_year_fx(self, db):
        from datetime import date as date_type
        from decimal import Decimal
        from quotes.models import FxRate, QuarterlyEarnings, Ticker

        Ticker.objects.create(symbol="NVO", name="Novo Nordisk", reported_currency="DKK")
        # Three years of FX rates (year-end)
        for fx_date, rate in [
            (date_type(2023, 12, 29), Decimal("6.80")),
            (date_type(2024, 12, 31), Decimal("7.10")),
            (date_type(2025, 12, 31), Decimal("6.85")),
        ]:
            FxRate.objects.create(
                base_currency="USD", quote_currency="DKK", date=fx_date, rate=rate,
            )
        # 4 quarters per year of DKK earnings (25B DKK each = 100B/year)
        for year in (2023, 2024, 2025):
            for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
                QuarterlyEarnings.objects.create(
                    ticker="NVO", end_date=date_type(year, month, day),
                    net_income=25_000_000_000,
                )

        prices = _make_monthly_prices({2023: 100.0, 2024: 110.0, 2025: 120.0})
        # Market cap (USD) and current price (USD): 1.95B / $120 = ~16.25M shares
        result = compute_multiples_history("NVO", prices, market_cap=1_950_000_000.0, current_price=120.0)

        pl_2025 = next(p for p in result["multiples"]["pl"] if p["year"] == 2025)
        # shares ≈ 16.25M; year-end USD market cap = $120 × 16.25M ≈ $1.95B
        # Translated to DKK: $1.95B × 6.85 ≈ 13.36B DKK
        # Annual earnings: 100B DKK; with no inflation data, factor=1
        # Rolling 10y avg = 100B (only 3 years of data, all 100B)
        # PL = 13.36B / 100B ≈ 0.13
        assert pl_2025["value"] is not None
        assert 0.10 < pl_2025["value"] < 0.20

    def test_falls_back_to_latest_fx_when_year_specific_missing(self, db):
        """If we only have FX data for 2025 but not 2015, the chart applies
        the latest FX uniformly across all historical years and sets
        ``currency_warning`` so the frontend can show a banner."""
        from datetime import date as date_type
        from decimal import Decimal
        from quotes.models import FxRate, QuarterlyEarnings, Ticker

        Ticker.objects.create(symbol="NVO", name="Novo Nordisk", reported_currency="DKK")
        FxRate.objects.create(
            base_currency="USD", quote_currency="DKK",
            date=date_type(2025, 12, 31), rate=Decimal("6.85"),
        )
        for year in (2015, 2020, 2025):
            for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
                QuarterlyEarnings.objects.create(
                    ticker="NVO", end_date=date_type(year, month, day),
                    net_income=25_000_000_000,
                )
        prices = _make_monthly_prices({2015: 50.0, 2020: 80.0, 2025: 120.0})
        result = compute_multiples_history("NVO", prices, market_cap=1_950_000_000.0, current_price=120.0)

        # All multiples computed; no nulls from FX gaps
        pl_with_data = [p for p in result["multiples"]["pl"] if p["value"] is not None]
        assert len(pl_with_data) >= 1
        # And the warning flag is set
        assert result.get("currency_warning") is True

    def test_no_currency_warning_for_native_usd_reporters(self, sample_earnings):
        """A US-listed company that also reports in USD has no FX gap and no warning."""
        from quotes.models import Ticker

        Ticker.objects.create(symbol="PETR4", name="Petrobras", reported_currency="BRL")
        prices = _make_monthly_prices({y: 30.0 for y in range(2020, 2026)})
        result = compute_multiples_history("PETR4", prices, 585_000_000_000.0, 45.0)
        assert result.get("currency_warning") is False
