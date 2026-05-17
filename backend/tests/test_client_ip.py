"""Shared CF-aware client-IP extraction + hashing."""
from __future__ import annotations

from django.test import RequestFactory

from quotes.client_ip import client_ip, client_ip_hash


def _req(**meta):
    request = RequestFactory().get("/api/quote/PETR4/")
    request.META.update(meta)
    return request


class TestClientIp:
    def test_prefers_cf_connecting_ip(self):
        request = _req(
            HTTP_CF_CONNECTING_IP="203.0.113.7",
            HTTP_X_FORWARDED_FOR="198.51.100.1, 10.0.0.1",
            REMOTE_ADDR="10.0.0.1",
        )
        assert client_ip(request) == "203.0.113.7"

    def test_falls_back_to_first_xff_hop(self):
        request = _req(
            HTTP_X_FORWARDED_FOR="198.51.100.1, 10.0.0.1",
            REMOTE_ADDR="10.0.0.1",
        )
        assert client_ip(request) == "198.51.100.1"

    def test_falls_back_to_remote_addr(self):
        request = _req(REMOTE_ADDR="192.0.2.55")
        assert client_ip(request) == "192.0.2.55"

    def test_unknown_when_nothing_present(self):
        request = _req()
        # RequestFactory sets REMOTE_ADDR to 127.0.0.1 by default; force empty.
        request.META.pop("REMOTE_ADDR", None)
        assert client_ip(request) == "0.0.0.0"

    def test_strips_whitespace_in_xff(self):
        request = _req(HTTP_X_FORWARDED_FOR="  198.51.100.9  , 10.0.0.1")
        assert client_ip(request) == "198.51.100.9"


class TestClientIpHash:
    def test_is_stable_and_sha256_shaped(self):
        request = _req(HTTP_CF_CONNECTING_IP="203.0.113.7")
        h1 = client_ip_hash(request)
        h2 = client_ip_hash(request)
        assert h1 == h2
        assert len(h1) == 64
        assert h1 != "203.0.113.7"  # never the raw IP

    def test_different_ips_hash_differently(self):
        a = client_ip_hash(_req(HTTP_CF_CONNECTING_IP="203.0.113.7"))
        b = client_ip_hash(_req(HTTP_CF_CONNECTING_IP="203.0.113.8"))
        assert a != b
