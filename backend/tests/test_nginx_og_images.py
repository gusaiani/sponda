"""The Open Graph image routes must reach crawlers without Next's RSC `Vary`.

Next stamps every app-router response, images included, with
`Vary: rsc, next-router-state-tree, next-router-prefetch,
next-router-segment-prefetch`. On an HTML page that is what lets a client
router and a browser share a URL. On a JPEG it is noise, and it was the one
header shared by every image X's crawler downloaded from this domain and
then declined to render. nginx strips it on the way out.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NGINX_CONF = REPO_ROOT / "nginx" / "sponda.capital.conf"


def _og_location_block() -> str:
    text = NGINX_CONF.read_text()
    match = re.search(r"location /og/ \{(.*?)\n    \}", text, re.S)
    assert match, "nginx/sponda.capital.conf has no `location /og/` block"
    return match.group(1)


class TestOpenGraphImageLocation:
    def test_it_proxies_to_next(self):
        assert "proxy_pass http://127.0.0.1:3100;" in _og_location_block()

    def test_it_hides_the_rsc_vary_header(self):
        assert re.search(r"proxy_hide_header\s+Vary;", _og_location_block())

    def test_it_declares_no_proxy_set_header_of_its_own(self):
        # A single proxy_set_header inside a location drops the inherited
        # set, CF-Connecting-IP included; see the comment above `location /`.
        assert "proxy_set_header" not in _og_location_block()
