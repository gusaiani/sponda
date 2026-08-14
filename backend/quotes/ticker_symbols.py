"""Which source owns a ticker, decided by the shape of its symbol.

Brazilian B3 symbols are letters followed by digits (PETR4, VALE3); the
US symbols we ingest never carry a trailing digit (AAPL, MSFT). Every
sync command needs that distinction to know which rows it may delete:
BRAPI lists Brazilian instruments only, FMP lists the US universe only,
and each sees the other's rows as simply absent rather than delisted.

The rule lived as a restated regex literal at four call sites, and the
two delete paths drifted apart · ``refresh_us_tickers`` guarded its
delete with it while ``sync_tickers`` did not, so every BRAPI run wiped
the entire US universe. Keeping the pattern in one place is what makes
that pairing reviewable.
"""
import re

# Kept as a string as well as a compiled pattern: the sync commands filter
# in the database with ``symbol__regex``, which takes the raw expression.
BRAZILIAN_SYMBOL_REGEX = r"^[A-Z]+\d+$"

BRAZILIAN_TICKER_PATTERN = re.compile(BRAZILIAN_SYMBOL_REGEX)


def is_brazilian_symbol(symbol: str) -> bool:
    """True for a B3-shaped symbol such as ``PETR4``, False for ``AAPL``."""
    return bool(BRAZILIAN_TICKER_PATTERN.match(symbol))
