"""Plain-Python screener query service.

Extracted from :class:`quotes.views.ScreenerView` so the same filter/sort/
paginate/rate logic can be called in-process (e.g. by an LLM tool layer)
without going through HTTP. The view remains the sole place that parses
query-string params and translates errors into HTTP responses; this module
owns the query itself.
"""
from decimal import Decimal
from typing import Mapping, Optional, Sequence

from django.db.models import F

from .models import IndicatorSnapshot, Ticker
from .ratings import rate_company

# Numeric indicator fields the screener can filter by. Explicit allow-list so
# unknown query params are ignored safely. Market cap is deliberately excluded —
# users rank by it (default sort) and read it in the results, but shouldn't
# screen by it as a min/max bound.
SCREENER_FILTERABLE_FIELDS = (
    "pe10",
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

# Sortable set is the filterable set plus market_cap (for the default ranking)
# and ticker (alphabetical). Kept as a separate constant so the filter/sort
# surfaces can diverge without tangling.
SCREENER_SORTABLE_FIELDS = SCREENER_FILTERABLE_FIELDS + ("market_cap", "ticker")
SCREENER_DEFAULT_SORT = "ticker"
SCREENER_DEFAULT_LIMIT = 50
SCREENER_MAX_LIMIT = 500


class ScreenerError(Exception):
    """Raised for invalid screener query input (e.g. an unknown sort field).

    Callers that speak HTTP (``ScreenerView``) catch this and translate it
    into a 400 response; in-process callers (e.g. an LLM tool) can catch it
    directly.
    """


def run_screener(
    *,
    bounds: Optional[Mapping[str, Mapping[str, Optional[Decimal]]]] = None,
    sectors: Optional[Sequence[str]] = None,
    countries: Optional[Sequence[str]] = None,
    sort: str = SCREENER_DEFAULT_SORT,
    limit: int = SCREENER_DEFAULT_LIMIT,
    offset: int = 0,
) -> tuple[int, list[dict]]:
    """Filter, sort, paginate, and rate IndicatorSnapshot rows.

    Args:
        bounds: mapping of indicator field name (must be in
            :data:`SCREENER_FILTERABLE_FIELDS`; unknown keys are ignored) to
            ``{"min": Decimal|None, "max": Decimal|None}``. Rows whose value
            is ``NULL`` are excluded from a bound filter (cannot prove they
            satisfy the threshold).
        sectors: ``Ticker.sector`` values to allow; empty/``None`` means all.
        countries: ``Ticker.country`` values to allow; empty/``None`` means
            all.
        sort: sortable field name, optionally prefixed with ``-`` for
            descending. Raises :class:`ScreenerError` if not in
            :data:`SCREENER_SORTABLE_FIELDS`.
        limit: max rows to return; clamped to ``[1, SCREENER_MAX_LIMIT]``.
        offset: rows to skip before returning; clamped to ``>= 0``.

    Returns:
        ``(total_count, results)`` where ``total_count`` is the number of
        matching rows before pagination and ``results`` is the paginated,
        rated list of row dicts.
    """
    queryset = IndicatorSnapshot.objects.all()

    # Sector + country filters (categorical, multi-select). Implemented as
    # one Ticker query with the filters AND'd together, then narrows the
    # snapshot queryset by symbol — keeps the IndicatorSnapshot model free
    # of denormalized columns.
    sector_values = [s for s in (sectors or []) if s]
    country_values = [c for c in (countries or []) if c]
    if sector_values or country_values:
        ticker_filter = Ticker.objects.all()
        if sector_values:
            ticker_filter = ticker_filter.filter(sector__in=sector_values)
        if country_values:
            ticker_filter = ticker_filter.filter(country__in=country_values)
        allowed_symbols = list(ticker_filter.values_list("symbol", flat=True))
        queryset = queryset.filter(ticker__in=allowed_symbols)

    # Apply numeric min/max filters ---------------------------------------
    for field, field_bounds in (bounds or {}).items():
        if field not in SCREENER_FILTERABLE_FIELDS:
            continue
        min_value = field_bounds.get("min")
        if min_value is not None:
            queryset = queryset.filter(**{f"{field}__gte": min_value})
        max_value = field_bounds.get("max")
        if max_value is not None:
            queryset = queryset.filter(**{f"{field}__lte": max_value})

    total_count = queryset.count()

    # Sort ----------------------------------------------------------------
    sort_param = sort or SCREENER_DEFAULT_SORT
    sort_field = sort_param.lstrip("-")
    if sort_field not in SCREENER_SORTABLE_FIELDS:
        raise ScreenerError(f"Invalid sort field: {sort_param!r}")
    # Nulls-last on DESC so rows with missing data don't dominate the top.
    queryset = queryset.order_by(
        F(sort_field).desc(nulls_last=True)
        if sort_param.startswith("-")
        else F(sort_field).asc(nulls_last=True),
        "ticker",
    )

    # Paginate ------------------------------------------------------------
    limit = max(1, min(limit, SCREENER_MAX_LIMIT))
    offset = max(0, offset)
    page = list(queryset[offset:offset + limit])

    # Hydrate ticker metadata in one query so the response is fully
    # self-contained for the frontend table.
    ticker_symbols = [snapshot.ticker for snapshot in page]
    ticker_metadata = {
        row["symbol"]: row
        for row in Ticker.objects.filter(symbol__in=ticker_symbols).values(
            "symbol", "name", "display_name", "sector", "logo",
        )
    }

    results = []
    for snapshot in page:
        metadata = ticker_metadata.get(snapshot.ticker, {})
        sector = metadata.get("sector") or ""
        indicator_values = {
            "pe10": snapshot.pe10,
            "pfcf10": snapshot.pfcf10,
            "peg": snapshot.peg,
            "pfcf_peg": snapshot.pfcf_peg,
            "debt_to_equity": snapshot.debt_to_equity,
            "debt_ex_lease_to_equity": snapshot.debt_ex_lease_to_equity,
            "liabilities_to_equity": snapshot.liabilities_to_equity,
            "current_ratio": snapshot.current_ratio,
            "debt_to_avg_earnings": snapshot.debt_to_avg_earnings,
            "debt_to_avg_fcf": snapshot.debt_to_avg_fcf,
        }
        rated = rate_company(indicator_values, sector=sector or None)
        results.append({
            "ticker": snapshot.ticker,
            "name": metadata.get("display_name") or metadata.get("name") or "",
            "sector": sector,
            "logo": metadata.get("logo") or "",
            **indicator_values,
            "market_cap": snapshot.market_cap,
            "current_price": snapshot.current_price,
            "ratings": {
                **rated["ratings"],
                "overall": rated["overall"],
                "methodology_version": rated["methodology_version"],
            },
        })

    return total_count, results
