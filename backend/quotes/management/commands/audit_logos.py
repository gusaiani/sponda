"""Report tickers whose logo resolution produces no real image.

For each stock ticker we walk the same resolution chain the LogoProxyView uses
and flag symbols that either have no URL to try or whose only sources return a
BRAPI placeholder. Use the output to populate LOGO_OVERRIDE_URLS.

Run:
    ./manage.py audit_logos
    ./manage.py audit_logos --limit 50          # stop after 50 missing
    ./manage.py audit_logos --symbols VALE3 KLBN4
"""
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand

from quotes.logo_overrides import LOGO_OVERRIDE_URLS, is_placeholder_logo_url
from quotes.models import Ticker
from quotes.views import BRAPI_LOGO_URL_TEMPLATE, is_brapi_placeholder


def _fetch(url: str) -> bytes | None:
    try:
        request = Request(url, headers={"User-Agent": "Sponda/1.0"})
        with urlopen(request, timeout=10) as response:
            return response.read()
    except Exception:
        return None


def _has_real_logo(symbol: str, db_logo_url: str) -> bool:
    """True if any source in our resolution chain returns a non-placeholder image."""
    candidate_urls: list[str] = []
    override = LOGO_OVERRIDE_URLS.get(symbol)
    if override:
        candidate_urls.append(override)
    if db_logo_url and not is_placeholder_logo_url(db_logo_url):
        candidate_urls.append(db_logo_url)
    candidate_urls.append(BRAPI_LOGO_URL_TEMPLATE.format(symbol=symbol))

    seen: set[str] = set()
    for url in candidate_urls:
        if url in seen:
            continue
        seen.add(url)
        data = _fetch(url)
        if data and not is_brapi_placeholder(data):
            return True
    return False


class Command(BaseCommand):
    help = "List stock tickers whose logo resolution ends in a generated fallback."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit", type=int, default=0,
            help="Stop after N missing logos (0 = no limit)",
        )
        parser.add_argument(
            "--symbols", nargs="+",
            help="Only audit the given symbols (default: all stocks)",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        symbols_filter = options.get("symbols")

        tickers = Ticker.objects.filter(type="stock").exclude(
            symbol__regex=r"^[A-Z]+\d+F$"
        ).order_by("symbol")
        if symbols_filter:
            tickers = tickers.filter(symbol__in=[s.upper() for s in symbols_filter])

        missing: list[tuple[str, str]] = []
        for ticker in tickers.values_list("symbol", "logo", "name"):
            symbol, db_logo_url, name = ticker
            if _has_real_logo(symbol, db_logo_url or ""):
                continue
            missing.append((symbol, name))
            self.stdout.write(f"{symbol}\t{name}")
            if limit and len(missing) >= limit:
                break

        self.stdout.write(self.style.WARNING(
            f"\n{len(missing)} ticker(s) without a real logo."
        ))
