"""Tests for the FX rate model, sync, and lookup helper."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from quotes.fmp import sync_fx_rates
from quotes.fx import get_fx_rate, market_cap_in_reported_currency
from quotes.models import FxRate, Ticker


MOCK_USDDKK_HISTORY = [
    {"symbol": "USDDKK", "date": "2025-09-30", "close": 6.85},
    {"symbol": "USDDKK", "date": "2025-09-29", "close": 6.83},
    {"symbol": "USDDKK", "date": "2024-12-31", "close": 7.10},
]

MOCK_USDEUR_HISTORY = [
    {"symbol": "USDEUR", "date": "2025-09-30", "close": 0.92},
    {"symbol": "USDEUR", "date": "2024-12-31", "close": 0.95},
]


class TestFxRateModel:
    def test_unique_per_pair_and_date(self, db):
        FxRate.objects.create(
            base_currency="USD", quote_currency="DKK",
            date=date(2025, 9, 30), rate=Decimal("6.85"),
        )
        with pytest.raises(Exception):
            FxRate.objects.create(
                base_currency="USD", quote_currency="DKK",
                date=date(2025, 9, 30), rate=Decimal("6.99"),
            )


class TestSyncFxRates:
    @patch("quotes.fmp._get")
    def test_writes_daily_rates_for_each_currency(self, mock_get, db):
        mock_get.side_effect = [MOCK_USDDKK_HISTORY, MOCK_USDEUR_HISTORY]
        sync_fx_rates(["DKK", "EUR"])
        assert FxRate.objects.filter(base_currency="USD", quote_currency="DKK").count() == 3
        assert FxRate.objects.filter(base_currency="USD", quote_currency="EUR").count() == 2
        assert FxRate.objects.get(
            base_currency="USD", quote_currency="DKK", date=date(2025, 9, 30),
        ).rate == Decimal("6.85")

    @patch("quotes.fmp._get")
    def test_is_idempotent(self, mock_get, db):
        mock_get.side_effect = [MOCK_USDDKK_HISTORY, MOCK_USDDKK_HISTORY]
        sync_fx_rates(["DKK"])
        sync_fx_rates(["DKK"])
        assert FxRate.objects.filter(base_currency="USD", quote_currency="DKK").count() == 3

    @patch("quotes.fmp._get")
    def test_passes_from_2010_to_fmp(self, mock_get, db):
        """Without an explicit `from`, FMP truncates history to ~4 years; the
        multiples-history chart needs 10+, so the sync must request 2010 onward."""
        mock_get.return_value = MOCK_USDDKK_HISTORY
        sync_fx_rates(["DKK"])
        # _get was called with the right symbol and `from` param
        assert mock_get.call_args.kwargs["params"]["symbol"] == "USDDKK"
        assert mock_get.call_args.kwargs["params"]["from"] == "2010-01-01"


class TestGetFxRate:
    def test_returns_exact_rate_when_date_matches(self, db):
        FxRate.objects.create(
            base_currency="USD", quote_currency="DKK",
            date=date(2025, 9, 30), rate=Decimal("6.85"),
        )
        assert get_fx_rate(date(2025, 9, 30), "USD", "DKK") == Decimal("6.85")

    def test_returns_nearest_earlier_rate(self, db):
        """When the requested date is missing (weekend/holiday), use the most
        recent available rate ≤ the requested date."""
        FxRate.objects.create(
            base_currency="USD", quote_currency="DKK",
            date=date(2025, 9, 26), rate=Decimal("6.85"),  # Friday
        )
        # Saturday (no FX data)
        assert get_fx_rate(date(2025, 9, 27), "USD", "DKK") == Decimal("6.85")

    def test_returns_none_when_no_history(self, db):
        assert get_fx_rate(date(2025, 9, 30), "USD", "XYZ") is None

    def test_returns_none_when_only_future_rates_exist(self, db):
        """Don't make up a rate from future data when we have no historical
        anchor for the requested date."""
        FxRate.objects.create(
            base_currency="USD", quote_currency="DKK",
            date=date(2025, 9, 30), rate=Decimal("6.85"),
        )
        assert get_fx_rate(date(2024, 1, 1), "USD", "DKK") is None

    def test_returns_one_for_same_currency(self, db):
        assert get_fx_rate(date(2025, 9, 30), "USD", "USD") == Decimal("1")
        assert get_fx_rate(date(2025, 9, 30), "DKK", "DKK") == Decimal("1")

    def test_pivots_via_usd(self, db):
        """For non-USD pairs (e.g. DKK→EUR), pivot through USD using the
        stored USD↔X and USD↔Y rates."""
        FxRate.objects.create(
            base_currency="USD", quote_currency="DKK",
            date=date(2025, 9, 30), rate=Decimal("6.85"),
        )
        FxRate.objects.create(
            base_currency="USD", quote_currency="EUR",
            date=date(2025, 9, 30), rate=Decimal("0.92"),
        )
        # 1 DKK = (1/6.85) USD = (0.92/6.85) EUR ≈ 0.1343
        result = get_fx_rate(date(2025, 9, 30), "DKK", "EUR")
        assert result is not None
        assert abs(result - Decimal("0.92") / Decimal("6.85")) < Decimal("0.0001")

    def test_inverts_when_swapping_base_and_quote(self, db):
        """Asking for DKK→USD when only USD→DKK is stored should invert."""
        FxRate.objects.create(
            base_currency="USD", quote_currency="DKK",
            date=date(2025, 9, 30), rate=Decimal("6.85"),
        )
        result = get_fx_rate(date(2025, 9, 30), "DKK", "USD")
        assert result is not None
        assert abs(result - Decimal("1") / Decimal("6.85")) < Decimal("0.0001")


class TestMarketCapInReportedCurrency:
    """The bridge between Sponda's USD/BRL market cap and the statement
    currency. Used by every market-cap-based indicator."""

    def test_passes_through_when_listing_matches_reported(self, db):
        """US-listed company that also reports in USD: no translation."""
        Ticker.objects.create(symbol="AAPL", name="Apple Inc.", reported_currency="USD")
        result = market_cap_in_reported_currency(Decimal("3000000000000"), "AAPL")
        assert result == Decimal("3000000000000")

    def test_translates_usd_listing_to_dkk_reporting(self, db):
        """The NVO case: USD market cap × USDDKK rate = DKK market cap.
        $195B × 6.85 ≈ 1.336T DKK."""
        Ticker.objects.create(symbol="NVO", name="Novo Nordisk A/S", reported_currency="DKK")
        FxRate.objects.create(
            base_currency="USD", quote_currency="DKK",
            date=date(2025, 9, 30), rate=Decimal("6.85"),
        )
        result = market_cap_in_reported_currency(
            Decimal("195000000000"), "NVO", on_date=date(2025, 9, 30),
        )
        assert result is not None
        # $195B × 6.85 = 1335.75B DKK
        assert abs(result - Decimal("1335750000000")) < Decimal("1")

    def test_returns_none_when_fx_missing(self, db):
        """Foreign reporter with no FX rates yet (sync pending). Indicator
        callers should treat None as 'cannot compute'."""
        Ticker.objects.create(symbol="NVO", name="Novo Nordisk A/S", reported_currency="DKK")
        result = market_cap_in_reported_currency(
            Decimal("195000000000"), "NVO", on_date=date(2025, 9, 30),
        )
        assert result is None

    def test_returns_none_when_market_cap_none(self, db):
        Ticker.objects.create(symbol="AAPL", name="Apple Inc.", reported_currency="USD")
        assert market_cap_in_reported_currency(None, "AAPL") is None

    def test_uses_latest_fx_when_no_date_given(self, db):
        """For snapshot indicators (PE10, PFCF10), we want today's FX."""
        Ticker.objects.create(symbol="NVO", name="Novo Nordisk A/S", reported_currency="DKK")
        FxRate.objects.create(
            base_currency="USD", quote_currency="DKK",
            date=date(2024, 1, 1), rate=Decimal("7.00"),
        )
        FxRate.objects.create(
            base_currency="USD", quote_currency="DKK",
            date=date(2025, 12, 1), rate=Decimal("6.50"),
        )
        result = market_cap_in_reported_currency(Decimal("100000000000"), "NVO")
        # Should use 6.50 (latest), not 7.00
        assert abs(result - Decimal("650000000000")) < Decimal("1")

    def test_legacy_brazilian_ticker_without_row(self, db):
        """Legacy fallback: a Brazilian-pattern ticker without a Ticker row
        still gets BRL→BRL passthrough."""
        result = market_cap_in_reported_currency(Decimal("100000000000"), "PETR4")
        assert result == Decimal("100000000000")
