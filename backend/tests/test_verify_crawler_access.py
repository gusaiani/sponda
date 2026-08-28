"""Tests for the verify_crawler_access management command.

The command exists for one failure: an edge rule (Cloudflare bot management,
a WAF rule, an access rule) answers Googlebot's page requests before they
reach the origin, while robots.txt keeps flowing because every Cloudflare bot
product exempts it. From the origin that looks like a crawler that reads
robots.txt twenty times a day and never fetches a page, and nothing in the
app notices. In 2026 that went on for four months.
"""
from datetime import datetime, timedelta, timezone
from ipaddress import ip_network
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import CommandError, call_command

from quotes.management.commands import verify_crawler_access as command_module

GOOGLE_IP = "66.249.65.37"
GOOGLE_IPV6 = "2001:4860:4801:10::1"
SPOOFER_IP = "161.35.0.150"
GOOGLEBOT_USER_AGENT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


def _log_line(ip: str, path: str, status: int = 200, when: datetime | None = None) -> str:
    when = when or datetime.now(timezone.utc)
    stamp = when.strftime("%d/%b/%Y:%H:%M:%S %z")
    return (
        f'{ip} - - [{stamp}] "GET {path} HTTP/1.1" {status} 512 "-" '
        f'"{GOOGLEBOT_USER_AGENT}"'
    )


def _write_log(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n")
    return path


@pytest.fixture
def published_prefixes(monkeypatch):
    """Skip the network: the published list is exactly the fallback list."""
    monkeypatch.setattr(
        command_module,
        "fetch_google_crawler_networks",
        lambda: command_module.FALLBACK_GOOGLE_CRAWLER_NETWORKS,
    )


class TestParseAccessLogLine:
    def test_extracts_ip_timestamp_path_and_status(self):
        when = datetime(2026, 8, 28, 9, 18, 30, tzinfo=timezone.utc)
        entry = command_module.parse_access_log_line(_log_line(GOOGLE_IP, "/en/AAPL", 200, when))

        assert entry is not None
        assert entry.client_ip == GOOGLE_IP
        assert entry.requested_at == when
        assert entry.path == "/en/AAPL"
        assert entry.status == 200

    def test_strips_query_string_from_path(self):
        entry = command_module.parse_access_log_line(_log_line(GOOGLE_IP, "/robots.txt?x=1"))

        assert entry is not None
        assert entry.path == "/robots.txt"

    def test_ipv6_client(self):
        entry = command_module.parse_access_log_line(_log_line(GOOGLE_IPV6, "/pt/PETR4"))

        assert entry is not None
        assert entry.client_ip == GOOGLE_IPV6

    def test_malformed_line_is_none(self):
        assert command_module.parse_access_log_line("not an access log line") is None
        assert command_module.parse_access_log_line("") is None


class TestIsGoogleCrawler:
    def test_googlebot_ipv4_range(self):
        networks = command_module.FALLBACK_GOOGLE_CRAWLER_NETWORKS

        assert command_module.is_google_crawler(GOOGLE_IP, networks)

    def test_googlebot_ipv6_range(self):
        networks = command_module.FALLBACK_GOOGLE_CRAWLER_NETWORKS

        assert command_module.is_google_crawler(GOOGLE_IPV6, networks)

    def test_spoofed_user_agent_from_elsewhere_is_not(self):
        networks = command_module.FALLBACK_GOOGLE_CRAWLER_NETWORKS

        assert not command_module.is_google_crawler(SPOOFER_IP, networks)

    def test_garbage_ip_is_not(self):
        networks = command_module.FALLBACK_GOOGLE_CRAWLER_NETWORKS

        assert not command_module.is_google_crawler("not-an-ip", networks)


class TestFetchGoogleCrawlerNetworks:
    def test_reads_published_prefixes(self):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "prefixes": [{"ipv4Prefix": "34.100.182.96/28"}, {"ipv6Prefix": "2001:4860:4801:2008::/64"}],
        }
        with patch.object(command_module.requests, "get", return_value=response):
            networks = command_module.fetch_google_crawler_networks()

        assert ip_network("34.100.182.96/28") in networks
        assert ip_network("2001:4860:4801:2008::/64") in networks

    def test_falls_back_when_google_is_unreachable(self):
        with patch.object(
            command_module.requests, "get", side_effect=command_module.requests.RequestException
        ):
            networks = command_module.fetch_google_crawler_networks()

        assert networks == command_module.FALLBACK_GOOGLE_CRAWLER_NETWORKS

    def test_falls_back_on_non_200(self):
        response = MagicMock()
        response.status_code = 503
        with patch.object(command_module.requests, "get", return_value=response):
            networks = command_module.fetch_google_crawler_networks()

        assert networks == command_module.FALLBACK_GOOGLE_CRAWLER_NETWORKS

    def test_ignores_malformed_prefixes(self):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"prefixes": [{"ipv4Prefix": "garbage"}, {"other": 1}]}
        with patch.object(command_module.requests, "get", return_value=response):
            networks = command_module.fetch_google_crawler_networks()

        assert networks == command_module.FALLBACK_GOOGLE_CRAWLER_NETWORKS


