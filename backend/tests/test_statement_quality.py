"""Tests for provider data-quality normalisation.

BRAPI and FMP both encode a missing net income as a literal `0` rather than
null for some filings. Stored as-is, a zero flows into the inflation-adjusted
earnings average behind P/E10, silently dragging it toward zero and inflating
the multiple. 2,801 rows across 565 companies were affected when this was
found; BBAS3 reported R$31bn of quarterly revenue and exactly R$0 of profit
for every quarter from 2013 to 2019.
"""
from datetime import date

import pytest

from quotes.models import BalanceSheet, QuarterlyEarnings
from quotes.statement_quality import (
    discard_implausible_debt_collapses,
    is_implausible_debt_collapse,
    normalize_net_income,
)


class TestNormalizeNetIncome:
    def test_passes_through_a_real_figure(self):
        assert normalize_net_income(8_680_714_000, 66_655_190_000) == 8_680_714_000

    def test_passes_through_a_real_loss(self):
        assert normalize_net_income(-500_000, 66_655_190_000) == -500_000

    def test_passes_through_none(self):
        assert normalize_net_income(None, 66_655_190_000) is None

    def test_zero_alongside_real_revenue_is_missing(self):
        # A bank booking R$31bn of revenue and exactly R$0.00 of profit is a
        # provider artifact, not a quarter.
        assert normalize_net_income(0, 31_678_067_000) is None

    def test_zero_with_no_revenue_is_kept(self):
        # A shell or pre-revenue company can genuinely earn nothing, and that
        # is a fact worth storing rather than erasing.
        assert normalize_net_income(0, 0) == 0
        assert normalize_net_income(0, None) == 0

    def test_zero_with_negative_revenue_is_kept(self):
        assert normalize_net_income(0, -100) == 0


# --- Debt that vanishes without the liabilities to match ------------------

CRM_QUARTER_BEFORE = dict(
    previous_debt=41_884_000_000, previous_total_liabilities=72_445_000_000,
)
CRM_MISPARSED_QUARTER = dict(debt=2_455_000_000, total_liabilities=71_242_000_000)


class TestIsImplausibleDebtCollapse:
    def test_the_crm_misparse(self):
        # Q2 FY2027, filed 2026-08-26. FMP tagged $39.3bn of senior notes as
        # `otherNonCurrentLiabilities`, leaving totalDebt at $2.46bn while
        # total liabilities barely moved. Repaying $39bn would have taken
        # total liabilities down with it.
        assert is_implausible_debt_collapse(
            **CRM_QUARTER_BEFORE, **CRM_MISPARSED_QUARTER,
        )

    def test_debt_reported_as_zero_beside_untouched_liabilities(self):
        # Honda, 2026-06-30: ¥13.5tn of debt became ¥0 while ¥21.4tn of
        # liabilities stayed put.
        assert is_implausible_debt_collapse(
            previous_debt=13_538_327_425_000,
            previous_total_liabilities=21_453_860_162_000,
            debt=0,
            total_liabilities=21_361_213_000_000,
        )

    def test_a_repayment_the_liabilities_confirm(self):
        # Debt actually retired: the cash went out, so total liabilities fell
        # by the same amount. Nothing to distrust.
        assert not is_implausible_debt_collapse(
            previous_debt=40_000_000_000,
            previous_total_liabilities=70_000_000_000,
            debt=1_000_000_000,
            total_liabilities=31_000_000_000,
        )

    def test_a_partial_paydown_is_ordinary(self):
        # Half the debt retired, liabilities flat because it was refinanced
        # within the quarter. Too small a share to distinguish from noise,
        # and too routine to erase.
        assert not is_implausible_debt_collapse(
            previous_debt=40_000_000_000,
            previous_total_liabilities=70_000_000_000,
            debt=20_000_000_000,
            total_liabilities=69_000_000_000,
        )

    def test_a_small_loan_disappearing_is_ordinary(self):
        # The whole debt went, but it was 5% of the balance sheet. A company
        # can clear a small facility without moving total liabilities much.
        assert not is_implausible_debt_collapse(
            previous_debt=500_000_000,
            previous_total_liabilities=10_000_000_000,
            debt=0,
            total_liabilities=9_600_000_000,
        )

    def test_debt_growing_is_never_a_collapse(self):
        assert not is_implausible_debt_collapse(
            previous_debt=1_000_000_000,
            previous_total_liabilities=10_000_000_000,
            debt=40_000_000_000,
            total_liabilities=10_100_000_000,
        )

    def test_missing_figures_are_not_judged(self):
        assert not is_implausible_debt_collapse(
            previous_debt=None, previous_total_liabilities=72_445_000_000,
            debt=2_455_000_000, total_liabilities=71_242_000_000,
        )
        assert not is_implausible_debt_collapse(
            **CRM_QUARTER_BEFORE, debt=None, total_liabilities=71_242_000_000,
        )
        assert not is_implausible_debt_collapse(
            previous_debt=41_884_000_000, previous_total_liabilities=None,
            **CRM_MISPARSED_QUARTER,
        )
        assert not is_implausible_debt_collapse(
            **CRM_QUARTER_BEFORE, debt=2_455_000_000, total_liabilities=None,
        )

    def test_no_prior_debt_means_nothing_could_collapse(self):
        assert not is_implausible_debt_collapse(
            previous_debt=0, previous_total_liabilities=10_000_000_000,
            debt=0, total_liabilities=10_000_000_000,
        )

    def test_a_prior_balance_sheet_with_no_liabilities_is_not_judged(self):
        # Nothing to measure materiality against.
        assert not is_implausible_debt_collapse(
            previous_debt=1_000_000, previous_total_liabilities=0,
            debt=0, total_liabilities=0,
        )


