"""Check that Googlebot's page requests are actually reaching the origin.

The failure this exists for is invisible from inside the app. An edge rule
(Cloudflare bot management, a WAF rule, an access rule) answers Googlebot's
requests with a 403 before they reach nginx, while robots.txt keeps flowing,
because every Cloudflare bot product exempts it. From the origin that looks
like a crawler that reads robots.txt twenty times a day and never asks for a
page. Nothing 500s, no test fails, and Search Console is the only place that
says anything.

That is not hypothetical. Between April and August 2026 verified Googlebot
fetched robots.txt 10 to 27 times a day and not one page or sitemap; Search
Console reported the sitemap as "HTTP error 403" and the last successful read
four months earlier. Cloudflare's bot settings were the cause. Every
"Googlebot" line that did reach the origin in that window carried the UA from
an unrelated IP, so counting user agents would have said the crawl was fine.

So: read the last day of the nginx access log, keep only requests from IPs
inside Google's published crawler ranges, and split them into robots.txt
fetches and everything else. A day of robots.txt and nothing else is the
block signature and fails the run; systemd marks the unit failed and
MonitoredCommand ships the error to Sentry.

The log has real client addresses only because nginx resolves
CF-Connecting-IP for connections from Cloudflare's ranges
(nginx/cloudflare-real-ip.conf). If that stops working every line shows a
Cloudflare edge address, no request matches Google's ranges, and this command
fails for that reason instead, which is also worth knowing.
"""
from __future__ import annotations

import gzip
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address, ip_network
from pathlib import Path
from typing import IO, Iterable, Iterator

import requests
from django.core.management.base import CommandError

from config.monitored_command import MonitoredCommand

DEFAULT_ACCESS_LOG = Path("/var/log/nginx/sponda.capital-access.log")
DEFAULT_WINDOW_HOURS = 24

# Below this, a day with no page fetch is more likely a quiet crawler than a
# blocked one. Google has fetched robots.txt at least ten times a day on every
# day of logs seen so far, so three is comfortably under a real day's floor.
DEFAULT_MINIMUM_ROBOTS_FETCHES = 3

# Google publishes the ranges its crawlers come from. The URL that used to be
# googlebot.json now redirects here, which is why the client follows redirects.
GOOGLE_CRAWLER_RANGES_URL = "https://developers.google.com/search/apis/ipranges/googlebot.json"
REQUEST_TIMEOUT_SECONDS = 15

# The ranges Googlebot has crawled from for years. Used only when the
# published list cannot be fetched, so a Google outage does not turn into a
# false alarm about Cloudflare.
FALLBACK_GOOGLE_CRAWLER_NETWORKS = (
    ip_network("66.249.64.0/19"),
    ip_network("2001:4860:4801::/48"),
)

ROBOTS_PATH = "/robots.txt"
SAMPLE_PATHS_TO_REPORT = 5

# Combined log format: `$remote_addr - $remote_user [$time_local] "$request"
# $status $body_bytes_sent "$http_referer" "$http_user_agent"`.
ACCESS_LOG_LINE = re.compile(
    r'^(?P<client_ip>\S+) \S+ \S+ \[(?P<timestamp>[^\]]+)\] '
    r'"(?P<method>[A-Z]+) (?P<target>\S+) [^"]*" (?P<status>\d{3}) '
)
ACCESS_LOG_TIMESTAMP_FORMAT = "%d/%b/%Y:%H:%M:%S %z"


@dataclass(frozen=True)
class AccessLogEntry:
    client_ip: str
    requested_at: datetime
    path: str
    status: int


@dataclass
class CrawlerAccessSummary:
    robots_fetches: int = 0
    page_fetches: int = 0
    sample_page_paths: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.robots_fetches + self.page_fetches


def parse_access_log_line(line: str) -> AccessLogEntry | None:
    """One combined-format line, or None for anything that is not one."""
    match = ACCESS_LOG_LINE.match(line)
    if not match:
        return None
    try:
        requested_at = datetime.strptime(match["timestamp"], ACCESS_LOG_TIMESTAMP_FORMAT)
    except ValueError:
        return None
    path = match["target"].split("?", 1)[0]
    return AccessLogEntry(
        client_ip=match["client_ip"],
        requested_at=requested_at,
        path=path,
        status=int(match["status"]),
    )


def is_google_crawler(client_ip: str, networks: Iterable) -> bool:
    try:
        address = ip_address(client_ip)
    except ValueError:
        return False
    return any(address in network for network in networks)


