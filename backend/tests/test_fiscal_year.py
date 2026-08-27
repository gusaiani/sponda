"""Tests for bucketing statements by fiscal year rather than calendar year.

Roughly a quarter of the companies covered close their books somewhere other
than 31 December. Salesforce closes on 31 January, Starbucks in late
September, Microsoft in June. Grouping their quarters by the calendar year
the quarter happens to end in produces two wrongs at once: the audited
year-end balance sheet is overwritten by a later quarter and never appears,
and the "annual" income is a rolling four quarters offset from the year the
company actually reported.

Starbucks is the plain case. Its FY2025 closed on 2025-09-28 with $26.6bn of
debt. The 2025 row showed 2025-12-28, the first quarter of FY2026, at
$33.5bn: a 26% overstatement on a row labelled with a year it does not
describe.

FMP hands us `fiscalYear` on all three statement endpoints. These tests hold
us to storing it and using it.
"""
from datetime import date
from decimal import Decimal

import pytest

from quotes.fiscal_year import fiscal_year_of, fiscal_year_from_year_end_month
from quotes.models import BalanceSheet, QuarterlyCashFlow, QuarterlyEarnings


class TestFiscalYearOf:
    def test_prefers_the_figure_the_provider_reported(self):
        quarter = QuarterlyEarnings(end_date=date(2026, 7, 31), fiscal_year=2027)
        assert fiscal_year_of(quarter) == 2027

    def test_falls_back_to_the_calendar_year(self):
        # BRAPI and CVM do not report a fiscal year, and do not need to:
        # Brazilian filers close on 31 December, so the two coincide.
        quarter = QuarterlyEarnings(end_date=date(2025, 6, 30), fiscal_year=None)
        assert fiscal_year_of(quarter) == 2025


class TestFiscalYearFromYearEndMonth:
    """Deriving the label for rows stored before the field existed."""

    def test_a_december_filer_is_its_own_calendar_year(self):
        assert fiscal_year_from_year_end_month(date(2025, 6, 30), 12) == 2025
        assert fiscal_year_from_year_end_month(date(2025, 12, 31), 12) == 2025

    def test_a_january_filer_rolls_into_the_next_year(self):
        # Salesforce: FY2026 closed 2026-01-31; the quarter ending
        # 2026-04-30 is the first of FY2027.
        assert fiscal_year_from_year_end_month(date(2026, 1, 31), 1) == 2026
        assert fiscal_year_from_year_end_month(date(2026, 4, 30), 1) == 2027
        assert fiscal_year_from_year_end_month(date(2027, 1, 31), 1) == 2027

    def test_a_september_filer_rolls_after_its_close(self):
        # Starbucks: FY2025 closed in September 2025, so the December
        # quarter opens FY2026.
        assert fiscal_year_from_year_end_month(date(2025, 9, 28), 9) == 2025
        assert fiscal_year_from_year_end_month(date(2025, 12, 28), 9) == 2026
        assert fiscal_year_from_year_end_month(date(2026, 3, 29), 9) == 2026

    def test_a_june_filer_rolls_after_its_close(self):
        assert fiscal_year_from_year_end_month(date(2026, 6, 30), 6) == 2026
        assert fiscal_year_from_year_end_month(date(2026, 9, 30), 6) == 2027


