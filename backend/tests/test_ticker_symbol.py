"""Tests for the ticker-symbol shape guard.

A symbol that cannot name a listed company must be rejected before it
reaches a provider. `$TFCO4`, the cashtag spelling of a B3 ticker, does
not match the Brazilian pattern, so it routed to FMP and spent four
calls per request on a guaranteed 404.
"""

import pytest

from quotes.ticker_symbol import MAX_TICKER_SYMBOL_LENGTH, is_plausible_ticker_symbol


class TestAcceptedSymbols:
    @pytest.mark.parametrize(
        "symbol",
        [
            "AAPL",      # the ordinary US case
            "F",         # the catalogue holds 21 one-letter symbols
            "PETR4",     # B3
            "KLBN11",    # B3 unit
            "AKO-A",     # share class
            "AHT-PD",    # preferred series
            "AMPX-WT",   # warrant
            "BRK.B",     # the dotted spelling of a share class
            "0P00000SXJ",  # the provider's own fund identifiers, ten characters
        ],
    )
    def test_accepts(self, symbol):
        assert is_plausible_ticker_symbol(symbol)

    def test_accepts_lowercase_the_way_the_views_do(self):
        assert is_plausible_ticker_symbol("petr4")


class TestRejectedSymbols:
    @pytest.mark.parametrize(
        "symbol",
        [
            "$TFCO4",           # the cashtag that started this
            "%24TFCO4",         # its percent-encoded twin
            "<script>",
            "../../etc/passwd",
            "PETR 4",
            "PETR;4",
            "-AAPL",            # a separator needs symbol on both sides
            "AAPL-",
            "AA--PL",
            "AAPL..B",
            "",
            "   ",
        ],
    )
    def test_rejects(self, symbol):
        assert not is_plausible_ticker_symbol(symbol)

    def test_rejects_anything_longer_than_the_longest_real_symbol(self):
        assert is_plausible_ticker_symbol("A" * MAX_TICKER_SYMBOL_LENGTH)
        assert not is_plausible_ticker_symbol("A" * (MAX_TICKER_SYMBOL_LENGTH + 1))

    def test_rejects_a_non_string(self):
        assert not is_plausible_ticker_symbol(None)
