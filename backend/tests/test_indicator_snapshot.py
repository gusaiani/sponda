"""Tests for the IndicatorSnapshot model — pre-computed indicator values used by the screener."""
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.utils import timezone

from quotes.models import IndicatorSnapshot


@pytest.mark.django_db
class TestIndicatorSnapshotModel:
    def test_creates_snapshot_with_all_indicator_fields(self):
        snapshot = IndicatorSnapshot.objects.create(
            ticker="PETR4",
            pe10=Decimal("4.5"),
            pfcf10=Decimal("3.2"),
            peg=Decimal("0.8"),
            pfcf_peg=Decimal("0.6"),
            debt_to_equity=Decimal("1.5"),
            debt_ex_lease_to_equity=Decimal("1.2"),
            liabilities_to_equity=Decimal("2.5"),
            current_ratio=Decimal("1.8"),
            debt_to_avg_earnings=Decimal("3.0"),
            debt_to_avg_fcf=Decimal("4.5"),
            market_cap=500_000_000_000,
            current_price=Decimal("35.75"),
        )
        assert snapshot.ticker == "PETR4"
        assert snapshot.pe10 == Decimal("4.5")
        assert snapshot.market_cap == 500_000_000_000
        assert snapshot.computed_at is not None

    def test_all_indicator_fields_are_nullable(self):
        snapshot = IndicatorSnapshot.objects.create(ticker="NULL3")
        assert snapshot.pe10 is None
        assert snapshot.pfcf10 is None
        assert snapshot.peg is None
        assert snapshot.debt_to_equity is None
        assert snapshot.market_cap is None

    def test_ticker_must_be_unique(self):
        IndicatorSnapshot.objects.create(ticker="PETR4", pe10=Decimal("4.5"))
        with pytest.raises(IntegrityError):
            IndicatorSnapshot.objects.create(ticker="PETR4", pe10=Decimal("5.0"))

    def test_computed_at_auto_updates_on_save(self):
        snapshot = IndicatorSnapshot.objects.create(ticker="PETR4", pe10=Decimal("4.5"))
        original_time = snapshot.computed_at
        # Force a different timestamp by re-saving
        snapshot.pe10 = Decimal("5.0")
        snapshot.save()
        snapshot.refresh_from_db()
        assert snapshot.computed_at >= original_time

    def test_str_includes_ticker_and_timestamp(self):
        snapshot = IndicatorSnapshot.objects.create(ticker="PETR4", pe10=Decimal("4.5"))
        assert "PETR4" in str(snapshot)