@pytest.mark.django_db
class TestFmpStoresTheFiscalYear:
    def test_balance_sheets(self, monkeypatch):
        from quotes import fmp
        monkeypatch.setattr(fmp, "fetch_balance_sheets", lambda ticker: [
            {"date": "2026-07-31", "fiscalYear": "2027", "period": "Q2",
             "totalDebt": 41_000_000_000, "totalLiabilities": 71_242_000_000},
        ])
        fmp.sync_balance_sheets("CRM")
        assert BalanceSheet.objects.get(ticker="CRM").fiscal_year == 2027

    def test_earnings(self, monkeypatch):
        from quotes import fmp
        monkeypatch.setattr(fmp, "fetch_income_statements", lambda ticker: [
            {"date": "2026-07-31", "fiscalYear": "2027", "period": "Q2",
             "netIncome": 1_500_000_000, "revenue": 10_000_000_000},
        ])
        fmp.sync_earnings("CRM")
        assert QuarterlyEarnings.objects.get(ticker="CRM").fiscal_year == 2027

    def test_cash_flows(self, monkeypatch):
        from quotes import fmp
        monkeypatch.setattr(fmp, "fetch_cash_flow_statements", lambda ticker: [
            {"date": "2026-07-31", "fiscalYear": "2027", "period": "Q2",
             "operatingCashFlow": 2_000_000_000, "freeCashFlow": 1_800_000_000},
        ])
        fmp.sync_cash_flows("CRM")
        assert QuarterlyCashFlow.objects.get(ticker="CRM").fiscal_year == 2027

    def test_a_payload_without_a_fiscal_year_stores_none(self, monkeypatch):
        from quotes import fmp
        monkeypatch.setattr(fmp, "fetch_balance_sheets", lambda ticker: [
            {"date": "2025-12-31", "totalDebt": 1, "totalLiabilities": 2},
        ])
        fmp.sync_balance_sheets("XYZ")
        assert BalanceSheet.objects.get(ticker="XYZ").fiscal_year is None


# Starbucks closes in late September. Its FY2025 ended 2025-09-28 with
# $26.6bn of debt; the quarter ending 2025-12-28 opens FY2026 at $33.5bn.
# Grouped by calendar year, the 2025 row showed the December figure.
SBUX_QUARTERS = [
    (date(2025, 3, 30), 2025, 26_009_000_000),
    (date(2025, 6, 29), 2025, 27_886_000_000),
    (date(2025, 9, 28), 2025, 26_611_000_000),
    (date(2025, 12, 28), 2026, 33_518_000_000),
    (date(2026, 3, 29), 2026, 24_391_000_000),
]


def _seed_starbucks_balance_sheets():
    BalanceSheet.objects.bulk_create([
        BalanceSheet(
            ticker="SBUX", end_date=end_date, fiscal_year=fiscal_year,
            total_debt=total_debt, total_liabilities=40_000_000_000,
            stockholders_equity=-8_000_000_000,
        )
        for end_date, fiscal_year, total_debt in SBUX_QUARTERS
    ])


def _seed_starbucks_earnings():
    QuarterlyEarnings.objects.bulk_create([
        QuarterlyEarnings(
            ticker="SBUX", end_date=end_date, fiscal_year=fiscal_year,
            net_income=500_000_000, revenue=9_000_000_000,
        )
        for end_date, fiscal_year, _ in SBUX_QUARTERS
    ])


@pytest.mark.django_db
class TestFundamentalsGroupByFiscalYear:
    def test_the_audited_year_end_is_the_years_balance_sheet(self):
        from quotes.fundamentals import compute_fundamentals
        _seed_starbucks_balance_sheets()

        rows = compute_fundamentals("SBUX", market_cap=None, current_price=None)
        fiscal_2025 = next(row for row in rows if row["year"] == 2025)

        assert fiscal_2025["balanceSheetDate"] == "2025-09-28"
        assert fiscal_2025["totalDebt"] == 26_611_000_000

    def test_the_first_quarter_of_the_next_year_does_not_leak_backwards(self):
        from quotes.fundamentals import compute_fundamentals
        _seed_starbucks_balance_sheets()

        rows = compute_fundamentals("SBUX", market_cap=None, current_price=None)
        fiscal_2026 = next(row for row in rows if row["year"] == 2026)

        assert fiscal_2026["balanceSheetDate"] == "2026-03-29"

    def test_a_year_counts_only_the_quarters_the_filer_put_in_it(self):
        from quotes.fundamentals import compute_fundamentals
        _seed_starbucks_earnings()

        rows = compute_fundamentals("SBUX", market_cap=None, current_price=None)
        by_year = {row["year"]: row for row in rows}

        assert by_year[2025]["quarters"] == 3   # Q2, Q3, Q4 of FY2025
        assert by_year[2026]["quarters"] == 2   # Q1, Q2 of FY2026
        assert by_year[2025]["netIncome"] == 1_500_000_000

    def test_a_december_filer_is_unaffected(self):
        from quotes.fundamentals import compute_fundamentals
        BalanceSheet.objects.bulk_create([
            BalanceSheet(ticker="PETR4", end_date=date(2025, month, day),
                         total_debt=100, total_liabilities=200,
                         stockholders_equity=300)
            for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]
        ])

        rows = compute_fundamentals("PETR4", market_cap=None, current_price=None)
        assert rows[0]["year"] == 2025
        assert rows[0]["balanceSheetDate"] == "2025-12-31"


