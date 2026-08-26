"""A DFP archive the CVM has not published yet is not an error.

WEB-DJANGO-1K: ``sync_cvm_fourth_quarters`` ran for 2025 on 2026-08-17,
before the CVM had put ``dfp_cia_aberta_2025.zip`` online, and the bare 404
travelled up through ``MonitoredCommand`` into Sentry as a production
error. The archive appeared later that year, so nothing was actually wrong.

This is structural: the job necessarily runs for a year before the CVM
publishes it, so the same page fires every year. A 404 on the archive means
"not published yet" and should end the run cleanly. Any other HTTP failure
is still a real error and must keep raising.
"""
from __future__ import annotations

import pytest
import requests

from quotes.cvm import DfpArchiveNotPublished, download_dfp_archive


class _FakeResponse:
    def __init__(self, status_code, content=b""):
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(
                f"{self.status_code} Client Error", response=self,
            )


def test_missing_archive_raises_the_dedicated_not_published_error(monkeypatch):
    monkeypatch.setattr(
        "quotes.cvm.requests.get", lambda *a, **kw: _FakeResponse(404),
    )

    with pytest.raises(DfpArchiveNotPublished) as raised:
        download_dfp_archive(2025)

    assert "2025" in str(raised.value)


def test_other_http_failures_still_raise_the_original_error(monkeypatch):
    """A 500 is a real failure and must stay loud."""
    monkeypatch.setattr(
        "quotes.cvm.requests.get", lambda *a, **kw: _FakeResponse(500),
    )

    with pytest.raises(requests.HTTPError):
        download_dfp_archive(2025)


def test_published_archive_returns_its_bytes(monkeypatch):
    monkeypatch.setattr(
        "quotes.cvm.requests.get",
        lambda *a, **kw: _FakeResponse(200, b"zip-bytes"),
    )

    assert download_dfp_archive(2024) == b"zip-bytes"


@pytest.mark.django_db
def test_command_reports_and_exits_cleanly_when_the_archive_is_absent(
    monkeypatch, capsys,
):
    """The command must not raise, so nothing reaches Sentry."""
    from django.core.management import call_command

    from quotes.models import Ticker

    Ticker.objects.create(symbol="PETR4", name="Petrobras", cvm_code="9512")

    def _absent(year):
        raise DfpArchiveNotPublished(
            f"CVM has not published the {year} DFP archive yet",
        )

    monkeypatch.setattr(
        "quotes.management.commands.sync_cvm_fourth_quarters.download_dfp_archive",
        _absent,
    )
    monkeypatch.setattr(
        "quotes.management.commands.sync_cvm_fourth_quarters.Command._pending",
        lambda self, year: [("PETR4", "9512", {})],
    )

    call_command("sync_cvm_fourth_quarters", "--year", "2025")

    assert "not published" in capsys.readouterr().out.lower()
