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


class TestLintRunsInCI:
    """Guards that both linters actually run.

    A linter nobody runs is worse than no linter: it accumulates violations
    silently and then looks like a wall of work whenever someone finally
    invokes it. Both were added on 2026-08-17 to a codebase that had never
    been linted, so pin the steps rather than trusting them to survive the
    next workflow edit.
    """

    def test_the_backend_is_linted(self):
        deploy = DEPLOY_WORKFLOW.read_text()
        assert "ruff check ." in deploy, (
            "the unit-tests job must run `ruff check .`; backend/ruff.toml "
            "keeps the ruleset narrow enough that it passes clean"
        )

    def test_the_frontend_is_linted(self):
        deploy = DEPLOY_WORKFLOW.read_text()
        assert "npm run lint" in deploy, (
            "the frontend-tests job must run `npm run lint`; existing "
            "violations are baselined in frontend/eslint-suppressions.json "
            "so only new ones fail"
        )

    def test_ruff_is_a_declared_dependency(self):
        requirements = (REPO_ROOT / "backend" / "requirements.txt").read_text()
        assert "ruff==" in requirements, (
            "CI installs from requirements.txt, so ruff has to be pinned "
            "there or the lint step runs whatever version it finds"
        )

    def test_the_backend_ruleset_is_committed(self):
        assert (REPO_ROOT / "backend" / "ruff.toml").is_file(), (
            "without ruff.toml, CI silently lints with ruff defaults, which "
            "report ~735 mostly-stylistic problems here"
        )


class TestUvComesFromPyPI:
    """CI must not depend on fetching astral-sh/setup-uv from codeload.

    Every Python job needs `uv` for one `uv pip install` line, and the action
    that provides it is downloaded from codeload.github.com per job — seven
    times per CI run. On 2026-08-17 GitHub rate-limited that download and
    returned 429/502/503 for hours, which failed five separate runs, twice on
    main, while nothing was wrong with the code. Installing uv from PyPI keeps
    the same speed benefit without putting a third-party action fetch on the
    critical path of every job.
    """

    def test_the_setup_uv_action_is_not_used(self):
        # Matches the `uses:` line, not the name: the comments explaining why
        # the action was dropped mention it, and should keep doing so.
        deploy = DEPLOY_WORKFLOW.read_text()
        assert "uses: astral-sh/setup-uv" not in deploy, (
            "uv should be installed from PyPI; the action is fetched from "
            "codeload on every job and its rate limits have taken CI down"
        )

    def test_uv_is_installed_before_it_is_used(self):
        workflow = yaml.safe_load(DEPLOY_WORKFLOW.read_text())
        for job_name, job in workflow["jobs"].items():
            steps = job.get("steps") or []
            installed_at = None
            for index, step in enumerate(steps):
                run = step.get("run") or ""
                if "pip install uv" in run:
                    installed_at = index
                if "uv pip install" in run:
                    assert installed_at is not None and installed_at <= index, (
                        f"{job_name} runs `uv pip install` without having "
                        f"installed uv first"
                    )


class TestGateStepsAreUnconditional:
    """A step that sets an output must not be gated on that output.

    If it were, it would never run, the output would never be set, every
    dependent step would skip, and the job would report green while testing
    nothing. Silence is the dangerous failure mode again.

    This is not hypothetical: removing the `astral-sh/setup-uv` step on
    2026-08-17 left its `if:` line behind, and YAML attached it to the
    preceding gate step.
    """

    def test_a_step_is_never_conditional_on_its_own_output(self):
        workflow = yaml.safe_load(DEPLOY_WORKFLOW.read_text())
        for job_name, job in workflow["jobs"].items():
            for step in job.get("steps") or []:
                step_id = step.get("id")
                condition = step.get("if")
                if not step_id or not condition:
                    continue
                assert f"steps.{step_id}.outputs" not in str(condition), (
                    f"{job_name}: step '{step_id}' is gated on its own output, "
                    f"so it can never run and everything downstream silently skips"
                )


ENV_FILE = "/opt/sponda/.env"


