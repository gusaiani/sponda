"""Guards on the trust boundary between Cloudflare and the origin nginx.

Every request to sponda.capital is supposed to arrive through Cloudflare, and
`quotes.client_ip.client_ip` trusts `CF-Connecting-IP` to identify the visitor
behind the anonymous lookup cap. Nothing enforced either half of that:

  * nginx forwarded whatever `CF-Connecting-IP` the peer sent, unread and
    unmodified, because nginx passes unknown request headers through by
    default. Anyone who reached the origin directly could mint a fresh
    visitor identity per request and the cap evaporated.
  * `X-Forwarded-For` was built with `$proxy_add_x_forwarded_for`, which
    *appends* to the client-supplied chain rather than replacing it, and
    `client_ip()` reads the leftmost entry. Same hole, second door.

The fix has two layers, and these tests pin both.

Layer one, always on: the realip module resolves `$remote_addr` from
`CF-Connecting-IP`, but *only* when the connection came from a published
Cloudflare range. Off a direct connection the forged header is ignored and
`$remote_addr` stays the peer's real address. nginx then overwrites every
forwarding header from `$remote_addr`, so what Django reads cannot be
attacker-controlled no matter which path the request took.

Layer two, opt-in per host: Authenticated Origin Pulls (mTLS) makes nginx
reject any TLS handshake that does not present Cloudflare's client
certificate, so direct connections never reach the request phase at all.
It is a wildcard include because it needs a CA file on the box and a zone
setting in the Cloudflare dashboard, neither of which the deploy controls.
"""
from __future__ import annotations

import ipaddress
import re
import stat
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
NGINX_DIR = REPO_ROOT / "nginx"
SITE_CONF = NGINX_DIR / "sponda.capital.conf"
REAL_IP_CONF = NGINX_DIR / "cloudflare-real-ip.conf"
UPDATE_IPS_SCRIPT = NGINX_DIR / "update-cloudflare-ips.sh"
ENABLE_ORIGIN_PULL_SCRIPT = NGINX_DIR / "enable-cloudflare-origin-pull.sh"
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy.yml"

REAL_IP_INCLUDE = "include /etc/nginx/snippets/sponda-cloudflare-real-ip.conf;"
ORIGIN_PULL_INCLUDE = "include /etc/nginx/snippets/sponda-origin-pull*.conf;"

# A range Cloudflare has announced for years. If a regenerated list ever drops
# it, the list was fetched from the wrong place.
A_KNOWN_CLOUDFLARE_RANGE = ipaddress.ip_network("104.16.0.0/13")


def apex_server_block() -> str:
    """The `server_name sponda.capital;` block, extracted by brace depth.

    The file holds three server blocks and only this one proxies to an
    application, so asserting against the whole file would let a directive
    in the www-redirect block satisfy a test about the real one.
    """
    text = SITE_CONF.read_text()
    for match in re.finditer(r"^server\s*\{", text, re.MULTILINE):
        depth, index = 0, match.start()
        while index < len(text):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    break
            index += 1
        block = text[match.start() : index + 1]
        if re.search(r"^\s*server_name\s+sponda\.capital;", block, re.MULTILINE):
            return block
    raise AssertionError("no `server_name sponda.capital;` block in the site config")


def proxying_locations() -> dict[str, str]:
    """Every `location ... { ... proxy_pass ... }` in the apex block, by path."""
    blocks = {}
    for match in re.finditer(
        r"location\s+([^\s{]+)\s*\{(.*?)\n    \}", apex_server_block(), re.DOTALL
    ):
        path, body = match.group(1), match.group(2)
        if "proxy_pass" in body:
            blocks[path] = body
    assert blocks, "expected at least one proxying location in the apex block"
    return blocks


def without_comments(config: str) -> str:
    """Strip `#` lines, so a directive named in a comment cannot satisfy a test."""
    return "\n".join(
        line for line in config.splitlines() if not line.strip().startswith("#")
    )


def server_scope_directives() -> str:
    """The apex block with its location blocks stripped out."""
    block = apex_server_block()
    for body in proxying_locations().values():
        block = block.replace(body, "")
    return block


