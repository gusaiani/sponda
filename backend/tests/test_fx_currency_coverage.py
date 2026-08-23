"""BRL must be part of FX coverage (sync_fx_rates, audit_currencies).

BRL was treated as a currency that never needs conversion, on the theory
that it is a *listing* currency: a B3 ticker is priced in BRL and files in
BRL. That holds for B3 tickers and fails for US-listed ADRs of Brazilian
issuers, which are priced in USD and file in BRL. With no USD→BRL anchor,
their market cap cannot be translated, so PE10/PFCF10 come back empty —
and any code path that quietly falls back to the untranslated cap reports
a ratio several times too cheap.

Both the sync command (which populates the rates) and the audit command
(which is supposed to notice they are missing) excluded BRL, so the gap
could never be detected by the tooling built to detect exactly it.
"""
from io import StringIO

import pytest
from django.core.management import call_command

from quotes.management.commands.sync_fx_rates import BASELINE_CURRENCIES
from quotes.models import FxRate, Ticker


class TestSyncCurrencySet:
    def test_brl_is_a_baseline_currency(self):
        assert "BRL" in BASELINE_CURRENCIES

    @pytest.mark.django_db
    def test_brl_is_synced_by_default(self, monkeypatch):
        synced = {}

        def fake_sync(currencies):
            synced["currencies"] = currencies
            return 0

        monkeypatch.setattr(
            "quotes.management.commands.sync_fx_rates.sync_fx_rates", fake_sync
        )
        call_command("sync_fx_rates", stdout=StringIO())

        assert "BRL" in synced["currencies"]

    @pytest.mark.django_db
    def test_discovery_still_skips_usd_and_blanks(self, monkeypatch):
        # USD is the base of every stored pair, so it never needs a rate;
        # blank means "unknown", not a currency.
        Ticker.objects.create(symbol="AAA1", name="A", type="stock", reported_currency="")
        Ticker.objects.create(symbol="BBB1", name="B", type="stock", reported_currency="USD")
        Ticker.objects.create(symbol="CCC1", name="C", type="stock", reported_currency="PLN")
        synced = {}

        def fake_sync(currencies):
            synced["currencies"] = currencies
            return 0

        monkeypatch.setattr(
            "quotes.management.commands.sync_fx_rates.sync_fx_rates", fake_sync
        )
        call_command("sync_fx_rates", stdout=StringIO())

        assert "USD" not in synced["currencies"]
        assert "" not in synced["currencies"]
        assert "PLN" in synced["currencies"]


@pytest.mark.django_db
class TestAuditCurrencyCoverage:
    def test_missing_brl_history_is_reported(self):
        # A USD-listed ADR reporting in BRL, with no USD→BRL rows: exactly
        # the gap the audit exists to surface.
        Ticker.objects.create(
            symbol="SID", name="CSN", type="stock",
            reported_currency="BRL", country="BR",
        )
        output = StringIO()
        call_command("audit_currencies", stdout=output)

        report = output.getvalue()
        assert "BRL" in report.split("FX coverage:")[1]

    def test_present_brl_history_is_not_flagged(self):
        from datetime import date

        Ticker.objects.create(
            symbol="SID", name="CSN", type="stock",
            reported_currency="BRL", country="BR",
        )
        FxRate.objects.create(
            date=date(2026, 8, 22), base_currency="USD",
            quote_currency="BRL", rate="5.40000000",
        )
        output = StringIO()
        call_command("audit_currencies", stdout=output)

        coverage_section = output.getvalue().split("FX coverage:")[1]
        assert "Missing FX history" not in coverage_section
