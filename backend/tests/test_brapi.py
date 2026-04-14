"""Tests for BRAPI client with mocked API responses."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from quotes.brapi import (
    BRAPIError,
    fetch_financial_data,
    fetch_historical_prices,
    fetch_income_statements,
    fetch_quote,
    sync_balance_sheets,
    sync_ipca,
    sync_earnings,
)
from quotes.models import BalanceSheet, IPCAIndex, QuarterlyEarnings


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
        assert len(result) == 4
        assert result[0]["endDate"] == "2025-12-31"
        assert result[0]["netIncome"] == 15653000000

    @patch("quotes.brapi._get")
    def test_returns_empty_list_when_no_statements(self, mock_get):
        mock_get.return_value = {"results": [{"incomeStatementHistoryQuarterly": []}]}
        result = fetch_income_statements("PETR4")
        assert result == []


class TestSyncQuarterlyEarnings:
    @patch("quotes.brapi.fetch_income_statements")
    def test_creates_earnings_records(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_INCOME_RESPONSE["results"][0][
            "incomeStatementHistoryQuarterly"
        ]
        earnings = sync_earnings("PETR4")
        assert len(earnings) == 4
        assert QuarterlyEarnings.objects.filter(ticker="PETR4").count() == 4

    @patch("quotes.brapi.fetch_income_statements")
    def test_stores_net_income(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_INCOME_RESPONSE["results"][0][
            "incomeStatementHistoryQuarterly"
        ]
        sync_earnings("PETR4")
        q4 = QuarterlyEarnings.objects.get(ticker="PETR4", end_date=date(2025, 12, 31))
        assert q4.net_income == 15653000000

    @patch("quotes.brapi.fetch_income_statements")
    def test_handles_null_eps(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_INCOME_RESPONSE["results"][0][
            "incomeStatementHistoryQuarterly"
        ]
        sync_earnings("PETR4")
        q4 = QuarterlyEarnings.objects.get(ticker="PETR4", end_date=date(2025, 12, 31))
        assert q4.eps is None

    @patch("quotes.brapi.fetch_income_statements")
    def test_updates_existing_records(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_INCOME_RESPONSE["results"][0][
            "incomeStatementHistoryQuarterly"
        ]
        sync_earnings("PETR4")
        sync_earnings("PETR4")
        # Should not create duplicates
        assert QuarterlyEarnings.objects.filter(ticker="PETR4").count() == 4

    @patch("quotes.brapi.fetch_income_statements")
    def test_skips_entries_without_end_date(self, mock_fetch, db):
        mock_fetch.return_value = [{"endDate": "", "netIncome": 1000}]
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
