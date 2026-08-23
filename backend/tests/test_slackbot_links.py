"""Ticker → Sponda link rewriting for Slack answers (slackbot/links.py).

Two problems solved at once. Models decorate Brazilian tickers with the
Yahoo-style ".SA" suffix Sponda does not use, and Slack then auto-links
that as a domain (.sa is a real TLD), so answers came out full of blue
links pointing at nothing. Rewriting every known ticker into an explicit
Slack link to its Sponda page fixes the destination and strips the
invented suffix in one pass.

Linking is allowlist-driven — only symbols the tools actually returned or
that exist in the ticker table — because ticker-shaped words are common
in this domain ("BR", "PEG") and a false link is worse than no link.
"""
import pytest

from quotes.models import Ticker
from slackbot.links import SPONDA_BASE_URL, linkify_tickers, resolve_known_symbols


class TestLinkifyTickers:
    def test_known_symbol_becomes_a_slack_link(self):
        result = linkify_tickers(
            "LREN3 looks cheap.", symbols={"LREN3"}, locale="en"
        )
        assert result == f"<{SPONDA_BASE_URL}/en/LREN3|LREN3> looks cheap."

    def test_invented_exchange_suffix_is_stripped(self):
        # The tools return LREN3; the model writes LREN3.SA from memory.
        result = linkify_tickers(
            "LREN3.SA is first.", symbols={"LREN3"}, locale="en"
        )
        assert result == f"<{SPONDA_BASE_URL}/en/LREN3|LREN3> is first."

    def test_locale_selects_the_url_prefix(self):
        result = linkify_tickers("LREN3", symbols={"LREN3"}, locale="pt")
        assert result == f"<{SPONDA_BASE_URL}/pt/LREN3|LREN3>"

    def test_unsupported_locale_falls_back_to_english(self):
        result = linkify_tickers("LREN3", symbols={"LREN3"}, locale="ja")
        assert f"{SPONDA_BASE_URL}/en/LREN3" in result

    def test_symbols_outside_the_allowlist_are_left_alone(self):
        result = linkify_tickers(
            "Screening: country=BR, sorted by PEG", symbols={"LREN3"}, locale="en"
        )
        assert result == "Screening: country=BR, sorted by PEG"

    def test_every_occurrence_is_linked(self):
        result = linkify_tickers(
            "LREN3 vs ELET3. LREN3 wins.",
            symbols={"LREN3", "ELET3"}, locale="en",
        )
        assert result.count(f"{SPONDA_BASE_URL}/en/LREN3") == 2
        assert result.count(f"{SPONDA_BASE_URL}/en/ELET3") == 1

    def test_symbol_inside_a_longer_word_is_not_touched(self):
        result = linkify_tickers(
            "XLREN3X and LREN3Z stay put.", symbols={"LREN3"}, locale="en"
        )
        assert result == "XLREN3X and LREN3Z stay put."

    def test_symbol_already_inside_a_slack_link_is_not_relinked(self):
        # to_mrkdwn runs first, so a model-authored markdown link is
        # already <url|label> by the time we get here.
        already_linked = "<https://sponda.capital/en/LREN3|LREN3> is cheap."
        assert linkify_tickers(
            already_linked, symbols={"LREN3"}, locale="en"
        ) == already_linked

    def test_no_symbols_is_a_no_op(self):
        assert linkify_tickers("nothing here", symbols=set(), locale="en") == (
            "nothing here"
        )


@pytest.mark.django_db
class TestResolveKnownSymbols:
    def test_finds_ticker_shaped_words_that_exist(self):
        Ticker.objects.create(symbol="LREN3", name="Lojas Renner", type="stock")
        assert resolve_known_symbols("how is LREN3 doing?") == {"LREN3"}

    def test_ignores_ticker_shaped_words_that_do_not_exist(self):
        assert resolve_known_symbols("how is ZZZZ9 doing?") == set()

    def test_matches_a_lowercase_mention(self):
        Ticker.objects.create(symbol="LREN3", name="Lojas Renner", type="stock")
        assert resolve_known_symbols("how is lren3 doing?") == {"LREN3"}

    def test_ignores_an_exchange_suffix_when_looking_up(self):
        Ticker.objects.create(symbol="LREN3", name="Lojas Renner", type="stock")
        assert resolve_known_symbols("what about LREN3.SA?") == {"LREN3"}

    def test_only_stock_rows_match(self):
        Ticker.objects.create(symbol="BOVA11", name="iShares Ibovespa", type="etf")
        assert resolve_known_symbols("what about BOVA11?") == set()
