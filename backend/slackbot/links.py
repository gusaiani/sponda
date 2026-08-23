"""Rewrite tickers in a Slack answer into links to their Sponda pages.

Two problems, one pass. Models decorate Brazilian tickers with the
Yahoo-style ".SA" suffix Sponda's data does not use, and Slack then
auto-links that as a domain (.sa is a real TLD), so answers arrived full
of blue links pointing nowhere. Emitting an explicit Slack link to the
company page both fixes the destination and drops the invented suffix.

Linking is allowlist-driven: only symbols the tools actually returned, or
that the asker named and the ticker table confirms. Ticker-shaped words
are everywhere in this domain ("BR", "PEG", "US"), and several are real
symbols elsewhere in the world — a confidently wrong link is worse than
no link at all.

The base URL is deliberately absolute rather than SITE_BASE_URL: a link
posted into someone's Slack is a public fact about the deployment, and a
message sent from any box must point at the real site, never localhost.
"""
import re

from quotes.models import Ticker

SPONDA_BASE_URL = "https://sponda.capital"

# Mirrors frontend/src/lib/i18n-config.ts::SUPPORTED_LOCALES, same list
# config/urls.py uses for its ticker-page routes.
SUPPORTED_LOCALES = ("pt", "en", "es", "zh", "fr", "de", "it")
DEFAULT_LOCALE = "en"

# A ticker as Sponda stores it, optionally carrying the exchange suffix a
# model may have invented (".SA", ".NYSE"). Bounded by non-alphanumerics
# so a symbol embedded in a longer word is left alone.
_TICKER_CANDIDATE = re.compile(
    r"(?<![A-Za-z0-9])([A-Za-z]{1,6}\d{0,2})(\.[A-Za-z]{2,4})?(?![A-Za-z0-9])"
)

# Spans already rendered as Slack links (<url|label>). Linking inside one
# would nest link syntax and break the rendering.
_EXISTING_LINK = re.compile(r"<[^<>]*\|[^<>]*>")


def company_url(symbol: str, locale: str) -> str:
    safe_locale = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
    return f"{SPONDA_BASE_URL}/{safe_locale}/{symbol}"


def _link_spans(text: str) -> list[tuple[int, int]]:
    return [match.span() for match in _EXISTING_LINK.finditer(text)]


def linkify_tickers(text: str, *, symbols: set[str], locale: str) -> str:
    """Replace each allowlisted symbol in `text` with a Slack link to its
    Sponda page, dropping any exchange suffix the model appended."""
    if not symbols or not text:
        return text

    by_upper = {symbol.upper(): symbol for symbol in symbols}
    protected = _link_spans(text)

    def replace(match: re.Match) -> str:
        symbol = by_upper.get(match.group(1).upper())
        if symbol is None:
            return match.group(0)
        if any(start <= match.start() < end for start, end in protected):
            return match.group(0)
        return f"<{company_url(symbol, locale)}|{symbol}>"

    return _TICKER_CANDIDATE.sub(replace, text)


def resolve_known_symbols(text: str) -> set[str]:
    """Ticker-shaped words in `text` that are real Sponda stock symbols.

    One indexed query, so a question naming a company still gets a link
    even when the answer came from get_company (which surfaces no
    screener rows to build an allowlist from).
    """
    candidates = {
        match.group(1).upper() for match in _TICKER_CANDIDATE.finditer(text or "")
    }
    if not candidates:
        return set()
    return set(
        Ticker.objects
        .filter(symbol__in=candidates, type="stock")
        .values_list("symbol", flat=True)
    )
