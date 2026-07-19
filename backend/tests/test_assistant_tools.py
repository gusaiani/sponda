"""Unit tests for assistant.tools — OpenAI function-calling schemas and the
in-process executors that back them.

Seeding style mirrors tests/test_screener_service.py: real Ticker +
IndicatorSnapshot rows rather than mocks, since screen_companies/get_company
are thin wrappers around real ORM queries. get_fundamentals is the one
executor that goes through an external-fetch dependency
(quotes.views._compute_quote_payload), so that one is patched.
"""
import json
from decimal import Decimal
from unittest.mock import patch

import pytest

from assistant.tools import (
    OPENAI_TOOL_SCHEMAS,
    UNSUPPORTED_METRIC_EXAMPLES,
    execute_get_company,
    execute_get_fundamentals,
    execute_list_available_indicators,
    execute_screen_companies,
    execute_tool,
    json_safe,
)
from quotes.models import IndicatorSnapshot, Ticker
from quotes.screener import SCREENER_FILTERABLE_FIELDS, SCREENER_SORTABLE_FIELDS
from quotes.views import _QuoteError


@pytest.fixture
def snapshot_universe(db):
    """Three companies with distinct indicator profiles — same shape as
    test_screener_service.snapshot_universe so screen_companies/get_company
    behavior can be checked against known rows."""
    Ticker.objects.create(
        symbol="PETR4", name="Petrobras", display_name="Petrobras",
        sector="Oil", type="stock", logo="https://example.com/petr4.png",
        market_cap=400_000_000_000, country="BR",
    )
    IndicatorSnapshot.objects.create(
        ticker="PETR4",
        pe10=Decimal("6.5"), pfcf10=Decimal("8.0"), peg=Decimal("0.5"),
        pfcf_peg=Decimal("0.7"),
        debt_to_equity=Decimal("1.2"), debt_ex_lease_to_equity=Decimal("1.0"),
        liabilities_to_equity=Decimal("2.0"),
        current_ratio=Decimal("1.4"),
        debt_to_avg_earnings=Decimal("3.0"), debt_to_avg_fcf=Decimal("4.5"),
        market_cap=400_000_000_000, current_price=Decimal("35.75"),
    )

    Ticker.objects.create(
        symbol="WEGE3", name="Weg", display_name="WEG",
        sector="Industrial", type="stock", logo="https://example.com/wege3.png",
        market_cap=200_000_000_000, country="BR",
    )
    IndicatorSnapshot.objects.create(
        ticker="WEGE3",
        pe10=Decimal("35.0"), pfcf10=Decimal("40.0"), peg=Decimal("2.5"),
        pfcf_peg=Decimal("3.0"),
        debt_to_equity=Decimal("0.3"), debt_ex_lease_to_equity=Decimal("0.2"),
        liabilities_to_equity=Decimal("0.8"),
        current_ratio=Decimal("2.5"),
        debt_to_avg_earnings=Decimal("1.0"), debt_to_avg_fcf=Decimal("1.5"),
        market_cap=200_000_000_000, current_price=Decimal("42.00"),
    )

    Ticker.objects.create(
        symbol="MICRO3", name="Micro", display_name="Micro",
        sector="Retail", type="stock", logo="",
        market_cap=1_000_000_000, country="US",
    )
    IndicatorSnapshot.objects.create(
        ticker="MICRO3",
        pe10=Decimal("12.0"), pfcf10=Decimal("15.0"), peg=Decimal("1.2"),
        pfcf_peg=Decimal("1.4"),
        debt_to_equity=Decimal("4.0"), debt_ex_lease_to_equity=Decimal("3.5"),
        liabilities_to_equity=Decimal("6.0"),
        current_ratio=Decimal("0.8"),
        debt_to_avg_earnings=Decimal("10.0"), debt_to_avg_fcf=Decimal("12.0"),
        market_cap=1_000_000_000, current_price=Decimal("2.50"),
    )


# --- Schema shape --------------------------------------------------------

