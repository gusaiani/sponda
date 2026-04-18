"""Tests for FMP API client with mocked API responses."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from quotes.fmp import (
    FMPError,
    fetch_balance_sheets,
    fetch_cash_flow_statements,
    fetch_dividends,
    fetch_etf_symbols,
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
        "netCashProvidedByInvestingActivities": -4500000000,
        "netCashProvidedByFinancingActivities": -22000000000,
        "capitalExpenditure": -2800000000,
        "freeCashFlow": 24100000000,
        "commonDividendsPaid": -3800000000,
    },
    {
        "date": "2025-06-30",
        "symbol": "AAPL",
        "operatingCashFlow": 28500000000,
        "netCashProvidedByInvestingActivities": -3900000000,
        "netCashProvidedByFinancingActivities": -25000000000,
        "capitalExpenditure": -2600000000,
        "freeCashFlow": 25900000000,
        "commonDividendsPaid": -3700000000,
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
    {"date": "2025-01-02", "close": 178.5, "volume": 50000000},
    {"date": "2024-12-31", "close": 175.0, "volume": 45000000},
    {"date": "2024-11-29", "close": 170.0, "volume": 48000000},
]

MOCK_DIVIDENDS = [
    {"date": "2025-02-07", "adjDividend": 0.25, "dividend": 0.25, "recordDate": "2025-02-10", "paymentDate": "2025-02-13"},
    {"date": "2024-11-08", "adjDividend": 0.25, "dividend": 0.25, "recordDate": "2024-11-11", "paymentDate": "2024-11-14"},
]

MOCK_CPI_RESPONSE = [
    {"date": "2025-12-01", "value": 320.0, "name": "CPI"},
    {"date": "2025-01-01", "value": 310.0, "name": "CPI"},
    {"date": "2024-12-01", "value": 310.0, "name": "CPI"},
    {"date": "2024-01-01", "value": 300.0, "name": "CPI"},
    {"date": "2023-12-01", "value": 300.0, "name": "CPI"},
    {"date": "2023-01-01", "value": 290.0, "name": "CPI"},
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
            "/stable/cash-flow-statement",
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
        assert result[0]["close"] == 178.5

    @patch("quotes.fmp._get")
    def test_requests_full_history_from_2000(self, mock_get):
        mock_get.return_value = MOCK_HISTORICAL_PRICES
        fetch_historical_prices("AAPL")
        mock_get.assert_called_once_with(
            "/stable/historical-price-eod/full",
            params={"symbol": "AAPL", "from": "2000-01-01"},
        )

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


def _synthetic_income_statements(count: int) -> list[dict]:
    return [
        {
            "date": f"20{25 - (i // 4):02d}-{((i % 4) * 3 + 1):02d}-15",
            "symbol": "AAPL",
            "revenue": 1000 + i,
            "netIncome": 500 + i,
            "eps": 1.0 + i * 0.01,
        }
        for i in range(count)
    ]


def _synthetic_cash_flow_statements(count: int) -> list[dict]:
    return [
        {
            "date": f"20{25 - (i // 4):02d}-{((i % 4) * 3 + 1):02d}-15",
            "symbol": "AAPL",
            "operatingCashFlow": 1000 + i,
            "netCashProvidedByInvestingActivities": -100 - i,
            "commonDividendsPaid": -50 - i,
        }
        for i in range(count)
    ]


def _synthetic_balance_sheets(count: int) -> list[dict]:
    return [
        {
            "date": f"20{25 - (i // 4):02d}-{((i % 4) * 3 + 1):02d}-15",
            "symbol": "AAPL",
            "totalDebt": 1000 + i,
            "totalLiabilities": 5000 + i,
            "totalStockholdersEquity": 2000 + i,
            "totalCurrentAssets": 3000 + i,
            "totalCurrentLiabilities": 1500 + i,
        }
        for i in range(count)
    ]


# Tight bound — one upsert + at most a couple of surrounding statements
# (e.g. a savepoint from an ambient transaction). The pre-fix loop issued
# 2 queries per row, so this would have been ~40 for 20 statements.
MAX_QUERIES_PER_SYNC = 5


class TestSyncEarningsIsBulk:
    @patch("quotes.fmp.fetch_income_statements")
    def test_uses_constant_query_count_regardless_of_row_count(self, mock_fetch, db):
        mock_fetch.return_value = _synthetic_income_statements(20)
        with CaptureQueriesContext(connection) as captured:
            earnings = sync_earnings("AAPL")
        assert len(earnings) == 20
        assert QuarterlyEarnings.objects.filter(ticker="AAPL").count() == 20
        assert len(captured) <= MAX_QUERIES_PER_SYNC, (
            f"Expected ≤{MAX_QUERIES_PER_SYNC} queries, got {len(captured)}:\n"
            + "\n".join(q["sql"] for q in captured)
        )

    @patch("quotes.fmp.fetch_income_statements")
    def test_upsert_preserves_data_on_second_sync(self, mock_fetch, db):
        mock_fetch.return_value = _synthetic_income_statements(5)
        sync_earnings("AAPL")
        mock_fetch.return_value = [
            {**stmt, "netIncome": (stmt["netIncome"] or 0) + 1}
            for stmt in _synthetic_income_statements(5)
        ]
        sync_earnings("AAPL")
        assert QuarterlyEarnings.objects.filter(ticker="AAPL").count() == 5
        latest = QuarterlyEarnings.objects.get(ticker="AAPL", end_date=date(2025, 1, 15))
        assert latest.net_income == 501


class TestSyncCashFlowsIsBulk:
    @patch("quotes.fmp.fetch_cash_flow_statements")
    def test_uses_constant_query_count_regardless_of_row_count(self, mock_fetch, db):
        mock_fetch.return_value = _synthetic_cash_flow_statements(20)
        with CaptureQueriesContext(connection) as captured:
            cash_flows = sync_cash_flows("AAPL")
        assert len(cash_flows) == 20
        assert QuarterlyCashFlow.objects.filter(ticker="AAPL").count() == 20
        assert len(captured) <= MAX_QUERIES_PER_SYNC, (
            f"Expected ≤{MAX_QUERIES_PER_SYNC} queries, got {len(captured)}:\n"
            + "\n".join(q["sql"] for q in captured)
        )


class TestSyncBalanceSheetsIsBulk:
    @patch("quotes.fmp.fetch_balance_sheets")
    def test_uses_constant_query_count_regardless_of_row_count(self, mock_fetch, db):
        mock_fetch.return_value = _synthetic_balance_sheets(20)
        with CaptureQueriesContext(connection) as captured:
            sheets = sync_balance_sheets("AAPL")
        assert len(sheets) == 20
        assert BalanceSheet.objects.filter(ticker="AAPL").count() == 20
        assert len(captured) <= MAX_QUERIES_PER_SYNC, (
            f"Expected ≤{MAX_QUERIES_PER_SYNC} queries, got {len(captured)}:\n"
            + "\n".join(q["sql"] for q in captured)
        )


class TestSyncUSCPI:
    @patch("quotes.fmp._get")
    def test_computes_yoy_rates_from_index(self, mock_get, db):
        mock_get.return_value = MOCK_CPI_RESPONSE
        count = sync_us_cpi()
        # 6 records but only 4 have a prior-year match (2025-12, 2025-01, 2024-12, 2024-01)
        assert count == 4
        assert USCPIIndex.objects.count() == 4

    @patch("quotes.fmp._get")
    def test_stores_correct_yoy_rate(self, mock_get, db):
        mock_get.return_value = MOCK_CPI_RESPONSE
        sync_us_cpi()
        # 2025-01: (310/300 - 1) * 100 = 3.3333%
        entry = USCPIIndex.objects.get(date=date(2025, 1, 1))
        assert abs(float(entry.annual_rate) - 3.3333) < 0.01

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


class TestFetchEtfSymbols:
    @patch("quotes.fmp._get")
    def test_returns_uppercase_symbols(self, mock_get):
        mock_get.return_value = [
            {"symbol": "SPY", "name": "SPDR S&P 500 ETF"},
            {"symbol": "QQQ", "name": "Invesco QQQ Trust"},
        ]
        result = fetch_etf_symbols()
        assert result == {"SPY", "QQQ"}

    @patch("quotes.fmp._get")
    def test_handles_empty_response(self, mock_get):
        mock_get.return_value = []
        result = fetch_etf_symbols()
        assert result == set()

    @patch("quotes.fmp._get")
    def test_handles_non_list_response(self, mock_get):
        mock_get.return_value = {"error": "something"}
        result = fetch_etf_symbols()
        assert result == set()

    @patch("quotes.fmp._get")
    def test_skips_entries_without_symbol(self, mock_get):
        mock_get.return_value = [
            {"symbol": "SPY", "name": "SPDR"},
            {"name": "No Symbol"},
            {"symbol": "", "name": "Empty"},
        ]
        result = fetch_etf_symbols()
        assert result == {"SPY"}


class TestFetchQuotesBatch:
    @patch("quotes.fmp._get")
    def test_returns_dict_keyed_by_symbol(self, mock_get):
        mock_get.return_value = [
            {"symbol": "AAPL", "price": 178.72, "marketCap": 2_800_000_000_000},
            {"symbol": "MSFT", "price": 420.0, "marketCap": 3_000_000_000_000},
        ]
        from quotes.fmp import fetch_quotes_batch
        result = fetch_quotes_batch(["AAPL", "MSFT"])
        assert result["AAPL"]["price"] == 178.72
        assert result["MSFT"]["marketCap"] == 3_000_000_000_000

    @patch("quotes.fmp._get")
    def test_passes_comma_separated_symbols(self, mock_get):
        mock_get.return_value = []
        from quotes.fmp import fetch_quotes_batch
        fetch_quotes_batch(["AAPL", "MSFT"])
        mock_get.assert_called_once_with("/stable/quote", params={"symbol": "AAPL,MSFT"})

    @patch("quotes.fmp._get")
    def test_empty_list_returns_empty_dict_without_api_call(self, mock_get):
        from quotes.fmp import fetch_quotes_batch
        result = fetch_quotes_batch([])
        assert result == {}
        mock_get.assert_not_called()

    @patch("quotes.fmp._get")
    def test_chunks_tickers_larger_than_batch_size(self, mock_get):
        mock_get.return_value = []
        from quotes.fmp import FMP_BATCH_SIZE, fetch_quotes_batch
        tickers = [f"TIC{i}" for i in range(FMP_BATCH_SIZE + 5)]
        fetch_quotes_batch(tickers)
        assert mock_get.call_count == 2
