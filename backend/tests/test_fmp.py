"""Tests for FMP API client with mocked API responses."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from quotes.fmp import (
    FMPError,
    fetch_balance_sheets,
    fetch_cash_flow_statements,
    fetch_dividends,
    fetch_historical_prices,
    fetch_income_statements,
    fetch_quote,
    sync_balance_sheets,
    sync_cash_flows,
    sync_earnings,
    sync_us_cpi,
)
from quotes.models import BalanceSheet, QuarterlyCashFlow, QuarterlyEarnings, USCPIIndex


MOCK_QUOTE_RESPONSE = [
    {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "price": 178.72,
        "marketCap": 2800000000000,
        "changesPercentage": 1.23,
        "change": 2.17,
        "dayLow": 176.0,
        "dayHigh": 179.5,
        "yearHigh": 199.62,
        "yearLow": 124.17,
        "volume": 54321000,
        "avgVolume": 60000000,
        "exchange": "NASDAQ",
        "earningsAnnouncement": "2025-01-30T00:00:00.000+0000",
        "sharesOutstanding": 15666700000,
        "timestamp": 1700000000,
    }
]

MOCK_INCOME_STATEMENTS = [
    {
        "date": "2025-09-30",
        "symbol": "AAPL",
        "reportedCurrency": "USD",
        "revenue": 89500000000,
        "netIncome": 22960000000,
        "eps": 1.46,
        "epsdiluted": 1.46,
    },
    {
        "date": "2025-06-30",
        "symbol": "AAPL",
        "reportedCurrency": "USD",
        "revenue": 85780000000,
        "netIncome": 21450000000,
        "eps": 1.37,
        "epsdiluted": 1.36,
    },
    {
        "date": "2025-03-31",
        "symbol": "AAPL",
        "reportedCurrency": "USD",
        "revenue": 94930000000,
        "netIncome": 23640000000,
        "eps": 1.52,
        "epsdiluted": 1.52,
    },
    {
        "date": "2024-12-31",
        "symbol": "AAPL",
        "reportedCurrency": "USD",
        "revenue": 119580000000,
        "netIncome": 36330000000,
        "eps": 2.40,
        "epsdiluted": 2.40,
    },
]

MOCK_CASH_FLOW_STATEMENTS = [
    {
        "date": "2025-09-30",
        "symbol": "AAPL",
        "operatingCashFlow": 26900000000,
        "investingCashFlow": -4500000000,
        "financingCashFlow": -22000000000,
        "capitalExpenditure": -2800000000,
        "freeCashFlow": 24100000000,
        "dividendsPaid": -3800000000,
    },
    {
        "date": "2025-06-30",
        "symbol": "AAPL",
        "operatingCashFlow": 28500000000,
        "investingCashFlow": -3900000000,
        "financingCashFlow": -25000000000,
        "capitalExpenditure": -2600000000,
        "freeCashFlow": 25900000000,
        "dividendsPaid": -3700000000,
    },
]

MOCK_BALANCE_SHEETS = [
    {
        "date": "2025-09-30",
        "symbol": "AAPL",
        "totalDebt": 111000000000,
        "totalLiabilities": 290000000000,
        "totalStockholdersEquity": 62000000000,
        "totalCurrentAssets": 143000000000,
        "totalCurrentLiabilities": 153000000000,
    },
    {
        "date": "2025-06-30",
        "symbol": "AAPL",
        "totalDebt": 109000000000,
        "totalLiabilities": 280000000000,
        "totalStockholdersEquity": 66000000000,
        "totalCurrentAssets": 140000000000,
        "totalCurrentLiabilities": 150000000000,
    },
]

MOCK_HISTORICAL_PRICES = [
    {"date": "2025-01-02", "adjClose": 178.5, "close": 178.5, "volume": 50000000},
    {"date": "2024-12-31", "adjClose": 175.0, "close": 175.0, "volume": 45000000},
    {"date": "2024-11-29", "adjClose": 170.0, "close": 170.0, "volume": 48000000},
]

MOCK_DIVIDENDS = [
    {"date": "2025-02-07", "adjDividend": 0.25, "dividend": 0.25, "recordDate": "2025-02-10", "paymentDate": "2025-02-13"},
    {"date": "2024-11-08", "adjDividend": 0.25, "dividend": 0.25, "recordDate": "2024-11-11", "paymentDate": "2024-11-14"},
]

MOCK_CPI_RESPONSE = [
    {"date": "2025-01-01", "value": 3.0, "country": "US", "name": "CPI"},
    {"date": "2024-01-01", "value": 3.4, "country": "US", "name": "CPI"},
    {"date": "2023-01-01", "value": 6.5, "country": "US", "name": "CPI"},
    {"date": "2022-01-01", "value": 7.0, "country": "US", "name": "CPI"},
]


class TestFetchQuote:
    @patch("quotes.fmp._get")
    def test_returns_quote_data(self, mock_get):
        mock_get.return_value = MOCK_QUOTE_RESPONSE
        result = fetch_quote("AAPL")
        assert result["symbol"] == "AAPL"
        assert result["price"] == 178.72
        assert result["marketCap"] == 2800000000000
        mock_get.assert_called_once_with("/stable/quote", params={"symbol": "AAPL"})

    @patch("quotes.fmp._get")
    def test_raises_on_empty_results(self, mock_get):
        mock_get.return_value = []
        with pytest.raises(FMPError, match="No results"):
            fetch_quote("FAKE")


class TestFetchIncomeStatements:
    @patch("quotes.fmp._get")
    def test_returns_quarterly_statements(self, mock_get):
        mock_get.return_value = MOCK_INCOME_STATEMENTS
        result = fetch_income_statements("AAPL")
        assert len(result) == 4
        assert result[0]["date"] == "2025-09-30"
        assert result[0]["netIncome"] == 22960000000
        mock_get.assert_called_once_with(
            "/stable/income-statement",
            params={"symbol": "AAPL", "period": "quarter", "limit": 80},
        )

    @patch("quotes.fmp._get")
    def test_returns_empty_list_when_no_data(self, mock_get):
        mock_get.return_value = []
        result = fetch_income_statements("AAPL")
        assert result == []


class TestFetchCashFlowStatements:
    @patch("quotes.fmp._get")
    def test_returns_quarterly_statements(self, mock_get):
        mock_get.return_value = MOCK_CASH_FLOW_STATEMENTS
        result = fetch_cash_flow_statements("AAPL")
        assert len(result) == 2
        assert result[0]["operatingCashFlow"] == 26900000000
        mock_get.assert_called_once_with(
            "/stable/cashflow-statement",
            params={"symbol": "AAPL", "period": "quarter", "limit": 80},
        )


class TestFetchBalanceSheets:
    @patch("quotes.fmp._get")
    def test_returns_quarterly_balance_sheets(self, mock_get):
        mock_get.return_value = MOCK_BALANCE_SHEETS
        result = fetch_balance_sheets("AAPL")
        assert len(result) == 2
        assert result[0]["totalDebt"] == 111000000000
        mock_get.assert_called_once_with(
            "/stable/balance-sheet-statement",
            params={"symbol": "AAPL", "period": "quarter", "limit": 80},
        )


class TestFetchHistoricalPrices:
    @patch("quotes.fmp._get")
    def test_returns_historical_data(self, mock_get):
        mock_get.return_value = MOCK_HISTORICAL_PRICES
        result = fetch_historical_prices("AAPL")
        assert len(result) == 3
        assert result[0]["adjClose"] == 178.5

    @patch("quotes.fmp._get")
    def test_raises_on_empty_results(self, mock_get):
        mock_get.return_value = []
        with pytest.raises(FMPError, match="No historical"):
            fetch_historical_prices("FAKE")


class TestFetchDividends:
    @patch("quotes.fmp._get")
    def test_returns_dividend_history(self, mock_get):
        mock_get.return_value = MOCK_DIVIDENDS
        result = fetch_dividends("AAPL")
        assert len(result) == 2
        assert result[0]["dividend"] == 0.25

    @patch("quotes.fmp._get")
    def test_returns_empty_list_when_no_dividends(self, mock_get):
        mock_get.return_value = []
        result = fetch_dividends("AAPL")
        assert result == []


class TestSyncEarnings:
    @patch("quotes.fmp.fetch_income_statements")
    def test_creates_earnings_records(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_INCOME_STATEMENTS
        earnings = sync_earnings("AAPL")
        assert len(earnings) == 4
        assert QuarterlyEarnings.objects.filter(ticker="AAPL").count() == 4

    @patch("quotes.fmp.fetch_income_statements")
    def test_stores_correct_values(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_INCOME_STATEMENTS
        sync_earnings("AAPL")
        record = QuarterlyEarnings.objects.get(ticker="AAPL", end_date=date(2025, 9, 30))
        assert record.net_income == 22960000000
        assert record.revenue == 89500000000
        assert record.eps == Decimal("1.46")

    @patch("quotes.fmp.fetch_income_statements")
    def test_updates_existing_records(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_INCOME_STATEMENTS
        sync_earnings("AAPL")
        sync_earnings("AAPL")
        assert QuarterlyEarnings.objects.filter(ticker="AAPL").count() == 4

    @patch("quotes.fmp.fetch_income_statements")
    def test_skips_entries_without_date(self, mock_fetch, db):
        mock_fetch.return_value = [{"date": "", "netIncome": 1000}]
        earnings = sync_earnings("AAPL")
        assert len(earnings) == 0


class TestSyncCashFlows:
    @patch("quotes.fmp.fetch_cash_flow_statements")
    def test_creates_cash_flow_records(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_CASH_FLOW_STATEMENTS
        cash_flows = sync_cash_flows("AAPL")
        assert len(cash_flows) == 2
        assert QuarterlyCashFlow.objects.filter(ticker="AAPL").count() == 2

    @patch("quotes.fmp.fetch_cash_flow_statements")
    def test_stores_correct_values(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_CASH_FLOW_STATEMENTS
        sync_cash_flows("AAPL")
        record = QuarterlyCashFlow.objects.get(ticker="AAPL", end_date=date(2025, 9, 30))
        assert record.operating_cash_flow == 26900000000
        assert record.investment_cash_flow == -4500000000
        assert record.dividends_paid == -3800000000

    @patch("quotes.fmp.fetch_cash_flow_statements")
    def test_updates_existing_records(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_CASH_FLOW_STATEMENTS
        sync_cash_flows("AAPL")
        sync_cash_flows("AAPL")
        assert QuarterlyCashFlow.objects.filter(ticker="AAPL").count() == 2


class TestSyncBalanceSheets:
    @patch("quotes.fmp.fetch_balance_sheets")
    def test_creates_balance_sheet_records(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_BALANCE_SHEETS
        sheets = sync_balance_sheets("AAPL")
        assert len(sheets) == 2
        assert BalanceSheet.objects.filter(ticker="AAPL").count() == 2

    @patch("quotes.fmp.fetch_balance_sheets")
    def test_stores_correct_values(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_BALANCE_SHEETS
        sync_balance_sheets("AAPL")
        record = BalanceSheet.objects.get(ticker="AAPL", end_date=date(2025, 9, 30))
        assert record.total_debt == 111000000000
        assert record.total_liabilities == 290000000000
        assert record.stockholders_equity == 62000000000
        assert record.current_assets == 143000000000
        assert record.current_liabilities == 153000000000
        assert record.total_lease is None

    @patch("quotes.fmp.fetch_balance_sheets")
    def test_updates_existing_records(self, mock_fetch, db):
        mock_fetch.return_value = MOCK_BALANCE_SHEETS
        sync_balance_sheets("AAPL")
        sync_balance_sheets("AAPL")
        assert BalanceSheet.objects.filter(ticker="AAPL").count() == 2


class TestSyncUSCPI:
    @patch("quotes.fmp._get")
    def test_creates_cpi_records(self, mock_get, db):
        mock_get.return_value = MOCK_CPI_RESPONSE
        count = sync_us_cpi()
        assert count == 4
        assert USCPIIndex.objects.count() == 4

    @patch("quotes.fmp._get")
    def test_stores_correct_values(self, mock_get, db):
        mock_get.return_value = MOCK_CPI_RESPONSE
        sync_us_cpi()
        entry = USCPIIndex.objects.get(date=date(2025, 1, 1))
        assert entry.annual_rate == Decimal("3.0")

    @patch("quotes.fmp._get")
    def test_updates_existing_records(self, mock_get, db):
        mock_get.return_value = MOCK_CPI_RESPONSE
        sync_us_cpi()
        sync_us_cpi()
        assert USCPIIndex.objects.count() == 4

    @patch("quotes.fmp._get")
    def test_skips_entries_without_value(self, mock_get, db):
        mock_get.return_value = [{"date": "2025-01-01", "value": None}]
        count = sync_us_cpi()
        assert count == 0
