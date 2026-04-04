"""Sync US stock tickers from FMP into the Ticker model."""
import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from quotes.models import Ticker


class Command(BaseCommand):
    help = "Fetch and update the US stock ticker list from FMP"

    def handle(self, *args, **options):
        self.stdout.write("Fetching US stock list from FMP...")
        try:
            stocks = self._fetch_stock_list()
            self.stdout.write(f"Found {len(stocks)} US stocks. Upserting...")
            self._upsert_tickers(stocks)
            self.stdout.write(self.style.SUCCESS(f"Synced {len(stocks)} US tickers."))
        except Exception as error:
            self.stderr.write(self.style.ERROR(f"Failed to sync US tickers: {error}"))

    def _fetch_stock_list(self) -> list[dict]:
        """Fetch the full stock list from FMP.

        Returns all entries with a symbol and company name. Filters out
        tickers with dots (preferred shares like BRK.B) since they cause
        URL routing issues, and tickers that look Brazilian (letters + digits).
        """
        url = f"{settings.FMP_BASE_URL}/stable/stock-list"
        response = requests.get(url, params={"apikey": settings.FMP_API_KEY}, timeout=60)
        response.raise_for_status()
        all_stocks = response.json()

        import re
        brazilian_pattern = re.compile(r"^[A-Z]+\d+$")

        return [
            stock for stock in all_stocks
            if stock.get("symbol")
            and stock.get("companyName")
            and "." not in stock["symbol"]
            and not brazilian_pattern.match(stock["symbol"])
        ]

    def _upsert_tickers(self, stocks: list[dict]) -> None:
        """Upsert stock list data into the Ticker model."""
        objects = []
        for stock in stocks:
            symbol = stock["symbol"].strip().upper()
            company_name = stock.get("companyName") or ""

            objects.append(Ticker(
                symbol=symbol,
                name=company_name,
                display_name=company_name,
                sector="",
                type="stock",
                logo=f"https://financialmodelingprep.com/image-stock/{symbol}.png",
            ))

        if objects:
            Ticker.objects.bulk_create(
                objects,
                update_conflicts=True,
                unique_fields=["symbol"],
                update_fields=["name", "display_name", "type", "logo"],
            )
