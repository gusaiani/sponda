"""Tests for the audit_logos management command."""
import io
from unittest.mock import patch, MagicMock

import pytest
from django.core.management import call_command

from quotes.models import Ticker


def _mock_urlopen_factory(content_by_url: dict[str, bytes]):
    def _opener(request, timeout=None):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        if url not in content_by_url:
            raise Exception("Connection refused")
        response = MagicMock()
        response.read.return_value = content_by_url[url]
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)
        return response
    return _opener


@pytest.mark.django_db
class TestAuditLogosCommand:
    @patch("quotes.management.commands.audit_logos.urlopen")
    def test_reports_tickers_with_no_real_logo(self, mock_urlopen):
        """Tickers whose URL returns a BRAPI placeholder — or nothing — must be listed."""
        Ticker.objects.create(
            symbol="REAL3", name="Real Co", type="stock",
            logo="https://example.com/real.png",
        )
        Ticker.objects.create(
            symbol="MISS3", name="Missing Co", type="stock",
            logo="",
        )
        Ticker.objects.create(
            symbol="PLAC3", name="Placeholder Co", type="stock",
            logo="https://icons.brapi.dev/icons/PLAC3.svg",
        )

        real_png = b"\x89PNG\r\n\x1a\nreal_image"
        brapi_placeholder = (
            b'<svg xmlns="http://www.w3.org/2000/svg">'
            b"<title>brapi</title></svg>"
        )
        mock_urlopen.side_effect = _mock_urlopen_factory({
            "https://example.com/real.png": real_png,
            "https://icons.brapi.dev/icons/PLAC3.svg": brapi_placeholder,
            # MISS3 has no URL stored; BRAPI fallback also returns placeholder
            "https://icons.brapi.dev/icons/MISS3.svg": brapi_placeholder,
        })

        out = io.StringIO()
        call_command("audit_logos", stdout=out)
        output = out.getvalue()

        assert "MISS3" in output
        assert "PLAC3" in output
        assert "REAL3" not in output

    @patch("quotes.management.commands.audit_logos.urlopen")
    def test_respects_manual_overrides(self, mock_urlopen):
        """Tickers covered by LOGO_OVERRIDE_URLS must not appear as missing."""
        Ticker.objects.create(
            symbol="OVERRIDE3", name="Override Co", type="stock",
            logo="https://icons.brapi.dev/icons/BRAPI.svg",
        )
        real_png = b"\x89PNG\r\n\x1a\noverride_real"
        mock_urlopen.side_effect = _mock_urlopen_factory({
            "https://example.com/override.png": real_png,
        })

        out = io.StringIO()
        with patch(
            "quotes.management.commands.audit_logos.LOGO_OVERRIDE_URLS",
            {"OVERRIDE3": "https://example.com/override.png"},
        ):
            call_command("audit_logos", stdout=out)

        assert "OVERRIDE3" not in out.getvalue()