@pytest.mark.django_db
class TestAnnualEarningsGroupByFiscalYear:
    def test_the_windows_behind_pe10_use_the_same_year_as_the_table(self):
        # The Fundamentos table joins its rows to `pe10CalculationDetails`
        # by year. If one side moved to fiscal years and the other did not,
        # every trailing ratio on an off-calendar filer would go blank.
        from quotes.pe10 import get_annual_earnings
        _seed_starbucks_earnings()

        annual = {entry["year"]: entry for entry in get_annual_earnings("SBUX")}

        assert annual[2025]["quarters"] == 3
        assert annual[2026]["quarters"] == 2

    def test_annual_fcf_groups_the_same_way(self):
        from quotes.pfcf10 import get_annual_fcf
        QuarterlyCashFlow.objects.bulk_create([
            QuarterlyCashFlow(
                ticker="SBUX", end_date=end_date, fiscal_year=fiscal_year,
                operating_cash_flow=1_000_000_000, free_cash_flow=800_000_000,
            )
            for end_date, fiscal_year, _ in SBUX_QUARTERS
        ])

        annual = {entry["year"]: entry for entry in get_annual_fcf("SBUX")}
        assert annual[2025]["quarters"] == 3
        assert annual[2026]["quarters"] == 2


@pytest.mark.django_db
class TestInflationIsKeyedOnRealTime:
    def test_a_fiscal_label_never_asks_for_a_year_that_has_not_happened(self):
        """The CPI series is calendar time; the fiscal label is not.

        Salesforce's fiscal 2027 was already open in mid-2026. Looking the
        adjustment factor up under 2027 finds nothing and silently returns
        1, which is a different number from the one the quarter deserves.
        The factor has to be resolved from when the quarter actually ended.
        """
        from quotes.fundamentals import compute_fundamentals
        from quotes.models import USCPIIndex

        USCPIIndex.objects.bulk_create([
            USCPIIndex(date=date(year, 12, 1), annual_rate=Decimal("10"))
            for year in (2024, 2025, 2026)
        ])
        BalanceSheet.objects.bulk_create([
            # Fiscal 2026 closed 2026-01-31; fiscal 2027 is open.
            BalanceSheet(ticker="CRM", end_date=date(2025, 1, 31), fiscal_year=2025,
                         total_debt=1_000, total_liabilities=2_000,
                         stockholders_equity=3_000),
            BalanceSheet(ticker="CRM", end_date=date(2026, 1, 31), fiscal_year=2026,
                         total_debt=1_000, total_liabilities=2_000,
                         stockholders_equity=3_000),
            BalanceSheet(ticker="CRM", end_date=date(2026, 7, 31), fiscal_year=2027,
                         total_debt=1_000, total_liabilities=2_000,
                         stockholders_equity=3_000),
        ])

        rows = {row["year"]: row for row in
                compute_fundamentals("CRM", market_cap=None, current_price=None)}

        # Fiscal 2027 and fiscal 2026 both ended their reported quarter in
        # calendar 2026, so both sit at the present day's purchasing power.
        assert rows[2027]["ipcaFactor"] == pytest.approx(1.0)
        assert rows[2026]["ipcaFactor"] == pytest.approx(1.0)
        # Fiscal 2025 closed in January 2025, one CPI year back.
        assert rows[2025]["ipcaFactor"] == pytest.approx(1.1)