def _sheet(year, month, day, debt, liabilities):
    return BalanceSheet(
        ticker="CRM", end_date=date(year, month, day),
        total_debt=debt, total_liabilities=liabilities,
    )


class TestDiscardImplausibleDebtCollapses:
    def test_nulls_the_collapsed_quarter_and_keeps_the_rest(self):
        sheets = [
            _sheet(2026, 1, 31, 17_176_000_000, 53_163_000_000),
            _sheet(2026, 4, 30, 41_884_000_000, 72_445_000_000),
            _sheet(2026, 7, 31, 2_455_000_000, 71_242_000_000),
        ]
        discard_implausible_debt_collapses(sheets)
        assert [sheet.total_debt for sheet in sheets] == [
            17_176_000_000, 41_884_000_000, None,
        ]

    def test_reads_the_sequence_in_date_order_whatever_order_it_arrives(self):
        # FMP returns newest first; the rule is about what preceded a quarter.
        sheets = [
            _sheet(2026, 7, 31, 2_455_000_000, 71_242_000_000),
            _sheet(2026, 4, 30, 41_884_000_000, 72_445_000_000),
        ]
        discard_implausible_debt_collapses(sheets)
        assert sheets[0].total_debt is None
        assert sheets[1].total_debt == 41_884_000_000

    def test_a_discarded_quarter_is_not_the_baseline_for_the_next(self):
        # Otherwise the recovery quarter reads as a debt explosion off a
        # bogus floor, and worse, the quarter after a nulled one would have
        # no comparison at all. The last trusted figure carries forward.
        sheets = [
            _sheet(2026, 4, 30, 41_884_000_000, 72_445_000_000),
            _sheet(2026, 7, 31, 2_455_000_000, 71_242_000_000),
            _sheet(2026, 10, 31, 1_900_000_000, 70_800_000_000),
        ]
        discard_implausible_debt_collapses(sheets)
        assert [sheet.total_debt for sheet in sheets] == [
            41_884_000_000, None, None,
        ]

    def test_leaves_a_clean_history_untouched(self):
        sheets = [
            _sheet(2024, 10, 31, 11_424_000_000, 32_870_000_000),
            _sheet(2025, 1, 31, 11_392_000_000, 41_755_000_000),
            _sheet(2025, 10, 31, 11_139_000_000, 35_123_000_000),
        ]
        discard_implausible_debt_collapses(sheets)
        assert [sheet.total_debt for sheet in sheets] == [
            11_424_000_000, 11_392_000_000, 11_139_000_000,
        ]

    def test_the_earliest_quarter_has_nothing_to_compare_against(self):
        sheets = [_sheet(2026, 7, 31, 2_455_000_000, 71_242_000_000)]
        discard_implausible_debt_collapses(sheets)
        assert sheets[0].total_debt == 2_455_000_000