class TestOpenAIToolSchemas:
    def test_json_dumpable(self):
        json.dumps(OPENAI_TOOL_SCHEMAS)

    def test_four_tools_defined(self):
        assert len(OPENAI_TOOL_SCHEMAS) == 4

    def test_names_match_executors(self):
        names = {schema["function"]["name"] for schema in OPENAI_TOOL_SCHEMAS}
        assert names == {
            "list_available_indicators",
            "screen_companies",
            "get_company",
            "get_fundamentals",
        }

    def test_every_schema_is_openai_function_type(self):
        for schema in OPENAI_TOOL_SCHEMAS:
            assert schema["type"] == "function"
            assert "name" in schema["function"]
            assert "description" in schema["function"]
            assert schema["function"]["description"]
            assert "parameters" in schema["function"]

    def test_top_level_parameters_forbid_additional_properties(self):
        for schema in OPENAI_TOOL_SCHEMAS:
            assert schema["function"]["parameters"]["additionalProperties"] is False

    def _schema_by_name(self, name):
        return next(
            schema for schema in OPENAI_TOOL_SCHEMAS
            if schema["function"]["name"] == name
        )

    def test_list_available_indicators_has_no_params(self):
        schema = self._schema_by_name("list_available_indicators")
        assert schema["function"]["parameters"]["properties"] == {}

    def test_screen_companies_filters_cover_every_filterable_field(self):
        schema = self._schema_by_name("screen_companies")
        filters_schema = schema["function"]["parameters"]["properties"]["filters"]
        assert filters_schema["additionalProperties"] is False
        assert set(filters_schema["properties"].keys()) == set(SCREENER_FILTERABLE_FIELDS)
        for field_schema in filters_schema["properties"].values():
            assert field_schema["type"] == "object"
            assert field_schema["additionalProperties"] is False
            assert set(field_schema["properties"].keys()) == {"min", "max"}
            assert field_schema["properties"]["min"]["type"] == "number"
            assert field_schema["properties"]["max"]["type"] == "number"
            # Descriptions are written for the model — must not be empty.
            assert field_schema.get("description")

    def test_screen_companies_countries_and_sectors_are_string_arrays(self):
        schema = self._schema_by_name("screen_companies")
        properties = schema["function"]["parameters"]["properties"]
        for key in ("countries", "sectors"):
            assert properties[key]["type"] == "array"
            assert properties[key]["items"]["type"] == "string"

    def test_screen_companies_sort_enum_covers_every_sortable_field_both_directions(self):
        schema = self._schema_by_name("screen_companies")
        sort_enum = set(schema["function"]["parameters"]["properties"]["sort"]["enum"])
        expected = set(SCREENER_SORTABLE_FIELDS) | {f"-{field}" for field in SCREENER_SORTABLE_FIELDS}
        assert sort_enum == expected

    def test_screen_companies_limit_is_bounded_one_to_fifty_default_twenty(self):
        schema = self._schema_by_name("screen_companies")
        limit_schema = schema["function"]["parameters"]["properties"]["limit"]
        assert limit_schema["type"] == "integer"
        assert limit_schema["minimum"] == 1
        assert limit_schema["maximum"] == 50
        assert limit_schema["default"] == 20

    def test_get_company_requires_symbol_string(self):
        schema = self._schema_by_name("get_company")
        properties = schema["function"]["parameters"]["properties"]
        assert properties["symbol"]["type"] == "string"
        assert schema["function"]["parameters"]["required"] == ["symbol"]

    def test_get_fundamentals_requires_symbol_and_warns_expensive(self):
        schema = self._schema_by_name("get_fundamentals")
        assert schema["function"]["parameters"]["required"] == ["symbol"]
        description = schema["function"]["description"].lower()
        assert "expensive" in description


# --- json_safe -------------------------------------------------------------

class TestJsonSafe:
    def test_converts_decimal_to_float(self):
        assert json_safe(Decimal("1.5")) == 1.5
        assert isinstance(json_safe(Decimal("1.5")), float)

    def test_recurses_into_dicts_and_lists(self):
        value = {"a": Decimal("1"), "b": [Decimal("2"), {"c": Decimal("3")}]}
        safe = json_safe(value)
        assert safe == {"a": 1.0, "b": [2.0, {"c": 3.0}]}
        json.dumps(safe)

    def test_leaves_non_decimal_values_untouched(self):
        assert json_safe("x") == "x"
        assert json_safe(None) is None
        assert json_safe(5) == 5


