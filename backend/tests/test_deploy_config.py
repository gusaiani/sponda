"""Guards on the deploy pipeline's handling of the Celery worker.

The Celery worker (`sponda-celery.service`) executes background tasks like
`quotes.refresh_provider_data`. It is a long-running process, so it keeps its
old code in memory until restarted. A deploy that updates gunicorn but never
restarts the worker leaves it running stale code indefinitely — which is how a
fix that was merged and deployed kept surfacing the old traceback in Sentry
(the worker had been up since before the fix landed).

These tests pin the invariant: the worker is a repo-managed systemd unit and
the deploy restarts it on every run, exactly like every other service.
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy.yml"
CELERY_UNIT = REPO_ROOT / "systemd" / "sponda-celery.service"


class TestCeleryWorkerDeploy:
    def test_celery_worker_unit_is_in_repo(self):
        assert CELERY_UNIT.is_file(), (
            "systemd/sponda-celery.service must be version-controlled so the "
            "deploy can install and restart it"
        )

    def test_celery_worker_unit_runs_the_worker(self):
        contents = CELERY_UNIT.read_text()
        assert "celery -A config worker" in contents

    def test_deploy_installs_the_celery_unit(self):
        deploy = DEPLOY_WORKFLOW.read_text()
        assert "sponda-celery.service /etc/systemd/system/" in deploy, (
            "deploy must copy sponda-celery.service into /etc/systemd/system/"
        )

    def test_deploy_restarts_the_celery_worker(self):
        deploy = DEPLOY_WORKFLOW.read_text()
        assert "systemctl restart sponda-celery" in deploy, (
            "deploy must restart sponda-celery so the worker picks up new code; "
            "otherwise the long-running worker serves stale code forever"
        )