@pytest.mark.django_db
class TestRepairCommand:
    def _earnings(self, ticker, year, net_income, revenue):
        return QuarterlyEarnings.objects.create(
            ticker=ticker, end_date=date(year, 12, 31),
            net_income=net_income, revenue=revenue,
        )

    def test_nulls_zero_earnings_that_sit_beside_revenue(self):
        from django.core.management import call_command
        row = self._earnings("BBAS3", 2019, 0, 31_678_067_000)
        call_command("repair_zero_net_income")
        row.refresh_from_db()
        assert row.net_income is None

    def test_leaves_a_genuine_zero_alone(self):
        from django.core.management import call_command
        row = self._earnings("SHELL3", 2019, 0, 0)
        call_command("repair_zero_net_income")
        row.refresh_from_db()
        assert row.net_income == 0

    def test_leaves_real_figures_alone(self):
        from django.core.management import call_command
        row = self._earnings("PETR4", 2024, 9_000_000, 50_000_000)
        call_command("repair_zero_net_income")
        row.refresh_from_db()
        assert row.net_income == 9_000_000

    def test_dry_run_changes_nothing(self):
        from django.core.management import call_command
        row = self._earnings("BBAS3", 2019, 0, 31_678_067_000)
        call_command("repair_zero_net_income", "--dry-run")
        row.refresh_from_db()
        assert row.net_income == 0

    def test_invalidates_derived_caches_for_touched_tickers(self):
        from django.core.cache import cache
        from django.core.management import call_command
        from quotes.derived_data import pe10_cache_key

        self._earnings("BBAS3", 2019, 0, 31_678_067_000)
        cache.set(pe10_cache_key("BBAS3"), {"stale": True}, 300)
        call_command("repair_zero_net_income")
        assert cache.get(pe10_cache_key("BBAS3")) is None


@pytest.mark.django_db
class TestIngestionAppliesTheRule:
    """Both providers must apply it, or the repair command fights the sync."""

    def test_brapi_stores_none_for_a_zero_beside_revenue(self, monkeypatch):
        from quotes import brapi
        monkeypatch.setattr(brapi, "fetch_income_statements", lambda ticker: brapi.IncomeStatements(
            quarterly=[{"endDate": "2019-12-31", "netIncome": 0, "totalRevenue": 27_894_387_000}],
            annual=[],
        ))
        brapi.sync_earnings("BBAS3")
        assert QuarterlyEarnings.objects.get(ticker="BBAS3").net_income is None

    def test_brapi_keeps_a_real_figure(self, monkeypatch):
        from quotes import brapi
        monkeypatch.setattr(brapi, "fetch_income_statements", lambda ticker: brapi.IncomeStatements(
            quarterly=[{"endDate": "2024-12-31", "netIncome": 5_140_255_000, "totalRevenue": 71_704_820_000}],
            annual=[],
        ))
        brapi.sync_earnings("BBAS3")
        assert QuarterlyEarnings.objects.get(ticker="BBAS3").net_income == 5_140_255_000

    def test_fmp_stores_none_for_a_zero_beside_revenue(self, monkeypatch):
        from quotes import fmp
        monkeypatch.setattr(fmp, "fetch_income_statements", lambda ticker: [
            {"date": "2019-12-31", "netIncome": 0, "revenue": 27_894_387_000},
        ])
        fmp.sync_earnings("AAPL")
        assert QuarterlyEarnings.objects.get(ticker="AAPL").net_income is None


