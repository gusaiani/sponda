"""Sync US stock tickers from FMP into the Ticker model.

Only imports actual companies. ETFs, funds, trusts, and other
non-company instruments are excluded.
"""
import re

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from quotes.fmp import fetch_etf_symbols
from quotes.models import Ticker

BRAZILIAN_TICKER_PATTERN = re.compile(r"^[A-Z]+\d+$")

NON_COMPANY_NAME_PATTERNS = re.compile(
    r"\b("
    r"ETF|Funds?\b|"
    r"iShares|Vanguard|SPDR|ProShares|"
    r"Direxion|WisdomTree|VanEck|"
    r"Trgt Date|Target Date|"
    r"Class [A-Z]\d|Cl [A-Z][-\d]|"
    r"Preferred|Depositary Shares|Convertible|"
    r"Warrant|Notes Due|Debenture"
    r")",
    re.IGNORECASE,
)

# Instruments with a percentage in the name (e.g. "4.125%", "5.70%") are
# almost always fixed-income securities, not common stock.
FIXED_RATE_PATTERN = re.compile(r"\d+\.\d+%")


class Command(BaseCommand):
    help = "Fetch and update the US stock ticker list from FMP"

    def handle(self, *args, **options):
        self.stdout.write("Fetching US stock list from FMP...")
        try:
            stocks = self._fetch_companies()
            self.stdout.write(f"Found {len(stocks)} US companies. Upserting...")
            self._upsert_tickers(stocks)
            self.stdout.write(self.style.SUCCESS(f"Synced {len(stocks)} US tickers."))
        except Exception as error:
            self.stderr.write(self.style.ERROR(f"Failed to sync US tickers: {error}"))

    def _fetch_companies(self) -> list[dict]:
        """Fetch the stock list from FMP, keeping only actual companies.

        Excludes ETFs (via FMP's ETF list), funds, trusts, and other
        non-company instruments (via name patterns). Also skips tickers
        with dots (preferred shares like BRK.B) and Brazilian-format
        tickers (letters + digits) since those come from BRAPI.
        """
        url = f"{settings.FMP_BASE_URL}/stable/stock-list"
        response = requests.get(url, params={"apikey": settings.FMP_API_KEY}, timeout=60)
        response.raise_for_status()
        all_stocks = response.json()

        self.stdout.write("Fetching ETF list for exclusion...")
        etf_symbols = fetch_etf_symbols()
        self.stdout.write(f"Found {len(etf_symbols)} ETF symbols to exclude.")

        companies = []
        for stock in all_stocks:
            symbol = (stock.get("symbol") or "").strip().upper()
            company_name = stock.get("companyName") or ""

            if not symbol or not company_name:
                continue
            if "." in symbol:
                continue
            if BRAZILIAN_TICKER_PATTERN.match(symbol):
                continue
            if symbol in etf_symbols:
                continue
            if NON_COMPANY_NAME_PATTERNS.search(company_name):
                continue
            if FIXED_RATE_PATTERN.search(company_name):
                continue

            companies.append(stock)

        return companies

    def _upsert_tickers(self, stocks: list[dict]) -> None:
        """Upsert company data into the Ticker model."""
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

            # Remove US tickers that are no longer in the filtered list.
            # US tickers are those that don't match the Brazilian pattern
            # (letters + digits like PETR4).
            synced_symbols = {ticker.symbol for ticker in objects}
            stale_us_tickers = (
                Ticker.objects.exclude(symbol__in=synced_symbols)
                .exclude(symbol__regex=r"^[A-Z]+\d+$")
            )
            deleted_count = stale_us_tickers.count()
            if deleted_count > 0:
                stale_us_tickers.delete()