class TestSummarize:
    def test_counts_robots_and_page_fetches_for_google_only(self):
        now = datetime.now(timezone.utc)
        entries = [
            command_module.parse_access_log_line(line)
            for line in [
                _log_line(GOOGLE_IP, "/robots.txt", 304),
                _log_line(GOOGLE_IP, "/robots.txt", 304),
                _log_line(GOOGLE_IP, "/en/AAPL", 200),
                _log_line(GOOGLE_IPV6, "/sitemap.xml", 200),
                _log_line(SPOOFER_IP, "/pt/PETR4", 200),
            ]
        ]

        summary = command_module.summarize(
            entries,
            command_module.FALLBACK_GOOGLE_CRAWLER_NETWORKS,
            since=now - timedelta(hours=24),
        )

        assert summary.robots_fetches == 2
        assert summary.page_fetches == 2

    def test_ignores_requests_before_the_window(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(hours=48)
        entries = [
            command_module.parse_access_log_line(_log_line(GOOGLE_IP, "/en/AAPL", 200, old)),
            command_module.parse_access_log_line(_log_line(GOOGLE_IP, "/robots.txt", 304, now)),
        ]

        summary = command_module.summarize(
            entries,
            command_module.FALLBACK_GOOGLE_CRAWLER_NETWORKS,
            since=now - timedelta(hours=24),
        )

        assert summary.page_fetches == 0
        assert summary.robots_fetches == 1

    def test_sample_paths_are_kept_for_the_report(self):
        now = datetime.now(timezone.utc)
        entries = [
            command_module.parse_access_log_line(_log_line(GOOGLE_IP, "/en/AAPL", 200)),
            command_module.parse_access_log_line(_log_line(GOOGLE_IP, "/pt/PETR4", 200)),
        ]

        summary = command_module.summarize(
            entries,
            command_module.FALLBACK_GOOGLE_CRAWLER_NETWORKS,
            since=now - timedelta(hours=24),
        )

        assert summary.sample_page_paths == ["/en/AAPL", "/pt/PETR4"]


@pytest.mark.usefixtures("published_prefixes")
class TestCommand:
    def test_healthy_crawl_reports_ok(self, tmp_path, capsys):
        log = _write_log(
            tmp_path / "access.log",
            [
                _log_line(GOOGLE_IP, "/robots.txt", 304),
                _log_line(GOOGLE_IP, "/en/AAPL", 200),
                _log_line(GOOGLE_IP, "/pt/VALE3/fundamentos", 200),
            ],
        )

        call_command("verify_crawler_access", log=str(log))

        out = capsys.readouterr().out
        assert "OK" in out
        assert "2 page fetch" in out

    def test_robots_only_is_an_edge_block(self, tmp_path):
        log = _write_log(
            tmp_path / "access.log",
            [_log_line(GOOGLE_IP, "/robots.txt", 304) for _ in range(5)],
        )

        with pytest.raises(CommandError, match="upstream of the origin"):
            call_command("verify_crawler_access", log=str(log))

    def test_spoofed_googlebot_does_not_count_as_a_crawl(self, tmp_path):
        log = _write_log(
            tmp_path / "access.log",
            [_log_line(GOOGLE_IP, "/robots.txt", 304) for _ in range(5)]
            + [_log_line(SPOOFER_IP, "/en/AAPL", 200) for _ in range(50)],
        )

        with pytest.raises(CommandError, match="upstream of the origin"):
            call_command("verify_crawler_access", log=str(log))

    def test_too_few_robots_fetches_is_not_yet_a_verdict(self, tmp_path, capsys):
        log = _write_log(
            tmp_path / "access.log",
            [_log_line(GOOGLE_IP, "/robots.txt", 304)],
        )

        call_command("verify_crawler_access", log=str(log))

        assert "not enough" in capsys.readouterr().out.lower()

    def test_no_google_traffic_at_all_fails(self, tmp_path):
        log = _write_log(
            tmp_path / "access.log",
            [_log_line(SPOOFER_IP, "/en/AAPL", 200) for _ in range(10)],
        )

        with pytest.raises(CommandError, match="no request from a Google crawler"):
            call_command("verify_crawler_access", log=str(log))

    def test_reads_the_rotated_sibling_too(self, tmp_path, capsys):
        _write_log(
            tmp_path / "access.log.1",
            [_log_line(GOOGLE_IP, "/en/AAPL", 200)],
        )
        log = _write_log(
            tmp_path / "access.log",
            [_log_line(GOOGLE_IP, "/robots.txt", 304) for _ in range(5)],
        )

        call_command("verify_crawler_access", log=str(log))

        assert "1 page fetch" in capsys.readouterr().out

    def test_missing_log_is_an_error(self, tmp_path):
        with pytest.raises(CommandError, match="No access log"):
            call_command("verify_crawler_access", log=str(tmp_path / "nope.log"))

    def test_window_is_configurable(self, tmp_path):
        now = datetime.now(timezone.utc)
        log = _write_log(
            tmp_path / "access.log",
            [_log_line(GOOGLE_IP, "/robots.txt", 304) for _ in range(5)]
            + [_log_line(GOOGLE_IP, "/en/AAPL", 200, now - timedelta(hours=30))],
        )

        # 48 hours sees the page fetch; 24 hours does not.
        call_command("verify_crawler_access", log=str(log), hours=48)
        with pytest.raises(CommandError, match="upstream of the origin"):
            call_command("verify_crawler_access", log=str(log), hours=24)
