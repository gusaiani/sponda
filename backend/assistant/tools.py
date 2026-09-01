"""OpenAI function-calling tool schemas and executors for the screening agent.

Pure request/response functions — no OpenAI SDK calls, no streaming. The
bounded tool-calling loop in assistant.agent drives these via execute_tool()
and feeds the returned dict back to the model as a tool message. Every
executor always returns a plain, json.dumps-able dict: a lookup or screener
failure comes back as ``{"error": "..."}`` data for the model to reason
about, never as a raised exception the loop has to special-case.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from quotes.company_snapshot import company_snapshot
from quotes.json_utils import json_safe
from quotes.models import (
    DEBT_COVERAGE_FIELDS,
    Ticker,
    debt_coverage_window_field,
)
from quotes.pe10 import LOOSE_AVERAGE_MAX_YEARS, PE_WINDOW_MAX_YEARS, PE_WINDOW_YEARS
from quotes.screener import (
    DEBT_WINDOW_MAX_YEARS,
    DEBT_WINDOW_MIN_YEARS,
    SCREENER_DEFAULT_SORT,
    SCREENER_FILTERABLE_FIELDS,
    SCREENER_SORTABLE_FIELDS,
    ScreenerError,
    run_screener,
    validate_debt_window_years,
)
from quotes.views import _QuoteError, _compute_quote_payload

# screen_companies caps rows returned to the model well below the raw
# screener API's ceiling (quotes.screener.SCREENER_MAX_LIMIT=500) — the
# agent's job is to reason over a handful of names, not paginate a table.
DEFAULT_SCREEN_LIMIT = 20
MAX_SCREEN_LIMIT = 50

# quote payload keys stripped from get_fundamentals' response: verbose
# year-by-year series and intermediate-calculation dumps the model doesn't
# need to answer a single-company follow-up, and that would otherwise
# balloon every tool round's token cost.
FUNDAMENTALS_STRIPPED_KEYS = (
    "pe10AnnualData",
    "pfcf10AnnualData",
    "pe10CalculationDetails",
    "pfcf10CalculationDetails",
)

# --- Indicator catalogue ----------------------------------------------
#
# Single source of truth for indicator metadata: list_available_indicators
# returns this catalogue verbatim, and screen_companies' per-field filter
# descriptions are generated from it below, so the two tool-facing surfaces
# can never drift apart. Order matches quotes.screener.SCREENER_FILTERABLE_FIELDS.

def _pe_window_catalogue_entry(years: int) -> dict[str, str]:
    """Catalogue entry for one strict P/E window (PE1..PE15)."""
    shiller_suffix = " (Shiller P/E)" if years == 10 else ""
    year_word = "year" if years == 1 else "years"
    return {
        "key": f"pe{years}",
        "name": f"P/E{years}{shiller_suffix}",
        "definition": (
            f"Market cap divided by inflation-adjusted average net income "
            f"over exactly {years} {year_word}."
        ),
        "direction": "lower_is_better",
        "note": (
            f"Strict window: empty unless the company has the full {years} "
            f"{year_word} of earnings history — pe_years_available tells "
            "the widest window a company can honestly fill. Cheap is "
            "typically below 10; expensive is above 20; shorter windows "
            "react faster but are noisier."
        ),
    }


PE_YEARS_AVAILABLE_CATALOGUE_ENTRY: dict[str, str] = {
    "key": "pe_years_available",
    "name": "P/E window years available",
    "definition": (
        "Number of complete years of earnings history available to the "
        f"strict P/E windows (maximum {PE_WINDOW_MAX_YEARS})."
    ),
    "direction": "higher_is_better",
    "note": (
        "peY is empty whenever Y exceeds this value; the widest honest "
        "window for a company is PE{pe_years_available}. Filter min=10 to "
        "demand a full decade of history."
    ),
}

# Shared by both debt-coverage catalogue entries and the tool parameter, so
# the model reads the same contract wherever it looks.
DEBT_WINDOW_NOTE = (
    f"By default the average spans up to {LOOSE_AVERAGE_MAX_YEARS} years of "
    "history (a company with 6 years is averaged over 6). Pass "
    "debt_window_years to demand exactly N years: the value is then empty "
    "for companies without N full years, like the strict P/E windows."
)

INDICATOR_CATALOGUE: tuple[dict[str, str], ...] = (
    *(_pe_window_catalogue_entry(years) for years in PE_WINDOW_YEARS),
    PE_YEARS_AVAILABLE_CATALOGUE_ENTRY,
    {
        "key": "pfcf10",
        "name": "P/FCF10",
        "definition": (
            "Market cap divided by inflation-adjusted average free cash "
            "flow over up to 10 years."
        ),
        "direction": "lower_is_better",
        "note": (
            "Same idea as P/E10 but built on free cash flow instead of "
            "net income. Cheap is typically below 10."
        ),
    },
    {
        "key": "peg",
        "name": "PEG (P/E10-to-growth)",
        "definition": "P/E10 divided by the long-term earnings growth rate (CAGR).",
        "direction": "lower_is_better",
        "note": (
            "Below 1 suggests the price is not fully pricing in growth; "
            "above 2 suggests growth is priced aggressively."
        ),
    },
    {
        "key": "pfcf_peg",
        "name": "PFCF-PEG (P/FCF10-to-growth)",
        "definition": (
            "P/FCF10 divided by the long-term free-cash-flow growth rate (CAGR)."
        ),
        "direction": "lower_is_better",
        "note": (
            "Same idea as PEG but built on free-cash-flow growth instead "
            "of earnings growth."
        ),
    },
    {
        "key": "debt_to_equity",
        "name": "Debt / Equity",
        "definition": (
            "Total debt (loans plus lease obligations) divided by "
            "stockholders' equity."
        ),
        "direction": "lower_is_better",
        "note": "Below 1 is conservative leverage; above 2 is elevated leverage.",
    },
    {
        "key": "debt_ex_lease_to_equity",
        "name": "Debt (ex-lease) / Equity",
        "definition": (
            "Total debt excluding lease obligations, divided by "
            "stockholders' equity."
        ),
        "direction": "lower_is_better",
        "note": (
            "Same as debt_to_equity but strips lease liabilities out of "
            "the numerator — useful for comparing heavy lessees against "
            "companies that own outright."
        ),
    },
    {
        "key": "liabilities_to_equity",
        "name": "Liabilities / Equity",
        "definition": (
            "Total liabilities (every obligation, not just interest-bearing "
            "debt) divided by stockholders' equity."
        ),
        "direction": "lower_is_better",
        "note": (
            "Broader than debt_to_equity — also captures payables, "
            "provisions, and other non-debt liabilities."
        ),
    },
    {
        "key": "current_ratio",
        "name": "Current Ratio",
        "definition": "Current assets divided by current liabilities.",
        "direction": "higher_is_better",
        "note": (
            "Above 1.5 suggests comfortable short-term liquidity; below 1 "
            "signals the company may struggle to cover near-term obligations."
        ),
    },
    {
        "key": "debt_to_avg_earnings",
        "name": "Debt / Average Earnings",
        "definition": "Total debt divided by average inflation-adjusted net income.",
        "direction": "lower_is_better",
        "note": (
            "Years of average earnings needed to fully repay total debt. "
            "Lower means debt is easier to pay down. "
            + DEBT_WINDOW_NOTE
        ),
    },
    {
        "key": "debt_to_avg_fcf",
        "name": "Debt / Average FCF",
        "definition": (
            "Total debt divided by average inflation-adjusted free cash flow."
        ),
        "direction": "lower_is_better",
        "note": (
            "Years of average free cash flow needed to repay total debt. "
            "Lower means debt is easier to pay down from cash generation. "
            + DEBT_WINDOW_NOTE
        ),
    },
)

INDICATOR_BY_KEY = {entry["key"]: entry for entry in INDICATOR_CATALOGUE}

# Metrics Sponda deliberately does not track, so the model can decline a
# request precisely ("Sponda doesn't have dividend yield") instead of
# fabricating a number or silently ignoring part of the question.
UNSUPPORTED_METRIC_EXAMPLES = (
    "ROE (return on equity)",
    "dividend yield",
    "revenue growth",
    "analyst price targets",
    "news or recent events",
)




def _filter_property_schema(field: str) -> dict:
    """JSON Schema for one screen_companies filter property, described for
    the model from the indicator catalogue entry so units/direction and the
    "missing values are excluded" caveat are never forgotten per-field."""
    entry = INDICATOR_BY_KEY[field]
    return {
        "type": "object",
        "description": (
            f"{entry['name']}: {entry['definition']} {entry['note']} "
            f"({entry['direction']}). Omit a bound to leave it open. "
            "Companies with no value for this indicator are excluded by "
            "any bound set here, even if they might otherwise qualify."
        ),
        "properties": {
            "min": {
                "type": "number",
                "description": f"Minimum {entry['name']} (inclusive).",
            },
            "max": {
                "type": "number",
                "description": f"Maximum {entry['name']} (inclusive).",
            },
        },
        "additionalProperties": False,
    }


_SORT_ENUM = [
    *SCREENER_SORTABLE_FIELDS,
    *(f"-{field}" for field in SCREENER_SORTABLE_FIELDS),
]

_DEBT_WINDOW_YEARS_SCHEMA = {
    "type": "integer",
    "minimum": DEBT_WINDOW_MIN_YEARS,
    "maximum": DEBT_WINDOW_MAX_YEARS,
    "description": (
        "Years of history behind debt_to_avg_earnings and debt_to_avg_fcf. "
        f"An integer from {DEBT_WINDOW_MIN_YEARS} to {DEBT_WINDOW_MAX_YEARS}: "
        "both ratios then divide total debt by the average over exactly "
        "that many years, and are empty for companies lacking that much "
        "history (a bound excludes them; a sort puts them last). Omit for "
        f"the loose average over up to {LOOSE_AVERAGE_MAX_YEARS} years. "
        "Other indicators are unaffected."
    ),
}

OPENAI_TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "list_available_indicators",
            "description": (
                "List every indicator Sponda can screen and sort companies "
                "by, the full list of countries and sectors present in the "
                "data, and examples of metrics Sponda does NOT have. Call "
                "this first when unsure which indicator key to use, or to "
                "precisely decline a request for an unsupported metric "
                "(e.g. ROE, dividend yield) instead of guessing."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screen_companies",
            "description": (
                "Filter, sort, and rank companies by Sponda's indicators, "
                "country, and sector. Returns the matching count plus a page "
                f"of rows ({DEFAULT_SCREEN_LIMIT} by default, "
                f"{MAX_SCREEN_LIMIT} max) — never the full universe. Filters "
                "are ANDed together; a company missing a value for a "
                "filtered indicator is excluded, never assumed to pass."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filters": {
                        "type": "object",
                        "description": (
                            "One optional min/max bound per indicator. Keys "
                            "must be indicator keys returned by "
                            "list_available_indicators."
                        ),
                        "properties": {
                            field: _filter_property_schema(field)
                            for field in SCREENER_FILTERABLE_FIELDS
                        },
                        "additionalProperties": False,
                    },
                    "countries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "ISO 3166-1 alpha-2 country codes to include "
                            "(e.g. 'BR', 'US'). Omit or leave empty for all "
                            "countries."
                        ),
                    },
                    "sectors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Sector names to include, exactly as returned by "
                            "list_available_indicators. Omit or leave empty "
                            "for all sectors."
                        ),
                    },
                    "sort": {
                        "type": "string",
                        "enum": _SORT_ENUM,
                        "description": (
                            "Field to sort by. A plain field name sorts "
                            "ascending (smallest value first); a '-' prefix "
                            "sorts descending — e.g. '-market_cap' returns "
                            "the largest companies first, and '-pe10' "
                            "returns the highest (most expensive) P/E10 "
                            "first. Defaults to 'ticker' if omitted. Rows "
                            "with no value for the sort field always sort "
                            "last, in either direction."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": MAX_SCREEN_LIMIT,
                        "default": DEFAULT_SCREEN_LIMIT,
                        "description": (
                            f"Max rows to return, {DEFAULT_SCREEN_LIMIT} by "
                            f"default, capped at {MAX_SCREEN_LIMIT}. Raise "
                            "it only when the user explicitly asks for more "
                            "names."
                        ),
                    },
                    "debt_window_years": _DEBT_WINDOW_YEARS_SCHEMA,
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_company",
            "description": (
                "Look up one company's metadata and current indicator "
                "values by ticker symbol. Cheap — safe to call freely to "
                "resolve a symbol the user named or that appeared in "
                "screen_companies results."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": (
                            "Ticker symbol, case-insensitive (e.g. 'PETR4', 'aapl')."
                        ),
                    },
                    "debt_window_years": _DEBT_WINDOW_YEARS_SCHEMA,
                },
                "required": ["symbol"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fundamentals",
            "description": (
                "Fetch the full fundamentals payload for one company. "
                "EXPENSIVE — triggers a live market-data provider fetch and "
                "a database recomputation, unlike get_company or "
                "screen_companies. Only call this for a specific follow-up "
                "question about ONE company the user has already named or "
                "selected — never in a loop over many companies, and never "
                "as a substitute for screen_companies."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": (
                            "Ticker symbol, case-insensitive (e.g. 'PETR4', 'aapl')."
                        ),
                    },
                },
                "required": ["symbol"],
                "additionalProperties": False,
            },
        },
    },
]


def execute_list_available_indicators() -> dict:
    """Static indicator catalogue + live country/sector lists.

    The country/sector queries mirror quotes.views.ScreenerCountriesView /
    ScreenerSectorsView exactly, so the model's dropdown-equivalent stays in
    sync with whatever the actual screener UI offers.
    """
    countries = list(
        Ticker.objects.exclude(country="")
        .values_list("country", flat=True)
        .distinct()
        .order_by("country"),
    )
    sectors = list(
        Ticker.objects.exclude(sector="")
        .values_list("sector", flat=True)
        .distinct()
        .order_by("sector"),
    )
    return {
        "indicators": [dict(entry) for entry in INDICATOR_CATALOGUE],
        "countries": countries,
        "sectors": sectors,
        "unsupported_examples": list(UNSUPPORTED_METRIC_EXAMPLES),
    }


def _resolve_filter_bounds(
    filters: Optional[dict],
) -> tuple[dict, Optional[str]]:
    """Convert the model's {field: {min?, max?}} JSON numbers into the
    {field: {min?: Decimal, max?: Decimal}} shape run_screener expects.

    Returns (bounds, error). Malformed input — an unknown indicator key, a
    non-object bound, a non-numeric min/max — returns a corrective error
    naming what is valid, never silently drops the filter: a dropped filter
    means the caller believes it screened and it did not (the same
    observed-live failure mode _resolve_sectors exists to prevent).
    """
    if filters is None:
        return {}, None
    if not isinstance(filters, dict):
        return {}, (
            "filters must be an object mapping indicator keys to "
            "{min, max} bounds."
        )

    unknown_fields = [
        field for field in filters if field not in SCREENER_FILTERABLE_FIELDS
    ]
    if unknown_fields:
        return {}, (
            f"Unknown indicator(s) in filters: "
            f"{', '.join(repr(field) for field in unknown_fields)}. "
            f"Valid indicator keys are: "
            f"{', '.join(SCREENER_FILTERABLE_FIELDS)}. Call "
            "list_available_indicators for definitions."
        )

    bounds: dict[str, dict[str, Decimal]] = {}
    for field, field_bounds in filters.items():
        if not isinstance(field_bounds, dict):
            return {}, (
                f"filters.{field} must be an object with optional numeric "
                "'min' and 'max' properties."
            )
        converted: dict[str, Decimal] = {}
        for bound_name in ("min", "max"):
            bound_value = field_bounds.get(bound_name)
            if bound_value is None:
                continue
            try:
                converted[bound_name] = Decimal(str(bound_value))
            except (InvalidOperation, ValueError, TypeError):
                return {}, (
                    f"filters.{field}.{bound_name} must be a number, "
                    f"got {bound_value!r}."
                )
        bounds[field] = converted
    return bounds, None


def _resolve_debt_window_years(raw_window: Any) -> tuple[Optional[int], Optional[str]]:
    """Coerce the model's debt_window_years argument to an int in range.

    Returns (window, error). A missing argument is the loose default
    (``None``); an integer-valued string ("5") is accepted since models
    sometimes stringify numbers; anything else is a corrective error
    naming the valid range, never a silent fallback to the loose average
    (the caller would believe it screened on a window it did not).
    """
    if raw_window is None:
        return None, None
    candidate = raw_window
    if isinstance(candidate, str) and candidate.strip().lstrip("-").isdigit():
        candidate = int(candidate.strip())
    try:
        return validate_debt_window_years(candidate), None
    except ScreenerError as error:
        return None, str(error)


def _clamp_screen_limit(raw_limit: Any) -> int:
    """Coerce the model's limit argument to an int in [1, MAX_SCREEN_LIMIT],
    falling back to DEFAULT_SCREEN_LIMIT for anything missing or unparseable."""
    if raw_limit is None:
        return DEFAULT_SCREEN_LIMIT
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return DEFAULT_SCREEN_LIMIT
    return max(1, min(limit, MAX_SCREEN_LIMIT))


# Indicator fields every trimmed row carries. The full strict P/E window
# family (pe1..pe15) is deliberately not here — 15 windows × 20 rows would
# balloon every tool round, so a window only rides along when the call
# actually filtered or sorted by it.
TRIMMED_ROW_INDICATOR_FIELDS = (
    "pe10",
    "pe_years_available",
    "pfcf10",
    "peg",
    "pfcf_peg",
    "debt_to_equity",
    "debt_ex_lease_to_equity",
    "liabilities_to_equity",
    "current_ratio",
    "debt_to_avg_earnings",
    "debt_to_avg_fcf",
)


def _trim_row_for_model(row: dict, extra_fields: tuple = ()) -> dict:
    """Reduce one full screener row to what the model needs to reason about
    and cite: ticker identity, sector, market cap, the core indicator
    values, and any extra fields this call filtered or sorted by.
    Ratings/logo/current_price are omitted here to save tokens — the
    frontend gets those straight from the untouched `full_rows`."""
    trimmed = {
        "ticker": row["ticker"],
        "name": row["name"],
        "sector": row["sector"],
        "market_cap": row["market_cap"],
    }
    for field in (*TRIMMED_ROW_INDICATOR_FIELDS, *extra_fields):
        trimmed[field] = row.get(field)
    return json_safe(trimmed)


def _resolve_sectors(requested_sectors: list) -> tuple[list, Optional[str]]:
    """Map model-provided sector names onto the exact DB values.

    Case-insensitive: "utilities" resolves to "Utilities". A sector with no
    match at any casing returns a corrective error naming the valid sectors,
    so the agent can fix its next call instead of silently screening an
    empty set (observed live: the model invented "Electric Utilities" and
    "Finance - Diversified" and then reported zero matches to the user).
    """
    if not requested_sectors:
        return [], None
    valid_sectors = list(
        Ticker.objects.exclude(sector="")
        .values_list("sector", flat=True)
        .distinct()
        .order_by("sector"),
    )
    sector_by_lowercase = {sector.lower(): sector for sector in valid_sectors}
    resolved: list = []
    unknown: list = []
    for requested in requested_sectors:
        match = sector_by_lowercase.get((requested or "").strip().lower())
        if match is None:
            unknown.append(requested)
        else:
            resolved.append(match)
    if unknown:
        return [], (
            f"Unknown sector(s): {', '.join(repr(s) for s in unknown)}. "
            f"Valid sectors are: {', '.join(valid_sectors)}."
        )
    return resolved, None


def _resolve_countries(requested_countries: list) -> tuple[list, Optional[str]]:
    """Map model-provided country codes onto the exact DB values.

    Case-insensitive: "br" resolves to "BR". A code with no companies in
    the data returns a corrective error naming the valid codes — same
    rationale as _resolve_sectors: a silent zero-match screen teaches the
    caller nothing, a corrective error fixes its next call.
    """
    if not requested_countries:
        return [], None
    normalized = [
        (country or "").strip().upper()
        for country in requested_countries if country
    ]
    valid_countries = list(
        Ticker.objects.exclude(country="")
        .values_list("country", flat=True)
        .distinct()
        .order_by("country"),
    )
    unknown = sorted(set(normalized) - set(valid_countries))
    if unknown:
        return [], (
            f"Unknown country code(s): "
            f"{', '.join(repr(code) for code in unknown)}. Valid ISO 3166-1 "
            f"alpha-2 codes present in the data are: "
            f"{', '.join(valid_countries)}."
        )
    return normalized, None


def execute_screen_companies(arguments: dict) -> dict:
    """Run the screener in-process and shape the result for the tool loop.

    Returns ``{"count", "rows_for_model", "full_rows"}`` on success, or
    ``{"error": message}`` for a ScreenerError (e.g. an invalid sort field),
    a malformed filter, or an unknown indicator/sector/country — always a
    corrective message naming the valid values, and never a raise, so the
    agent loop can always feed the result straight back to the model as a
    tool message.
    """
    arguments = arguments or {}
    bounds, filter_error = _resolve_filter_bounds(arguments.get("filters"))
    if filter_error:
        return {"error": filter_error}
    limit = _clamp_screen_limit(arguments.get("limit"))
    debt_window_years, window_error = _resolve_debt_window_years(
        arguments.get("debt_window_years"),
    )
    if window_error:
        return {"error": window_error}

    sectors, sector_error = _resolve_sectors(arguments.get("sectors") or [])
    if sector_error:
        return {"error": sector_error}

    countries, country_error = _resolve_countries(
        arguments.get("countries") or []
    )
    if country_error:
        return {"error": country_error}

    sort = arguments.get("sort") or SCREENER_DEFAULT_SORT
    try:
        total_count, rows = run_screener(
            bounds=bounds,
            sectors=sectors,
            countries=countries,
            sort=sort,
            limit=limit,
            debt_window_years=debt_window_years,
        )
    except ScreenerError as error:
        return {"error": str(error)}

    fields_this_call_used = (*bounds.keys(), sort.lstrip("-"))
    extra_row_fields = tuple(
        field for field in fields_this_call_used
        if field in SCREENER_FILTERABLE_FIELDS
        and field not in TRIMMED_ROW_INDICATOR_FIELDS
    )

    return {
        "count": total_count,
        "debt_window_years": debt_window_years,
        "rows_for_model": [
            _trim_row_for_model(row, extra_row_fields) for row in rows
        ],
        "full_rows": json_safe(rows),
    }


# The exact key set this tool has always returned. Pinned as a constant so
# that widening quotes.company_snapshot (which also feeds the public markdown
# pages) can never silently reshape a payload an LLM is prompted against.
GET_COMPANY_FIELDS = (
    "symbol",
    "name",
    "sector",
    "country",
    "market_cap",
    "current_price",
    *SCREENER_FILTERABLE_FIELDS,
)


def execute_get_company(symbol: str, debt_window_years: Any = None) -> dict:
    """Ticker metadata + IndicatorSnapshot values for one stock symbol.

    Case-insensitive; only ``type="stock"`` rows match (funds/ETFs are out
    of scope for this tool). Unknown symbol or missing snapshot both come
    back as an ``{"error": ...}`` dict rather than raising.

    ``debt_window_years`` (1..15) swaps ``debt_to_avg_earnings`` and
    ``debt_to_avg_fcf`` for their strict N-year windows; the response
    always says which window it applied under ``debt_window_years``
    (``None`` for the loose pair).

    Delegates the read to ``quotes.company_snapshot``, which is the same
    DB-only accessor the markdown company pages render from, so the two
    surfaces cannot drift.
    """
    normalized_symbol = (symbol or "").strip().upper()
    if not normalized_symbol:
        return {"error": "No symbol provided."}
    debt_window_years, window_error = _resolve_debt_window_years(debt_window_years)
    if window_error:
        return {"error": window_error}

    payload = company_snapshot(normalized_symbol)
    if payload is None:
        # Two different facts for the model to relay: a symbol that does not
        # exist is a typo to correct, a company with no snapshot is a coverage
        # gap to admit. Worth one extra query on the error path.
        if not Ticker.objects.filter(
            symbol__iexact=normalized_symbol, type="stock",
        ).exists():
            return {"error": f"Unknown symbol: {symbol!r}"}
        return {"error": f"No indicator data available for {normalized_symbol}."}

    result = {field: payload[field] for field in GET_COMPANY_FIELDS}
    if debt_window_years is not None:
        for field in DEBT_COVERAGE_FIELDS:
            result[field] = payload[
                debt_coverage_window_field(field, debt_window_years)
            ]
    result["debt_window_years"] = debt_window_years
    return result


def execute_get_fundamentals(symbol: str) -> dict:
    """Full fundamentals payload for one symbol, with heavy keys stripped.

    Delegates to quotes.views._compute_quote_payload — the same live-fetch
    + DB-calc path PE10View uses — so the numbers always match what the
    page shows. A ``_QuoteError`` (ticker not found, provider down, market
    data unavailable) is caught and converted to ``{"error": message}``.
    """
    normalized_symbol = (symbol or "").strip().upper()
    if not normalized_symbol:
        return {"error": "No symbol provided."}

    try:
        payload = _compute_quote_payload(normalized_symbol, request=None)
    except _QuoteError as error:
        return {"error": error.message}

    trimmed_payload = {
        key: value for key, value in payload.items()
        if key not in FUNDAMENTALS_STRIPPED_KEYS
    }
    return json_safe(trimmed_payload)


def execute_tool(name: str, arguments: Optional[dict]) -> dict:
    """Dispatch one OpenAI tool call by name to its executor.

    Every branch returns a dict — an unknown tool name is structured error
    data too, so the agent loop never has to special-case a KeyError from a
    hallucinated or malformed tool call.
    """
    arguments = arguments or {}
    if name == "list_available_indicators":
        return execute_list_available_indicators()
    if name == "screen_companies":
        return execute_screen_companies(arguments)
    if name == "get_company":
        return execute_get_company(
            arguments.get("symbol", ""),
            debt_window_years=arguments.get("debt_window_years"),
        )
    if name == "get_fundamentals":
        return execute_get_fundamentals(arguments.get("symbol", ""))
    return {"error": f"Unknown tool: {name}"}