@pytest.mark.django_db
class TestProvidersDiscardCollapsedDebtAtIngestion:
    """Caught at the door, so the repair command has nothing to fight."""

    FMP_QUARTERS = [
        {"date": "2026-07-31", "totalDebt": 2_455_000_000,
         "totalLiabilities": 71_242_000_000, "totalStockholdersEquity": 38_378_000_000},
        {"date": "2026-04-30", "totalDebt": 41_884_000_000,
         "totalLiabilities": 72_445_000_000, "totalStockholdersEquity": 34_235_000_000},
        {"date": "2026-01-31", "totalDebt": 17_176_000_000,
         "totalLiabilities": 53_163_000_000, "totalStockholdersEquity": 59_142_000_000},
    ]

    def test_fmp_stores_none_for_a_collapsed_quarter(self, monkeypatch):
        from quotes import fmp
        monkeypatch.setattr(fmp, "fetch_balance_sheets", lambda ticker: self.FMP_QUARTERS)
        fmp.sync_balance_sheets("CRM")

        assert BalanceSheet.objects.get(
            ticker="CRM", end_date=date(2026, 7, 31),
        ).total_debt is None

    def test_fmp_keeps_the_quarters_around_it(self, monkeypatch):
        from quotes import fmp
        monkeypatch.setattr(fmp, "fetch_balance_sheets", lambda ticker: self.FMP_QUARTERS)
        fmp.sync_balance_sheets("CRM")

        assert BalanceSheet.objects.get(
            ticker="CRM", end_date=date(2026, 4, 30),
        ).total_debt == 41_884_000_000
        assert BalanceSheet.objects.get(
            ticker="CRM", end_date=date(2026, 1, 31),
        ).total_debt == 17_176_000_000

    def test_brapi_stores_none_for_a_collapsed_quarter(self, monkeypatch):
        from quotes import brapi
        monkeypatch.setattr(brapi, "fetch_balance_sheets", lambda ticker: [
            {"endDate": "2026-03-31", "loansAndFinancing": 40_000_000_000,
             "currentLiabilities": 30_000_000_000, "nonCurrentLiabilities": 40_000_000_000},
            {"endDate": "2026-06-30", "loansAndFinancing": 0,
             "currentLiabilities": 30_000_000_000, "nonCurrentLiabilities": 39_000_000_000},
        ])
        monkeypatch.setattr(brapi, "_fetch_annual_lease_data", lambda ticker: {})
        monkeypatch.setattr(brapi, "fetch_financial_data", lambda ticker: {})
        brapi.sync_balance_sheets("PETR4")

        assert BalanceSheet.objects.get(
            ticker="PETR4", end_date=date(2026, 6, 30),
        ).total_debt is None
        assert BalanceSheet.objects.get(
            ticker="PETR4", end_date=date(2026, 3, 31),
        ).total_debt == 40_000_000_000


