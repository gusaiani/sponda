"""Check that Cloudflare is serving what the origin serves, and heal it if not.

The deploy already gates on a frontend health check, but that check polls
127.0.0.1:3100 and never crosses the edge. It cannot see the one failure this
command exists for: a deploy changes what a URL returns, and Cloudflare keeps
handing out the pre-deploy body for its four-hour TTL.

That is not hypothetical. When the per-company Open Graph cards shipped,
`/og/pt/VULC3.png` had been fetched while the path still proxied to Django and
answered with the legacy SPA shell. For hours afterwards the origin served a
valid PNG while Cloudflare served HTML with a 200 to every crawler that asked
for the image. Client `Cache-Control: no-cache` does not help; Cloudflare
ignores it. Only a purge does.

So: fetch a handful of canaries through the edge, compare the content-type
against what it must be, purge anything that disagrees, and re-check. Exit
non-zero only if a URL is still wrong after the purge, because at that point
something is broken that a cache flush cannot fix.
"""
import os
from dataclasses import dataclass

import requests
from django.core.management.base import BaseCommand, CommandError


@dataclass(frozen=True)
class Canary:
    url: str
    expected_content_type: str


# Deliberately short. These are not coverage; they are tripwires for the class
# of bug above, so they cover each *kind* of asset whose route could change
# hands, not each asset. A rendered card and a static file is the whole space
# today. Cloudflare accepts 30 URLs per purge call, which is the ceiling here.
CANARIES: tuple[Canary, ...] = (
    # Rendered on demand by Next (src/app/og/[locale]/[ticker]/route.tsx). The
    # route answers for unknown symbols too, so a delisted ticker still yields
    # a PNG and will not turn this into a flaky check.
    Canary("https://sponda.capital/og/pt/VULC3.png", "image/png"),
    Canary("https://sponda.capital/og/en/AAPL.png", "image/png"),
    # Static file from frontend/public/, used by pages with no company to render.
    Canary("https://sponda.capital/images/sponda-og-v2.jpg", "image/jpeg"),
    # The markdown twin of a public page, rewritten by middleware onto
    # src/app/md/[...slug]/route.ts. What this catches is the middleware
    # matcher losing its .md entry: the URL then falls through to the Next
    # 404 page, which answers text/html with a 404 through the edge.
    #
    # Two of the three cannot 404 by construction. Unlike the Open Graph
    # route, which renders a card for any symbol, the markdown route 404s a
    # company with no IndicatorSnapshot row, so a delisted ticker as the only
    # canary would fail the deploy gate for a reason that is not a cache
    # problem. The home page and the screener glossary render from static copy
    # and the indicator catalogue; the company canary is the largest listing
    # we cover.
    Canary("https://sponda.capital/en.md", "text/markdown"),
    Canary("https://sponda.capital/pt/screener.md", "text/markdown"),
    Canary("https://sponda.capital/en/AAPL.md", "text/markdown"),
)

PURGE_ENDPOINT = "https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache"
REQUEST_TIMEOUT_SECONDS = 15


def _base_content_type(header_value: str) -> str:
    """`image/png; charset=binary` → `image/png`."""
    return header_value.split(";")[0].strip().lower()


def _is_stale(canary: Canary) -> bool:
    """True when the edge is not serving what this URL is supposed to serve.

    A transport error counts as stale: the point is to notice and try a purge,
    not to decide why the edge is unhappy.
    """
    try:
        response = requests.get(
            canary.url,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": "sponda-deploy-canary"},
        )
    except requests.RequestException:
        return True

    if response.status_code != 200:
        return True

    served = _base_content_type(response.headers.get("Content-Type", ""))
    return served != canary.expected_content_type


def _purge(urls: list[str], token: str, zone_id: str) -> None:
    """Purge exact URLs. Raises CommandError with Cloudflare's own message."""
    response = requests.post(
        PURGE_ENDPOINT.format(zone_id=zone_id),
        headers={"Authorization": f"Bearer {token}"},
        json={"files": urls},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    try:
        body = response.json()
    except ValueError:
        body = {}

    if response.status_code != 200 or not body.get("success"):
        reasons = "; ".join(
            error.get("message", "unknown") for error in body.get("errors", [])
        ) or f"HTTP {response.status_code}"
        raise CommandError(f"Cloudflare purge failed: {reasons}")


class Command(BaseCommand):
    help = "Verify Cloudflare is serving current content; purge and re-check if not."

    def handle(self, *args, **options):
        stale = [canary for canary in CANARIES if _is_stale(canary)]

        if not stale:
            self.stdout.write(
                self.style.SUCCESS(f"OK · {len(CANARIES)} edge canaries serving current content")
            )
            return

        stale_urls = [canary.url for canary in stale]
        for url in stale_urls:
            self.stdout.write(f"Stale at the edge: {url}")

        token = os.environ.get("CLOUDFLARE_API_TOKEN")
        zone_id = os.environ.get("CLOUDFLARE_ZONE_ID")
        if not token or not zone_id:
            raise CommandError(
                "Cloudflare is serving stale content and no purge credentials are "
                "configured. Set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ZONE_ID in "
                f"/opt/sponda/.env, or purge by hand: {', '.join(stale_urls)}"
            )

        _purge(stale_urls, token, zone_id)
        self.stdout.write(f"Purged {len(stale_urls)} URL(s); re-checking")

        still_stale = [canary.url for canary in stale if _is_stale(canary)]
        if still_stale:
            raise CommandError(
                "Still wrong after purging, so this is not a cache problem: "
                + ", ".join(still_stale)
            )

        self.stdout.write(
            self.style.SUCCESS(f"OK · purge fixed {len(stale_urls)} URL(s) at the edge")
        )
