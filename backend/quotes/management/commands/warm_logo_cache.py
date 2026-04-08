"""Pre-warm the disk-based logo cache for popular tickers.

Fetches logos from the ticker's DB URL or BRAPI for each popular ticker
and saves them to LOGO_CACHE_DIR. Skips tickers that are already cached
and rejects BRAPI placeholder logos. Run on deploy or on a schedule.
"""
import logging
from pathlib import Path
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand

from quotes.models import Ticker
from quotes.views import is_brapi_placeholder, BRAPI_LOGO_URL_TEMPLATE

logger = logging.getLogger(__name__)

POPULAR_SYMBOLS = {
    "brazil": [
        "PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3",
        "WEGE3", "ABEV3", "B3SA3", "RENT3", "SUZB3",
        "ITSA4", "ELET3", "JBSS3", "RADL3", "EQTL3",
        "VIVT3", "PRIO3", "LREN3", "TOTS3", "SBSP3",
        "GGBR4", "CSNA3", "CSAN3", "KLBN11", "ENEV3",
        "HAPV3", "RDOR3", "RAIL3", "BBSE3", "CPLE6",
        "UGPA3", "CMIG4", "TAEE11", "EMBR3", "FLRY3",
        "ARZZ3", "MULT3", "PETZ3", "VBBR3", "MGLU3",
        "COGN3", "CYRE3", "EGIE3", "GOAU4", "HYPE3",
        "IRBR3", "MRFG3", "NTCO3", "QUAL3", "SANB11",
        "SLCE3", "SMTO3", "SULA11", "TIMS3", "USIM5",
        "YDUQ3", "AZUL4", "BRFS3", "CCRO3", "CIEL3",
    ],
    "us": [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "META", "TSLA", "JPM", "BRK.B", "UNH",
        "V", "MA", "JNJ", "PG", "HD",
        "XOM", "COST", "ABBV", "KO", "PEP",
        "MRK", "LLY", "AVGO", "CRM", "NFLX",
        "ORCL", "ACN", "ADBE", "CSCO", "AMD",
        "WMT", "DIS", "NKE", "BA", "GS",
        "CAT", "UPS", "MCD", "SBUX", "INTC",
        "T", "VZ", "IBM", "GE", "CVX",
        "COP", "NEE", "LOW", "ISRG", "GILD",
        "AMGN", "MDLZ", "TGT", "F", "GM",
        "SO", "DUK", "PYPL", "TMO", "SLB",
    ],
    "europe": [
        "ASML", "NVO", "SAP", "AZN", "SHEL",
        "UL", "HSBC", "TTE", "SNY", "DEO",
        "GSK", "BCS", "PHG", "ERIC", "NOK",
        "SAN", "BBVA", "ING", "DB", "UBS",
        "ABB", "SPOT", "SE", "SHOP", "LULU",
    ],
    "asia": [
        "TSM", "SONY", "TM", "BABA", "HMC",
        "MUFG", "INFY", "LI", "NIO", "BIDU",
        "JD", "PDD", "WIT", "KB", "SHG",
        "MFG", "SMFG", "IBN", "XPEV", "SE",
    ],
}


class Command(BaseCommand):
    help = "Pre-warm the disk-based logo cache for popular tickers"

    def add_arguments(self, parser):
        parser.add_argument(
            "--region",
            default="all",
            choices=["brazil", "us", "europe", "asia", "all"],
            help="Region to warm logos for (default: all)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Max logos per region (0 = all)",
        )

    def handle(self, *args, **options):
        region = options["region"]
        limit = options["limit"]

        cache_dir = Path(settings.LOGO_CACHE_DIR)
        cache_dir.mkdir(parents=True, exist_ok=True)

        regions = list(POPULAR_SYMBOLS.keys()) if region == "all" else [region]
        total_cached = 0
        total_skipped = 0
        total_failed = 0

        for current_region in regions:
            symbols = POPULAR_SYMBOLS[current_region]
            if limit:
                symbols = symbols[:limit]

            for symbol in symbols:
                cached_path = cache_dir / f"{symbol}.png"

                if cached_path.exists() and not is_brapi_placeholder(cached_path.read_bytes()):
                    total_skipped += 1
                    continue

                image_data = None

                # Try the ticker's own logo URL from DB first (covers FMP, etc.)
                try:
                    ticker = Ticker.objects.get(symbol=symbol)
                    if ticker.logo:
                        logo_request = Request(ticker.logo, headers={"User-Agent": "Sponda/1.0"})
                        with urlopen(logo_request, timeout=10) as response:
                            image_data = response.read()
                except (Ticker.DoesNotExist, Exception):
                    pass

                # Reject BRAPI placeholders from DB URL
                if image_data and is_brapi_placeholder(image_data):
                    image_data = None

                # Fallback to BRAPI direct URL
                if not image_data:
                    brapi_url = BRAPI_LOGO_URL_TEMPLATE.format(symbol=symbol)
                    try:
                        logo_request = Request(brapi_url, headers={"User-Agent": "Sponda/1.0"})
                        with urlopen(logo_request, timeout=10) as response:
                            image_data = response.read()
                    except Exception:
                        pass

                # Reject BRAPI placeholders from fallback
                if image_data and is_brapi_placeholder(image_data):
                    image_data = None

                if not image_data:
                    logger.warning("Failed to fetch logo for %s", symbol)
                    total_failed += 1
                    continue

                cached_path.write_bytes(image_data)
                total_cached += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {total_cached} cached, {total_skipped} skipped, "
                f"{total_failed} failed."
            )
        )