@pytest.mark.django_db
class TestMultiplesHistoryAgreesWithTheTable:
    """The chart and the Fundamentos table must mean the same by "2026".

    They are two views of one company's history. Once the table moved to
    fiscal years, a chart still plotting calendar years would put a
    December price against a year that closed in September, and label two
    different periods with the same number on two tabs.
    """

    def _close_at(self, target: date) -> float:
        """The generated series' last close at or before `target`."""
        last = None
        for point_date, price in self._series(date(2026, 6, 30)):
            if point_date <= target:
                last = price
        assert last is not None
        return last

    def _series(self, last_close: date) -> list[tuple[date, float]]:
        points = []
        current = date(2024, 1, 31)
        price = 50.0
        while current <= last_close:
            points.append((current, price))
            price += 1.0
            month = current.month + 1
            year = current.year + (month - 1) // 12
            month = (month - 1) % 12 + 1
            current = date(year, month, 28)
        return points

    def _prices_through(self, last_close: date) -> list[dict]:
        from datetime import datetime as datetime_type
        from datetime import timezone as timezone_type

        return [
            {
                "date": int(datetime_type(
                    point_date.year, point_date.month, point_date.day,
                    tzinfo=timezone_type.utc,
                ).timestamp()),
                "adjustedClose": price,
            }
            for point_date, price in self._series(last_close)
        ]

    def test_the_chart_plots_the_years_the_filer_reported(self, monkeypatch):
        from quotes import multiples_history

        _seed_starbucks_earnings()
        monkeypatch.setattr(
            multiples_history, "_resolve_listing_currency", lambda ticker: "USD",
        )
        monkeypatch.setattr(
            multiples_history, "_resolve_reported_currency", lambda ticker: "USD",
        )

        result = multiples_history.compute_multiples_history(
            "SBUX",
            market_cap=1_000_000_000,
            current_price=100.0,
            historical_prices=self._prices_through(date(2026, 6, 30)),
        )

        # Fiscal 2025 closed on 2025-09-28. It must be priced at that day's
        # close, not at the following 31 December, which is three months of
        # price movement away and belongs to the next fiscal year.
        by_year = {point["year"]: point["value"] for point in result["multiples"]["pl"]}
        shares = 1_000_000_000 / 100.0
        fiscal_2025_earnings = 3 * 500_000_000

        def multiple_at(price: float) -> float:
            return round((price * shares) / fiscal_2025_earnings, 2)

        assert by_year[2025] == multiple_at(self._close_at(date(2025, 9, 28)))
        assert by_year[2025] != multiple_at(self._close_at(date(2025, 12, 31)))


