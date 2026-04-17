"""Guards idempotence of the e2e seed helper so flaky unique-constraint
failures from cross-test data leaks don't resurface (see PR #165 CI)."""
import pytest

from quotes.models import IPCAIndex, QuarterlyCashFlow, QuarterlyEarnings
from tests.conftest import seed_e2e_baseline


@pytest.mark.django_db
def test_is_idempotent_on_second_call():
    seed_e2e_baseline("PETR4")
    earnings_first = QuarterlyEarnings.objects.filter(ticker="PETR4").count()
    ipca_first = IPCAIndex.objects.count()
    cash_flows_first = QuarterlyCashFlow.objects.filter(ticker="PETR4").count()

    seed_e2e_baseline("PETR4")

    assert QuarterlyEarnings.objects.filter(ticker="PETR4").count() == earnings_first
    assert IPCAIndex.objects.count() == ipca_first
    assert QuarterlyCashFlow.objects.filter(ticker="PETR4").count() == cash_flows_first


@pytest.mark.django_db
def test_different_ticker_adds_rows_without_touching_first():
    seed_e2e_baseline("PETR4")
    petr4_earnings = QuarterlyEarnings.objects.filter(ticker="PETR4").count()

    seed_e2e_baseline("VALE3")

    assert QuarterlyEarnings.objects.filter(ticker="PETR4").count() == petr4_earnings
    assert QuarterlyEarnings.objects.filter(ticker="VALE3").count() == petr4_earnings
