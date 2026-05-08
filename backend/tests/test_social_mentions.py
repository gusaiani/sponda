"""Tests for the @handle / $TICKER mention parser."""
import pytest

from social.mentions import (
    MENTION_LIMIT_PER_SPOND,
    extract_handle_mentions,
    extract_ticker_mentions,
)


class TestHandleMentions:
    def test_simple(self):
        assert extract_handle_mentions("hello @alice") == ["alice"]

    def test_multiple(self):
        assert extract_handle_mentions("@alice and @bob met @carol") == [
            "alice", "bob", "carol",
        ]

    def test_dedup_preserves_first_seen_order(self):
        assert extract_handle_mentions("@alice hi @alice and @bob") == [
            "alice", "bob",
        ]

    def test_lowercased(self):
        assert extract_handle_mentions("@Alice and @BOB") == ["alice", "bob"]

    def test_ignores_email_like(self):
        # "@alice" embedded inside an email address should not be treated as
        # a mention of "alice".
        assert extract_handle_mentions("send to me@alice.com") == []

    def test_ignores_too_short(self):
        assert extract_handle_mentions("@a is too short") == []

    def test_respects_max_length(self):
        assert extract_handle_mentions("@" + "a" * 30) == []

    def test_punctuation_terminates_handle(self):
        assert extract_handle_mentions("@alice, are you there?") == ["alice"]
        assert extract_handle_mentions("ping @alice.") == ["alice"]
        assert extract_handle_mentions("(@alice)") == ["alice"]

    def test_invalid_chars_break_handle(self):
        # Capital letters/digits OK; punctuation stops the match.
        assert extract_handle_mentions("@alice-smith") == ["alice"]

    def test_empty_string(self):
        assert extract_handle_mentions("") == []

    def test_skips_reserved_words(self):
        # Reserved words should not be returned as mentions, since they can
        # never be a real user.
        assert extract_handle_mentions("@admin and @api") == []


class TestTickerMentions:
    def test_simple(self):
        assert extract_ticker_mentions("watching $PETR4 closely") == ["PETR4"]

    def test_multiple(self):
        assert extract_ticker_mentions("$PETR4 vs $VALE3 vs $ITUB4") == [
            "PETR4", "VALE3", "ITUB4",
        ]

    def test_dedup(self):
        assert extract_ticker_mentions("$PETR4 again $PETR4 and $VALE3") == [
            "PETR4", "VALE3",
        ]

    def test_uppercased(self):
        assert extract_ticker_mentions("$petr4 normalized") == ["PETR4"]

    def test_brazilian_ticker_pattern(self):
        # 4 letters + 1 or 2 digits.
        assert extract_ticker_mentions("$PETR4 $PETR11") == ["PETR4", "PETR11"]

    def test_us_style_ticker(self):
        # 1-5 letters, no digits — common for US tickers.
        assert extract_ticker_mentions("$AAPL and $TSLA, $MSFT") == [
            "AAPL", "TSLA", "MSFT",
        ]

    def test_punctuation_terminates(self):
        assert extract_ticker_mentions("$PETR4, the giant.") == ["PETR4"]

    def test_ignores_dollar_amounts(self):
        # "$500" is money, not a ticker.
        assert extract_ticker_mentions("market cap is $500B") == []
        assert extract_ticker_mentions("$1.5T valuation") == []


class TestMentionLimits:
    def test_handle_mention_cap(self):
        # Author cannot mention more than MENTION_LIMIT_PER_SPOND distinct
        # handles in one Spond — beyond that, the parser truncates.
        body = " ".join(f"@user{i:02d}" for i in range(MENTION_LIMIT_PER_SPOND + 5))
        assert len(extract_handle_mentions(body)) == MENTION_LIMIT_PER_SPOND
