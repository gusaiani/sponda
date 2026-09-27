"""Tests for Sentry initialization and scrubbing.

We do not test that Sentry actually delivers events to the service
(that is third-party surface). We test:
  - init_sentry is a no-op when DSN is unset
  - init_sentry forwards expected options when DSN is set
  - scrub_event redacts Authorization, Cookie, and DATABASE_URL
"""
from pathlib import Path
from unittest.mock import patch


from config.observability import init_sentry, resolve_release, scrub_event


class TestInitSentry:
    def test_noop_when_dsn_missing(self):
        with patch("config.observability.sentry_sdk.init") as mocked_init:
            result = init_sentry(dsn=None, environment="development", release="abc123")
        assert result is False
        mocked_init.assert_not_called()

    def test_noop_when_dsn_blank(self):
        with patch("config.observability.sentry_sdk.init") as mocked_init:
            result = init_sentry(dsn="", environment="development", release="abc123")
        assert result is False
        mocked_init.assert_not_called()

    def test_initializes_when_dsn_provided(self):
        with patch("config.observability.sentry_sdk.init") as mocked_init:
            result = init_sentry(
                dsn="https://public@sentry.example/1",
                environment="production",
                release="deadbeef",
            )
        assert result is True
        mocked_init.assert_called_once()
        kwargs = mocked_init.call_args.kwargs
        assert kwargs["dsn"] == "https://public@sentry.example/1"
        assert kwargs["environment"] == "production"
        assert kwargs["release"] == "deadbeef"
        assert kwargs["send_default_pii"] is False
        assert kwargs["before_send"] is scrub_event
        # Expect Django + Celery + Logging integrations wired
        integration_names = {type(i).__name__ for i in kwargs["integrations"]}
        assert "DjangoIntegration" in integration_names
        assert "CeleryIntegration" in integration_names
        assert "LoggingIntegration" in integration_names

    def test_default_trace_propagation_targets_restrict_to_internal_hosts(self):
        """Without an explicit list, the SDK propagates sentry-trace to every
        outbound URL — including third-party APIs (brapi, FRED, FMP) that have
        no use for the header. Confirm we ship a safe default."""
        import re

        with patch("config.observability.sentry_sdk.init") as mocked_init:
            init_sentry(
                dsn="https://public@sentry.example/1",
                environment="production",
                release="deadbeef",
            )
        targets = mocked_init.call_args.kwargs["trace_propagation_targets"]
        assert targets, "trace_propagation_targets must be set explicitly"

        def is_propagated(url: str) -> bool:
            return any(re.search(pattern, url) for pattern in targets)

        # Should propagate to internal hosts
        assert is_propagated("http://127.0.0.1:8710/api/quote/VALE3/")
        assert is_propagated("http://localhost:3100/")
        assert is_propagated("https://sponda.capital/api/quote/VALE3/")
        assert is_propagated("https://api.poe.ma/v1/data")

        # Should NOT propagate to third-party data providers
        assert not is_propagated("https://brapi.dev/api/quote/VALE3")
        assert not is_propagated("https://api.stlouisfed.org/fred/series")
        assert not is_propagated("https://financialmodelingprep.com/api/v3/")
        assert not is_propagated("https://api.openai.com/v1/chat")

    def test_caller_can_override_trace_propagation_targets(self):
        custom = [r"^https://custom\.example/"]
        with patch("config.observability.sentry_sdk.init") as mocked_init:
            init_sentry(
                dsn="https://public@sentry.example/1",
                environment="production",
                release="deadbeef",
                trace_propagation_targets=custom,
            )
        assert mocked_init.call_args.kwargs["trace_propagation_targets"] == custom


class TestScrubEvent:
    def test_redacts_authorization_header(self):
        event = {
            "request": {
                "headers": {
                    "Authorization": "Bearer secret-token",
                    "Content-Type": "application/json",
                }
            }
        }
        scrubbed = scrub_event(event, hint={})
        assert scrubbed["request"]["headers"]["Authorization"] == "[Filtered]"
        assert scrubbed["request"]["headers"]["Content-Type"] == "application/json"

    def test_redacts_cookie_header_case_insensitive(self):
        event = {"request": {"headers": {"cookie": "sessionid=xyz"}}}
        scrubbed = scrub_event(event, hint={})
        assert scrubbed["request"]["headers"]["cookie"] == "[Filtered]"

    def test_redacts_database_url_in_extra(self):
        event = {
            "extra": {
                "DATABASE_URL": "postgres://user:pw@host/db",
                "other": "safe",
            }
        }
        scrubbed = scrub_event(event, hint={})
        assert scrubbed["extra"]["DATABASE_URL"] == "[Filtered]"
        assert scrubbed["extra"]["other"] == "safe"

    def test_returns_event_when_nothing_to_scrub(self):
        event = {"request": {"headers": {"Content-Type": "application/json"}}}
        scrubbed = scrub_event(event, hint={})
        assert scrubbed == event

    def test_handles_event_without_request(self):
        event = {"message": "hello"}
        scrubbed = scrub_event(event, hint={})
        assert scrubbed == event


