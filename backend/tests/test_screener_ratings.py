"""Tests for Learning Mode ratings on the screener endpoint."""
from decimal import Decimal

import pytest
from django.test import Client

from quotes.models import IndicatorSnapshot, Ticker


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def seeded_universe(db):
    Ticker.objects.create(
        symbol="PETR4", name="Petrobras", sector="Oil",
        market_cap=400_000_000_000, country="BR",
    )
    Ticker.objects.create(
        symbol="VALE3", name="Vale", sector="Mining",
        market_cap=300_000_000_000, country="BR",
    )
    IndicatorSnapshot.objects.create(
        ticker="PETR4",
        pe10=Decimal("8"), pfcf10=Decimal("10"),
        peg=Decimal("0.5"), pfcf_peg=Decimal("0.6"),
        debt_to_equity=Decimal("0.4"),
        debt_ex_lease_to_equity=Decimal("0.3"),
        liabilities_to_equity=Decimal("0.8"),
        current_ratio=Decimal("2.0"),
        debt_to_avg_earnings=Decimal("3.0"),
        debt_to_avg_fcf=Decimal("4.0"),
        market_cap=400_000_000_000,
        current_price=Decimal("35"),
    )
    IndicatorSnapshot.objects.create(
        ticker="VALE3",
        pe10=Decimal("50"),  # expensive
        debt_to_equity=Decimal("4.0"),  # heavy
        market_cap=300_000_000_000,
    )


@pytest.mark.django_db
class TestScreenerRatings:
    def test_each_result_includes_ratings_block(self, api_client, seeded_universe):
        response = api_client.get("/api/screener/")
        assert response.status_code == 200
        data = response.json()
        for row in data["results"]:
            assert "ratings" in row
            assert "overall" in row["ratings"]
            assert "methodology_version" in row["ratings"]

    def test_well_priced_company_grades_higher_than_overpriced(
        self, api_client, seeded_universe,
    ):
        response = api_client.get("/api/screener/")
        rows = {row["ticker"]: row for row in response.json()["results"]}
        petr_grade = rows["PETR4"]["ratings"]["overall"]
        vale_grade = rows["VALE3"]["ratings"]["overall"]
        # PETR4 has 10 strong indicators; VALE3 has 2 weak ones -> below MIN
        assert petr_grade is not None
        assert petr_grade >= 4
        assert vale_grade is None  # not enough rated indicators for a grade

    def test_per_indicator_ratings_use_snake_case(
        self, api_client, seeded_universe,
    ):
        response = api_client.get("/api/screener/")
        ratings = next(
            row["ratings"] for row in response.json()["results"] if row["ticker"] == "PETR4"
        )
        for key in (
            "pe10", "pfcf10", "peg", "pfcf_peg",
            "debt_to_equity", "debt_ex_lease_to_equity", "liabilities_to_equity",
            "current_ratio", "debt_to_avg_earnings", "debt_to_avg_fcf",
        ):
            assert key in ratings
