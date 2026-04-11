"""Tests for company visits: mark visited, visit history, revisit scheduling, sharing, reminders."""
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from accounts.models import CompanyVisit, RevisitSchedule
from accounts.tasks import send_revisit_reminders

User = get_user_model()


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="test@example.com",
        email="test@example.com",
        password="securepass123",
    )


@pytest.fixture
def authenticated_client(api_client, user):
    api_client.login(username="test@example.com", password="securepass123")
    return api_client


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username="other@example.com",
        email="other@example.com",
        password="otherpass456",
    )


# ── Mark Visited ──


class TestMarkVisited:
    def test_mark_visited_creates_visit(self, authenticated_client, user):
        response = authenticated_client.post(
            "/api/auth/visits/mark/",
            {"ticker": "PETR4"},
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.json()
        assert data["visit"]["ticker"] == "PETR4"
        assert data["visit"]["visited_at"] == str(date.today())
        assert CompanyVisit.objects.filter(user=user, ticker="PETR4").exists()

    def test_mark_visited_normalizes_ticker(self, authenticated_client, user):
        authenticated_client.post(
            "/api/auth/visits/mark/",
            {"ticker": "petr4"},
            content_type="application/json",
        )
        assert CompanyVisit.objects.filter(user=user, ticker="PETR4").exists()

    def test_mark_visited_with_note(self, authenticated_client, user):
        response = authenticated_client.post(
            "/api/auth/visits/mark/",
            {"ticker": "VALE3", "note": "Looks cheap after earnings"},
            content_type="application/json",
        )
        assert response.status_code == 201
        visit = CompanyVisit.objects.get(user=user, ticker="VALE3")
        assert visit.note == "Looks cheap after earnings"

    def test_mark_visited_with_schedule(self, authenticated_client, user):
        next_date = str(date.today() + timedelta(days=30))
        response = authenticated_client.post(
            "/api/auth/visits/mark/",
            {"ticker": "WEGE3", "next_revisit": next_date},
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.json()
        assert data["schedule"]["next_revisit"] == next_date
        assert RevisitSchedule.objects.filter(user=user, ticker="WEGE3").exists()

    def test_mark_visited_with_recurrence(self, authenticated_client, user):
        next_date = str(date.today() + timedelta(days=90))
        response = authenticated_client.post(
            "/api/auth/visits/mark/",
            {"ticker": "ITUB4", "next_revisit": next_date, "recurrence_days": 90},
            content_type="application/json",
        )
        assert response.status_code == 201
        schedule = RevisitSchedule.objects.get(user=user, ticker="ITUB4")
        assert schedule.recurrence_days == 90

    def test_mark_visited_again_bumps_recurring_schedule(self, authenticated_client, user):
        today = date.today()
        RevisitSchedule.objects.create(
            user=user,
            ticker="BBDC4",
            next_revisit=today,
            recurrence_days=30,
            share_token=RevisitSchedule.generate_share_token(),
        )
        response = authenticated_client.post(
            "/api/auth/visits/mark/",
            {"ticker": "BBDC4"},
            content_type="application/json",
        )
        assert response.status_code == 201
        schedule = RevisitSchedule.objects.get(user=user, ticker="BBDC4")
        assert schedule.next_revisit == today + timedelta(days=30)

    def test_mark_visited_same_day_is_idempotent(self, authenticated_client, user):
        authenticated_client.post(
            "/api/auth/visits/mark/",
            {"ticker": "PETR4"},
            content_type="application/json",
        )
        response = authenticated_client.post(
            "/api/auth/visits/mark/",
            {"ticker": "PETR4"},
            content_type="application/json",
        )
        assert response.status_code == 201
        assert CompanyVisit.objects.filter(user=user, ticker="PETR4").count() == 1

    def test_mark_visited_requires_auth(self, api_client, db):
        response = api_client.post(
            "/api/auth/visits/mark/",
            {"ticker": "PETR4"},
            content_type="application/json",
        )
        assert response.status_code == 403


# ── Visit List ──


class TestVisitList:
    def test_list_visits_empty(self, authenticated_client):
        response = authenticated_client.get("/api/auth/visits/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_visits(self, authenticated_client, user):
        CompanyVisit.objects.create(user=user, ticker="PETR4", visited_at=date.today())
        CompanyVisit.objects.create(user=user, ticker="VALE3", visited_at=date.today())
        response = authenticated_client.get("/api/auth/visits/")
        tickers = [v["ticker"] for v in response.json()]
        assert "PETR4" in tickers
        assert "VALE3" in tickers

    def test_list_visits_filtered_by_ticker(self, authenticated_client, user):
        CompanyVisit.objects.create(user=user, ticker="PETR4", visited_at=date.today())
        CompanyVisit.objects.create(user=user, ticker="VALE3", visited_at=date.today())
        response = authenticated_client.get("/api/auth/visits/?ticker=PETR4")
        data = response.json()
        assert len(data) == 1
        assert data[0]["ticker"] == "PETR4"

    def test_list_visits_excludes_other_users(self, authenticated_client, user, other_user):
        CompanyVisit.objects.create(user=user, ticker="PETR4", visited_at=date.today())
        CompanyVisit.objects.create(user=other_user, ticker="VALE3", visited_at=date.today())
        response = authenticated_client.get("/api/auth/visits/")
        tickers = [v["ticker"] for v in response.json()]
        assert "PETR4" in tickers
        assert "VALE3" not in tickers

    def test_list_visits_requires_auth(self, api_client, db):
        response = api_client.get("/api/auth/visits/")
        assert response.status_code == 403


# ── Visit Detail ──


class TestVisitDetail:
    def test_update_visit_note(self, authenticated_client, user):
        visit = CompanyVisit.objects.create(user=user, ticker="PETR4", visited_at=date.today())
        response = authenticated_client.put(
            f"/api/auth/visits/{visit.pk}/",
            {"note": "Updated note"},
            content_type="application/json",
        )
        assert response.status_code == 200
        visit.refresh_from_db()
        assert visit.note == "Updated note"

    def test_delete_visit(self, authenticated_client, user):
        visit = CompanyVisit.objects.create(user=user, ticker="PETR4", visited_at=date.today())
        response = authenticated_client.delete(f"/api/auth/visits/{visit.pk}/")
        assert response.status_code == 204
        assert not CompanyVisit.objects.filter(pk=visit.pk).exists()

    def test_cannot_access_other_users_visit(self, authenticated_client, other_user):
        visit = CompanyVisit.objects.create(user=other_user, ticker="PETR4", visited_at=date.today())
        response = authenticated_client.put(
            f"/api/auth/visits/{visit.pk}/",
            {"note": "Hacked"},
            content_type="application/json",
        )
        assert response.status_code == 404


# ── Revisit Schedules ──


class TestRevisitSchedules:
    def test_list_schedules(self, authenticated_client, user):
        RevisitSchedule.objects.create(
            user=user,
            ticker="PETR4",
            next_revisit=date.today() + timedelta(days=30),
            share_token=RevisitSchedule.generate_share_token(),
        )
        response = authenticated_client.get("/api/auth/visits/schedules/")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["ticker"] == "PETR4"

    def test_list_due_schedules(self, authenticated_client, user):
        RevisitSchedule.objects.create(
            user=user,
            ticker="PETR4",
            next_revisit=date.today() - timedelta(days=1),
            share_token=RevisitSchedule.generate_share_token(),
        )
        RevisitSchedule.objects.create(
            user=user,
            ticker="VALE3",
            next_revisit=date.today() + timedelta(days=30),
            share_token=RevisitSchedule.generate_share_token(),
        )
        response = authenticated_client.get("/api/auth/visits/schedules/?status=due")
        data = response.json()
        assert len(data) == 1
        assert data[0]["ticker"] == "PETR4"

    def test_update_schedule(self, authenticated_client, user):
        schedule = RevisitSchedule.objects.create(
            user=user,
            ticker="PETR4",
            next_revisit=date.today() + timedelta(days=30),
            share_token=RevisitSchedule.generate_share_token(),
        )
        new_date = str(date.today() + timedelta(days=60))
        response = authenticated_client.put(
            f"/api/auth/visits/schedules/{schedule.pk}/",
            {"next_revisit": new_date, "recurrence_days": 90},
            content_type="application/json",
        )
        assert response.status_code == 200
        schedule.refresh_from_db()
        assert str(schedule.next_revisit) == new_date
        assert schedule.recurrence_days == 90

    def test_delete_schedule(self, authenticated_client, user):
        schedule = RevisitSchedule.objects.create(
            user=user,
            ticker="PETR4",
            next_revisit=date.today() + timedelta(days=30),
            share_token=RevisitSchedule.generate_share_token(),
        )
        response = authenticated_client.delete(f"/api/auth/visits/schedules/{schedule.pk}/")
        assert response.status_code == 204
        assert not RevisitSchedule.objects.filter(pk=schedule.pk).exists()


# ── Shared Visits ──


class TestSharedVisits:
    def test_shared_visits_returns_data_without_auth(self, api_client, user, db):
        schedule = RevisitSchedule.objects.create(
            user=user,
            ticker="PETR4",
            next_revisit=date.today() + timedelta(days=30),
            share_token=RevisitSchedule.generate_share_token(),
        )
        CompanyVisit.objects.create(user=user, ticker="PETR4", visited_at=date.today())
        response = api_client.get(f"/api/auth/visits/shared/{schedule.share_token}/")
        assert response.status_code == 200
        data = response.json()
        assert data["ticker"] == "PETR4"
        assert len(data["visits"]) == 1

    def test_shared_visits_invalid_token_returns_404(self, api_client, db):
        response = api_client.get("/api/auth/visits/shared/invalid-token/")
        assert response.status_code == 404


# ── Pending Reminders ──


class TestPendingReminders:
    def test_returns_due_reminders(self, authenticated_client, user):
        RevisitSchedule.objects.create(
            user=user,
            ticker="PETR4",
            next_revisit=date.today(),
            share_token=RevisitSchedule.generate_share_token(),
        )
        RevisitSchedule.objects.create(
            user=user,
            ticker="VALE3",
            next_revisit=date.today() - timedelta(days=3),
            share_token=RevisitSchedule.generate_share_token(),
        )
        response = authenticated_client.get("/api/auth/visits/reminders/")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

    def test_returns_empty_when_nothing_due(self, authenticated_client, user):
        RevisitSchedule.objects.create(
            user=user,
            ticker="PETR4",
            next_revisit=date.today() + timedelta(days=30),
            share_token=RevisitSchedule.generate_share_token(),
        )
        response = authenticated_client.get("/api/auth/visits/reminders/")
        data = response.json()
        assert data["count"] == 0

    def test_reminders_require_auth(self, api_client, db):
        response = api_client.get("/api/auth/visits/reminders/")
        assert response.status_code == 403


# ── Revisit Reminder Task ──


class TestRevisitReminderTask:
    @patch("accounts.tasks.send_mail")
    def test_sends_email_for_due_revisit(self, mock_send_mail, user, db):
        RevisitSchedule.objects.create(
            user=user,
            ticker="PETR4",
            next_revisit=date.today(),
            share_token=RevisitSchedule.generate_share_token(),
        )
        result = send_revisit_reminders()
        assert result == 1
        mock_send_mail.assert_called_once()
        call_kwargs = mock_send_mail.call_args
        assert "PETR4" in call_kwargs[1]["subject"]

    @patch("accounts.tasks.send_mail")
    def test_does_not_resend_after_notified(self, mock_send_mail, user, db):
        from django.utils import timezone
        RevisitSchedule.objects.create(
            user=user,
            ticker="PETR4",
            next_revisit=date.today(),
            notified_at=timezone.now(),
            share_token=RevisitSchedule.generate_share_token(),
        )
        result = send_revisit_reminders()
        assert result == 0
        mock_send_mail.assert_not_called()

    @patch("accounts.tasks.send_mail")
    def test_only_sends_for_due_dates(self, mock_send_mail, user, db):
        RevisitSchedule.objects.create(
            user=user,
            ticker="PETR4",
            next_revisit=date.today() + timedelta(days=30),
            share_token=RevisitSchedule.generate_share_token(),
        )
        result = send_revisit_reminders()
        assert result == 0
        mock_send_mail.assert_not_called()
