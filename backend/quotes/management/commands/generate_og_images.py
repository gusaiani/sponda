"""Pre-generate Open Graph images for stock tickers.

Saves images to <project_root>/og_images/ so they can be served as
static files at /og/<ticker>.png without hitting the external API.

Skips tickers whose image already exists and is less than --max-age days old.
Limits BRAPI calls per run with --max to stay within rate limits.

Usage:
    python manage.py generate_og_images              # stale/missing only (default 50)
    python manage.py generate_og_images --max 200     # up to 200 images
    python manage.py generate_og_images --force        # regenerate all
    python manage.py generate_og_images PETR4 VALE3    # specific tickers
"""
import time
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from quotes.brapi import BRAPIError, fetch_quote
from quotes.models import Ticker
from quotes.og_image import generate_homepage_og_image, generate_og_image
from quotes.pe10 import calculate_pe10
from quotes.peg import calculate_peg
from quotes.pfcf10 import calculate_pfcf10
from quotes.views import _clean_company_name

DEFAULT_MAX_PER_RUN = 50
DEFAULT_MAX_AGE_DAYS = 7


class Command(BaseCommand):
    help = "Pre-generate OG images for stock tickers (skips fresh images)"

    def add_arguments(self, parser):
        parser.add_argument(
            "tickers",
            nargs="*",
            help="Optional: specific tickers to generate (default: all stale/missing)",
        )
        parser.add_argument(
            "--max",
            type=int,
            default=DEFAULT_MAX_PER_RUN,
            help=f"Max images to generate per run (default: {DEFAULT_MAX_PER_RUN})",
        )
        parser.add_argument(
            "--max-age",
            type=int,
            default=DEFAULT_MAX_AGE_DAYS,
            help=f"Regenerate images older than this many days (default: {DEFAULT_MAX_AGE_DAYS})",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Regenerate all images regardless of age",
        )

    def handle(self, *args, **options):
        og_dir = Path(settings.BASE_DIR).parent / "og_images"
        og_dir.mkdir(exist_ok=True)
        max_per_run = options["max"]
        max_age_days = options["max_age"]
        force = options["force"]

        # Always generate homepage image (no BRAPI call)
        homepage_png = generate_homepage_og_image()
        (og_dir / "home.png").write_bytes(homepage_png)

        # Build ticker list
        specific_tickers = options["tickers"]
        if specific_tickers:
            ticker_list = [t.upper() for t in specific_tickers]
        else:
            ticker_list = list(
                Ticker.objects.filter(type="stock")
                .exclude(symbol__regex=r"^[A-Z]+\d+F$")
                .values_list("symbol", flat=True)
                .order_by("symbol")
            )

        # Filter to only stale/missing images (unless --force)
        now = timezone.now().timestamp()
        max_age_seconds = max_age_days * 86400
        needs_generation = []

        for symbol in ticker_list:
            image_path = og_dir / f"{symbol}.png"
            if force or not image_path.exists():
                needs_generation.append(symbol)
            elif (now - image_path.stat().st_mtime) > max_age_seconds:
                needs_generation.append(symbol)

        if not needs_generation:
            self.stdout.write(self.style.SUCCESS("All images are fresh, nothing to do"))
            return

        # Cap at --max
        batch = needs_generation[:max_per_run]
        self.stdout.write(
            f"Generating {len(batch)} of {len(needs_generation)} stale/missing images "
            f"({len(ticker_list)} total tickers)"
        )

        generated = 0
        api_errors = 0

        for index, symbol in enumerate(batch, 1):
            try:
                quote = fetch_quote(symbol)
                name = _clean_company_name(
                    quote.get("longName") or quote.get("shortName") or symbol
                )
                market_cap = quote.get("marketCap")
                market_cap_decimal = Decimal(str(market_cap)) if market_cap else None

                pe10_result = calculate_pe10(symbol, market_cap_decimal) if market_cap_decimal else {}
                pfcf10_result = calculate_pfcf10(symbol, market_cap_decimal) if market_cap_decimal else {}
                peg_result = calculate_peg(symbol, pe10_result.get("pe10")) if pe10_result else {}

                png = generate_og_image(
                    ticker=symbol,
                    name=name,
                    pe10=pe10_result.get("pe10"),
                    pe10_label=pe10_result.get("label", "PE10"),
                    pfcf10=pfcf10_result.get("pfcf10"),
                    pfcf10_label=pfcf10_result.get("label", "PFCF10"),
                    peg=peg_result.get("peg"),
                    market_cap=float(market_cap) if market_cap else None,
                )
            except BRAPIError:
                # Generate image from database only (no BRAPI needed)
                ticker_obj = Ticker.objects.filter(symbol=symbol).first()
                name = ticker_obj.name if ticker_obj else symbol
                png = generate_og_image(ticker=symbol, name=name)
                api_errors += 1

            (og_dir / f"{symbol}.png").write_bytes(png)
            generated += 1

            if index % 10 == 0:
                self.stdout.write(f"  [{index}/{len(batch)}] {symbol}")
                time.sleep(2)  # Rate-limit: ~5 BRAPI requests per 10 seconds

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {generated} generated, {api_errors} from DB only"
            )
        )
