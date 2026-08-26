"""Tests for IndexNow submission.

IndexNow pushes changed URLs to Bing, DuckDuckGo, Yandex, Seznam and Naver
instead of waiting to be crawled. That matters more than usual here: Bing's
index feeds DuckDuckGo and Copilot, so it is a direct route to the assistants
the markdown pages were built for.

The failure mode worth guarding is silence. A key file that drifts from the
configured key means every submission is rejected with a 403 and nothing
tells you.
"""
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from quotes.indexnow import (
    INDEXNOW_ENDPOINT,
    MAX_URLS_PER_SUBMISSION,
    build_company_urls,
    key_file_url,
)
from quotes.models import IndexNowSubmission, IndicatorSnapshot, Ticker


@pytest.fixture
def covered_universe(db, settings):
    settings.INDEXNOW_KEY = "a5f3f339c2ccec965e5023c23cccbcdb"
    for symbol in ("PETR4", "VALE3", "AAPL"):
        Ticker.objects.create(symbol=symbol, name=symbol, type="stock")
        IndicatorSnapshot.objects.create(ticker=symbol)
    # Listed, but we hold no indicators. Nothing to index.
    Ticker.objects.create(symbol="NODATA3", name="No Data", type="stock")
    # Not a company.
    Ticker.objects.create(symbol="BOVA11", name="Bova", type="fund")
    IndicatorSnapshot.objects.create(ticker="BOVA11")


class TestUrlBuilding:
    def test_submits_the_html_page_per_sitemap_locale(self):
        assert build_company_urls(["PETR4"]) == [
            "https://sponda.capital/en/PETR4",
            "https://sponda.capital/pt/PETR4",
        ]

    def test_does_not_submit_the_markdown_twin(self):
        # IndexNow is for search indexing. The .md pages are not in the
        # sitemap and are not meant to rank; they are for direct readers.
        assert not any(url.endswith(".md") for url in build_company_urls(["PETR4"]))

    def test_does_not_submit_tab_pages(self):
        assert all(url.count("/") == 4 for url in build_company_urls(["PETR4"]))

    def test_key_file_url_matches_the_configured_key(self, settings):
        settings.INDEXNOW_KEY = "abc123"
        assert key_file_url() == "https://sponda.capital/abc123.txt"