@pytest.mark.django_db
class TestBackfillCommand:
    """Rows stored before the field existed carry no fiscal year.

    One annual call per ticker says which month the company closes in, and
    every row it already has follows from that. Re-pulling twenty years of
    quarterly statements for the whole universe, three endpoints deep, would
    cost seventy thousand calls to learn one number per company.
    """

    def _crm_quarters(self):
        BalanceSheet.objects.bulk_create([
            BalanceSheet(ticker="CRM", end_date=end_date,
                         total_debt=1, total_liabilities=2, stockholders_equity=3)
            for end_date in (date(2026, 1, 31), date(2026, 4, 30), date(2026, 7, 31))
        ])

    def test_derives_every_row_from_the_companys_closing_month(self, monkeypatch):
        from django.core.management import call_command
        from quotes.management.commands import backfill_fiscal_year

        self._crm_quarters()
        monkeypatch.setattr(
            backfill_fiscal_year, "fetch_year_end_month",
            lambda ticker: 1,  # Salesforce closes in January
        )
        call_command("backfill_fiscal_year", "--ticker", "CRM")

        by_end_date = {
            sheet.end_date: sheet.fiscal_year
            for sheet in BalanceSheet.objects.filter(ticker="CRM")
        }
        assert by_end_date[date(2026, 1, 31)] == 2026
        assert by_end_date[date(2026, 4, 30)] == 2027
        assert by_end_date[date(2026, 7, 31)] == 2027

    def test_leaves_a_row_the_provider_already_labelled_alone(self, monkeypatch):
        from django.core.management import call_command
        from quotes.management.commands import backfill_fiscal_year

        BalanceSheet.objects.create(
            ticker="CRM", end_date=date(2026, 7, 31), fiscal_year=2027,
            total_debt=1, total_liabilities=2, stockholders_equity=3,
        )
        monkeypatch.setattr(
            backfill_fiscal_year, "fetch_year_end_month", lambda ticker: 12,
        )
        call_command("backfill_fiscal_year", "--ticker", "CRM")

        assert BalanceSheet.objects.get(ticker="CRM").fiscal_year == 2027

    def test_skips_a_company_whose_closing_month_cannot_be_learned(self, monkeypatch):
        from django.core.management import call_command
        from quotes.management.commands import backfill_fiscal_year

        self._crm_quarters()
        monkeypatch.setattr(
            backfill_fiscal_year, "fetch_year_end_month", lambda ticker: None,
        )
        call_command("backfill_fiscal_year", "--ticker", "CRM")

        assert not BalanceSheet.objects.filter(
            ticker="CRM", fiscal_year__isnull=False,
        ).exists()

    def test_dry_run_writes_nothing(self, monkeypatch):
        from django.core.management import call_command
        from quotes.management.commands import backfill_fiscal_year

        self._crm_quarters()
        monkeypatch.setattr(
            backfill_fiscal_year, "fetch_year_end_month", lambda ticker: 1,
        )
        call_command("backfill_fiscal_year", "--ticker", "CRM", "--dry-run")

        assert not BalanceSheet.objects.filter(
            ticker="CRM", fiscal_year__isnull=False,
        ).exists()

    def test_labels_earnings_and_cash_flows_too(self, monkeypatch):
        from django.core.management import call_command
        from quotes.management.commands import backfill_fiscal_year

        QuarterlyEarnings.objects.create(
            ticker="CRM", end_date=date(2026, 4, 30), net_income=1, revenue=2,
        )
        QuarterlyCashFlow.objects.create(
            ticker="CRM", end_date=date(2026, 4, 30), operating_cash_flow=1,
        )
        monkeypatch.setattr(
            backfill_fiscal_year, "fetch_year_end_month", lambda ticker: 1,
        )
        call_command("backfill_fiscal_year", "--ticker", "CRM")

        assert QuarterlyEarnings.objects.get(ticker="CRM").fiscal_year == 2027
        assert QuarterlyCashFlow.objects.get(ticker="CRM").fiscal_year == 2027


@pytest.mark.django_db
class TestFetchYearEndMonth:
    """One annual statement is the whole question the backfill has to ask."""

    def test_reads_the_closing_month_off_the_annual_statement(self, monkeypatch):
        from quotes import fmp
        from quotes.management.commands import backfill_fiscal_year

        monkeypatch.setattr(
            fmp, "_get", lambda endpoint, params=None: [{"date": "2026-01-31"}],
        )
        assert backfill_fiscal_year.fetch_year_end_month("CRM") == 1

    def test_a_provider_failure_is_not_a_missing_closing_month(self):
        """The distinction the first production run got wrong.

        Pushed at 2,000 companies with no pacing, FMP's circuit breaker
        opened and every call for the next minute raised. Treating that as
        "this company has no annual statement" skipped 1,611 of 2,000
        companies, American Airlines among them, and the cursor advanced
        past every one of them. A provider being unavailable says nothing
        about the company.
        """
        from quotes import fmp
        from quotes.management.commands import backfill_fiscal_year

        def _raise(endpoint, params=None):
            raise fmp.FMPError("circuit open")

        with pytest.raises(backfill_fiscal_year.ProviderUnavailable):
            backfill_fiscal_year.fetch_year_end_month("CRM", _get=_raise)

    def test_a_company_with_no_annual_statement_is_a_genuine_skip(self, monkeypatch):
        # An empty answer from a healthy provider is a fact about the
        # company, and the only thing that earns a permanent skip.
        from quotes import fmp
        from quotes.management.commands import backfill_fiscal_year

        monkeypatch.setattr(fmp, "_get", lambda endpoint, params=None: [])
        assert backfill_fiscal_year.fetch_year_end_month("NEWCO") is None


