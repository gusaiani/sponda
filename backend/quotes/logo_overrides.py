"""Manual logo URL overrides for tickers where auto-discovery fails.

Many Brazilian mid-caps and small-caps aren't covered by BRAPI's logo database,
and FMP's generic URL pattern for US tickers sometimes returns 404s. When the
data provider can't serve a real logo, we fall back to a generated letter-SVG,
which works visually but looks uneven next to real logos in the compare table.

This file is the escape hatch. Any symbol mapped here wins over the URL stored
on the Ticker row, and over any provider fallback. Use it to point at a
known-good logo URL (official CDN, Wikimedia, another trusted source).

Keys are uppercase symbols. Values are absolute URLs.
"""

LOGO_OVERRIDE_URLS: dict[str, str] = {
    # Add entries here as you find missing logos. Example:
    # "KLBN4": "https://logo.clearbit.com/klabin.com.br",
}


# URLs that should be ignored when seen on Ticker.logo — they are known
# provider placeholders that never resolve to a real image.
PLACEHOLDER_LOGO_URLS: frozenset[str] = frozenset({
    "https://icons.brapi.dev/icons/BRAPI.svg",
})


def is_placeholder_logo_url(url: str) -> bool:
    """True if `url` is a known provider-side placeholder (no real logo)."""
    if not url:
        return True
    return url in PLACEHOLDER_LOGO_URLS
