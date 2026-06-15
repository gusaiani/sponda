"""Server-side context assembly for the LLM assistant.

Builds the <COMPANY_DATA>…</COMPANY_DATA> block the answer model sees.
The delimiters are the prompt-injection boundary: the system prompt tells
the model to treat anything inside strictly as data, never instructions.
"""
from __future__ import annotations

from accounts.models import CompanyVisit, IndicatorAlert
from quotes.views import _compute_quote_payload

# Each entry is (payload_key, context_label): the camelCase key as it appears
# in the quote payload, paired with the snake_case label shown to the model.
# An explicit allowlist is the cost defense — verbose *CalculationDetails*
# blocks can never leak into the prompt because they are simply not named here.

# Identity + the three core valuation multiples Sponda is built around.
# Shown for every question regardless of which tab is open.
BASE_FIELDS = (
    ("name", "display_name"),
    ("currentPrice", "current_price"),
    ("pe10", "pe10"),
    ("pfcf10", "pfcf10"),
    ("peg", "peg"),
)

# Extra numbers layered in for the tab the user is actually looking at, so the
# model sees what's on screen without every prompt carrying the whole payload.
TAB_FIELDS = {
    "metrics": (
        ("pfcfPeg", "pfcf_peg"),
        ("earningsCAGR", "earnings_cagr"),
        ("fcfCAGR", "fcf_cagr"),
    ),
    "fundamentals": (
        ("debtToEquity", "debt_to_equity"),
        ("currentRatio", "current_ratio"),
        ("debtToAvgEarnings", "debt_to_avg_earnings"),
        ("debtToAvgFCF", "debt_to_avg_fcf"),
        ("totalDebt", "total_debt"),
        ("totalLiabilities", "total_liabilities"),
        ("stockholdersEquity", "stockholders_equity"),
    ),
    "charts": (
        ("maxYearsAvailable", "years_of_history"),
    ),
}

# Conservative ~3000-token budget at 4 chars/token. The whole
# <COMPANY_DATA>…</COMPANY_DATA> block, including delimiters and any
# truncation marker, is guaranteed to fit within this length.
MAX_CONTEXT_CHARS = 12_000


def _append_fields(lines, payload, fields):
    """Append `label: value` lines for each named field present in payload.

    Missing or None values are skipped so the block stays tight — the model
    only sees numbers that actually exist for this company.
    """
    for payload_key, label in fields:
        value = payload.get(payload_key)
        if value is not None:
            lines.append(f"{label}: {value}")


def build_company_context(
    ticker: str,
    tab: str,
    locale: str,
    user,
) -> str:
    """Assemble the bounded data block for one company question."""
    payload = _compute_quote_payload(ticker)

    lines = [f"ticker: {ticker}"]
    _append_fields(lines, payload, BASE_FIELDS)
    # Tab-specific numbers: follow whichever tab the user has open.
    _append_fields(lines, payload, TAB_FIELDS.get(tab, ()))

    if user is not None and getattr(user, "is_authenticated", False):
        latest_visit = (
            CompanyVisit.objects
            .filter(user=user, ticker=ticker)
                .order_by("-visited_at")
            .first()
        )
        if latest_visit and latest_visit.note:
            lines.append(f"your_note: {latest_visit.note}")

        active_alerts = (
            IndicatorAlert.objects
            .filter(user=user, ticker=ticker, active=True)
            .order_by("indicator")
        )

        for alert in active_alerts:
            threshold = f"{float(alert.threshold):g}"
            lines.append(
                f"your_alert: {alert.indicator} {alert.comparison} {threshold}"
            )

    # Delimiters are part of the safety contract — pull the pieces out
    # so the truncation branch below can rebuild the string without
    # losing the closing tag.
    prefix = "<COMPANY_DATA>\n"
    closing = "\n</COMPANY_DATA>"
    body = "\n".join(lines)

    full = f"{prefix}{body}{closing}"
    if len(full) <= MAX_CONTEXT_CHARS:
        return full

    # Oversized — crop the body, leave room for the marker and the
    # closing delimiter. The marker is visible to the model so it knows
    # the data is incomplete and answers accordingly.
    marker = "\n…[truncated]"
    budget_for_body = MAX_CONTEXT_CHARS - len(prefix) - len(marker) - len(closing)
    truncated_body = body[:budget_for_body]
    return f"{prefix}{truncated_body}{marker}{closing}"