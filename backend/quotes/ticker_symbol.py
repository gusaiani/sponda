"""What a ticker symbol can look like, before a call is spent on it.

A symbol arrives from the URL, so it is whatever the caller typed. Most
junk is harmless, but a symbol that cannot name a listed company still
costs four FMP calls on the cold path (income statement, cash flows,
balance sheet, quote) before the provider says what its shape already
said. Nothing is stored for a company that does not exist, so the next
request pays again.

The shape below is drawn from the catalogue itself, all 18,329 symbols
of it: uppercase letters and digits, optionally in groups joined by a
single hyphen for a share class, preferred series or warrant (AKO-A,
AHT-PD, AMPX-WT), and never longer than ten characters. Five entries
are the provider's own fund identifiers (0P00000SXJ), which is why a
leading digit is allowed. The dotted spelling of a share class (BRK.B)
is accepted too: a person may well type it, and it is a real symbol
somewhere even when it is not ours.

This is a shape test, not a membership test. Plenty of real tickers are
absent from the ``Ticker`` table (EMBR3, LVMUY and OZON were all looked
up in the last fortnight without being listed there), so refusing what
the catalogue does not hold would refuse real companies.
"""
from __future__ import annotations

import re

# The longest symbol in the catalogue is ten characters. The two spare
# characters are headroom for a longer listing, not a real example.
MAX_TICKER_SYMBOL_LENGTH = 12

_TICKER_SYMBOL = re.compile(r"^[A-Z0-9]+(?:[.-][A-Z0-9]+)*$")


def is_plausible_ticker_symbol(symbol: object) -> bool:
    """Whether ``symbol`` could name a listed company at all."""
    if not isinstance(symbol, str):
        return False
    candidate = symbol.strip().upper()
    if not candidate or len(candidate) > MAX_TICKER_SYMBOL_LENGTH:
        return False
    return bool(_TICKER_SYMBOL.match(candidate))
