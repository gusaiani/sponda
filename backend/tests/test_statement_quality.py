"""Tests for provider data-quality normalisation.

BRAPI and FMP both encode a missing net income as a literal `0` rather than
null for some filings. Stored as-is, a zero flows into the inflation-adjusted
earnings average behind P/E10, silently dragging it toward zero and inflating
the multiple. 2,801 rows across 565 companies were affected when this was
found; BBAS3 reported R$31bn of quarterly revenue and exactly R$0 of profit
for every quarter from 2013 to 2019.
"""
from datetime import date

import pytest

from quotes.models import QuarterlyEarnings
from quotes.statement_quality import normalize_net_income


class TestNormalizeNetIncome:
    def test_passes_through_a_real_figure(self):
        assert normalize_net_income(8_680_714_000, 66_655_190_000) == 8_680_714_000

    def test_passes_through_a_real_loss(self):
        assert normalize_net_income(-500_000, 66_655_190_000) == -500_000

    def test_passes_through_none(self):
        assert normalize_net_income(None, 66_655_190_000) is None

    def test_zero_alongside_real_revenue_is_missing(self):
        # A bank booking R$31bn of revenue and exactly R$0.00 of profit is a
        # provider artifact, not a quarter.
        assert normalize_net_income(0, 31_678_067_000) is None

    def test_zero_with_no_revenue_is_kept(self):
        # A shell or pre-revenue company can genuinely earn nothing, and that
        # is a fact worth storing rather than erasing.
        assert normalize_net_income(0, 0) == 0
        assert normalize_net_income(0, None) == 0

    def test_zero_with_negative_revenue_is_kept(self):
        assert normalize_net_income(0, -100) == 0


@pytest.mark.django_db
class TestRepairCommand:
    def _earnings(self, ticker, year, net_income, revenue):
        return QuarterlyEarnings.objects.create(
            ticker=ticker, end_date=date(year, 12, 31),
            net_income=net_income, revenue=revenue,
        )

    def test_nulls_zero_earnings_that_sit_beside_revenue(self):
        from django.core.management import call_command
        row = self._earnings("BBAS3", 2019, 0, 31_678_067_000)
        call_command("repair_zero_net_income")
        row.refresh_from_db()
        assert row.net_income is None

    def test_leaves_a_genuine_zero_alone(self):
        from django.core.management import call_command
        row = self._earnings("SHELL3", 2019, 0, 0)
        call_command("repair_zero_net_income")
        row.refresh_from_db()
        assert row.net_income == 0

    def test_leaves_real_figures_alone(self):
        from django.core.management import call_command
        row = self._earnings("PETR4", 2024, 9_000_000, 50_000_000)
        call_command("repair_zero_net_income")
        row.refresh_from_db()
        assert row.net_income == 9_000_000

    def test_dry_run_changes_nothing(self):
        from django.core.management import call_command
        row = self._earnings("BBAS3", 2019, 0, 31_678_067_000)
        call_command("repair_zero_net_income", "--dry-run")
        row.refresh_from_db()
        assert row.net_income == 0

    def test_invalidates_derived_caches_for_touched_tickers(self):
        from django.core.cache import cache
        from django.core.management import call_command
        from quotes.derived_data import pe10_cache_key

        self._earnings("BBAS3", 2019, 0, 31_678_067_000)
        cache.set(pe10_cache_key("BBAS3"), {"stale": True}, 300)
        call_command("repair_zero_net_income")
        assert cache.get(pe10_cache_key("BBAS3")) is None


@pytest.mark.django_db
class TestIngestionAppliesTheRule:
    """Both providers must apply it, or the repair command fights the sync."""

    def test_brapi_stores_none_for_a_zero_beside_revenue(self, monkeypatch):
        from quotes import brapi
        monkeypatch.setattr(brapi, "fetch_income_statements", lambda ticker: [
            {"endDate": "2019-12-31", "netIncome": 0, "totalRevenue": 27_894_387_000},
        ])
        brapi.sync_earnings("BBAS3")
        assert QuarterlyEarnings.objects.get(ticker="BBAS3").net_income is None

    def test_brapi_keeps_a_real_figure(self, monkeypatch):
        from quotes import brapi
        monkeypatch.setattr(brapi, "fetch_income_statements", lambda ticker: [
            {"endDate": "2024-12-31", "netIncome": 5_140_255_000, "totalRevenue": 71_704_820_000},
        ])
        brapi.sync_earnings("BBAS3")
        assert QuarterlyEarnings.objects.get(ticker="BBAS3").net_income == 5_140_255_000

    def test_fmp_stores_none_for_a_zero_beside_revenue(self, monkeypatch):
        from quotes import fmp
        monkeypatch.setattr(fmp, "fetch_income_statements", lambda ticker: [
            {"date": "2019-12-31", "netIncome": 0, "revenue": 27_894_387_000},
        ])
        fmp.sync_earnings("AAPL")
        assert QuarterlyEarnings.objects.get(ticker="AAPL").net_income is None
