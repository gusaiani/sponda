"""Tests for check_indicator_alerts — evaluates alerts against fresh snapshots."""
from decimal import Decimal
from io import StringIO

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from accounts.models import IndicatorAlert, User
from quotes.models import IndicatorSnapshot


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="analyst@example.com", username="analyst", password="x",
    )


@pytest.fixture
def snapshot_petr4_cheap(db):
    # PE10 = 6.5 → triggers "pe10 <= 10"
    return IndicatorSnapshot.objects.create(
        ticker="PETR4", pe10=Decimal("6.5"),
        debt_to_equity=Decimal("1.2"), market_cap=400_000_000_000,
    )


@pytest.fixture
def snapshot_petr4_expensive(db):
    # PE10 = 25 → does not trigger "pe10 <= 10"
    return IndicatorSnapshot.objects.create(
        ticker="PETR4", pe10=Decimal("25"),
        debt_to_equity=Decimal("1.2"), market_cap=400_000_000_000,
    )


@pytest.mark.django_db
class TestCheckIndicatorAlerts:
    def test_triggers_alert_when_indicator_meets_threshold(
        self, user, snapshot_petr4_cheap,
    ):
        alert = IndicatorAlert.objects.create(
            user=user, ticker="PETR4", indicator="pe10",
            comparison="lte", threshold=Decimal("10"),
        )
        call_command("check_indicator_alerts", stdout=StringIO())
        alert.refresh_from_db()
        assert alert.triggered_at is not None

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
        # Body should mention the indicator and threshold so the user knows why
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

    def test_does_not_resend_email_while_still_triggered(
        self, user, snapshot_petr4_cheap,
    ):
        # First run triggers + emails. Second run finds same condition — should
        # NOT email again (already triggered_at).
        IndicatorAlert.objects.create(
            user=user, ticker="PETR4", indicator="pe10",
            comparison="lte", threshold=Decimal("10"),
        )
        mail.outbox = []
        call_command("check_indicator_alerts", stdout=StringIO())
        assert len(mail.outbox) == 1
        mail.outbox = []
        call_command("check_indicator_alerts", stdout=StringIO())
        assert len(mail.outbox) == 0

    def test_re_triggers_after_condition_resets(self, user):
        """If the indicator leaves the threshold and re-enters, fire again."""
        alert = IndicatorAlert.objects.create(
            user=user, ticker="PETR4", indicator="pe10",
            comparison="lte", threshold=Decimal("10"),
            triggered_at=timezone.now(),  # previously triggered
        )
        # Snapshot now shows PE10 = 25 (above threshold) — should clear triggered_at
        IndicatorSnapshot.objects.create(
            ticker="PETR4", pe10=Decimal("25"), market_cap=400_000_000_000,
        )
        mail.outbox = []
        call_command("check_indicator_alerts", stdout=StringIO())
        alert.refresh_from_db()
        assert alert.triggered_at is None
        assert len(mail.outbox) == 0

        # Flip back below — should re-trigger and email again
        IndicatorSnapshot.objects.filter(ticker="PETR4").update(pe10=Decimal("5"))
        call_command("check_indicator_alerts", stdout=StringIO())
        alert.refresh_from_db()
        assert alert.triggered_at is not None
        assert len(mail.outbox) == 1

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

    def test_alert_without_matching_snapshot_is_skipped(self, user):
        # No snapshot row exists for this ticker yet.
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
        # Snapshot exists but this specific indicator is null.
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

    def test_gte_alert_triggers_when_indicator_meets_ceiling(
        self, user, snapshot_petr4_cheap,
    ):
        # debt_to_equity = 1.2, threshold 1.0 → 1.2 >= 1.0 → triggers
        alert = IndicatorAlert.objects.create(
            user=user, ticker="PETR4", indicator="debt_to_equity",
            comparison="gte", threshold=Decimal("1.0"),
        )
        mail.outbox = []
        call_command("check_indicator_alerts", stdout=StringIO())
        alert.refresh_from_db()
        assert alert.triggered_at is not None
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
        assert "1" in text  # at least one count is printed