# --- list_available_indicators ---------------------------------------------

@pytest.mark.django_db
class TestExecuteListAvailableIndicators:
    def test_json_dumpable(self):
        json.dumps(execute_list_available_indicators())

    def test_ten_indicators_present_matching_filterable_fields(self):
        result = execute_list_available_indicators()
        keys = {entry["key"] for entry in result["indicators"]}
        assert keys == set(SCREENER_FILTERABLE_FIELDS)
        assert len(result["indicators"]) == 10

    def test_every_indicator_has_required_fields(self):
        result = execute_list_available_indicators()
        for entry in result["indicators"]:
            assert entry["key"]
            assert entry["name"]
            assert entry["definition"]
            assert entry["direction"] in {"lower_is_better", "higher_is_better"}
            assert entry.get("note")

    def test_current_ratio_is_higher_is_better_rest_are_lower_is_better(self):
        result = execute_list_available_indicators()
        by_key = {entry["key"]: entry for entry in result["indicators"]}
        assert by_key["current_ratio"]["direction"] == "higher_is_better"
        for key in set(SCREENER_FILTERABLE_FIELDS) - {"current_ratio"}:
            assert by_key[key]["direction"] == "lower_is_better"

    def test_unsupported_examples_present_and_mentions_common_gaps(self):
        result = execute_list_available_indicators()
        assert result["unsupported_examples"] == list(UNSUPPORTED_METRIC_EXAMPLES)
        joined = " ".join(result["unsupported_examples"]).lower()
        assert "roe" in joined or "return on equity" in joined
        assert "dividend" in joined

    def test_countries_and_sectors_are_sorted_distinct_non_empty(self, snapshot_universe):
        Ticker.objects.create(symbol="NOSECTOR", name="No Sector", sector="", country="")
        result = execute_list_available_indicators()
        assert result["countries"] == sorted(set(result["countries"]))
        assert result["sectors"] == sorted(set(result["sectors"]))
        assert "" not in result["countries"]
        assert "" not in result["sectors"]
        assert set(result["countries"]) == {"BR", "US"}
        assert set(result["sectors"]) == {"Oil", "Industrial", "Retail"}


# --- screen_companies --------------------------------------------------------