@pytest.mark.django_db
class TestRepairCollapsedDebtCommand:
    def _sheets(self, ticker, quarters):
        for end_date, debt, liabilities in quarters:
            BalanceSheet.objects.create(
                ticker=ticker, end_date=end_date,
                total_debt=debt, total_liabilities=liabilities,
                stockholders_equity=38_378_000_000,
            )

    CRM_QUARTERS = [
        (date(2026, 4, 30), 41_884_000_000, 72_445_000_000),
        (date(2026, 7, 31), 2_455_000_000, 71_242_000_000),
    ]

    def test_nulls_debt_that_vanished_without_the_liabilities_to_match(self):
        from django.core.management import call_command
        self._sheets("CRM", self.CRM_QUARTERS)
        call_command("repair_collapsed_debt")

        assert BalanceSheet.objects.get(
            ticker="CRM", end_date=date(2026, 7, 31),
        ).total_debt is None

    def test_leaves_the_trusted_quarter_alone(self):
        from django.core.management import call_command
        self._sheets("CRM", self.CRM_QUARTERS)
        call_command("repair_collapsed_debt")

        assert BalanceSheet.objects.get(
            ticker="CRM", end_date=date(2026, 4, 30),
        ).total_debt == 41_884_000_000

    def test_leaves_a_confirmed_repayment_alone(self):
        from django.core.management import call_command
        self._sheets("REPAY", [
            (date(2026, 3, 31), 40_000_000_000, 70_000_000_000),
            (date(2026, 6, 30), 1_000_000_000, 31_000_000_000),
        ])
        call_command("repair_collapsed_debt")

        assert BalanceSheet.objects.get(
            ticker="REPAY", end_date=date(2026, 6, 30),
        ).total_debt == 1_000_000_000

    def test_dry_run_changes_nothing(self):
        from django.core.management import call_command
        self._sheets("CRM", self.CRM_QUARTERS)
        call_command("repair_collapsed_debt", "--dry-run")

        assert BalanceSheet.objects.get(
            ticker="CRM", end_date=date(2026, 7, 31),
        ).total_debt == 2_455_000_000

    def test_invalidates_derived_caches_for_touched_tickers(self):
        from django.core.cache import cache
        from django.core.management import call_command
        from quotes.derived_data import pe10_cache_key

        self._sheets("CRM", self.CRM_QUARTERS)
        cache.set(pe10_cache_key("CRM"), {"stale": True}, 300)
        call_command("repair_collapsed_debt")

        assert cache.get(pe10_cache_key("CRM")) is None

    def test_ticker_flag_leaves_other_companies_alone(self):
        from django.core.management import call_command
        self._sheets("CRM", self.CRM_QUARTERS)
        self._sheets("HMC", [
            (date(2026, 3, 31), 13_538_327_425_000, 21_453_860_162_000),
            (date(2026, 6, 30), 0, 21_361_213_000_000),
        ])
        call_command("repair_collapsed_debt", "--ticker", "CRM")

        assert BalanceSheet.objects.get(
            ticker="CRM", end_date=date(2026, 7, 31),
        ).total_debt is None
        assert BalanceSheet.objects.get(
            ticker="HMC", end_date=date(2026, 6, 30),
        ).total_debt == 0

    def test_counts_the_quarters_that_drive_live_ratios(self):
        from django.core.management import call_command
        from io import StringIO

        self._sheets("CRM", self.CRM_QUARTERS)
        output = StringIO()
        call_command("repair_collapsed_debt", "--dry-run", stdout=output)

        assert "1 of them the company's latest quarter" in output.getvalue()

    def test_latest_only_repairs_the_quarter_driving_live_ratios(self):
        # The live debt/equity, debt/EARN10 and debt/FCF10 all read the most
        # recent quarter. Repairing just those fixes what a visitor sees
        # without rewriting a decade of history in one transaction.
        from django.core.management import call_command
        self._sheets("CRM", [
            (date(2025, 10, 31), 41_884_000_000, 72_445_000_000),
            (date(2026, 1, 31), 2_400_000_000, 71_900_000_000),
            (date(2026, 4, 30), 2_455_000_000, 71_242_000_000),
        ])
        call_command("repair_collapsed_debt", "--latest-only")

        by_end_date = {
            sheet.end_date: sheet.total_debt
            for sheet in BalanceSheet.objects.filter(ticker="CRM")
        }
        assert by_end_date[date(2026, 4, 30)] is None
        assert by_end_date[date(2026, 1, 31)] == 2_400_000_000  # history untouched

    def test_latest_only_leaves_a_company_whose_latest_quarter_is_sound(self):
        from django.core.management import call_command
        self._sheets("SBUX", [
            (date(2025, 9, 28), 26_611_000_000, 40_108_000_000),
            (date(2025, 12, 28), 2_000_000_000, 40_609_000_000),
            (date(2026, 3, 29), 24_391_000_000, 39_015_000_000),
        ])
        call_command("repair_collapsed_debt", "--latest-only")

        assert BalanceSheet.objects.get(
            ticker="SBUX", end_date=date(2026, 3, 29),
        ).total_debt == 24_391_000_000

    def test_limit_takes_a_tranche_and_successive_runs_converge(self):
        # A 31,000-row mutation is worth taking in bites. Each run nulls what
        # it takes; a nulled quarter no longer looks like a collapse, so the
        # next run picks up where the last stopped rather than redoing it.
        from django.core.management import call_command
        self._sheets("AAA", [
            (date(2025, 3, 31), 40_000_000_000, 70_000_000_000),
            (date(2025, 6, 30), 1_000_000_000, 69_500_000_000),
        ])
        self._sheets("BBB", [
            (date(2025, 3, 31), 40_000_000_000, 70_000_000_000),
            (date(2025, 6, 30), 1_000_000_000, 69_500_000_000),
        ])

        call_command("repair_collapsed_debt", "--limit", "1")
        nulled_after_first = BalanceSheet.objects.filter(total_debt__isnull=True).count()
        assert nulled_after_first == 1

        call_command("repair_collapsed_debt", "--limit", "1")
        assert BalanceSheet.objects.filter(total_debt__isnull=True).count() == 2
