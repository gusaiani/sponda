"""Tests for the record of who is refreshing a company's statements.

Three endpoints serve one company page and each used to enqueue its own
background refresh, so a single visit to a stale company could cost nine
provider calls instead of three. The state kept here lets the first caller
claim the refresh, lets every other caller see that one is in flight, and
keeps a company whose refresh just failed from being retried on every
request.
"""
import pytest

from quotes.statement_refresh_state import (
    claim_statement_refresh,
    is_statement_refresh_pending,
    record_statement_refresh_attempt,
    release_statement_refresh_claim,
)


class TestClaimingARefresh:
    def test_the_first_caller_claims_the_refresh(self):
        assert claim_statement_refresh("PETR4") is True

    def test_a_second_caller_cannot_claim_a_refresh_already_in_flight(self):
        claim_statement_refresh("PETR4")

        assert claim_statement_refresh("PETR4") is False

    def test_a_claim_on_one_company_leaves_another_free(self):
        claim_statement_refresh("PETR4")

        assert claim_statement_refresh("VALE3") is True

    def test_the_ticker_case_does_not_split_the_claim(self):
        claim_statement_refresh("petr4")

        assert claim_statement_refresh("PETR4") is False


class TestSeeingARefreshInFlight:
    def test_nothing_is_pending_before_any_claim(self):
        assert is_statement_refresh_pending("PETR4") is False

    def test_a_claimed_refresh_is_pending(self):
        claim_statement_refresh("PETR4")

        assert is_statement_refresh_pending("PETR4") is True

    def test_a_released_claim_is_no_longer_pending_and_can_be_claimed_again(self):
        claim_statement_refresh("PETR4")

        release_statement_refresh_claim("PETR4")

        assert is_statement_refresh_pending("PETR4") is False
        assert claim_statement_refresh("PETR4") is True


class TestAfterARefreshAttempt:
    def test_a_finished_attempt_is_no_longer_pending(self):
        claim_statement_refresh("PETR4")

        record_statement_refresh_attempt("PETR4")

        assert is_statement_refresh_pending("PETR4") is False

    def test_a_recent_attempt_cannot_be_claimed_again_straight_away(self):
        """A company whose provider is failing stays stale after the refresh.
        Without a cool-down every request for it would enqueue another one."""
        claim_statement_refresh("PETR4")

        record_statement_refresh_attempt("PETR4")

        assert claim_statement_refresh("PETR4") is False
