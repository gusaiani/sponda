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
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from quotes.models import Ticker
from quotes.og_image import generate_homepage_og_image, generate_og_image
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

        for index, symbol in enumerate(batch, 1):
            ticker_obj = Ticker.objects.filter(symbol=symbol).values("name", "logo").first()
            name = _clean_company_name(ticker_obj["name"]) if ticker_obj and ticker_obj["name"] else symbol
            logo_url = (ticker_obj.get("logo") or None) if ticker_obj else None

            png = generate_og_image(ticker=symbol, name=name, logo_url=logo_url)
            (og_dir / f"{symbol}.png").write_bytes(png)
            generated += 1

            if index % 10 == 0:
                self.stdout.write(f"  [{index}/{len(batch)}] {symbol}")

        self.stdout.write(
            self.style.SUCCESS(f"Done: {generated} images generated")
        )
