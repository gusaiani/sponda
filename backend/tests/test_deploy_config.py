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


def repo_timers():
    return sorted(path.name for path in (REPO_ROOT / "systemd").glob("*.timer"))


class TestTimersAreWiredIntoDeploy:
    """Adding a timer means touching three places; forgetting one is silent.

    A timer that is committed but never copied and enabled simply never runs.
    Nothing errors, no unit fails, and the job it was meant to do quietly does
    not happen — which is indistinguishable from the job having nothing to do.
    """

    @pytest.mark.parametrize("timer", repo_timers())
    def test_every_timer_has_a_service_to_run(self, timer):
        service = REPO_ROOT / "systemd" / timer.replace(".timer", ".service")
        assert service.is_file(), f"{timer} has no matching {service.name}"

    @pytest.mark.parametrize("timer", repo_timers())
    def test_deploy_installs_every_timer(self, timer):
        deploy = DEPLOY_WORKFLOW.read_text()
        service = timer.replace(".timer", ".service")
        assert f"{timer} /etc/systemd/system/" in deploy, (
            f"deploy must copy {timer} into /etc/systemd/system/"
        )
        assert f"{service} /etc/systemd/system/" in deploy, (
            f"deploy must copy {service} into /etc/systemd/system/"
        )

    @pytest.mark.parametrize("timer", repo_timers())
    def test_deploy_enables_every_timer(self, timer):
        deploy = DEPLOY_WORKFLOW.read_text()
        assert f"systemctl enable --now {timer}" in deploy, (
            f"deploy must enable {timer}; a copied but unenabled timer never fires"
        )

    def test_the_cvm_snapshot_timer_is_among_them(self):
        """Pins that the parametrized guards above actually cover this PR."""
        assert "sponda-snapshot-cvm.timer" in repo_timers()