@pytest.mark.django_db
class TestSubmitCommand:
    def _response(self, status_code=200, text=""):
        response = MagicMock()
        response.status_code = status_code
        response.text = text
        return response

    def _run(self, requests_stub, *args):
        with patch("quotes.indexnow.requests", requests_stub):
            call_command("submit_indexnow", *args)

    def _stub(self, key_text="a5f3f339c2ccec965e5023c23cccbcdb", post_status=200):
        stub = MagicMock()
        stub.RequestException = Exception
        stub.get.return_value = self._response(200, key_text)
        stub.post.return_value = self._response(post_status)
        return stub

    def test_submits_companies_with_indicator_data(self, covered_universe):
        stub = self._stub()
        self._run(stub)
        payload = stub.post.call_args.kwargs["json"]
        assert "https://sponda.capital/en/PETR4" in payload["urlList"]

    def test_skips_companies_with_no_indicator_data(self, covered_universe):
        stub = self._stub()
        self._run(stub)
        payload = stub.post.call_args.kwargs["json"]
        assert not any("NODATA3" in url for url in payload["urlList"])

    def test_skips_funds(self, covered_universe):
        stub = self._stub()
        self._run(stub)
        payload = stub.post.call_args.kwargs["json"]
        assert not any("BOVA11" in url for url in payload["urlList"])

    def test_records_what_it_submitted(self, covered_universe):
        self._run(self._stub())
        assert set(IndexNowSubmission.objects.values_list("ticker", flat=True)) == {
            "PETR4", "VALE3", "AAPL",
        }

    def test_does_not_resubmit_a_company_already_sent(self, covered_universe):
        self._run(self._stub())
        stub = self._stub()
        self._run(stub)
        # Nothing left to send, so no second POST.
        assert stub.post.call_count == 0

    def test_posts_to_the_shared_endpoint(self, covered_universe):
        stub = self._stub()
        self._run(stub)
        assert stub.post.call_args.args[0] == INDEXNOW_ENDPOINT

    def test_payload_carries_host_key_and_key_location(self, covered_universe):
        stub = self._stub()
        self._run(stub)
        payload = stub.post.call_args.kwargs["json"]
        assert payload["host"] == "sponda.capital"
        assert payload["key"] == "a5f3f339c2ccec965e5023c23cccbcdb"
        assert payload["keyLocation"] == key_file_url()

    # --- the failure that would otherwise be silent -----------------------

    def test_refuses_when_the_hosted_key_does_not_match(self, covered_universe):
        # Every submission would 403 and nothing would say so.
        stub = self._stub(key_text="a-different-key")
        with pytest.raises(CommandError, match="key"):
            self._run(stub)
        assert stub.post.call_count == 0

    def test_refuses_when_the_key_file_is_missing(self, covered_universe):
        stub = self._stub()
        stub.get.return_value = self._response(404, "")
        with pytest.raises(CommandError):
            self._run(stub)
        assert stub.post.call_count == 0

    def test_tolerates_a_trailing_newline_in_the_key_file(self, covered_universe):
        stub = self._stub(key_text="a5f3f339c2ccec965e5023c23cccbcdb\n")
        self._run(stub)
        assert stub.post.call_count == 1

    def test_refuses_when_no_key_is_configured(self, covered_universe, settings):
        settings.INDEXNOW_KEY = ""
        stub = self._stub()
        with pytest.raises(CommandError, match="INDEXNOW_KEY"):
            self._run(stub)

    def test_records_nothing_when_the_submission_is_rejected(self, covered_universe):
        stub = self._stub(post_status=403)
        self._run(stub)
        assert IndexNowSubmission.objects.count() == 0

    # --- operator controls -------------------------------------------------

    def test_dry_run_neither_posts_nor_records(self, covered_universe):
        stub = self._stub()
        self._run(stub, "--dry-run")
        assert stub.post.call_count == 0
        assert IndexNowSubmission.objects.count() == 0

    def test_limit_caps_the_companies_sent(self, covered_universe):
        stub = self._stub()
        self._run(stub, "--limit", "1")
        assert len(stub.post.call_args.kwargs["json"]["urlList"]) == 2
        assert IndexNowSubmission.objects.count() == 1

    def test_resubmit_ignores_the_already_sent_record(self, covered_universe):
        self._run(self._stub())
        stub = self._stub()
        self._run(stub, "--resubmit")
        assert stub.post.call_count == 1

    def test_batches_at_the_protocol_ceiling(self, covered_universe):
        assert MAX_URLS_PER_SUBMISSION <= 10_000

    def test_splits_a_large_run_into_several_requests(self, db, settings):
        settings.INDEXNOW_KEY = "a5f3f339c2ccec965e5023c23cccbcdb"
        companies = MAX_URLS_PER_SUBMISSION  # 2 URLs each, so at least 2 batches
        Ticker.objects.bulk_create(
            Ticker(symbol=f"T{i}", name=f"T{i}", type="stock") for i in range(companies)
        )
        IndicatorSnapshot.objects.bulk_create(
            IndicatorSnapshot(ticker=f"T{i}") for i in range(companies)
        )
        stub = self._stub()
        self._run(stub)
        assert stub.post.call_count >= 2
        for call in stub.post.call_args_list:
            assert len(call.kwargs["json"]["urlList"]) <= MAX_URLS_PER_SUBMISSION


class TestKeyFileIsCommitted:
    """The hosted file and the setting must agree, or every POST 403s.

    `verify_key_is_live` catches the drift at runtime. This catches it in CI,
    which is cheaper.
    """

    def _public_dir(self):
        from pathlib import Path
        from django.conf import settings
        return Path(settings.BASE_DIR).parent / "frontend" / "public"

    def test_a_key_file_exists(self):
        assert list(self._public_dir().glob("*.txt")), "no key file in frontend/public/"

    def test_the_key_file_contains_only_its_own_name(self):
        # IndexNow requires the file's content to be the key, and the file to
        # be named after the key.
        for path in self._public_dir().glob("*.txt"):
            if path.name in ("robots.txt", "llms.txt"):
                continue
            assert path.read_text().strip() == path.stem, path.name

    def test_the_key_file_has_no_bom_or_trailing_content(self):
        for path in self._public_dir().glob("*.txt"):
            if path.name in ("robots.txt", "llms.txt"):
                continue
            raw = path.read_bytes()
            assert not raw.startswith(b"\xef\xbb\xbf"), "BOM in the key file"
            assert raw == raw.strip(), "whitespace around the key"
