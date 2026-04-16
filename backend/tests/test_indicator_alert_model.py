"""Tests for the IndicatorAlert model — per-user thresholds on snapshot indicators."""
from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.db.utils import DataError

from accounts.models import IndicatorAlert, User


@pytest.fixture
def user(db):
    return User.objects.create_user(email="a@example.com", username="a", password="x")


@pytest.mark.django_db
class TestIndicatorAlertModel:
    def test_creates_alert_with_threshold(self, user):
        alert = IndicatorAlert.objects.create(
            user=user, ticker="PETR4",
            indicator="pe10", comparison="lte", threshold=Decimal("10"),
        )
        assert alert.id is not None
        assert alert.active is True
        assert alert.triggered_at is None
        assert alert.created_at is not None

    def test_indicator_must_be_a_snapshot_field(self, user):
        # Whitelist check — we reject unknown indicator names before the DB even sees them.
        with pytest.raises(ValueError):
            alert = IndicatorAlert(
                user=user, ticker="PETR4",
                indicator="bogus_field", comparison="lte",
                threshold=Decimal("10"),
            )
            alert.full_clean()

    def test_comparison_must_be_valid_choice(self, user):
        alert = IndicatorAlert(
            user=user, ticker="PETR4",
            indicator="pe10", comparison="wibble",
            threshold=Decimal("10"),
        )
        with pytest.raises(Exception):
            alert.full_clean()

    def test_unique_per_user_ticker_indicator_comparison(self, user):
        IndicatorAlert.objects.create(
            user=user, ticker="PETR4",
            indicator="pe10", comparison="lte", threshold=Decimal("10"),
        )
        # Same user+ticker+indicator+comparison collides (can't have two "PE10 <= X"
        # rules for the same pair — one rule holds one threshold).
        with pytest.raises(IntegrityError):
            IndicatorAlert.objects.create(
                user=user, ticker="PETR4",
                indicator="pe10", comparison="lte", threshold=Decimal("12"),
            )

    def test_two_alerts_with_different_comparison_coexist(self, user):
        # "PE10 <= 10" and "PE10 >= 20" are both valid for the same ticker.
        IndicatorAlert.objects.create(
            user=user, ticker="PETR4",
            indicator="pe10", comparison="lte", threshold=Decimal("10"),
        )
        IndicatorAlert.objects.create(
            user=user, ticker="PETR4",
            indicator="pe10", comparison="gte", threshold=Decimal("20"),
        )
        assert IndicatorAlert.objects.filter(user=user, ticker="PETR4").count() == 2

    def test_is_triggered_lte(self, user):
        alert = IndicatorAlert(
            user=user, ticker="PETR4",
            indicator="pe10", comparison="lte", threshold=Decimal("10"),
        )
        assert alert.is_triggered_by(Decimal("9.99")) is True
        assert alert.is_triggered_by(Decimal("10")) is True
        assert alert.is_triggered_by(Decimal("10.01")) is False
        # Null indicator can't trigger.
        assert alert.is_triggered_by(None) is False

    def test_is_triggered_gte(self, user):
        alert = IndicatorAlert(
            user=user, ticker="PETR4",
            indicator="debt_to_equity", comparison="gte",
            threshold=Decimal("2.0"),
        )
        assert alert.is_triggered_by(Decimal("2.5")) is True
        assert alert.is_triggered_by(Decimal("2.0")) is True
        assert alert.is_triggered_by(Decimal("1.9")) is False

    def test_str_readable(self, user):
        alert = IndicatorAlert.objects.create(
            user=user, ticker="PETR4",
            indicator="pe10", comparison="lte", threshold=Decimal("10"),
        )
        text = str(alert)
        assert "PETR4" in text
        assert "pe10" in text
        assert "10" in text