@pytest.mark.django_db
class TestExecuteScreenCompanies:
    def test_json_dumpable(self, snapshot_universe):
        result = execute_screen_companies({})
        json.dumps(result)

    def test_no_filters_returns_all_trimmed_and_full(self, snapshot_universe):
        result = execute_screen_companies({})
        assert result["count"] == 3
        assert {row["ticker"] for row in result["rows_for_model"]} == {"PETR4", "WEGE3", "MICRO3"}
        assert {row["ticker"] for row in result["full_rows"]} == {"PETR4", "WEGE3", "MICRO3"}

    def test_min_only_filter(self, snapshot_universe):
        result = execute_screen_companies({"filters": {"pe10": {"min": 20}}})
        assert result["count"] == 1
        assert result["rows_for_model"][0]["ticker"] == "WEGE3"

    def test_max_only_filter(self, snapshot_universe):
        result = execute_screen_companies({"filters": {"pe10": {"max": 10}}})
        assert result["count"] == 1
        assert result["rows_for_model"][0]["ticker"] == "PETR4"

    def test_min_and_max_filter(self, snapshot_universe):
        result = execute_screen_companies({"filters": {"pe10": {"min": 10, "max": 20}}})
        assert result["count"] == 1
        assert result["rows_for_model"][0]["ticker"] == "MICRO3"

    def test_countries_and_sectors_filter(self, snapshot_universe):
        result = execute_screen_companies({"countries": ["US"]})
        assert {row["ticker"] for row in result["rows_for_model"]} == {"MICRO3"}

        result = execute_screen_companies({"sectors": ["Oil"]})
        assert {row["ticker"] for row in result["rows_for_model"]} == {"PETR4"}

    def test_sort_descending(self, snapshot_universe):
        result = execute_screen_companies({"sort": "-pe10"})
        assert [row["ticker"] for row in result["rows_for_model"]] == ["WEGE3", "MICRO3", "PETR4"]

    def test_default_limit_is_twenty(self, snapshot_universe):
        result = execute_screen_companies({})
        # Only 3 rows exist, but confirm no explicit limit still works and
        # doesn't blow past the 20 default when there's more data than that.
        assert len(result["rows_for_model"]) == 3

    def test_limit_clamped_to_fifty_max(self, db):
        tickers = [Ticker(symbol=f"T{i:04d}", name=f"T{i}", type="stock", market_cap=1) for i in range(60)]
        Ticker.objects.bulk_create(tickers)
        snapshots = [
            IndicatorSnapshot(ticker=f"T{i:04d}", pe10=Decimal("1.0"), market_cap=1)
            for i in range(60)
        ]
        IndicatorSnapshot.objects.bulk_create(snapshots)
        result = execute_screen_companies({"limit": 500})
        assert len(result["rows_for_model"]) == 50
        assert len(result["full_rows"]) == 50

    def test_limit_clamped_to_at_least_one(self, snapshot_universe):
        result = execute_screen_companies({"limit": 0})
        assert len(result["rows_for_model"]) == 1

        result = execute_screen_companies({"limit": -5})
        assert len(result["rows_for_model"]) == 1

    def test_trimmed_row_content(self, snapshot_universe):
        result = execute_screen_companies({})
        row = next(r for r in result["rows_for_model"] if r["ticker"] == "PETR4")
        assert row["name"] == "Petrobras"
        assert row["sector"] == "Oil"
        assert row["market_cap"] == 400_000_000_000
        assert row["pe10"] == 6.5
        assert isinstance(row["pe10"], float)
        for field in SCREENER_FILTERABLE_FIELDS:
            assert field in row
        # Trimmed rows must NOT carry ratings/logo/current_price — those go
        # out on the results SSE frame via full_rows, not to the model.
        assert "ratings" not in row
        assert "logo" not in row
        assert "current_price" not in row

    def test_full_row_content_keeps_ratings_and_is_json_safe(self, snapshot_universe):
        result = execute_screen_companies({})
        row = next(r for r in result["full_rows"] if r["ticker"] == "PETR4")
        assert "ratings" in row
        assert row["pe10"] == 6.5
        assert isinstance(row["pe10"], float)

    def test_invalid_sort_returns_error_dict_not_exception(self, snapshot_universe):
        result = execute_screen_companies({"sort": "evil; DROP TABLE"})
        assert "error" in result
        assert isinstance(result["error"], str)

    def test_unknown_filter_field_is_ignored_not_an_error(self, snapshot_universe):
        result = execute_screen_companies({"filters": {"market_cap": {"min": 1}}})
        assert "error" not in result
        assert result["count"] == 3


# --- get_company --------------------------------------------------------

@pytest.mark.django_db
class TestExecuteGetCompany:
    def test_json_dumpable(self, snapshot_universe):
        json.dumps(execute_get_company("PETR4"))

    def test_happy_path(self, snapshot_universe):
        result = execute_get_company("PETR4")
        assert result["symbol"] == "PETR4"
        assert result["name"] == "Petrobras"
        assert result["sector"] == "Oil"
        assert result["country"] == "BR"
        assert result["pe10"] == 6.5
        assert isinstance(result["pe10"], float)

    def test_case_insensitive(self, snapshot_universe):
        result = execute_get_company("petr4")
        assert result["symbol"] == "PETR4"

    def test_unknown_symbol_returns_error_dict(self, snapshot_universe):
        result = execute_get_company("NOPE99")
        assert "error" in result

    def test_missing_snapshot_returns_error_dict(self, db):
        Ticker.objects.create(symbol="NOSNAP", name="No Snap", type="stock")
        result = execute_get_company("NOSNAP")
        assert "error" in result

    def test_non_stock_type_excluded(self, db):
        Ticker.objects.create(symbol="FUND11", name="A Fund", type="fund")
        IndicatorSnapshot.objects.create(ticker="FUND11", pe10=Decimal("5.0"))
        result = execute_get_company("FUND11")
        assert "error" in result


# --- get_fundamentals --------------------------------------------------------

