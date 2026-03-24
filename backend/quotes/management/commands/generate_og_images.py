"""Pre-generate Open Graph images for all stock tickers.

Saves images to <project_root>/og_images/ so they can be served as
static files at /og/<ticker>.png without hitting the external API.

Usage:
    python manage.py generate_og_images          # all tickers + homepage
    python manage.py generate_og_images PETR4     # single ticker
"""
import time
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from quotes.brapi import BRAPIError, fetch_quote
from quotes.models import Ticker
from quotes.og_image import generate_homepage_og_image, generate_og_image
from quotes.pe10 import calculate_pe10
from quotes.peg import calculate_peg
from quotes.pfcf10 import calculate_pfcf10
from quotes.views import _clean_company_name


class Command(BaseCommand):
    help = "Pre-generate OG images for all stock tickers"

    def add_arguments(self, parser):
        parser.add_argument(
            "tickers",
            nargs="*",
            help="Optional: specific tickers to generate (default: all)",
        )

    def handle(self, *args, **options):
        og_dir = Path(settings.BASE_DIR).parent / "og_images"
        og_dir.mkdir(exist_ok=True)

        # Always generate homepage image
        homepage_png = generate_homepage_og_image()
        (og_dir / "home.png").write_bytes(homepage_png)
        self.stdout.write(self.style.SUCCESS("Generated home.png"))

        # Get tickers to generate
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

        total = len(ticker_list)
        generated = 0
        skipped = 0
        errors = 0

        for index, symbol in enumerate(ticker_list, 1):
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
                # Generate a minimal image with just the ticker name
                ticker_obj = Ticker.objects.filter(symbol=symbol).first()
                name = ticker_obj.name if ticker_obj else symbol
                png = generate_og_image(ticker=symbol, name=name)
                skipped += 1

            (og_dir / f"{symbol}.png").write_bytes(png)
            generated += 1

            if index % 25 == 0:
                self.stdout.write(f"  [{index}/{total}] {symbol}")
                time.sleep(1)  # Rate-limit brapi requests

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {generated} generated, {skipped} without live data, {errors} errors"
            )
        )
