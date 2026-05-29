"""Server-side context assembly for the LLM assistant.

Builds the <COMPANY_DATA>…</COMPANY_DATA> block the answer model sees.
The delimiters are the prompt-injection boundary: the system prompt tells
the model to treat anything inside strictly as data, never instructions.
"""
from __future__ import annotations

from accounts.models import CompanyVisit, IndicatorAlert
from quotes.views import _compute_quote_payload

INDICATOR_KEYS = ("pe10", "pfcf10", "peg", "current_price")

# Conservative ~3000-token budget at 4 chars/token. The whole
# <COMPANY_DATA>…</COMPANY_DATA> block, including delimiters and any
# truncation marker, is guaranteed to fit within this length.
MAX_CONTEXT_CHARS = 12_000


def build_company_context(
    ticker: str,
    tab: str,
    locale: str,
    user,
) -> str:
    """Assemble the bounded data block for one company question."""
    payload = _compute_quote_payload(ticker)

    lines = [f"ticker: {ticker}"]
    display_name = payload.get("display_name")
    if display_name:
        lines.append(f"display_name: {display_name}")

    for key in INDICATOR_KEYS:
        value = payload.get(key)
        if value is not None:
            lines.append(f"{key}: {value}")

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