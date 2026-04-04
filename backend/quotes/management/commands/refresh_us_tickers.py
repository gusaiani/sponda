"""Sync US stock tickers from FMP into the Ticker model."""
import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from quotes.models import Ticker


BATCH_SIZE = 50
ALLOWED_EXCHANGES = {"NYSE", "NASDAQ"}


class Command(BaseCommand):
    help = "Fetch and update the US stock ticker list from FMP"

    def handle(self, *args, **options):
        self.stdout.write("Fetching US stock list from FMP...")
        try:
            stocks = self._fetch_stock_list()
            self.stdout.write(f"Found {len(stocks)} US stocks. Fetching profiles...")
            tickers = self._fetch_profiles_in_batches(stocks)
            self._upsert_tickers(tickers)
            self.stdout.write(self.style.SUCCESS(f"Synced {len(tickers)} US tickers."))
        except Exception as error:
            self.stderr.write(self.style.ERROR(f"Failed to sync US tickers: {error}"))

    def _fetch_stock_list(self) -> list[dict]:
        """Fetch the full stock list and filter to US common stocks."""
        url = f"{settings.FMP_BASE_URL}/stable/company-symbols-list"
        response = requests.get(url, params={"apikey": settings.FMP_API_KEY}, timeout=60)
        response.raise_for_status()
        all_stocks = response.json()

        return [
            stock for stock in all_stocks
            if stock.get("exchangeShortName") in ALLOWED_EXCHANGES
            and stock.get("type") == "stock"
            and stock.get("symbol")
            and "." not in stock.get("symbol", "")
        ]

    def _fetch_profiles_in_batches(self, stocks: list[dict]) -> list[dict]:
        """Fetch company profiles in batches (FMP supports comma-separated symbols)."""
        symbols = [stock["symbol"] for stock in stocks]
        tickers = []

        for batch_start in range(0, len(symbols), BATCH_SIZE):
            batch = symbols[batch_start:batch_start + BATCH_SIZE]
            joined_symbols = ",".join(batch)
            url = f"{settings.FMP_BASE_URL}/stable/profile-symbol"
            try:
                response = requests.get(
                    url,
                    params={"symbol": joined_symbols, "apikey": settings.FMP_API_KEY},
                    timeout=60,
                )
                response.raise_for_status()
                profiles = response.json()
                if isinstance(profiles, list):
                    tickers.extend(profiles)
            except requests.RequestException as error:
                self.stderr.write(f"  Batch failed ({batch[0]}..{batch[-1]}): {error}")

        return tickers

    def _upsert_tickers(self, profiles: list[dict]) -> None:
        """Upsert profile data into the Ticker model."""
        objects = []
        for profile in profiles:
            symbol = (profile.get("symbol") or "").strip().upper()
            if not symbol:
                continue

            objects.append(Ticker(
                symbol=symbol,
                name=profile.get("companyName") or "",
                display_name=profile.get("companyName") or "",
                sector=profile.get("sector") or "",
                type="stock",
                logo=profile.get("image") or "",
            ))

        if objects:
            Ticker.objects.bulk_create(
                objects,
                update_conflicts=True,
                unique_fields=["symbol"],
                update_fields=["name", "display_name", "sector", "type", "logo"],
            )
