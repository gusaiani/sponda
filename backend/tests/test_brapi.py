"""Tests for BRAPI client with mocked API responses."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from quotes.brapi import (
    BRAPIError,
    IncomeStatements,
    _get,
    fetch_financial_data,
    fetch_historical_prices,
    fetch_income_statements,
    fetch_quote,
    sync_balance_sheets,
    sync_cash_flows,
    sync_ipca,
    sync_earnings,
)
from quotes.circuit_breaker import CircuitOpenError
from quotes.models import BalanceSheet, IPCAIndex, QuarterlyCashFlow, QuarterlyEarnings


class TestGetWrapsCircuitOpen:
    """An open breaker must surface as BRAPIError, not a bare CircuitOpenError.

    Otherwise it escapes every ``except BRAPIError`` / ``except ProviderError``
    handler in the refresh pipeline and floods Sentry instead of degrading
    gracefully like any other provider outage.
    """

    @patch("quotes.brapi._BREAKER")
    def test_open_breaker_raises_brapi_error(self, mock_breaker):
        mock_breaker.call.side_effect = CircuitOpenError("Circuit 'brapi' is open")
        with pytest.raises(BRAPIError, match="circuit"):
            _get("/quote/PETR4")


MOCK_QUOTE_RESPONSE = {
    "results": [
        {
            "symbol": "PETR4",
            "shortName": "PETR4",
            "longName": "Petroleo Brasileiro SA Pfd",
            "regularMarketPrice": 45.0,
            "marketCap": 602167750093,
            "earningsPerShare": 8.54,
        }
    ]
}

MOCK_INCOME_RESPONSE = {
    "results": [
        {
            "incomeStatementHistoryQuarterly": [
                {
                    "endDate": "2025-12-31",
                    "netIncome": 15653000000,
                    "basicEarningsPerCommonShare": None,
                },
                {
                    "endDate": "2025-09-30",
                    "netIncome": 32847000000,
                    "basicEarningsPerCommonShare": 2540,
                },
                {
                    "endDate": "2025-06-30",
                    "netIncome": 26774000000,
                    "basicEarningsPerCommonShare": 2070,
                },
                {
                    "endDate": "2025-03-31",
                    "netIncome": 35331000000,
                    "basicEarningsPerCommonShare": 2730,
                },
            ]
        }
    ]
}

MOCK_IPCA_RESPONSE = {
    "inflation": [
        {"date": "01/12/2025", "value": "4.26", "epochDate": 1764547200000},
        {"date": "01/11/2025", "value": "4.46", "epochDate": 1761955200000},
        {"date": "01/12/2024", "value": "4.83", "epochDate": 1733011200000},
    ]
}


class TestFetchQuote:
    @patch("quotes.brapi._get")
    def test_returns_first_result(self, mock_get):
        mock_get.return_value = MOCK_QUOTE_RESPONSE
        result = fetch_quote("PETR4")
        assert result["symbol"] == "PETR4"
        assert result["regularMarketPrice"] == 45.0

    @patch("quotes.brapi._get")
    def test_raises_on_empty_results(self, mock_get):
        mock_get.return_value = {"results": []}
        with pytest.raises(BRAPIError, match="No results"):
            fetch_quote("FAKE3")


MOCK_HISTORICAL_RESPONSE = {
    "results": [
        {
            "historicalDataPrice": [
                {"date": 1704067200, "adjustedClose": 30.0},
                {"date": 1706745600, "adjustedClose": 32.0},
            ]
        }
    ]
}


class TestFetchHistoricalPrices:
    @patch("quotes.brapi._get")
    def test_returns_historical_data(self, mock_get):
        mock_get.return_value = MOCK_HISTORICAL_RESPONSE
        result = fetch_historical_prices("PETR4")
        assert len(result) == 2
        assert result[0]["adjustedClose"] == 30.0
        mock_get.assert_called_once_with(
            "/quote/PETR4", params={"range": "max", "interval": "1mo"}
        )

    @patch("quotes.brapi._get")
    def test_raises_on_empty_results(self, mock_get):
        mock_get.return_value = {"results": []}
        with pytest.raises(BRAPIError, match="No results"):
            fetch_historical_prices("FAKE3")

    @patch("quotes.brapi._get")
    def test_returns_empty_list_when_no_historical_data(self, mock_get):
        mock_get.return_value = {"results": [{"historicalDataPrice": []}]}
        result = fetch_historical_prices("PETR4")
        assert result == []


class TestFetchIncomeStatements:
    @patch("quotes.brapi._get")
    def test_returns_quarterly_statements(self, mock_get):
        mock_get.return_value = MOCK_INCOME_RESPONSE
        result = fetch_income_statements("PETR4")
        assert len(result.quarterly) == 4
        assert result.quarterly[0]["endDate"] == "2025-12-31"
        assert result.quarterly[0]["netIncome"] == 15653000000

    @patch("quotes.brapi._get")
    def test_returns_empty_list_when_no_statements(self, mock_get):
        mock_get.return_value = {"results": [{"incomeStatementHistoryQuarterly": []}]}
        result = fetch_income_statements("PETR4")
        assert result.periods == []


class TestSyncQuarterlyEarnings:
    @patch("quotes.brapi.fetch_income_statements")
    def test_creates_earnings_records(self, mock_fetch, db):
        mock_fetch.return_value = IncomeStatements(
            quarterly=MOCK_INCOME_RESPONSE["results"][0][
                "incomeStatementHistoryQuarterly"
            ],
            annual=[],
        )
        earnings = sync_earnings("PETR4")
        assert len(earnings) == 4
        assert QuarterlyEarnings.objects.filter(ticker="PETR4").count() == 4

    @patch("quotes.brapi.fetch_income_statements")
    def test_stores_net_income(self, mock_fetch, db):
        mock_fetch.return_value = IncomeStatements(
            quarterly=MOCK_INCOME_RESPONSE["results"][0][
                "incomeStatementHistoryQuarterly"
            ],
            annual=[],
        )
        sync_earnings("PETR4")
        q4 = QuarterlyEarnings.objects.get(ticker="PETR4", end_date=date(2025, 12, 31))
        assert q4.net_income == 15653000000

    @patch("quotes.brapi.fetch_income_statements")
    def test_handles_null_eps(self, mock_fetch, db):
        mock_fetch.return_value = IncomeStatements(
            quarterly=MOCK_INCOME_RESPONSE["results"][0][
                "incomeStatementHistoryQuarterly"
            ],
            annual=[],
        )
        sync_earnings("PETR4")
        q4 = QuarterlyEarnings.objects.get(ticker="PETR4", end_date=date(2025, 12, 31))
        assert q4.eps is None

    @patch("quotes.brapi.fetch_income_statements")
    def test_updates_existing_records(self, mock_fetch, db):
        mock_fetch.return_value = IncomeStatements(
            quarterly=MOCK_INCOME_RESPONSE["results"][0][
                "incomeStatementHistoryQuarterly"
            ],
            annual=[],
        )
        sync_earnings("PETR4")
        sync_earnings("PETR4")
        # Should not create duplicates
        assert QuarterlyEarnings.objects.filter(ticker="PETR4").count() == 4

    @patch("quotes.brapi.fetch_income_statements")
    def test_skips_entries_without_end_date(self, mock_fetch, db):
        mock_fetch.return_value = IncomeStatements(
            quarterly=[{"endDate": "", "netIncome": 1000}], annual=[],
        )
        earnings = sync_earnings("PETR4")
        assert len(earnings) == 0


MOCK_BALANCE_SHEET_WITH_TOTAL_CURRENT_ASSETS = [
    {
        "endDate": "2025-09-30",
        "loansAndFinancing": 50000000000,
        "longTermLoansAndFinancing": 100000000000,
        "currentLiabilities": 200000000000,
        "nonCurrentLiabilities": 300000000000,
        "shareholdersEquity": 200000000000,
        "totalCurrentAssets": 150000000000,
    },
]

MOCK_BALANCE_SHEET_WITH_CURRENT_ASSETS_FALLBACK = [
    {
        "endDate": "2025-06-30",
        "loansAndFinancing": 50000000000,
        "longTermLoansAndFinancing": 100000000000,
        "currentLiabilities": 200000000000,
        "nonCurrentLiabilities": 300000000000,
        "shareholdersEquity": 200000000000,
        "currentAssets": 120000000000,
    },
]


class TestSyncBalanceSheets:
    @patch("quotes.brapi.fetch_financial_data")
    @patch("quotes.brapi.fetch_balance_sheets")
    @patch("quotes.brapi._fetch_annual_lease_data")
    def test_maps_total_current_assets_to_current_assets(
        self, mock_annual_lease, mock_fetch, mock_financial_data, db
    ):
        """BRAPI returns totalCurrentAssets instead of currentAssets for some tickers."""
        mock_fetch.return_value = MOCK_BALANCE_SHEET_WITH_TOTAL_CURRENT_ASSETS
        mock_annual_lease.return_value = {}
        mock_financial_data.return_value = {}
        sheets = sync_balance_sheets("PETR4")
        assert len(sheets) == 1
        balance_sheet = BalanceSheet.objects.get(
            ticker="PETR4", end_date=date(2025, 9, 30)
        )
        assert balance_sheet.current_assets == 150000000000

    @patch("quotes.brapi.fetch_financial_data")
    @patch("quotes.brapi.fetch_balance_sheets")
    @patch("quotes.brapi._fetch_annual_lease_data")
    def test_falls_back_to_current_assets_field(
        self, mock_annual_lease, mock_fetch, mock_financial_data, db
    ):
        """When totalCurrentAssets is absent, currentAssets is used instead."""
        mock_fetch.return_value = MOCK_BALANCE_SHEET_WITH_CURRENT_ASSETS_FALLBACK
        mock_annual_lease.return_value = {}
        mock_financial_data.return_value = {}
        sync_balance_sheets("PETR4")
        balance_sheet = BalanceSheet.objects.get(
            ticker="PETR4", end_date=date(2025, 6, 30)
        )
        assert balance_sheet.current_assets == 120000000000

    @patch("quotes.brapi.fetch_financial_data")
    @patch("quotes.brapi.fetch_balance_sheets")
    @patch("quotes.brapi._fetch_annual_lease_data")
    def test_current_assets_null_when_neither_field_present(
        self, mock_annual_lease, mock_fetch, mock_financial_data, db
    ):
        """When neither totalCurrentAssets nor currentAssets is present, current_assets is None."""
        mock_fetch.return_value = [
            {
                "endDate": "2025-03-31",
                "loansAndFinancing": 50000000000,
                "longTermLoansAndFinancing": 100000000000,
                "currentLiabilities": 200000000000,
                "nonCurrentLiabilities": 300000000000,
                "shareholdersEquity": 200000000000,
            },
        ]
        mock_annual_lease.return_value = {}
        mock_financial_data.return_value = {}
        sync_balance_sheets("PETR4")
        balance_sheet = BalanceSheet.objects.get(
            ticker="PETR4", end_date=date(2025, 3, 31)
        )
        assert balance_sheet.current_assets is None


class TestFetchFinancialData:
    @patch("quotes.brapi._get")
    def test_returns_financial_data_dict(self, mock_get):
        mock_get.return_value = {
            "results": [
                {"financialData": {"totalDebt": 146216990, "debtToEquity": 0.1665}}
            ]
        }
        result = fetch_financial_data("CGRA3")
        assert result["totalDebt"] == 146216990
        mock_get.assert_called_once_with(
            "/quote/CGRA3", params={"modules": "financialData"}
        )

    @patch("quotes.brapi._get")
    def test_returns_empty_dict_when_no_results(self, mock_get):
        mock_get.return_value = {"results": []}
        assert fetch_financial_data("FAKE3") == {}

    @patch("quotes.brapi._get")
    def test_returns_empty_dict_when_module_absent(self, mock_get):
        mock_get.return_value = {"results": [{}]}
        assert fetch_financial_data("PETR4") == {}

    @patch("quotes.brapi._get")
    def test_returns_empty_dict_on_brapi_error(self, mock_get):
        mock_get.side_effect = BRAPIError("boom")
        assert fetch_financial_data("PETR4") == {}


class TestSyncBalanceSheetsPatchesLatestDebtFromFinancialData:
    """BRAPI's balanceSheetHistory returns 0 for loansAndFinancing on many
    mid/small caps and banks, even when the company has real debt.  The
    financialData module carries a more accurate point-in-time totalDebt.
    Override the most recent balance sheet so the Leverage card reflects
    reality instead of a spurious zero.
    """

    HISTORY = [
        {
            "endDate": "2025-09-30",
            "loansAndFinancing": 0,
            "longTermLoansAndFinancing": 0,
            "currentLiabilities": 200_000_000,
            "nonCurrentLiabilities": 146_216_990,
            "shareholdersEquity": 878_113_000,
        },
        {
            "endDate": "2025-06-30",
            "loansAndFinancing": 0,
            "longTermLoansAndFinancing": 0,
            "currentLiabilities": 200_000_000,
            "nonCurrentLiabilities": 140_000_000,
            "shareholdersEquity": 870_000_000,
        },
    ]

    @patch("quotes.brapi.fetch_financial_data")
    @patch("quotes.brapi._fetch_annual_lease_data")
    @patch("quotes.brapi.fetch_balance_sheets")
    def test_patches_latest_total_debt_when_financial_data_reports_debt(
        self, mock_fetch, mock_annual_lease, mock_financial_data, db
    ):
        mock_fetch.return_value = self.HISTORY
        mock_annual_lease.return_value = {}
        mock_financial_data.return_value = {"totalDebt": 146_216_990}

        sync_balance_sheets("CGRA3")

        latest = BalanceSheet.objects.get(ticker="CGRA3", end_date=date(2025, 9, 30))
        assert latest.total_debt == 146_216_990

    @patch("quotes.brapi.fetch_financial_data")
    @patch("quotes.brapi._fetch_annual_lease_data")
    @patch("quotes.brapi.fetch_balance_sheets")
    def test_does_not_patch_historical_balance_sheets(
        self, mock_fetch, mock_annual_lease, mock_financial_data, db
    ):
        mock_fetch.return_value = self.HISTORY
        mock_annual_lease.return_value = {}
        mock_financial_data.return_value = {"totalDebt": 146_216_990}

        sync_balance_sheets("CGRA3")

        older = BalanceSheet.objects.get(ticker="CGRA3", end_date=date(2025, 6, 30))
        assert older.total_debt == 0

    @patch("quotes.brapi.fetch_financial_data")
    @patch("quotes.brapi._fetch_annual_lease_data")
    @patch("quotes.brapi.fetch_balance_sheets")
    def test_skips_patch_when_financial_data_debt_is_none(
        self, mock_fetch, mock_annual_lease, mock_financial_data, db
    ):
        """Banks (BEES3, PINE3) report totalDebt=None — leave total_debt as None
        so the card can show "not available" instead of a wrong zero."""
        mock_fetch.return_value = self.HISTORY
        mock_annual_lease.return_value = {}
        mock_financial_data.return_value = {"totalDebt": None}

        sync_balance_sheets("CGRA3")

        latest = BalanceSheet.objects.get(ticker="CGRA3", end_date=date(2025, 9, 30))
        assert latest.total_debt is None

    @patch("quotes.brapi.fetch_financial_data")
    @patch("quotes.brapi._fetch_annual_lease_data")
    @patch("quotes.brapi.fetch_balance_sheets")
    def test_keeps_balance_sheet_debt_when_financial_data_is_larger(
        self, mock_fetch, mock_annual_lease, mock_financial_data, db
    ):
        """When balanceSheetHistory already reports real loansAndFinancing,
        trust it — BRAPI's financialData.totalDebt is sometimes inflated
        (observed on VALE3: 203.6B vs the correct 103.5B). Overriding with
        the larger value would produce a D/E ratio that disagrees with the
        ADR (VALE via FMP) by nearly 2x."""
        mock_fetch.return_value = [
            {
                "endDate": "2025-09-30",
                "loansAndFinancing": 3_731_000_000,
                "longTermLoansAndFinancing": 99_726_000_000,
                "currentLiabilities": 87_320_000_000,
                "nonCurrentLiabilities": 199_848_000_000,
                "shareholdersEquity": 188_000_000_000,
            },
        ]
        mock_annual_lease.return_value = {}
        mock_financial_data.return_value = {"totalDebt": 203_579_000_000}

        sync_balance_sheets("VALE3")

        latest = BalanceSheet.objects.get(ticker="VALE3", end_date=date(2025, 9, 30))
        assert latest.total_debt == 103_457_000_000

    @patch("quotes.brapi.fetch_financial_data")
    @patch("quotes.brapi._fetch_annual_lease_data")
    @patch("quotes.brapi.fetch_balance_sheets")
    def test_keeps_local_calc_when_financial_data_is_smaller(
        self, mock_fetch, mock_annual_lease, mock_financial_data, db
    ):
        mock_fetch.return_value = [
            {
                "endDate": "2025-09-30",
                "loansAndFinancing": 3_731_000_000,
                "longTermLoansAndFinancing": 99_726_000_000,
                "currentLiabilities": 87_320_000_000,
                "nonCurrentLiabilities": 199_848_000_000,
                "shareholdersEquity": 188_000_000_000,
            },
        ]
        mock_annual_lease.return_value = {}
        mock_financial_data.return_value = {"totalDebt": 50_000_000_000}

        sync_balance_sheets("VALE3")

        latest = BalanceSheet.objects.get(ticker="VALE3", end_date=date(2025, 9, 30))
        assert latest.total_debt == 103_457_000_000  # sum of the two loan fields


def _synthetic_brapi_income_statements(count: int) -> list[dict]:
    return [
        {
            "endDate": f"20{25 - (i // 4):02d}-{((i % 4) * 3 + 1):02d}-15",
            "netIncome": 1000 + i,
            "totalRevenue": 5000 + i,
            "basicEarningsPerCommonShare": 1.0 + i * 0.01,
        }
        for i in range(count)
    ]


def _synthetic_brapi_cash_flows(count: int) -> list[dict]:
    return [
        {
            "endDate": f"20{25 - (i // 4):02d}-{((i % 4) * 3 + 1):02d}-15",
            "operatingCashFlow": 1000 + i,
            "investmentCashFlow": -100 - i,
            "dividendsPaid": -50 - i,
        }
        for i in range(count)
    ]


def _synthetic_brapi_balance_sheets(count: int) -> list[dict]:
    return [
        {
            "endDate": f"20{25 - (i // 4):02d}-{((i % 4) * 3 + 1):02d}-15",
            "loansAndFinancing": 1000 + i,
            "longTermLoansAndFinancing": 2000 + i,
            "currentLiabilities": 500 + i,
            "nonCurrentLiabilities": 1500 + i,
            "shareholdersEquity": 3000 + i,
            "totalCurrentAssets": 4000 + i,
        }
        for i in range(count)
    ]


MAX_QUERIES_PER_SYNC = 5


class TestBrapiSyncEarningsIsBulk:
    @patch("quotes.brapi.fetch_income_statements")
    def test_uses_constant_query_count_regardless_of_row_count(self, mock_fetch, db):
        mock_fetch.return_value = IncomeStatements(
            quarterly=_synthetic_brapi_income_statements(20), annual=[],
        )
        with CaptureQueriesContext(connection) as captured:
            earnings = sync_earnings("PETR4")
        assert len(earnings) == 20
        assert QuarterlyEarnings.objects.filter(ticker="PETR4").count() == 20
        assert len(captured) <= MAX_QUERIES_PER_SYNC, (
            f"Expected ≤{MAX_QUERIES_PER_SYNC} queries, got {len(captured)}:\n"
            + "\n".join(q["sql"] for q in captured)
        )


class TestBrapiSyncHandlesDuplicateDates:
    """BRAPI occasionally returns two statements with the same endDate for
    one ticker. Dedupe inside sync_* before bulk upsert (last-wins),
    or Postgres ON CONFLICT rejects the whole statement.
    """

    @patch("quotes.brapi.fetch_income_statements")
    def test_earnings_dedup(self, mock_fetch, db):
        mock_fetch.return_value = IncomeStatements(
            quarterly=[
                {"endDate": "2025-09-30", "netIncome": 111, "totalRevenue": 1, "basicEarningsPerCommonShare": 0.1},
                {"endDate": "2025-09-30", "netIncome": 222, "totalRevenue": 2, "basicEarningsPerCommonShare": 0.2},
            ],
            annual=[],
        )
        earnings = sync_earnings("PETR4")
        assert len(earnings) == 1
        record = QuarterlyEarnings.objects.get(ticker="PETR4", end_date=date(2025, 9, 30))
        assert record.net_income == 222

    @patch("quotes.brapi.fetch_cash_flow_statements")
    def test_cash_flows_dedup(self, mock_fetch, db):
        mock_fetch.return_value = [
            {"endDate": "2025-09-30", "operatingCashFlow": 1, "investmentCashFlow": -1, "dividendsPaid": -1},
            {"endDate": "2025-09-30", "operatingCashFlow": 99, "investmentCashFlow": -9, "dividendsPaid": -9},
        ]
        cash_flows = sync_cash_flows("PETR4")
        assert len(cash_flows) == 1
        record = QuarterlyCashFlow.objects.get(ticker="PETR4", end_date=date(2025, 9, 30))
        assert record.operating_cash_flow == 99

    @patch("quotes.brapi.fetch_financial_data")
    @patch("quotes.brapi._fetch_annual_lease_data")
    @patch("quotes.brapi.fetch_balance_sheets")
    def test_balance_sheets_dedup(self, mock_fetch, mock_annual_lease, mock_financial_data, db):
        mock_fetch.return_value = [
            {"endDate": "2025-09-30", "loansAndFinancing": 1, "longTermLoansAndFinancing": 1, "currentLiabilities": 1, "nonCurrentLiabilities": 1, "shareholdersEquity": 1},
            {"endDate": "2025-09-30", "loansAndFinancing": 500, "longTermLoansAndFinancing": 500, "currentLiabilities": 1, "nonCurrentLiabilities": 1, "shareholdersEquity": 1},
        ]
        mock_annual_lease.return_value = {}
        mock_financial_data.return_value = {}
        sheets = sync_balance_sheets("PETR4")
        assert len(sheets) == 1
        record = BalanceSheet.objects.get(ticker="PETR4", end_date=date(2025, 9, 30))
        assert record.total_debt == 1000


class TestBrapiSyncCashFlowsIsBulk:
    @patch("quotes.brapi.fetch_cash_flow_statements")
    def test_uses_constant_query_count_regardless_of_row_count(self, mock_fetch, db):
        mock_fetch.return_value = _synthetic_brapi_cash_flows(20)
        with CaptureQueriesContext(connection) as captured:
            cash_flows = sync_cash_flows("PETR4")
        assert len(cash_flows) == 20
        assert QuarterlyCashFlow.objects.filter(ticker="PETR4").count() == 20
        assert len(captured) <= MAX_QUERIES_PER_SYNC, (
            f"Expected ≤{MAX_QUERIES_PER_SYNC} queries, got {len(captured)}:\n"
            + "\n".join(q["sql"] for q in captured)
        )


class TestBrapiSyncBalanceSheetsIsBulk:
    @patch("quotes.brapi.fetch_financial_data")
    @patch("quotes.brapi._fetch_annual_lease_data")
    @patch("quotes.brapi.fetch_balance_sheets")
    def test_uses_constant_query_count_regardless_of_row_count(
        self, mock_fetch, mock_annual_lease, mock_financial_data, db
    ):
        mock_fetch.return_value = _synthetic_brapi_balance_sheets(20)
        mock_annual_lease.return_value = {}
        mock_financial_data.return_value = {}
        with CaptureQueriesContext(connection) as captured:
            sheets = sync_balance_sheets("PETR4")
        assert len(sheets) == 20
        assert BalanceSheet.objects.filter(ticker="PETR4").count() == 20
        assert len(captured) <= MAX_QUERIES_PER_SYNC, (
            f"Expected ≤{MAX_QUERIES_PER_SYNC} queries, got {len(captured)}:\n"
            + "\n".join(q["sql"] for q in captured)
        )


class TestSyncIPCA:
    @patch("quotes.brapi.fetch_ipca_data")
    def test_creates_ipca_records(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_IPCA_RESPONSE["inflation"]
        count = sync_ipca()
        assert count == 3
        assert IPCAIndex.objects.count() == 3

    @patch("quotes.brapi.fetch_ipca_data")
    def test_parses_brapi_date_format(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_IPCA_RESPONSE["inflation"]
        sync_ipca()
        entry = IPCAIndex.objects.get(date=date(2025, 12, 1))
        assert entry.annual_rate == Decimal("4.26")

    @patch("quotes.brapi.fetch_ipca_data")
    def test_updates_existing_records(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_IPCA_RESPONSE["inflation"]
        sync_ipca()
        sync_ipca()
        assert IPCAIndex.objects.count() == 3

    @patch("quotes.brapi.fetch_ipca_data")
    def test_skips_entries_without_value(self, mock_fetch, db):
        mock_fetch.return_value = [{"date": "01/01/2025", "value": None}]
        count = sync_ipca()
        assert count == 0


class TestFetchQuotesBatch:
    @patch("quotes.brapi._get")
    def test_returns_dict_keyed_by_symbol(self, mock_get):
        mock_get.return_value = {
            "results": [
                {"symbol": "PETR4", "regularMarketPrice": 32.50, "marketCap": 100_000_000},
                {"symbol": "VALE3", "regularMarketPrice": 65.0, "marketCap": 200_000_000},
            ]
        }
        from quotes.brapi import fetch_quotes_batch
        result = fetch_quotes_batch(["PETR4", "VALE3"])
        assert result["PETR4"]["regularMarketPrice"] == 32.50
        assert result["VALE3"]["marketCap"] == 200_000_000

    @patch("quotes.brapi._get")
    def test_calls_api_with_tickers_in_path(self, mock_get):
        mock_get.return_value = {"results": []}
        from quotes.brapi import fetch_quotes_batch
        fetch_quotes_batch(["PETR4", "VALE3"])
        mock_get.assert_called_once_with("/quote/PETR4,VALE3")

    @patch("quotes.brapi._get")
    def test_chunks_when_tickers_exceed_batch_size(self, mock_get):
        mock_get.return_value = {"results": []}
        from quotes.brapi import BRAPI_BATCH_SIZE, fetch_quotes_batch
        tickers = [f"TIC{i}" for i in range(BRAPI_BATCH_SIZE + 5)]
        fetch_quotes_batch(tickers)
        assert mock_get.call_count == 2

    @patch("quotes.brapi._get")
    def test_empty_list_returns_empty_dict_without_api_call(self, mock_get):
        from quotes.brapi import fetch_quotes_batch
        result = fetch_quotes_batch([])
        assert result == {}
        mock_get.assert_not_called()


# Kepler Weber's real 2025 and 2026 filings, as BRAPI served them on
# 2026-08-27. Q2 and Q3 are differenced against the quarter before them, so
# both come through negative. See quotes.cumulative_quarters.
MOCK_DOUBLE_DIFFERENCED_QUARTERS = [
    {"endDate": "2026-06-30", "totalRevenue": -18988000, "netIncome": -10810000},
    {"endDate": "2026-03-31", "totalRevenue": 318059000, "netIncome": 17128000},
    {"endDate": "2025-12-31", "totalRevenue": 398662020, "netIncome": 64752000},
    {"endDate": "2025-09-30", "totalRevenue": 112262000, "netIncome": 37174000},
    {"endDate": "2025-06-30", "totalRevenue": -46157000, "netIncome": -11156000},
    {"endDate": "2025-03-31", "totalRevenue": 357230020, "netIncome": 25552000},
]

MOCK_AUDITED_ANNUALS = [
    {"endDate": "2025-12-31", "totalRevenue": 1490300000, "netIncome": 156270000},
    {"endDate": "2024-12-31", "totalRevenue": 1607297000, "netIncome": 199183010},
]


class TestSyncEarningsRestatesDifferencedQuarters:
    """Ingestion reconciles the quarters against the company's own annual.

    The check belongs here rather than in a repair script because a quarter
    that arrives wrong is wrong for everyone who loads the page before the
    next repair runs.
    """

    @patch("quotes.brapi.fetch_income_statements")
    def test_stores_the_quarters_the_company_actually_filed(self, mock_fetch, db):
        mock_fetch.return_value = IncomeStatements(
            quarterly=MOCK_DOUBLE_DIFFERENCED_QUARTERS, annual=MOCK_AUDITED_ANNUALS,
        )
        sync_earnings("KEPL3")

        stored = {
            row.end_date: row.revenue
            for row in QuarterlyEarnings.objects.filter(ticker="KEPL3")
        }
        assert stored[date(2025, 6, 30)] == 311073020
        assert stored[date(2025, 9, 30)] == 423335020
        assert stored[date(2025, 12, 31)] == 398662020

    @patch("quotes.brapi.fetch_income_statements")
    def test_stored_year_ties_to_the_audited_annual(self, mock_fetch, db):
        mock_fetch.return_value = IncomeStatements(
            quarterly=MOCK_DOUBLE_DIFFERENCED_QUARTERS, annual=MOCK_AUDITED_ANNUALS,
        )
        sync_earnings("KEPL3")

        year = QuarterlyEarnings.objects.filter(
            ticker="KEPL3", end_date__year=2025,
        )
        assert sum(row.net_income for row in year) == 156270000

    @patch("quotes.brapi.fetch_income_statements")
    def test_repairs_the_year_still_in_progress(self, mock_fetch, db):
        """2026 has no annual yet, and is what the company page shows."""
        mock_fetch.return_value = IncomeStatements(
            quarterly=MOCK_DOUBLE_DIFFERENCED_QUARTERS, annual=MOCK_AUDITED_ANNUALS,
        )
        sync_earnings("KEPL3")

        second_quarter = QuarterlyEarnings.objects.get(
            ticker="KEPL3", end_date=date(2026, 6, 30),
        )
        assert second_quarter.revenue == 299071000

    @patch("quotes.brapi.fetch_income_statements")
    def test_leaves_a_healthy_company_untouched(self, mock_fetch, db):
        """Three of the eight largest B3 filers on this path have no bug."""
        healthy = [
            {"endDate": "2025-12-31", "totalRevenue": 14340918000, "netIncome": 435543000},
            {"endDate": "2025-09-30", "totalRevenue": 10866683000, "netIncome": 688122000},
            {"endDate": "2025-06-30", "totalRevenue": 10270363000, "netIncome": 397477000},
            {"endDate": "2025-03-31", "totalRevenue": 6405270000, "netIncome": 470895000},
        ]
        mock_fetch.return_value = IncomeStatements(
            quarterly=healthy,
            annual=[{
                "endDate": "2025-12-31",
                "totalRevenue": 41883234000,
                "netIncome": 1992037000,
            }],
        )
        sync_earnings("EMBR3")

        stored = QuarterlyEarnings.objects.get(ticker="EMBR3", end_date=date(2025, 6, 30))
        assert stored.revenue == 10270363000

    @patch("quotes.brapi.fetch_income_statements")
    def test_stores_plausible_figures_as_filed_when_no_annual_came_back(self, mock_fetch, db):
        """A degraded provider response must not trigger a guess.

        Nothing here is impossible as filed, so there is nothing to act on.
        A quarter reporting negative revenue is a different matter, and is
        covered in tests/test_cumulative_quarters.py.
        """
        healthy = [
            {"endDate": "2025-12-31", "totalRevenue": 14340918000, "netIncome": 435543000},
            {"endDate": "2025-09-30", "totalRevenue": 10866683000, "netIncome": 688122000},
            {"endDate": "2025-06-30", "totalRevenue": 10270363000, "netIncome": 397477000},
            {"endDate": "2025-03-31", "totalRevenue": 6405270000, "netIncome": 470895000},
        ]
        mock_fetch.return_value = IncomeStatements(quarterly=healthy, annual=[])
        sync_earnings("EMBR3")

        stored = QuarterlyEarnings.objects.get(ticker="EMBR3", end_date=date(2025, 6, 30))
        assert stored.revenue == 10270363000

    @patch("quotes.brapi._get")
    def test_asks_for_both_modules_in_one_request(self, mock_get):
        """The annual is free: BRAPI returns both modules from one call."""
        mock_get.return_value = {"results": [{
            "incomeStatementHistoryQuarterly": MOCK_DOUBLE_DIFFERENCED_QUARTERS,
            "incomeStatementHistory": MOCK_AUDITED_ANNUALS,
        }]}
        statements = fetch_income_statements("KEPL3")

        assert mock_get.call_count == 1
        assert len(statements.quarterly) == 6
        assert len(statements.annual) == 2

    @patch("quotes.brapi._get")
    def test_falls_back_to_annual_periods_without_a_quarterly_module(self, mock_get):
        """Some BRAPI plans omit quarterly data entirely."""
        mock_get.return_value = {"results": [{
            "incomeStatementHistoryQuarterly": [],
            "incomeStatementHistory": MOCK_AUDITED_ANNUALS,
        }]}
        statements = fetch_income_statements("KEPL3")

        assert statements.periods == MOCK_AUDITED_ANNUALS