class TestInitSentryIntegration:
    """Smoke-test that the real sentry_sdk is importable and init works end-to-end.

    We init with an obviously-fake DSN that sentry_sdk accepts structurally.
    """

    def test_init_with_fake_dsn_does_not_raise(self):
        # sentry_sdk.init is idempotent — safe to call with a throwaway DSN in tests.
        result = init_sentry(
            dsn="https://public@o0.ingest.sentry.io/0",
            environment="test",
            release="test",
            traces_sample_rate=0.0,
        )
        assert result is True


class TestResolveRelease:
    """The release tag comes from the deployed checkout, not the environment.

    Deploys reload gunicorn rather than restart it, and systemd only reads
    `EnvironmentFile` when a unit starts. So a `SENTRY_RELEASE` written to
    `.env` on each deploy never reached the running master: on 2026-09-27
    every backend event was still tagged with the SHA from 2026-08-26, a
    month and twenty-eight merges earlier. Workers do re-import settings on
    reload, so reading `.git/HEAD` at import time is always current.
    """

    def write_head(self, repository_root, contents):
        git_directory = repository_root / ".git"
        git_directory.mkdir(exist_ok=True)
        (git_directory / "HEAD").write_text(contents)
        return git_directory

    def test_an_explicit_release_wins(self, tmp_path):
        self.write_head(tmp_path, "deadbeef" * 5 + "\n")
        assert resolve_release("explicit-tag", tmp_path) == "explicit-tag"

    def test_a_blank_explicit_release_is_treated_as_unset(self, tmp_path):
        git_directory = self.write_head(tmp_path, "ref: refs/heads/main\n")
        (git_directory / "refs" / "heads").mkdir(parents=True)
        (git_directory / "refs" / "heads" / "main").write_text("abc123" * 6 + "\n")
        assert resolve_release("", tmp_path) == "abc123" * 6

    def test_a_symbolic_head_is_followed_to_its_loose_ref(self, tmp_path):
        git_directory = self.write_head(tmp_path, "ref: refs/heads/main\n")
        (git_directory / "refs" / "heads").mkdir(parents=True)
        (git_directory / "refs" / "heads" / "main").write_text("f" * 40 + "\n")
        assert resolve_release(None, tmp_path) == "f" * 40

    def test_a_symbolic_head_falls_back_to_packed_refs(self, tmp_path):
        git_directory = self.write_head(tmp_path, "ref: refs/heads/main\n")
        (git_directory / "packed-refs").write_text(
            "# pack-refs with: peeled fully-peeled sorted\n"
            f"{'a' * 40} refs/heads/feature\n"
            f"{'b' * 40} refs/heads/main\n"
            f"{'c' * 40} refs/remotes/origin/main\n"
        )
        assert resolve_release(None, tmp_path) == "b" * 40

    def test_a_detached_head_is_the_release_itself(self, tmp_path):
        self.write_head(tmp_path, "0123456789abcdef0123456789abcdef01234567\n")
        assert resolve_release(None, tmp_path) == "0123456789abcdef0123456789abcdef01234567"

    def test_no_git_directory_means_no_release(self, tmp_path):
        assert resolve_release(None, tmp_path) is None

    def test_a_dangling_symbolic_head_means_no_release(self, tmp_path):
        self.write_head(tmp_path, "ref: refs/heads/nowhere\n")
        assert resolve_release(None, tmp_path) is None

    def test_settings_derive_the_release_from_the_checkout(self):
        """Pins the wiring: base.py must go through resolve_release."""
        from config.settings import base as base_settings

        source = Path(base_settings.__file__).read_text()
        assert "resolve_release(" in source, (
            "settings/base.py must resolve the Sentry release via "
            "resolve_release, or a reloaded gunicorn keeps reporting the SHA "
            "it was started with"
        )