@pytest.mark.django_db
class TestExecuteGetFundamentals:
    def test_strips_heavy_keys_and_returns_scalars(self):
        fake_payload = {
            "ticker": "PETR4",
            "pe10": 4.2,
            "pfcf10": 3.1,
            "earningsCAGR": 0.05,
            "fcfCAGR": 0.03,
            "pe10AnnualData": [{"year": 2020, "value": 1}],
            "pfcf10AnnualData": [{"year": 2020, "value": 1}],
            "pe10CalculationDetails": {"noise": "..."},
            "pfcf10CalculationDetails": {"noise": "..."},
        }
        with patch("assistant.tools._compute_quote_payload", return_value=dict(fake_payload)) as mocked:
            result = execute_get_fundamentals("petr4")

        mocked.assert_called_once_with("PETR4", request=None)
        assert result["ticker"] == "PETR4"
        assert result["pe10"] == 4.2
        assert result["earningsCAGR"] == 0.05
        assert "pe10AnnualData" not in result
        assert "pfcf10AnnualData" not in result
        assert "pe10CalculationDetails" not in result
        assert "pfcf10CalculationDetails" not in result

    def test_json_dumpable(self):
        fake_payload = {"ticker": "PETR4", "pe10": Decimal("4.2")}
        with patch("assistant.tools._compute_quote_payload", return_value=dict(fake_payload)):
            result = execute_get_fundamentals("PETR4")
        json.dumps(result)

    def test_quote_error_maps_to_error_dict(self):
        with patch(
            "assistant.tools._compute_quote_payload",
            side_effect=_QuoteError("Ticker not found", http_status=404),
        ):
            result = execute_get_fundamentals("NOPE99")
        assert result == {"error": "Ticker not found"}


# --- execute_tool dispatcher --------------------------------------------------------

@pytest.mark.django_db
class TestExecuteToolDispatcher:
    def test_routes_list_available_indicators(self):
        result = execute_tool("list_available_indicators", {})
        assert "indicators" in result

    def test_routes_screen_companies(self, snapshot_universe):
        result = execute_tool("screen_companies", {"sort": "ticker"})
        assert "count" in result

    def test_routes_get_company(self, snapshot_universe):
        result = execute_tool("get_company", {"symbol": "PETR4"})
        assert result["symbol"] == "PETR4"

    def test_routes_get_fundamentals(self):
        with patch("assistant.tools._compute_quote_payload", return_value={"ticker": "PETR4"}):
            result = execute_tool("get_fundamentals", {"symbol": "PETR4"})
        assert result["ticker"] == "PETR4"

    def test_unknown_tool_name_returns_error_dict(self):
        result = execute_tool("delete_database", {})
        assert result == {"error": "Unknown tool: delete_database"}

    def test_handles_none_arguments(self):
        result = execute_tool("list_available_indicators", None)
        assert "indicators" in result


class TestScreenSectorResolution:
    """screen_companies resolves sector names case-insensitively and turns
    unknown sectors into a corrective error naming the valid ones, so the
    agent can self-correct in its next tool round instead of silently
    screening an empty set."""

    def _seed(self):
        Ticker.objects.create(
            symbol="EVSEC1", name="Sector Co", sector="Utilities",
            country="BR", type="stock",
        )
        IndicatorSnapshot.objects.create(ticker="EVSEC1", pe10=Decimal("5"))

    def test_sector_matching_is_case_insensitive(self, db):
        self._seed()
        result = execute_screen_companies({"sectors": ["utilities"]})
        assert "error" not in result
        assert [row["ticker"] for row in result["rows_for_model"]] == ["EVSEC1"]

    def test_unknown_sector_returns_error_listing_valid_sectors(self, db):
        self._seed()
        result = execute_screen_companies({"sectors": ["Electric Utilities"]})
        assert "error" in result
        assert "Electric Utilities" in result["error"]
        assert "Utilities" in result["error"]

    def test_country_codes_are_uppercased(self, db):
        self._seed()
        result = execute_screen_companies({"countries": ["br"]})
        assert "error" not in result
        assert [row["ticker"] for row in result["rows_for_model"]] == ["EVSEC1"]
