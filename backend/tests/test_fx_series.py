"""Tests for the FX time-series helper and endpoint.

The comparison chart's "common currency" mode needs a historical FX path so
each company's price/market-cap series can be translated into one currency
before being rebased. `fx_series` returns that path; `FxSeriesView` exposes it.
"""
from datetime import date
from decimal import Decimal

import pytest

from quotes.fx import fx_series
from quotes.models import FxRate


def _seed_usd_brl():
    FxRate.objects.create(
        base_currency="USD", quote_currency="BRL",
        date=date(2024, 1, 2), rate=Decimal("5.00"),
    )
    FxRate.objects.create(
        base_currency="USD", quote_currency="BRL",
        date=date(2024, 1, 3), rate=Decimal("5.10"),
    )


class TestFxSeriesHelper:
    def test_identity_pair_returns_empty(self, db):
        assert fx_series("USD", "USD") == []

    def test_inverts_usd_pivot_for_brl_to_usd(self, db):
        _seed_usd_brl()
        series = fx_series("BRL", "USD")
        assert len(series) == 2
        first_date, first_rate = series[0]
        assert first_date == date(2024, 1, 2)
        # 1 BRL = 1/5.00 USD = 0.20
        assert abs(float(first_rate) - 0.20) < 1e-9

    def test_respects_start_filter(self, db):
        _seed_usd_brl()
        series = fx_series("BRL", "USD", start=date(2024, 1, 3))
        assert len(series) == 1
        assert series[0][0] == date(2024, 1, 3)

    def test_pivots_non_usd_pair_through_usd(self, db):
        FxRate.objects.create(
            base_currency="USD", quote_currency="BRL",
            date=date(2024, 1, 2), rate=Decimal("5.00"),
        )
        FxRate.objects.create(
            base_currency="USD", quote_currency="DKK",
            date=date(2024, 1, 2), rate=Decimal("7.00"),
        )
        series = fx_series("BRL", "DKK")
        assert len(series) == 1
        # 1 BRL = (7.00 DKK/USD) / (5.00 BRL/USD) = 1.4 DKK
        assert abs(float(series[0][1]) - 1.4) < 1e-9


class TestFxSeriesView:
    def test_returns_rates_payload(self, client, db):
        _seed_usd_brl()
        resp = client.get("/api/fx/series/?from=BRL&to=USD")
        assert resp.status_code == 200
        data = resp.json()
        assert data["from"] == "BRL"
        assert data["to"] == "USD"
        assert len(data["rates"]) == 2
        assert data["rates"][0]["date"] == "2024-01-02"
        assert abs(data["rates"][0]["rate"] - 0.20) < 1e-9

    def test_identity_returns_empty_rates(self, client, db):
        resp = client.get("/api/fx/series/?from=USD&to=USD")
        assert resp.status_code == 200
        assert resp.json()["rates"] == []

    def test_missing_params_is_bad_request(self, client, db):
        assert client.get("/api/fx/series/?from=BRL").status_code == 400
        assert client.get("/api/fx/series/?to=USD").status_code == 400

    def test_invalid_start_is_bad_request(self, client, db):
        resp = client.get("/api/fx/series/?from=BRL&to=USD&start=not-a-date")
        assert resp.status_code == 400
