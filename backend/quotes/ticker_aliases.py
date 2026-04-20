"""Known former or alternate names for tickers whose current display name
no longer contains the phrase users still search for.

The ticker sync job applies this mapping on every refresh so the search
index stays consistent with real-world rebrands.

Add entries conservatively — each alias widens the search surface, so
only include names that users genuinely still type.
"""

TICKER_ALIASES: dict[str, list[str]] = {
    "GE": ["General Electric"],
}


def aliases_for(symbol: str) -> list[str]:
    return TICKER_ALIASES.get(symbol.upper(), [])


def serialize_aliases(aliases: list[str]) -> str:
    return "\n".join(aliases)