class TestGunicornPicksUpEnvChanges:
    """A reloaded gunicorn keeps the environment it was started with.

    `systemctl reload` sends HUP: workers re-fork and import fresh code, but
    systemd applies `EnvironmentFile` only when the unit starts, so the master
    and every worker it forks keep the old variables. Found on 2026-09-27:
    the web app had been up since 2026-08-26 and still carried that day's
    `SENTRY_RELEASE`, so a month of backend events were tagged with a release
    twenty-eight merges old. Any secret rotated in `.env` would have gone the
    same way, silently, while celery and the frontend (restarted) picked it up.

    Two rules follow. The release is read from the checkout, never written to
    `.env`. And when `.env` is newer than the running master, the deploy
    restarts gunicorn instead of reloading it, paying the 502 window only on
    the rare deploy that actually changes the environment.
    """

    def test_the_deploy_no_longer_writes_the_release_into_env(self):
        assigning = [
            line for line in deploy_ssh_commands().splitlines()
            if "SENTRY_RELEASE=$" in line or "SENTRY_RELEASE=${" in line
        ]
        assert not assigning, (
            "the deploy must not write SENTRY_RELEASE to .env; the value never "
            f"reaches a reloaded gunicorn: {assigning}"
        )

    def test_the_deploy_removes_the_stale_release_line_once(self):
        commands = deploy_ssh_commands()
        assert "/^SENTRY_RELEASE=/d" in commands, (
            "the deploy must delete the SENTRY_RELEASE line the old pipeline "
            "left in .env, or the stale value keeps overriding the checkout"
        )
        assert 'grep -q "^SENTRY_RELEASE="' in commands, (
            "the deletion must be guarded by a grep; `sed -i` rewrites the file "
            "even when nothing matches, and a touched .env restarts gunicorn "
            "on every deploy"
        )

    def test_the_deploy_compares_env_age_to_the_running_master(self):
        commands = deploy_ssh_commands()
        assert f"stat -c %Y {ENV_FILE}" in commands, (
            "the deploy must read the .env modification time"
        )
        assert "ActiveEnterTimestamp --value sponda" in commands, (
            "the deploy must read when the running gunicorn master started"
        )

    def test_a_newer_env_restarts_gunicorn_and_an_unchanged_one_reloads_it(self):
        commands = deploy_ssh_commands()
        restart_branch = commands.index("systemctl restart sponda\n")
        reload_branch = commands.index("systemctl reload sponda || systemctl restart sponda")
        assert restart_branch < reload_branch, (
            "the env-changed branch (restart) must be tested before the "
            "default branch (reload)"
        )


def parse_restart_policy(contents):
    """(RestartSec, StartLimitBurst, StartLimitIntervalSec) as integers."""
    values = {}
    for line in contents.splitlines():
        for key in ("RestartSec", "StartLimitBurst", "StartLimitIntervalSec"):
            if line.startswith(f"{key}="):
                values[key] = int(line.split("=", 1)[1])
    return values


class TestARestartCeilingIsActuallyReachable:
    """`StartLimitBurst` starts inside `StartLimitIntervalSec` must be possible.

    A oneshot job that fails and restarts every `RestartSec` seconds spaces
    its starts that far apart. If `(StartLimitBurst - 1) * RestartSec` is not
    strictly inside the interval, the burst-th start always falls outside the
    window, the counter never fills, and the job retries forever instead of
    giving up until its timer fires again.

    `sponda-indexnow.service` had burst 3 in 600 s with 300 s between starts:
    three starts span exactly 600 s, the ceiling never tripped, and the unit
    restarted every five minutes for a month (restart counter 8863 on
    2026-09-27), each time to print `INDEXNOW_KEY is not set`.
    """

    @pytest.mark.parametrize("service", repo_services())
    def test_the_burst_fits_inside_the_interval(self, service):
        contents = (REPO_ROOT / "systemd" / service).read_text()
        if "Restart=on-failure" not in contents:
            return
        policy = parse_restart_policy(contents)
        retries_before_ceiling = policy["StartLimitBurst"] - 1
        span = retries_before_ceiling * policy["RestartSec"]
        assert span < policy["StartLimitIntervalSec"], (
            f"{service}: {policy['StartLimitBurst']} starts {policy['RestartSec']}s "
            f"apart span {span}s, not inside StartLimitIntervalSec="
            f"{policy['StartLimitIntervalSec']}; the ceiling can never trip"
        )