@pytest.mark.django_db
class TestBackfillChunking:
    """25,000 companies is one FMP call each, so it has to run in tranches.

    ``--limit`` alone is not enough. A company whose closing month cannot be
    learned stays unlabelled forever, so it sits at the front of the queue
    and burns a call on every subsequent run. The cursor is what lets a
    tranche move past it.
    """

    def _sheets(self, *tickers):
        BalanceSheet.objects.bulk_create([
            BalanceSheet(ticker=ticker, end_date=date(2026, 4, 30),
                         total_debt=1, total_liabilities=2, stockholders_equity=3)
            for ticker in tickers
        ])

    def test_limit_takes_the_first_tranche_in_ticker_order(self, monkeypatch):
        from django.core.management import call_command
        from quotes.management.commands import backfill_fiscal_year

        self._sheets("AAA", "BBB", "CCC")
        monkeypatch.setattr(
            backfill_fiscal_year, "fetch_year_end_month", lambda ticker: 1,
        )
        call_command("backfill_fiscal_year", "--limit", "2")

        labelled = set(
            BalanceSheet.objects
            .filter(fiscal_year__isnull=False)
            .values_list("ticker", flat=True)
        )
        assert labelled == {"AAA", "BBB"}

    def test_after_resumes_past_a_company_that_can_never_be_labelled(self, monkeypatch):
        from django.core.management import call_command
        from quotes.management.commands import backfill_fiscal_year

        self._sheets("AAA", "BBB")
        # AAA can never be learned; without a cursor it would head the queue
        # on every run and cost a call each time.
        monkeypatch.setattr(
            backfill_fiscal_year, "fetch_year_end_month",
            lambda ticker: None if ticker == "AAA" else 1,
        )
        call_command("backfill_fiscal_year", "--after", "AAA")

        assert BalanceSheet.objects.get(ticker="BBB").fiscal_year == 2027
        assert BalanceSheet.objects.get(ticker="AAA").fiscal_year is None

    def test_reports_the_cursor_to_resume_from(self, monkeypatch):
        from io import StringIO

        from django.core.management import call_command
        from quotes.management.commands import backfill_fiscal_year

        self._sheets("AAA", "BBB", "CCC")
        monkeypatch.setattr(
            backfill_fiscal_year, "fetch_year_end_month", lambda ticker: 1,
        )
        output = StringIO()
        call_command("backfill_fiscal_year", "--limit", "2", stdout=output)

        assert "--after BBB" in output.getvalue()

    def test_says_nothing_to_resume_from_when_the_queue_is_drained(self, monkeypatch):
        from io import StringIO

        from django.core.management import call_command
        from quotes.management.commands import backfill_fiscal_year

        self._sheets("AAA")
        monkeypatch.setattr(
            backfill_fiscal_year, "fetch_year_end_month", lambda ticker: 1,
        )
        output = StringIO()
        call_command("backfill_fiscal_year", "--limit", "5", stdout=output)

        assert "--after" not in output.getvalue()


