"""Tests for the verify_edge_cache management command.

The command exists for one failure: a deploy changes what a URL returns, and
Cloudflare keeps serving the old body for its four-hour TTL. That is invisible
to the existing health gate, which polls the origin on 127.0.0.1 and never
crosses the edge.
"""
import io
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import CommandError, call_command

from quotes.management.commands import verify_edge_cache


def _response(content_type: str, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.headers = {"Content-Type": content_type}
    return response


def _healthy_responses() -> dict[str, MagicMock]:
    return {
        canary.url: _response(canary.expected_content_type)
        for canary in verify_edge_cache.CANARIES
    }


class _EdgeStub:
    """Serves a scripted content-type per URL, switching after a purge.

    Stands in for the `requests` module, so it also has to expose the
    exception type the command catches.
    """

    RequestException = Exception

    def __init__(self, before: dict[str, MagicMock], after: dict[str, MagicMock] | None = None):
        self.before = before
        self.after = after
        self.purged: list[list[str]] = []
        self.get_calls: list[str] = []

    def get(self, url, **kwargs):
        self.get_calls.append(url)
        table = self.after if (self.purged and self.after is not None) else self.before
        return table[url]

    def post(self, url, **kwargs):
        self.purged.append(kwargs["json"]["files"])
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"success": True, "errors": []}
        return response


@pytest.fixture
def cloudflare_credentials(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token-abc")
    monkeypatch.setenv("CLOUDFLARE_ZONE_ID", "zone-123")


def _run(stub) -> str:
    out = io.StringIO()
    with patch.object(verify_edge_cache, "requests", stub):
        call_command("verify_edge_cache", stdout=out, stderr=out)
    return out.getvalue()


class TestCanaryDefinitions:
    def test_covers_a_rendered_card_and_a_static_image(self):
        """The two content-types a deploy has actually broken before."""
        expected = {canary.expected_content_type for canary in verify_edge_cache.CANARIES}

        assert "image/png" in expected
        assert "image/jpeg" in expected

    def test_every_canary_is_an_absolute_production_url(self):
        for canary in verify_edge_cache.CANARIES:
            assert canary.url.startswith("https://sponda.capital/")

    def test_the_list_stays_small_enough_for_one_purge_call(self):
        # Cloudflare accepts 30 URLs per purge call on every plan.
        assert 0 < len(verify_edge_cache.CANARIES) <= 30


@pytest.mark.usefixtures("cloudflare_credentials")
class TestHealthyEdge:
    def test_passes_without_purging_when_every_canary_matches(self):
        stub = _EdgeStub(before=_healthy_responses())

        output = _run(stub)

        assert stub.purged == []
        assert "OK" in output

    def test_checks_every_canary(self):
        stub = _EdgeStub(before=_healthy_responses())

        _run(stub)

        for canary in verify_edge_cache.CANARIES:
            assert canary.url in stub.get_calls

    def test_ignores_charset_when_comparing_content_types(self):
        responses = _healthy_responses()
        first = verify_edge_cache.CANARIES[0]
        responses[first.url] = _response(f"{first.expected_content_type}; charset=utf-8")

        stub = _EdgeStub(before=responses)
        output = _run(stub)

        assert stub.purged == []
        assert "OK" in output


@pytest.mark.usefixtures("cloudflare_credentials")
class TestStaleEdge:
    def test_purges_only_the_stale_url_and_passes_once_it_recovers(self):
        stale = verify_edge_cache.CANARIES[0]
        before = _healthy_responses()
        before[stale.url] = _response("text/html")

        stub = _EdgeStub(before=before, after=_healthy_responses())
        output = _run(stub)

        assert stub.purged == [[stale.url]]
        assert stale.url in output

    def test_fails_when_the_url_is_still_wrong_after_purging(self):
        stale = verify_edge_cache.CANARIES[0]
        before = _healthy_responses()
        before[stale.url] = _response("text/html")

        stub = _EdgeStub(before=before)  # never recovers

        with pytest.raises(CommandError) as excinfo:
            _run(stub)

        assert stale.url in str(excinfo.value)

    def test_treats_a_non_200_as_a_mismatch(self):
        stale = verify_edge_cache.CANARIES[0]
        before = _healthy_responses()
        before[stale.url] = _response(stale.expected_content_type, status_code=404)

        stub = _EdgeStub(before=before, after=_healthy_responses())
        _run(stub)

        assert stub.purged == [[stale.url]]


class TestMissingCredentials:
    def test_still_reports_a_stale_url_when_no_token_is_configured(self, monkeypatch):
        monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
        monkeypatch.delenv("CLOUDFLARE_ZONE_ID", raising=False)
        stale = verify_edge_cache.CANARIES[0]
        before = _healthy_responses()
        before[stale.url] = _response("text/html")

        stub = _EdgeStub(before=before)

        with pytest.raises(CommandError):
            _run(stub)

        assert stub.purged == []

    def test_healthy_edge_passes_without_credentials(self, monkeypatch):
        monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
        monkeypatch.delenv("CLOUDFLARE_ZONE_ID", raising=False)

        stub = _EdgeStub(before=_healthy_responses())
        output = _run(stub)

        assert "OK" in output


@pytest.mark.usefixtures("cloudflare_credentials")
class TestNetworkFailures:
    def test_a_request_that_raises_counts_as_a_mismatch_rather_than_crashing(self):
        """A timeout should trigger a purge attempt, not a traceback."""
        stale = verify_edge_cache.CANARIES[0]

        class _TimingOutStub(_EdgeStub):
            def get(self, url, **kwargs):
                if url == stale.url and not self.purged:
                    raise TimeoutError("edge timeout")
                return super().get(url, **kwargs)

        stub = _TimingOutStub(before=_healthy_responses(), after=_healthy_responses())

        _run(stub)

        assert stub.purged == [[stale.url]]

    def test_fails_when_the_purge_api_rejects_the_call(self):
        stale = verify_edge_cache.CANARIES[0]
        before = _healthy_responses()
        before[stale.url] = _response("text/html")

        class _RejectingStub(_EdgeStub):
            def post(self, url, **kwargs):
                self.purged.append(kwargs["json"]["files"])
                response = MagicMock()
                response.status_code = 403
                response.json.return_value = {
                    "success": False,
                    "errors": [{"message": "Invalid API Token"}],
                }
                return response

        stub = _RejectingStub(before=before, after=_healthy_responses())

        with pytest.raises(CommandError) as excinfo:
            _run(stub)

        assert "Invalid API Token" in str(excinfo.value)
