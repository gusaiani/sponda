"""IndexNow submission: push changed URLs instead of waiting to be crawled.

Bing, DuckDuckGo, Yandex, Seznam and Naver all consume the shared endpoint.
Google does not. That is a better trade than it sounds for this project:
Bing's index feeds DuckDuckGo and Microsoft Copilot, so IndexNow is a direct
route to the assistants the markdown pages were built for.

Ownership is proved by a key file hosted on the site, not by any registration
step. The key is public by design; its only power is to submit URLs for a host
you already control.

What gets submitted is the HTML company page, per sitemap locale. Not the
markdown twins, which are for direct readers rather than search results, and
not the tab pages, which are detail views of a page already being submitted.
"""
from __future__ import annotations

from django.conf import settings

import requests

from quotes.models import IndicatorSnapshot, Ticker

INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"

SITE_HOST = "sponda.capital"
SITE_BASE_URL = f"https://{SITE_HOST}"

# The protocol allows 10,000 URLs per request.
MAX_URLS_PER_SUBMISSION = 10_000

# Locales that get their own <url> entry in the sitemap. Submitting the same
# set keeps the two surfaces telling search engines the same thing.
SITEMAP_LOCALES = ("en", "pt")

REQUEST_TIMEOUT_SECONDS = 30


def key_file_url() -> str:
    """Where the key file must live for a submission to validate."""
    return f"{SITE_BASE_URL}/{settings.INDEXNOW_KEY}.txt"


def build_company_urls(symbols) -> list[str]:
    """The HTML company page for each symbol, in each sitemap locale."""
    return [
        f"{SITE_BASE_URL}/{locale}/{symbol}"
        for symbol in symbols
        for locale in SITEMAP_LOCALES
    ]


def covered_symbols(exclude: set[str] | None = None):
    """Listed companies we actually hold indicators for, sorted.

    A company page with no numbers is a thin page; asking a search engine to
    crawl a few hundred of them promptly is the opposite of the point.
    """
    excluded = exclude or set()
    return [
        symbol
        for symbol in Ticker.objects.filter(
            type="stock",
            symbol__in=IndicatorSnapshot.objects.values("ticker"),
        )
        .order_by("symbol")
        .values_list("symbol", flat=True)
        if symbol not in excluded
    ]


class KeyMismatch(Exception):
    """The hosted key file does not agree with the configured key."""


def verify_key_is_live() -> None:
    """Fetch the key file and check it matches, before submitting anything.

    Without this, a key that has drifted from the file produces a 403 on every
    submission and nothing anywhere says so. One request turns a silent
    failure into a loud one.
    """
    if not settings.INDEXNOW_KEY:
        raise KeyMismatch("INDEXNOW_KEY is not set.")

    url = key_file_url()
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as error:
        raise KeyMismatch(f"Could not fetch the key file at {url}: {error}") from error

    if response.status_code != 200:
        raise KeyMismatch(
            f"The key file at {url} answered {response.status_code}. "
            "It must be deployed before submitting.",
        )

    if response.text.strip() != settings.INDEXNOW_KEY:
        raise KeyMismatch(
            f"The key file at {url} does not contain INDEXNOW_KEY. "
            "Every submission would be rejected.",
        )


def submit(urls: list[str]) -> bool:
    """Submit one batch. True when the endpoint accepted it."""
    response = requests.post(
        INDEXNOW_ENDPOINT,
        json={
            "host": SITE_HOST,
            "key": settings.INDEXNOW_KEY,
            "keyLocation": key_file_url(),
            "urlList": urls,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    # 200 accepted, 202 accepted but the key is still being validated.
    return response.status_code in (200, 202)


def batched(items: list, size: int):
    for start in range(0, len(items), size):
        yield items[start:start + size]