@pytest.mark.django_db
class TestBackfillSurvivesAProviderOutage:
    """A rate limit must cost a pause, never a company.

    The first production run lost 1,611 companies to FMP's circuit breaker
    because a transient failure looked exactly like a missing statement, and
    the resume cursor then stepped past all of them. These hold the command
    to retrying, and to stopping rather than stepping past what it could not
    reach.
    """

    def _sheets(self, *tickers):
        BalanceSheet.objects.bulk_create([
            BalanceSheet(ticker=ticker, end_date=date(2026, 4, 30),
                         total_debt=1, total_liabilities=2, stockholders_equity=3)
            for ticker in tickers
        ])

    def test_retries_a_transient_failure_and_carries_on(self, monkeypatch):
        from django.core.management import call_command
        from quotes.management.commands import backfill_fiscal_year

        self._sheets("AAA")
        attempts = {"count": 0}

        def _flaky(ticker):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise backfill_fiscal_year.ProviderUnavailable("circuit open")
            return 1

        monkeypatch.setattr(backfill_fiscal_year, "fetch_year_end_month", _flaky)
        monkeypatch.setattr(backfill_fiscal_year.time, "sleep", lambda seconds: None)
        call_command("backfill_fiscal_year")

        assert attempts["count"] == 2
        assert BalanceSheet.objects.get(ticker="AAA").fiscal_year == 2027

    def test_stops_rather_than_stepping_past_what_it_could_not_reach(self, monkeypatch):
        from io import StringIO

        from django.core.management import call_command
        from quotes.management.commands import backfill_fiscal_year

        self._sheets("AAA", "BBB", "CCC")

        def _down_after_the_first(ticker):
            if ticker == "AAA":
                return 1
            raise backfill_fiscal_year.ProviderUnavailable("circuit open")

        monkeypatch.setattr(
            backfill_fiscal_year, "fetch_year_end_month", _down_after_the_first,
        )
        monkeypatch.setattr(backfill_fiscal_year.time, "sleep", lambda seconds: None)
        output = StringIO()
        call_command("backfill_fiscal_year", stdout=output)

        assert BalanceSheet.objects.get(ticker="AAA").fiscal_year == 2027
        # BBB was unreachable, not unlabellable. It must stay in the queue.
        assert BalanceSheet.objects.get(ticker="BBB").fiscal_year is None
        assert BalanceSheet.objects.get(ticker="CCC").fiscal_year is None
        assert "--after AAA" in output.getvalue()

    def test_says_plainly_that_it_stopped_on_the_provider(self, monkeypatch):
        from io import StringIO

        from django.core.management import call_command
        from quotes.management.commands import backfill_fiscal_year

        self._sheets("AAA")

        def _down(ticker):
            raise backfill_fiscal_year.ProviderUnavailable("circuit open")

        monkeypatch.setattr(backfill_fiscal_year, "fetch_year_end_month", _down)
        monkeypatch.setattr(backfill_fiscal_year.time, "sleep", lambda seconds: None)
        output = StringIO()
        call_command("backfill_fiscal_year", stdout=output)

        assert "provider unavailable" in output.getvalue().lower()

    def test_a_genuinely_unlabellable_company_is_still_only_skipped(self, monkeypatch):
        from django.core.management import call_command
        from quotes.management.commands import backfill_fiscal_year

        self._sheets("AAA", "BBB")
        monkeypatch.setattr(
            backfill_fiscal_year, "fetch_year_end_month",
            lambda ticker: None if ticker == "AAA" else 1,
        )
        monkeypatch.setattr(backfill_fiscal_year.time, "sleep", lambda seconds: None)
        call_command("backfill_fiscal_year")

        assert BalanceSheet.objects.get(ticker="AAA").fiscal_year is None
        assert BalanceSheet.objects.get(ticker="BBB").fiscal_year == 2027

    def test_paces_its_calls_so_the_breaker_stays_shut(self, monkeypatch):
        from django.core.management import call_command
        from quotes.management.commands import backfill_fiscal_year

        self._sheets("AAA", "BBB", "CCC")
        pauses = []
        monkeypatch.setattr(
            backfill_fiscal_year, "fetch_year_end_month", lambda ticker: 1,
        )
        monkeypatch.setattr(
            backfill_fiscal_year.time, "sleep", lambda seconds: pauses.append(seconds),
        )
        call_command("backfill_fiscal_year", "--pause", "0.5")

        assert pauses == [0.5, 0.5, 0.5]
