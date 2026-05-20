"""Server-side context assembly for the LLM assistant.

Builds the <COMPANY_DATA>…</COMPANY_DATA> block the answer model sees.
The delimiters are the prompt-injection boundary: the system prompt tells
the model to treat anything inside strictly as data, never instructions.
"""
from __future__ import annotations

from quotes.views import _compute_quote_payload


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

    body = "\n".join(lines)
    return f"<COMPANY_DATA>\n{body}\n</COMPANY_DATA>"