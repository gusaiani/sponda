"""Tests for check_indicator_alerts — one-shot alerts that create notifications."""
from decimal import Decimal
from io import StringIO

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from accounts.models import AlertNotification, IndicatorAlert, User
from quotes.models import IndicatorSnapshot


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="analyst@example.com", username="analyst", password="x",
    )


@pytest.fixture
def snapshot_petr4_cheap(db):
    return IndicatorSnapshot.objects.create(
        ticker="PETR4", pe10=Decimal("6.5"),
        debt_to_equity=Decimal("1.2"), market_cap=400_000_000_000,
    )


@pytest.fixture
def snapshot_petr4_expensive(db):
    return IndicatorSnapshot.objects.create(
        ticker="PETR4", pe10=Decimal("25"),
        debt_to_equity=Decimal("1.2"), market_cap=400_000_000_000,
    )


@pytest.mark.django_db
class TestCheckIndicatorAlerts:
    def test_triggers_alert_and_deletes_it(
        self, user, snapshot_petr4_cheap,
    ):
        IndicatorAlert.objects.create(
            user=user, ticker="PETR4", indicator="pe10",
            comparison="lte", threshold=Decimal("10"),
        )
        call_command("check_indicator_alerts", stdout=StringIO())
        assert IndicatorAlert.objects.count() == 0

    def test_creates_notification_when_alert_triggers(
        self, user, snapshot_petr4_cheap,
    ):
        IndicatorAlert.objects.create(
            user=user, ticker="PETR4", indicator="pe10",
            comparison="lte", threshold=Decimal("10"),
        )
        call_command("check_indicator_alerts", stdout=StringIO())
        notifications = AlertNotification.objects.filter(user=user)
        assert notifications.count() == 1
        notification = notifications.first()
        assert notification.ticker == "PETR4"
        assert notification.indicator == "pe10"
        assert notification.comparison == "lte"
        assert notification.threshold == Decimal("10")
        assert notification.indicator_value == Decimal("6.5")
        assert notification.dismissed_at is None

    def test_sends_email_when_alert_triggers(
        self, user, snapshot_petr4_cheap,
    ):
        IndicatorAlert.objects.create(
            user=user, ticker="PETR4", indicator="pe10",
            comparison="lte", threshold=Decimal("10"),
        )
        mail.outbox = []
        call_command("check_indicator_alerts", stdout=StringIO())
        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert user.email in message.to
        assert "PETR4" in message.subject or "PETR4" in message.body
        assert "PE10" in message.body.upper()

    def test_does_not_trigger_when_indicator_above_lte_threshold(
        self, user, snapshot_petr4_expensive,
    ):
        alert = IndicatorAlert.objects.create(
            user=user, ticker="PETR4", indicator="pe10",
            comparison="lte", threshold=Decimal("10"),
        )
        mail.outbox = []
        call_command("check_indicator_alerts", stdout=StringIO())
        alert.refresh_from_db()
        assert alert.triggered_at is None
        assert len(mail.outbox) == 0
        assert AlertNotification.objects.count() == 0

    def test_inactive_alerts_are_skipped(
        self, user, snapshot_petr4_cheap,
    ):
        alert = IndicatorAlert.objects.create(
            user=user, ticker="PETR4", indicator="pe10",
            comparison="lte", threshold=Decimal("10"),
            active=False,
        )
        mail.outbox = []
        call_command("check_indicator_alerts", stdout=StringIO())
        alert.refresh_from_db()
        assert alert.triggered_at is None
        assert len(mail.outbox) == 0
        assert AlertNotification.objects.count() == 0

    def test_alert_without_matching_snapshot_is_skipped(self, user):
        alert = IndicatorAlert.objects.create(
            user=user, ticker="NEW3", indicator="pe10",
            comparison="lte", threshold=Decimal("10"),
        )
        mail.outbox = []
        call_command("check_indicator_alerts", stdout=StringIO())
        alert.refresh_from_db()
        assert alert.triggered_at is None
        assert len(mail.outbox) == 0

    def test_alert_on_null_indicator_is_skipped(self, user, db):
        IndicatorSnapshot.objects.create(
            ticker="NODATA3", pe10=None, market_cap=100_000_000_000,
        )
        alert = IndicatorAlert.objects.create(
            user=user, ticker="NODATA3", indicator="pe10",
            comparison="lte", threshold=Decimal("10"),
        )
        mail.outbox = []
        call_command("check_indicator_alerts", stdout=StringIO())
        alert.refresh_from_db()
        assert alert.triggered_at is None
        assert len(mail.outbox) == 0

    def test_gte_alert_triggers_and_deletes(
        self, user, snapshot_petr4_cheap,
    ):
        IndicatorAlert.objects.create(
            user=user, ticker="PETR4", indicator="debt_to_equity",
            comparison="gte", threshold=Decimal("1.0"),
        )
        mail.outbox = []
        call_command("check_indicator_alerts", stdout=StringIO())
        assert IndicatorAlert.objects.count() == 0
        assert AlertNotification.objects.count() == 1
        assert len(mail.outbox) == 1

    def test_reports_counts_in_stdout(
        self, user, snapshot_petr4_cheap,
    ):
        IndicatorAlert.objects.create(
            user=user, ticker="PETR4", indicator="pe10",
            comparison="lte", threshold=Decimal("10"),
        )
        output = StringIO()
        call_command("check_indicator_alerts", stdout=output)
        text = output.getvalue()
        assert "1" in text
