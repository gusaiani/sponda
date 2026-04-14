"""Tests for logo proxy view."""
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from django.test import Client

from quotes.models import Ticker

LOGO_CACHE_DIR = Path("/tmp/test_logo_cache")


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture(autouse=True)
def use_test_logo_cache(settings):
    """Point LOGO_CACHE_DIR to a temp directory and clean up after."""
    settings.LOGO_CACHE_DIR = LOGO_CACHE_DIR
    if LOGO_CACHE_DIR.exists():
        shutil.rmtree(LOGO_CACHE_DIR)
    LOGO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    yield
    if LOGO_CACHE_DIR.exists():
        shutil.rmtree(LOGO_CACHE_DIR)


def _mock_urlopen(image_data=b"\x89PNG\r\n\x1a\nfake_image_data"):
    mock_response = MagicMock()
    mock_response.read.return_value = image_data
    mock_response.headers = {"Content-Type": "image/png"}
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


class TestLogoProxy:
    @patch("quotes.views.urlopen")
    def test_returns_fallback_for_unknown_ticker(self, mock_urlopen, api_client, db):
        mock_urlopen.side_effect = Exception("Not found")
        response = api_client.get("/api/logos/UNKNOWN.png")
        assert response.status_code == 200
        assert response["Content-Type"] == "image/svg+xml"
        assert b">U<" in response.content

    @patch("quotes.views.urlopen")
    def test_returns_fallback_for_ticker_without_logo(self, mock_urlopen, api_client, db):
        mock_urlopen.side_effect = Exception("Not found")
        Ticker.objects.create(symbol="AAPL", name="Apple", type="stock", logo="")
        response = api_client.get("/api/logos/AAPL.png")
        assert response.status_code == 200
        assert response["Content-Type"] == "image/svg+xml"
        assert b">A<" in response.content

    @patch("quotes.views.urlopen")
    def test_downloads_and_caches_logo(self, mock_urlopen, api_client, db):
        Ticker.objects.create(
            symbol="AAPL", name="Apple", type="stock",
            logo="https://example.com/AAPL.png",
        )
        fake_image = b"\x89PNG\r\n\x1a\nfake_image_data"
        mock_urlopen.return_value = _mock_urlopen(fake_image)

        response = api_client.get("/api/logos/AAPL.png")
        assert response.status_code == 200
        assert response["Content-Type"] == "image/png"
        assert response.content == fake_image

        cached_path = LOGO_CACHE_DIR / "AAPL.png"
        assert cached_path.exists()
        assert cached_path.read_bytes() == fake_image

    @patch("quotes.views.urlopen")
    def test_serves_from_cache_without_fetching(self, mock_urlopen, api_client, db):
        Ticker.objects.create(
            symbol="AAPL", name="Apple", type="stock",
            logo="https://example.com/AAPL.png",
        )
        fake_image = b"\x89PNG\r\n\x1a\nfake_image_data"
        (LOGO_CACHE_DIR / "AAPL.png").write_bytes(fake_image)

        response = api_client.get("/api/logos/AAPL.png")
        assert response.status_code == 200
        assert response.content == fake_image
        mock_urlopen.assert_not_called()

    @patch("quotes.views.urlopen")
    def test_has_long_cache_headers(self, mock_urlopen, api_client, db):
        Ticker.objects.create(
            symbol="AAPL", name="Apple", type="stock",
            logo="https://example.com/AAPL.png",
        )
        mock_urlopen.return_value = _mock_urlopen()

        response = api_client.get("/api/logos/AAPL.png")
        assert "max-age" in response.get("Cache-Control", "")

    @patch("quotes.views.urlopen")
    def test_returns_fallback_when_download_fails(self, mock_urlopen, api_client, db):
        Ticker.objects.create(
            symbol="AAPL", name="Apple", type="stock",
            logo="https://example.com/AAPL.png",
        )
        mock_urlopen.side_effect = Exception("Connection refused")

        response = api_client.get("/api/logos/AAPL.png")
        assert response.status_code == 200
        assert response["Content-Type"] == "image/svg+xml"
        assert b">A<" in response.content

    @patch("quotes.views.urlopen")
    def test_serves_svg_logo_with_correct_content_type(self, mock_urlopen, api_client, db):
        Ticker.objects.create(
            symbol="PETR4", name="Petrobras", type="stock",
            logo="https://icons.brapi.dev/icons/PETR4.svg",
        )
        svg_data = b'<svg xmlns="http://www.w3.org/2000/svg" width="56" height="56"></svg>'
        mock_urlopen.return_value = _mock_urlopen(svg_data)

        response = api_client.get("/api/logos/PETR4.png")
        assert response.status_code == 200
        assert response["Content-Type"] == "image/svg+xml"
        assert response.content == svg_data

    def test_serves_cached_svg_with_correct_content_type(self, api_client, db):
        svg_data = b'<svg xmlns="http://www.w3.org/2000/svg" width="56" height="56"></svg>'
        (LOGO_CACHE_DIR / "VALE3.png").write_bytes(svg_data)

        Ticker.objects.create(
            symbol="VALE3", name="Vale", type="stock",
            logo="https://icons.brapi.dev/icons/VALE3.svg",
        )
        response = api_client.get("/api/logos/VALE3.png")
        assert response.status_code == 200
        assert response["Content-Type"] == "image/svg+xml"

    @patch("quotes.views.urlopen")
    def test_serves_jpeg_logo_with_correct_content_type(self, mock_urlopen, api_client, db):
        Ticker.objects.create(
            symbol="MSFT", name="Microsoft", type="stock",
            logo="https://example.com/MSFT.jpg",
        )
        jpeg_data = b"\xff\xd8\xff\xe0fake_jpeg_data"
        mock_urlopen.return_value = _mock_urlopen(jpeg_data)

        response = api_client.get("/api/logos/MSFT.png")
        assert response.status_code == 200
        assert response["Content-Type"] == "image/jpeg"

    @patch("quotes.views.urlopen")
    def test_serves_png_logo_with_png_content_type(self, mock_urlopen, api_client, db):
        Ticker.objects.create(
            symbol="GOOG", name="Google", type="stock",
            logo="https://example.com/GOOG.png",
        )
        png_data = b"\x89PNG\r\n\x1a\nfake_png_data"
        mock_urlopen.return_value = _mock_urlopen(png_data)

        response = api_client.get("/api/logos/GOOG.png")
        assert response.status_code == 200
        assert response["Content-Type"] == "image/png"

    @patch("quotes.views.urlopen")
    def test_tries_brapi_when_ticker_not_in_database(self, mock_urlopen, api_client, db):
        """When a ticker is in the popular list but not in our DB, try BRAPI directly."""
        svg_data = b'<svg xmlns="http://www.w3.org/2000/svg" width="56" height="56"><circle/></svg>'
        mock_urlopen.return_value = _mock_urlopen(svg_data)

        response = api_client.get("/api/logos/ELET3.png")
        assert response.status_code == 200
        assert response["Content-Type"] == "image/svg+xml"
        assert response.content == svg_data

        # Verify it tried the BRAPI URL
        call_args = mock_urlopen.call_args[0][0]
        assert "icons.brapi.dev" in call_args.full_url
        assert "ELET3" in call_args.full_url

    @patch("quotes.views.urlopen")
    def test_caches_brapi_fallback_logo(self, mock_urlopen, api_client, db):
        """BRAPI fallback logos should be cached to disk."""
        svg_data = b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
        mock_urlopen.return_value = _mock_urlopen(svg_data)

        api_client.get("/api/logos/JBSS3.png")

        cached_path = LOGO_CACHE_DIR / "JBSS3.png"
        assert cached_path.exists()
        assert cached_path.read_bytes() == svg_data

    @patch("quotes.views.urlopen")
    def test_rejects_brapi_placeholder_logo(self, mock_urlopen, api_client, db):
        """BRAPI returns its own branding SVG for unknown tickers. Reject it."""
        Ticker.objects.create(
            symbol="ITSA4", name="Itausa", type="stock",
            logo="https://icons.brapi.dev/icons/BRAPI.svg",
        )
        brapi_placeholder = (
            b'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512">'
            b"<title>brapi</title>"
            b'<desc>Logo oficial da brapi em brapi.dev</desc>'
            b"</svg>"
        )
        mock_urlopen.return_value = _mock_urlopen(brapi_placeholder)

        response = api_client.get("/api/logos/ITSA4.png")
        # Should return a fallback SVG, not the BRAPI placeholder
        assert response.status_code == 200
        assert response["Content-Type"] == "image/svg+xml"
        assert b"brapi" not in response.content

    @patch("quotes.views.urlopen")
    def test_does_not_cache_brapi_placeholder(self, mock_urlopen, api_client, db):
        """BRAPI placeholders should never be written to disk cache."""
        Ticker.objects.create(
            symbol="FAKE1", name="Fake", type="stock",
            logo="https://icons.brapi.dev/icons/BRAPI.svg",
        )
        brapi_placeholder = (
            b'<svg xmlns="http://www.w3.org/2000/svg">'
            b"<title>brapi</title>"
            b'<desc>Logo oficial da brapi em brapi.dev</desc>'
            b"</svg>"
        )
        mock_urlopen.return_value = _mock_urlopen(brapi_placeholder)

        api_client.get("/api/logos/FAKE1.png")

        cached_path = LOGO_CACHE_DIR / "FAKE1.png"
        assert not cached_path.exists()

    def test_returns_fallback_svg_when_all_sources_fail(self, api_client, db):
        """When no logo can be fetched, return a generated fallback SVG."""
        response = api_client.get("/api/logos/NOPE3.png")
        assert response.status_code == 200
        assert response["Content-Type"] == "image/svg+xml"
        # Fallback should contain the ticker initial
        assert b">N<" in response.content

    @patch("quotes.views.urlopen")
    def test_brapi_fallback_failure_returns_fallback_svg(self, mock_urlopen, api_client, db):
        """When BRAPI also fails, return a generated fallback SVG."""
        mock_urlopen.side_effect = Exception("Connection refused")

        response = api_client.get("/api/logos/ELET3.png")
        assert response.status_code == 200
        assert response["Content-Type"] == "image/svg+xml"
        assert b">E<" in response.content

    def test_fallback_svg_is_not_cached(self, api_client, db):
        """Fallback SVGs should not be cached to avoid masking future real logos."""
        api_client.get("/api/logos/NOPE3.png")

        cached_path = LOGO_CACHE_DIR / "NOPE3.png"
        assert not cached_path.exists()

    @patch("quotes.views.LOGO_OVERRIDE_URLS", {"TKNO4": "https://example.com/tekno.png"})
    @patch("quotes.views.urlopen")
    def test_manual_override_is_used_before_db_logo(self, mock_urlopen, api_client, db):
        """Manual override takes precedence over the logo URL stored on the Ticker row."""
        Ticker.objects.create(
            symbol="TKNO4", name="Tekno", type="stock",
            logo="https://icons.brapi.dev/icons/BRAPI.svg",
        )
        fake_image = b"\x89PNG\r\n\x1a\nfake_tekno"
        mock_urlopen.return_value = _mock_urlopen(fake_image)

        response = api_client.get("/api/logos/TKNO4.png")
        assert response.status_code == 200
        assert response.content == fake_image
        # Must have fetched the override URL, not the BRAPI placeholder
        fetched_url = mock_urlopen.call_args[0][0].full_url
        assert fetched_url == "https://example.com/tekno.png"

    @patch("quotes.views.urlopen")
    def test_rejects_brapi_placeholder_url_from_db(self, mock_urlopen, api_client, db):
        """BRAPI's generic placeholder URL stored on the Ticker row must be ignored entirely,
        skipping the wasted fetch and going straight to the BRAPI symbol fallback."""
        Ticker.objects.create(
            symbol="KLBN4", name="Klabin", type="stock",
            logo="https://icons.brapi.dev/icons/BRAPI.svg",
        )
        real_logo = b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
        mock_urlopen.return_value = _mock_urlopen(real_logo)

        response = api_client.get("/api/logos/KLBN4.png")
        assert response.status_code == 200
        # We never fetched the placeholder URL
        for call in mock_urlopen.call_args_list:
            assert "BRAPI.svg" not in call[0][0].full_url

    @patch("quotes.views.urlopen")
    def test_negative_cache_prevents_repeat_fetches(self, mock_urlopen, api_client, db):
        """When all sources fail for a ticker, subsequent requests must serve the fallback
        without re-fetching from the network for the duration of the negative-cache TTL."""
        Ticker.objects.create(symbol="MISSING3", name="Missing", type="stock", logo="")
        mock_urlopen.side_effect = Exception("Not found")

        # First request exhausts all sources and falls back.
        api_client.get("/api/logos/MISSING3.png")
        first_call_count = mock_urlopen.call_count
        assert first_call_count >= 1

        # Second request within TTL should hit the negative cache — no new fetches.
        api_client.get("/api/logos/MISSING3.png")
        assert mock_urlopen.call_count == first_call_count

    @patch("quotes.views.urlopen")
    def test_purges_cached_brapi_placeholder(self, mock_urlopen, api_client, db):
        """If a cached file is a BRAPI placeholder, delete it and serve fallback."""
        brapi_placeholder = (
            b'<svg xmlns="http://www.w3.org/2000/svg">'
            b"<title>brapi</title>"
            b'<desc>Logo oficial da brapi em brapi.dev</desc>'
            b"</svg>"
        )
        (LOGO_CACHE_DIR / "ITSA4.png").write_bytes(brapi_placeholder)
        # All fetch attempts also return placeholders or fail
        mock_urlopen.side_effect = Exception("Unavailable")

        response = api_client.get("/api/logos/ITSA4.png")
        assert response.status_code == 200
        assert b"brapi" not in response.content
        # Cached placeholder should have been deleted
        assert not (LOGO_CACHE_DIR / "ITSA4.png").exists()
