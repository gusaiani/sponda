"""Tiered per-IP / per-user lookup limits.

Rules (distinct companies per UTC day):
  - anonymous              -> 20, scoped by client IP (hashed)
  - logged in, unverified  -> 50, scoped by user
  - logged in, verified    -> unlimited

Enforced server-side in PE10View and reported by QuotaView; the
frontend opens the auth modal (anon) or email-verification prompt
(unverified) when the cap is hit.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from quotes.models import LookupLog

User = get_user_model()


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def verified_user(db):
    return User.objects.create_user(
        username="v@example.com", email="v@example.com",
        password="pw123456", email_verified=True,
    )


@pytest.fixture
def unverified_user(db):
    return User.objects.create_user(
        username="u@example.com", email="u@example.com",
        password="pw123456", email_verified=False,
    )


class TestLookupLogIpHash:
    def test_can_persist_ip_hash(self, db):
        entry = LookupLog.objects.create(ticker="PETR4", ip_hash="abc123")
        entry.refresh_from_db()
        assert entry.ip_hash == "abc123"

    def test_ip_hash_optional_for_authenticated_rows(self, db, verified_user):
        entry = LookupLog.objects.create(user=verified_user, ticker="PETR4")
        entry.refresh_from_db()
        assert entry.ip_hash in (None, "")

    def test_distinct_tickers_today_for_ip(self, db):
        today = timezone.now()
        # Same IP, same ticker twice + a second ticker => 2 distinct.
        LookupLog.objects.create(ticker="PETR4", ip_hash="ip-a")
        LookupLog.objects.create(ticker="PETR4", ip_hash="ip-a")
        LookupLog.objects.create(ticker="VALE3", ip_hash="ip-a")
        # Different IP must not bleed into the count.
        LookupLog.objects.create(ticker="ITUB4", ip_hash="ip-b")

        day_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        distinct = (
            LookupLog.objects.filter(ip_hash="ip-a", timestamp__gte=day_start)
            .values("ticker")
            .distinct()
            .count()
        )
        assert distinct == 2


class TestLookupQuota:
    """quotes.lookup_quota.lookup_quota(request) — the single source of truth
    for limits, consumed by both PE10View enforcement and QuotaView."""

    def _get(self, api_client, path="/api/auth/quota/", **extra):
        return api_client.get(path, **extra)

    def test_anonymous_limit_is_20_per_ip(self, api_client, db):
        from quotes.lookup_quota import lookup_quota
        from django.test import RequestFactory

        req = RequestFactory().get("/api/quote/PETR4/")
        req.user = __import__("django.contrib.auth.models", fromlist=["AnonymousUser"]).AnonymousUser()
        req.META["HTTP_CF_CONNECTING_IP"] = "203.0.113.10"
        q = lookup_quota(req)
        assert q["scope"] == "anonymous"
        assert q["limit"] == 20
        assert q["used"] == 0
        assert q["remaining"] == 20
        assert q["authenticated"] is False

    def test_unverified_user_limit_is_50(self, db, unverified_user):
        from quotes.lookup_quota import lookup_quota
        from django.test import RequestFactory

        req = RequestFactory().get("/api/quote/PETR4/")
        req.user = unverified_user
        q = lookup_quota(req)
        assert q["scope"] == "unverified"
        assert q["limit"] == 50
        assert q["remaining"] == 50

    def test_verified_user_is_unlimited(self, db, verified_user):
        from quotes.lookup_quota import lookup_quota
        from django.test import RequestFactory

        req = RequestFactory().get("/api/quote/PETR4/")
        req.user = verified_user
        q = lookup_quota(req)
        assert q["scope"] == "verified"
        assert q["limit"] is None
        assert q["remaining"] is None

    def test_used_counts_distinct_tickers_only(self, db):
        from quotes.lookup_quota import lookup_quota
        from quotes.client_ip import client_ip_hash
        from django.test import RequestFactory

        req = RequestFactory().get("/api/quote/PETR4/")
        req.user = __import__("django.contrib.auth.models", fromlist=["AnonymousUser"]).AnonymousUser()
        req.META["HTTP_CF_CONNECTING_IP"] = "203.0.113.11"
        h = client_ip_hash(req)
        LookupLog.objects.create(ticker="PETR4", ip_hash=h)
        LookupLog.objects.create(ticker="PETR4", ip_hash=h)
        LookupLog.objects.create(ticker="VALE3", ip_hash=h)
        q = lookup_quota(req)
        assert q["used"] == 2
        assert q["remaining"] == 18

    def test_would_exceed_limit_blocks_new_ticker_over_cap(self, db, settings):
        from quotes.lookup_quota import would_exceed_limit
        from quotes.client_ip import client_ip_hash
        from django.test import RequestFactory

        settings.SPONDA_ANON_LOOKUPS_PER_DAY = 2
        req = RequestFactory().get("/api/quote/NEW1/")
        req.user = __import__("django.contrib.auth.models", fromlist=["AnonymousUser"]).AnonymousUser()
        req.META["HTTP_CF_CONNECTING_IP"] = "203.0.113.12"
        h = client_ip_hash(req)
        LookupLog.objects.create(ticker="AAA", ip_hash=h)
        LookupLog.objects.create(ticker="BBB", ip_hash=h)
        # At cap (2 distinct). A brand-new ticker must be blocked...
        assert would_exceed_limit(req, "CCC") is True
        # ...but re-viewing one already counted today is allowed.
        assert would_exceed_limit(req, "AAA") is False

    def test_verified_user_never_exceeds(self, db, verified_user, settings):
        from quotes.lookup_quota import would_exceed_limit
        from django.test import RequestFactory

        settings.SPONDA_ANON_LOOKUPS_PER_DAY = 1
        req = RequestFactory().get("/api/quote/ZZZ/")
        req.user = verified_user
        for t in ("A", "B", "C", "D"):
            LookupLog.objects.create(user=verified_user, ticker=t)
        assert would_exceed_limit(req, "NEVER") is False


class TestPE10ViewEnforcement:
    """PE10View returns 429 (no payload) once the scope is over its cap."""

    def _seed_ip(self, ip, tickers):
        from quotes.client_ip import client_ip_hash
        from django.test import RequestFactory
        r = RequestFactory().get("/")
        r.META["HTTP_CF_CONNECTING_IP"] = ip
        h = client_ip_hash(r)
        for t in tickers:
            LookupLog.objects.create(ticker=t, ip_hash=h)
        return h

    def test_anon_over_cap_gets_429(self, api_client, db, settings):
        settings.SPONDA_ANON_LOOKUPS_PER_DAY = 3
        self._seed_ip("203.0.113.20", ["AAA", "BBB", "CCC"])
        resp = api_client.get(
            "/api/quote/DDDD/", HTTP_CF_CONNECTING_IP="203.0.113.20"
        )
        assert resp.status_code == 429
        body = resp.json()
        assert body["code"] == "lookup_limit"
        assert body["limit"] == 3
        assert body["scope"] == "anonymous"
        # A blocked request must not be logged (no quota burn for a 429).
        from quotes.client_ip import client_ip_hash
        from django.test import RequestFactory
        r = RequestFactory().get("/")
        r.META["HTTP_CF_CONNECTING_IP"] = "203.0.113.20"
        assert not LookupLog.objects.filter(
            ip_hash=client_ip_hash(r), ticker="DDDD"
        ).exists()

    def test_anon_can_revisit_already_seen_ticker_when_capped(
        self, api_client, db, settings, sample_ipca, sample_cash_flows,
        sample_balance_sheet,
    ):
        settings.SPONDA_ANON_LOOKUPS_PER_DAY = 1
        self._seed_ip("203.0.113.21", ["PETR4"])
        resp = api_client.get(
            "/api/quote/PETR4/", HTTP_CF_CONNECTING_IP="203.0.113.21"
        )
        assert resp.status_code != 429

    def test_429_is_not_cacheable(self, api_client, db, settings):
        settings.SPONDA_ANON_LOOKUPS_PER_DAY = 1
        self._seed_ip("203.0.113.22", ["AAA"])
        resp = api_client.get(
            "/api/quote/ZZZZ/", HTTP_CF_CONNECTING_IP="203.0.113.22"
        )
        assert resp.status_code == 429
        assert "no-store" in resp.headers.get("Cache-Control", "")

    def test_verified_user_never_429(
        self, api_client, db, settings, verified_user,
    ):
        settings.SPONDA_ANON_LOOKUPS_PER_DAY = 1
        settings.SPONDA_UNVERIFIED_LOOKUPS_PER_DAY = 1
        for t in ("A", "B", "C"):
            LookupLog.objects.create(user=verified_user, ticker=t)
        api_client.force_login(verified_user)
        resp = api_client.get("/api/quote/WHATEVER/")
        assert resp.status_code != 429

    def test_anon_lookup_records_ip_hash(
        self, api_client, db, sample_ipca, sample_cash_flows,
        sample_balance_sheet,
    ):
        from quotes.client_ip import client_ip_hash
        from django.test import RequestFactory
        api_client.get("/api/quote/PETR4/", HTTP_CF_CONNECTING_IP="203.0.113.23")
        r = RequestFactory().get("/")
        r.META["HTTP_CF_CONNECTING_IP"] = "203.0.113.23"
        assert LookupLog.objects.filter(
            ip_hash=client_ip_hash(r), ticker="PETR4"
        ).exists()


class TestDataEndpointEnforcement:
    """The heavy ticker DATA endpoints (multiples-history, fundamentals) must
    enforce the same daily distinct-company cap as PE10View.

    Otherwise a client that skips the main quote page can still enumerate the
    whole catalogue through these unmetered sub-endpoints, hitting providers
    for every ticker. Enforcement must short-circuit *before* any provider
    call, exactly like PE10View.
    """

    def _seed_ip(self, ip, tickers):
        from quotes.client_ip import client_ip_hash
        from django.test import RequestFactory
        r = RequestFactory().get("/")
        r.META["HTTP_CF_CONNECTING_IP"] = ip
        h = client_ip_hash(r)
        for t in tickers:
            LookupLog.objects.create(ticker=t, ip_hash=h)
        return h

    @pytest.fixture
    def no_provider_calls(self, monkeypatch):
        """Fail loudly if enforcement ever lets a request reach a provider."""
        import quotes.views as views

        def _boom(*_a, **_k):  # pragma: no cover - asserted via not-called
            raise AssertionError("provider was called despite over-cap request")

        monkeypatch.setattr(views, "_ensure_fresh_data", _boom)
        monkeypatch.setattr(views, "fetch_quote", _boom)

    def test_multiples_history_over_cap_gets_429(
        self, api_client, db, settings, no_provider_calls
    ):
        settings.SPONDA_ANON_LOOKUPS_PER_DAY = 3
        self._seed_ip("203.0.113.40", ["AAA", "BBB", "CCC"])
        resp = api_client.get(
            "/api/quote/DDDD/multiples-history/",
            HTTP_CF_CONNECTING_IP="203.0.113.40",
        )
        assert resp.status_code == 429
        body = resp.json()
        assert body["code"] == "lookup_limit"
        assert body["scope"] == "anonymous"
        assert "no-store" in resp.headers.get("Cache-Control", "")

    def test_fundamentals_over_cap_gets_429(
        self, api_client, db, settings, no_provider_calls
    ):
        settings.SPONDA_ANON_LOOKUPS_PER_DAY = 3
        self._seed_ip("203.0.113.41", ["AAA", "BBB", "CCC"])
        resp = api_client.get(
            "/api/quote/DDDD/fundamentals/",
            HTTP_CF_CONNECTING_IP="203.0.113.41",
        )
        assert resp.status_code == 429
        assert resp.json()["code"] == "lookup_limit"

    def test_over_cap_data_request_is_not_logged(
        self, api_client, db, settings, no_provider_calls
    ):
        from quotes.client_ip import client_ip_hash
        from django.test import RequestFactory

        settings.SPONDA_ANON_LOOKUPS_PER_DAY = 1
        self._seed_ip("203.0.113.42", ["AAA"])
        api_client.get(
            "/api/quote/NOPE/fundamentals/",
            HTTP_CF_CONNECTING_IP="203.0.113.42",
        )
        r = RequestFactory().get("/")
        r.META["HTTP_CF_CONNECTING_IP"] = "203.0.113.42"
        assert not LookupLog.objects.filter(
            ip_hash=client_ip_hash(r), ticker="NOPE"
        ).exists()

    def test_revisit_of_seen_ticker_is_not_blocked_at_quota_layer(
        self, db, settings
    ):
        """A ticker already counted today must pass the quota gate even when
        the scope is otherwise over its cap (mirrors PE10View revisit rule)."""
        from quotes.lookup_enforcement import LookupQuotaEnforcedView
        from quotes.client_ip import client_ip_hash
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory

        settings.SPONDA_ANON_LOOKUPS_PER_DAY = 1
        req = RequestFactory().get("/api/quote/SEEN/fundamentals/")
        req.user = AnonymousUser()
        req.META["HTTP_CF_CONNECTING_IP"] = "203.0.113.43"
        LookupLog.objects.create(ticker="SEEN", ip_hash=client_ip_hash(req))

        view = LookupQuotaEnforcedView()
        assert view.enforce_lookup_quota(req, "SEEN") is None  # revisit allowed
        assert view.enforce_lookup_quota(req, "OTHER") is not None  # new -> 429


class TestLookupQuotaMixin:
    """quotes.lookup_enforcement.LookupQuotaEnforcedView — the shared gate +
    logger reused by every ticker payload endpoint."""

    def test_record_lookup_persists_ip_hash_for_anon(self, db):
        from quotes.lookup_enforcement import LookupQuotaEnforcedView
        from quotes.client_ip import client_ip_hash
        from django.contrib.auth.models import AnonymousUser
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.test import RequestFactory

        req = RequestFactory().get("/api/quote/PETR4/fundamentals/")
        req.user = AnonymousUser()
        req.META["HTTP_CF_CONNECTING_IP"] = "203.0.113.44"
        SessionMiddleware(lambda r: None).process_request(req)

        LookupQuotaEnforcedView().record_lookup(req, "PETR4")
        assert LookupLog.objects.filter(
            ip_hash=client_ip_hash(req), ticker="PETR4"
        ).exists()

    def test_record_lookup_attributes_to_user_when_authenticated(
        self, db, verified_user
    ):
        from quotes.lookup_enforcement import LookupQuotaEnforcedView
        from django.test import RequestFactory

        req = RequestFactory().get("/api/quote/PETR4/fundamentals/")
        req.user = verified_user
        LookupQuotaEnforcedView().record_lookup(req, "PETR4")
        assert LookupLog.objects.filter(
            user=verified_user, ticker="PETR4"
        ).exists()


class TestQuotaViewEndpoint:
    def test_anon_quota_endpoint(self, api_client, db):
        resp = api_client.get(
            "/api/auth/quota/", HTTP_CF_CONNECTING_IP="203.0.113.30"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["limit"] == 20
        assert body["used"] == 0
        assert body["remaining"] == 20
        assert body["authenticated"] is False
        assert body["scope"] == "anonymous"

    def test_unverified_quota_endpoint(self, api_client, db, unverified_user):
        api_client.force_login(unverified_user)
        body = api_client.get("/api/auth/quota/").json()
        assert body["limit"] == 50
        assert body["scope"] == "unverified"
        assert body["authenticated"] is True
        assert body["email_verified"] is False

    def test_verified_quota_endpoint_is_unlimited(
        self, api_client, db, verified_user
    ):
        api_client.force_login(verified_user)
        body = api_client.get("/api/auth/quota/").json()
        assert body["limit"] is None
        assert body["remaining"] is None
        assert body["scope"] == "verified"
        assert body["email_verified"] is True

    def test_anon_used_reflects_distinct_lookups(
        self, api_client, db, sample_ipca, sample_cash_flows,
        sample_balance_sheet,
    ):
        ip = "203.0.113.31"
        api_client.get("/api/quote/PETR4/", HTTP_CF_CONNECTING_IP=ip)
        api_client.get("/api/quote/PETR4/", HTTP_CF_CONNECTING_IP=ip)
        body = api_client.get("/api/auth/quota/", HTTP_CF_CONNECTING_IP=ip).json()
        assert body["used"] == 1
        assert body["remaining"] == 19