def fetch_google_crawler_networks() -> tuple:
    """Google's published crawler ranges, or the fallback if they cannot be read."""
    try:
        response = requests.get(GOOGLE_CRAWLER_RANGES_URL, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException:
        return FALLBACK_GOOGLE_CRAWLER_NETWORKS
    if response.status_code != 200:
        return FALLBACK_GOOGLE_CRAWLER_NETWORKS
    try:
        prefixes = response.json().get("prefixes", [])
    except ValueError:
        return FALLBACK_GOOGLE_CRAWLER_NETWORKS

    networks = []
    for prefix in prefixes:
        candidate = prefix.get("ipv4Prefix") or prefix.get("ipv6Prefix")
        if not candidate:
            continue
        try:
            networks.append(ip_network(candidate))
        except ValueError:
            continue
    return tuple(networks) or FALLBACK_GOOGLE_CRAWLER_NETWORKS


def summarize(
    entries: Iterable[AccessLogEntry | None],
    networks: Iterable,
    since: datetime,
) -> CrawlerAccessSummary:
    summary = CrawlerAccessSummary()
    for entry in entries:
        if entry is None or entry.requested_at < since:
            continue
        if not is_google_crawler(entry.client_ip, networks):
            continue
        if entry.path == ROBOTS_PATH:
            summary.robots_fetches += 1
            continue
        summary.page_fetches += 1
        if len(summary.sample_page_paths) < SAMPLE_PATHS_TO_REPORT:
            summary.sample_page_paths.append(entry.path)
    return summary


def _open_log(path: Path) -> IO[str]:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open(encoding="utf-8", errors="replace")


def _log_files_for_window(log_path: Path) -> list[Path]:
    """The live log and its most recent rotation.

    logrotate runs daily, so a 24-hour window always straddles one rotation.
    `delaycompress` keeps `.1` uncompressed; `.gz` is handled anyway in case
    that changes.
    """
    candidates = [log_path, log_path.with_name(log_path.name + ".1")]
    candidates.append(log_path.with_name(log_path.name + ".1.gz"))
    return [candidate for candidate in candidates if candidate.exists()]


def _read_entries(log_files: list[Path]) -> Iterator[AccessLogEntry | None]:
    for log_file in log_files:
        with _open_log(log_file) as handle:
            for line in handle:
                yield parse_access_log_line(line)


class Command(MonitoredCommand):
    help = "Fail when Googlebot reaches the origin for robots.txt but never for a page."
    sentry_monitor_slug = "sponda-verify-crawler-access"

    def add_arguments(self, parser):
        parser.add_argument(
            "--log",
            default=str(DEFAULT_ACCESS_LOG),
            help=f"nginx access log to read (default {DEFAULT_ACCESS_LOG}); its .1 rotation is read too",
        )
        parser.add_argument(
            "--hours",
            type=int,
            default=DEFAULT_WINDOW_HOURS,
            help=f"How far back to look (default {DEFAULT_WINDOW_HOURS})",
        )
        parser.add_argument(
            "--min-robots-fetches",
            type=int,
            default=DEFAULT_MINIMUM_ROBOTS_FETCHES,
            help="robots.txt fetches needed before a page-less window counts as a block",
        )

    def run(self, *args, **options):
        log_path = Path(options["log"])
        log_files = _log_files_for_window(log_path)
        if not log_files:
            raise CommandError(f"No access log at {log_path}")

        window_hours = options["hours"]
        since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        networks = fetch_google_crawler_networks()
        summary = summarize(_read_entries(log_files), networks, since)

        if summary.total == 0:
            raise CommandError(
                f"In the last {window_hours}h the origin saw no request from a Google "
                "crawler IP at all. Either Google has stopped crawling or nginx is no "
                "longer resolving CF-Connecting-IP (check nginx/cloudflare-real-ip.conf)."
            )

        if summary.page_fetches > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"OK · Googlebot reached the origin for {summary.page_fetches} page fetch(es) "
                    f"and {summary.robots_fetches} robots.txt fetch(es) in the last {window_hours}h, "
                    f"e.g. {', '.join(summary.sample_page_paths)}"
                )
            )
            return

        if summary.robots_fetches < options["min_robots_fetches"]:
            self.stdout.write(
                f"Not enough Googlebot traffic to judge: {summary.robots_fetches} robots.txt "
                f"fetch(es) and no page fetch in the last {window_hours}h"
            )
            return

        raise CommandError(
            f"Googlebot fetched robots.txt {summary.robots_fetches} time(s) in the last "
            f"{window_hours}h and not one page or sitemap. Something upstream of the origin "
            "is answering its page requests (Cloudflare bot management, a WAF rule, an "
            "access rule); robots.txt is exempt from those, which is why it still arrives. "
            "Check Cloudflare Security → Events for the Googlebot user agent."
        )
