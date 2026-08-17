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
import yaml

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


def repo_services():
    return sorted(path.name for path in (REPO_ROOT / "systemd").glob("*.service"))


RESTART_LIMIT_DIRECTIVES = ("StartLimitIntervalSec", "StartLimitBurst")


def unit_section(contents, section):
    """The lines of one ini section, e.g. everything under [Service]."""
    lines = contents.splitlines()
    try:
        start = lines.index(f"[{section}]") + 1
    except ValueError:
        return []
    body = []
    for line in lines[start:]:
        if line.startswith("["):
            break
        body.append(line)
    return body


class TestRestartLimitsAreInTheRightSection:
    """`StartLimitIntervalSec` and `StartLimitBurst` belong in [Unit].

    systemd parses them nowhere else. Placed under [Service] they are ignored
    with a log warning, which leaves `Restart=on-failure` with no rate limit at
    all — a unit whose dependency is down then retries forever instead of
    giving up. The whole point of pairing them with Restart is the ceiling, so
    losing it silently defeats the configuration rather than degrading it.
    """

    @pytest.mark.parametrize("service", repo_services())
    def test_restart_limits_are_not_under_service(self, service):
        body = unit_section((REPO_ROOT / "systemd" / service).read_text(), "Service")
        misplaced = [
            directive for directive in RESTART_LIMIT_DIRECTIVES
            if any(line.startswith(directive) for line in body)
        ]
        assert not misplaced, (
            f"{service} puts {', '.join(misplaced)} under [Service], where "
            f"systemd ignores it; move it to [Unit]"
        )

    @pytest.mark.parametrize("service", repo_services())
    def test_a_restarting_service_keeps_its_limit(self, service):
        """Whatever declares Restart= must still carry a ceiling somewhere."""
        contents = (REPO_ROOT / "systemd" / service).read_text()
        if "Restart=on-failure" not in contents:
            return
        assert any(
            line.startswith("StartLimitBurst")
            for line in unit_section(contents, "Unit")
        ), f"{service} restarts on failure but declares no StartLimitBurst in [Unit]"


def e2e_test_modules():
    return sorted(path.name for path in (REPO_ROOT / "backend" / "tests").glob("test_e2e*.py"))


class TestEveryBrowserSuiteRunsSomewhere:
    """A Playwright suite must be in the e2e matrix, not the unit-tests job.

    The unit-tests job builds no frontend, so a browser suite there calls
    `pytest.skip("Frontend build failed")` and the run still reports success.
    test_e2e_visited.py sat in exactly that position: five tests for the
    visited feature, skipped on every CI run, absent from the matrix, and
    passing locally only because a built frontend happened to be lying around.

    Skipping is the dangerous failure here · nothing is red, and the coverage
    simply is not there.
    """

    @pytest.mark.parametrize("module", e2e_test_modules())
    def test_the_unit_tests_job_does_not_try_to_run_it(self, module):
        deploy = DEPLOY_WORKFLOW.read_text()
        assert f"--ignore=tests/{module}" in deploy, (
            f"{module} is a browser suite; the unit-tests job must ignore it "
            f"rather than skip it silently"
        )

    @pytest.mark.parametrize("module", e2e_test_modules())
    def test_it_is_a_shard_of_the_e2e_matrix(self, module):
        deploy = DEPLOY_WORKFLOW.read_text()
        assert f"          - {module}" in deploy, (
            f"{module} is ignored by unit-tests but is not an e2e shard, so it "
            f"runs nowhere at all"
        )


def deploy_ssh_commands() -> str:
    """The shell the deploy job runs on the server, comments stripped.

    Ordering assertions have to read the commands, not the file. Matching
    raw text would let a mention inside a comment — or the identical `npm ci`
    in the build-frontend job — stand in for the real thing and quietly
    satisfy the check.
    """
    workflow = yaml.safe_load(DEPLOY_WORKFLOW.read_text())
    steps = workflow["jobs"]["deploy"]["steps"]
    script = next(
        step for step in steps if step.get("name") == "Deploy via SSH"
    )["with"]["script"]
    return "\n".join(
        line for line in script.splitlines() if not line.strip().startswith("#")
    )


ARTIFACT_PATH = "/opt/sponda/_deploy/next-build.tar.gz"
ARTIFACT_GUARD = f"test -f {ARTIFACT_PATH}"

# Everything below changes the box in a way the running site can feel. The
# guard has to come before all of them.
MUTATING_STEPS = (
    "git reset --hard origin/main",
    "uv pip install -r backend/requirements.txt",
    "npm ci",
)


class TestFrontendArtifactGuard:
    """A missing build artifact must fail the deploy before it touches the box.

    Seen in production on 2026-08-17: the scp step reported success but the
    tarball was not on the server. By the time `tar` discovered that, the
    script had already run `npm ci`, swapping node_modules under the Next
    server that was serving traffic. The deploy failed *and* took the site
    down with it, returning 500 until the job was re-run.

    The old `.next` was never at risk — the script validates BUILD_ID before
    swapping. What was missing is the cheapest check of all, in the only
    position where it helps: first.
    """

    def test_the_artifact_is_checked_at_all(self):
        assert ARTIFACT_GUARD in deploy_ssh_commands(), (
            f"deploy must verify {ARTIFACT_PATH} exists before using it"
        )

    @pytest.mark.parametrize("mutation", MUTATING_STEPS)
    def test_the_artifact_is_checked_before_anything_mutates_the_box(self, mutation):
        commands = deploy_ssh_commands()

        assert commands.index(ARTIFACT_GUARD) < commands.index(mutation), (
            f"the {ARTIFACT_PATH} check must run before {mutation!r}; "
            "a deploy that aborts after that step leaves the live site broken"
        )
