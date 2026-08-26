"""An interactive shell is an operator typing, not production.

Five of the unresolved issues in the Sentry inbox were typos made at a
``manage.py shell`` prompt, all grouped under ``commands.shell in
<module>``: WEB-DJANGO-1Q (``No module named 'quotes.tickers'``), 1P
(``cannot import name 'FXRate'``, a misspelling of ``FxRate``), 1M (``No
module named 'screening'``), 1J and 1G (bad ORM lookups), and
WEB-DJANGO-S (a shell started without the environment file, so Postgres
refused the ``root`` role).

None of them is a fault in the running service, and each one paged as if
it were. Skipping Sentry for a REPL also drops the two-second flush that
was being paid on every shell exit.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from config.observability import init_sentry, is_interactive_shell_session


@pytest.mark.parametrize(
    "argv",
    [
        ["manage.py", "shell"],
        ["manage.py", "shell", "-c", "print(1)"],
        ["manage.py", "shell_plus"],
        ["manage.py", "dbshell"],
        ["/opt/sponda/backend/manage.py", "shell"],
        ["django-admin", "shell"],
    ],
)
def test_recognizes_an_interactive_shell(argv):
    with patch("config.observability.sys.argv", argv):
        assert is_interactive_shell_session() is True


@pytest.mark.parametrize(
    "argv",
    [
        ["manage.py", "runserver"],
        ["manage.py", "sync_cvm_fourth_quarters"],
        ["manage.py", "refresh_snapshot_prices"],
        ["manage.py", "migrate"],
        ["/opt/sponda/venv/bin/gunicorn", "config.wsgi:application"],
        ["/opt/sponda/venv/bin/celery", "-A", "config", "worker"],
        ["pytest"],
        [],
    ],
)
def test_does_not_mistake_real_workloads_for_a_shell(argv):
    """Everything that actually serves or ingests must keep reporting."""
    with patch("config.observability.sys.argv", argv):
        assert is_interactive_shell_session() is False


def test_init_is_skipped_inside_an_interactive_shell():
    with patch("config.observability.sys.argv", ["manage.py", "shell"]):
        with patch("config.observability.sentry_sdk.init") as mocked_init:
            result = init_sentry(
                dsn="https://public@example.ingest.sentry.io/1",
                environment="production",
                release="abc123",
            )

    assert result is False
    mocked_init.assert_not_called()


def test_init_still_runs_for_a_management_command():
    """Timer-driven commands are exactly what MonitoredCommand reports on."""
    with patch("config.observability.sys.argv", ["manage.py", "refresh_snapshot_prices"]):
        with patch("config.observability.sentry_sdk.init") as mocked_init:
            result = init_sentry(
                dsn="https://public@example.ingest.sentry.io/1",
                environment="production",
                release="abc123",
            )

    assert result is True
    mocked_init.assert_called_once()
