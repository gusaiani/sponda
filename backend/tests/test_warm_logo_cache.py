"""Tests for the warm_logo_cache management command."""
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from django.core.management import call_command

from quotes.models import Ticker

LOGO_CACHE_DIR = Path("/tmp/test_logo_cache_warmup")


@pytest.fixture(autouse=True)
def use_test_logo_cache(settings):
    settings.LOGO_CACHE_DIR = LOGO_CACHE_DIR
    if LOGO_CACHE_DIR.exists():
        shutil.rmtree(LOGO_CACHE_DIR)
    LOGO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    yield
    if LOGO_CACHE_DIR.exists():
        shutil.rmtree(LOGO_CACHE_DIR)


def _mock_urlopen_factory(valid_symbols=None):
    """Return a mock urlopen that serves real SVGs for valid_symbols, fails for others."""
    valid_symbols = valid_symbols or set()

    def side_effect(request, timeout=10):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        symbol = url.split("/")[-1].replace(".svg", "").replace(".png", "")
        if symbol in valid_symbols:
            svg = f'<svg xmlns="http://www.w3.org/2000/svg"><text>{symbol}</text></svg>'
            mock_response = MagicMock()
            mock_response.read.return_value = svg.encode()
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            return mock_response
        raise Exception(f"Not found: {symbol}")

    return side_effect


class TestWarmLogoCache:
    @patch("quotes.management.commands.warm_logo_cache.urlopen")
    def test_fetches_logos_for_popular_symbols(self, mock_urlopen, db):
        mock_urlopen.side_effect = _mock_urlopen_factory({"PETR4", "VALE3"})

        call_command("warm_logo_cache", "--region", "brazil", "--limit", "2")

        assert (LOGO_CACHE_DIR / "PETR4.png").exists()
        assert (LOGO_CACHE_DIR / "VALE3.png").exists()

    @patch("quotes.management.commands.warm_logo_cache.urlopen")
    def test_skips_already_cached_symbols(self, mock_urlopen, db):
        (LOGO_CACHE_DIR / "PETR4.png").write_bytes(b"<svg>existing</svg>")
        mock_urlopen.side_effect = _mock_urlopen_factory({"VALE3"})

        call_command("warm_logo_cache", "--region", "brazil", "--limit", "2")

        # Should not have re-fetched PETR4
        assert (LOGO_CACHE_DIR / "PETR4.png").read_bytes() == b"<svg>existing</svg>"

    @patch("quotes.management.commands.warm_logo_cache.urlopen")
    def test_rejects_brapi_placeholder(self, mock_urlopen, db):
        def side_effect(request, timeout=10):
            mock_response = MagicMock()
            mock_response.read.return_value = (
                b'<svg xmlns="http://www.w3.org/2000/svg">'
                b"<title>brapi</title>"
                b'<desc>Logo oficial da brapi em brapi.dev</desc>'
                b"</svg>"
            )
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            return mock_response

        mock_urlopen.side_effect = side_effect

        call_command("warm_logo_cache", "--region", "brazil", "--limit", "1")

        # Should not cache BRAPI placeholders
        assert not (LOGO_CACHE_DIR / "PETR4.png").exists()

    @patch("quotes.management.commands.warm_logo_cache.urlopen")
    def test_continues_on_individual_failure(self, mock_urlopen, db):
        """A failed logo fetch should not stop the entire warmup."""
        mock_urlopen.side_effect = _mock_urlopen_factory({"VALE3"})

        call_command("warm_logo_cache", "--region", "brazil", "--limit", "2")

        # PETR4 failed but VALE3 should still be cached
        assert not (LOGO_CACHE_DIR / "PETR4.png").exists()
        assert (LOGO_CACHE_DIR / "VALE3.png").exists()

    @patch("quotes.management.commands.warm_logo_cache.urlopen")
    def test_supports_all_regions(self, mock_urlopen, db):
        mock_urlopen.side_effect = _mock_urlopen_factory({"AAPL"})

        call_command("warm_logo_cache", "--region", "us", "--limit", "1")

        assert (LOGO_CACHE_DIR / "AAPL.png").exists()

    @patch("quotes.management.commands.warm_logo_cache.urlopen")
    def test_all_regions_mode(self, mock_urlopen, db):
        mock_urlopen.side_effect = _mock_urlopen_factory(
            {"PETR4", "AAPL", "ASML", "TSM"}
        )

        call_command("warm_logo_cache", "--region", "all", "--limit", "1")

        # Should have fetched 1 per region
        assert (LOGO_CACHE_DIR / "PETR4.png").exists()
        assert (LOGO_CACHE_DIR / "AAPL.png").exists()
        assert (LOGO_CACHE_DIR / "ASML.png").exists()
        assert (LOGO_CACHE_DIR / "TSM.png").exists()

    @patch("quotes.management.commands.warm_logo_cache.urlopen")
    def test_tries_db_logo_url_before_brapi(self, mock_urlopen, db):
        """Should try the ticker's FMP URL from DB before falling back to BRAPI."""
        Ticker.objects.create(
            symbol="AAPL", name="Apple", type="stock",
            logo="https://financialmodelingprep.com/image-stock/AAPL.png",
        )
        mock_urlopen.side_effect = _mock_urlopen_factory({"AAPL"})

        call_command("warm_logo_cache", "--region", "us", "--limit", "1")

        assert (LOGO_CACHE_DIR / "AAPL.png").exists()
        # Should have tried the FMP URL first
        first_call_url = mock_urlopen.call_args_list[0][0][0].full_url
        assert "financialmodelingprep.com" in first_call_url
