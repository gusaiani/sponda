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
    def test_returns_404_for_unknown_ticker(self, api_client, db):
        response = api_client.get("/api/logos/UNKNOWN.png")
        assert response.status_code == 404

    def test_returns_404_for_ticker_without_logo(self, api_client, db):
        Ticker.objects.create(symbol="AAPL", name="Apple", type="stock", logo="")
        response = api_client.get("/api/logos/AAPL.png")
        assert response.status_code == 404

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
    def test_returns_404_when_download_fails(self, mock_urlopen, api_client, db):
        Ticker.objects.create(
            symbol="AAPL", name="Apple", type="stock",
            logo="https://example.com/AAPL.png",
        )
        mock_urlopen.side_effect = Exception("Connection refused")

        response = api_client.get("/api/logos/AAPL.png")
        assert response.status_code == 404

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
