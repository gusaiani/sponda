"""The symbol list the sitemap is generated from.

The sitemap needs every listed company's symbol and nothing else. The
existing /api/tickers/ endpoint carries names, sectors and logo URLs for
~27K rows, which is megabytes of payload to answer a question that fits in
about 150KB.
"""
import pytest
from django.urls import reverse

from quotes.models import IndicatorSnapshot, Ticker


@pytest.fixture
def universe(db):
    Ticker.objects.create(symbol="PETR4", name="Petrobras", type="stock")
    Ticker.objects.create(symbol="AAPL", name="Apple", type="stock")
    Ticker.objects.create(symbol="BOVA11", name="Bova", type="fund")
    # Fractional B3 symbols end in F and are the same company as the round
    # lot, so the existing sitemap excludes them.
    Ticker.objects.create(symbol="PETR4F", name="Petrobras frac", type="stock")
    # A listed company we hold no indicators for. 768 of the 18,400 stock
    # tickers were in this state when the sitemap was rebuilt.
    Ticker.objects.create(symbol="NODATA3", name="No Data", type="stock")

    for symbol in ("PETR4", "AAPL", "PETR4F", "BOVA11"):
        IndicatorSnapshot.objects.create(ticker=symbol)


@pytest.mark.django_db
class TestTickerSymbolsView:
    def _url(self):
        return reverse("ticker-symbols")

    def test_lists_listed_companies(self, universe):
        payload = self.client_get()
        assert "PETR4" in payload["symbols"]
        assert "AAPL" in payload["symbols"]

    def test_excludes_funds(self, universe):
        assert "BOVA11" not in self.client_get()["symbols"]

    def test_excludes_fractional_symbols(self, universe):
        assert "PETR4F" not in self.client_get()["symbols"]

    def test_excludes_companies_with_no_indicator_data(self, universe):
        # A company page with no numbers is a thin page. Listing hundreds of
        # them in a sitemap invites a soft-404 judgement across the domain.
        assert "NODATA3" not in self.client_get()["symbols"]

    def test_reports_a_count_matching_the_list(self, universe):
        payload = self.client_get()
        assert payload["count"] == len(payload["symbols"])

    def test_is_sorted_so_the_sitemap_is_stable_between_builds(self, universe):
        symbols = self.client_get()["symbols"]
        assert symbols == sorted(symbols)

    def test_is_publicly_cacheable(self, universe):
        from django.test import Client
        assert "public" in Client().get(self._url())["Cache-Control"]

    def test_carries_no_per_company_detail(self, universe):
        # Just strings. Anything richer belongs on /api/tickers/.
        assert all(isinstance(s, str) for s in self.client_get()["symbols"])

    def client_get(self):
        from django.test import Client
        return Client().get(self._url()).json()