class TestCloudflareRealIpList:
    def test_the_trust_list_is_version_controlled(self):
        # Fetching the ranges at reload time would make nginx's ability to
        # start depend on Cloudflare being reachable. The list changes about
        # once a year; a committed file is refreshed by running the script.
        assert REAL_IP_CONF.is_file(), f"{REAL_IP_CONF} must be committed"

    def test_every_directive_is_a_valid_cidr_trust_entry(self):
        for line in REAL_IP_CONF.read_text().splitlines():
            directive = line.strip()
            if not directive or directive.startswith("#"):
                continue
            if directive.startswith("real_ip_header"):
                continue
            match = re.fullmatch(r"set_real_ip_from\s+(\S+);", directive)
            assert match, f"unexpected directive in the trust list: {directive!r}"
            ipaddress.ip_network(match.group(1))  # raises if malformed

    def test_the_list_covers_both_address_families(self):
        networks = [
            ipaddress.ip_network(match)
            for match in re.findall(
                r"set_real_ip_from\s+(\S+);", REAL_IP_CONF.read_text()
            )
        ]
        assert any(network.version == 4 for network in networks)
        assert any(network.version == 6 for network in networks)
        assert any(
            A_KNOWN_CLOUDFLARE_RANGE.subnet_of(network)
            for network in networks
            if network.version == 4
        ), "the list does not cover 104.16.0.0/13, so it is not Cloudflare's"

    def test_the_real_client_address_comes_from_the_cloudflare_header(self):
        # Without this, `set_real_ip_from` alone does nothing: the module
        # would keep reading the default X-Real-IP, which the peer controls.
        assert "real_ip_header CF-Connecting-IP;" in REAL_IP_CONF.read_text()

    def test_a_refresh_script_exists_and_is_executable(self):
        assert UPDATE_IPS_SCRIPT.is_file()
        assert UPDATE_IPS_SCRIPT.stat().st_mode & stat.S_IXUSR, (
            "the refresh script must be committed executable, or the deploy "
            "and the runbook both have to remember to chmod it"
        )


class TestTheSiteConfigTrustsOnlyCloudflare:
    def test_the_apex_block_includes_the_trust_list(self):
        # Server scope, not http scope: this box serves seventeen other sites
        # and only sponda.capital is behind Cloudflare.
        assert REAL_IP_INCLUDE in apex_server_block()

    def test_the_visitor_header_is_overwritten_not_forwarded(self):
        # $remote_addr is the realip-resolved client on a Cloudflare connection
        # and the true peer on a direct one. Either way it is nginx's value,
        # never the sender's.
        assert (
            "proxy_set_header CF-Connecting-IP $remote_addr;"
            in server_scope_directives()
        ), (
            "the peer's own CF-Connecting-IP reaches Django, which trusts it "
            "for the anonymous lookup cap"
        )

    def test_the_forwarded_chain_is_replaced_not_appended(self):
        directives = server_scope_directives()
        assert "$proxy_add_x_forwarded_for" not in without_comments(
            apex_server_block()
        ), (
            "$proxy_add_x_forwarded_for appends to the client-supplied "
            "X-Forwarded-For, and client_ip() reads the leftmost entry, so the "
            "client picks its own address"
        )
        assert "proxy_set_header X-Forwarded-For $remote_addr;" in directives

    def test_the_real_ip_header_is_the_resolved_client(self):
        assert "proxy_set_header X-Real-IP $remote_addr;" in server_scope_directives()

    def test_the_public_hostname_survives_the_proxy_hop(self):
        # nginx's default is $proxy_host, which would hand Next and Django
        # "127.0.0.1:3100" to build canonical URLs and redirects from.
        assert "proxy_set_header Host $host;" in server_scope_directives()

    @pytest.mark.parametrize("path", sorted(proxying_locations()))
    def test_no_location_shadows_the_inherited_headers(self, path):
        # nginx inherits proxy_set_header from the enclosing level only when
        # the location declares none of its own. One header inside a location
        # drops all of them, silently, including CF-Connecting-IP.
        assert "proxy_set_header" not in proxying_locations()[path], (
            f"location {path} declares its own proxy_set_header, which discards "
            "every header set at server scope; restate the full set or move it up"
        )

    def test_authenticated_origin_pulls_is_a_wildcard_include(self):
        # A literal include of a missing file is a hard `nginx -t` failure, so
        # it would break every deploy until someone installed the CA by hand.
        # A wildcard that matches nothing is silently empty, which lets the
        # config ship disabled and be switched on by the script.
        assert ORIGIN_PULL_INCLUDE in apex_server_block()
        assert ORIGIN_PULL_INCLUDE.count("*") == 1


class TestAuthenticatedOriginPullsRunbook:
    def test_the_enable_script_exists_and_is_executable(self):
        assert ENABLE_ORIGIN_PULL_SCRIPT.is_file()
        assert ENABLE_ORIGIN_PULL_SCRIPT.stat().st_mode & stat.S_IXUSR

    def test_the_enable_script_turns_on_client_verification(self):
        script = ENABLE_ORIGIN_PULL_SCRIPT.read_text()
        assert "ssl_verify_client on;" in script
        assert "ssl_client_certificate" in script

    def test_the_enable_script_validates_before_reloading(self):
        # Reloading an untested config on a box that fronts eighteen sites
        # takes all of them down, not just this one.
        script = ENABLE_ORIGIN_PULL_SCRIPT.read_text()
        assert "nginx -t" in script
        assert script.index("nginx -t") < script.index("systemctl reload nginx")


class TestDeployInstallsTheTrustList:
    def test_deploy_copies_the_trust_list_to_the_path_the_config_includes(self):
        deploy = DEPLOY_WORKFLOW.read_text()
        assert (
            "/etc/nginx/snippets/sponda-cloudflare-real-ip.conf" in deploy
        ), "the include path must be written by the deploy, or nginx -t fails"

    def test_deploy_still_validates_before_reloading(self):
        deploy = DEPLOY_WORKFLOW.read_text()
        assert "nginx -t && systemctl reload nginx" in deploy
