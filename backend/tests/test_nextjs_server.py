"""Tests for the Next.js server lifecycle helpers the browser suites use.

A leaked server is not hypothetical: a `next start` from an aborted run sat
on its port burning a full CPU core for two days, because in-process teardown
cannot survive pytest being killed outright. These tests pin the two guards
that prevent a repeat: the pre-start port sweep that lets the next run reap
whatever the last one left behind, and the group termination that kills the
real server rather than only the npm wrapper in front of it.
"""
import os
import signal
import socket
import subprocess
import sys
import time

from tests.nextjs_server import kill_port_listeners, terminate_process_group

LISTENER_SCRIPT = (
    "import socket, sys, time\n"
    "server = socket.socket()\n"
    "server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
    "server.bind(('127.0.0.1', int(sys.argv[1])))\n"
    "server.listen()\n"
    "print('listening', flush=True)\n"
    "time.sleep(60)\n"
)

STARTUP_TIMEOUT_SECONDS = 10


def _free_port() -> int:
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


def _spawn_listener(port: int) -> subprocess.Popen:
    process = subprocess.Popen(
        [sys.executable, "-c", LISTENER_SCRIPT, str(port)],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert process.stdout.readline().strip() == "listening"
    return process


def _is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _wait_until_gone(pid: int, timeout_seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not _is_alive(pid):
            return True
        time.sleep(0.1)
    return not _is_alive(pid)


# --- The pre-start port sweep -----------------------------------------------


def test_kills_whatever_is_listening_on_the_port():
    port = _free_port()
    squatter = _spawn_listener(port)
    try:
        kill_port_listeners(port)
        # The squatter is this process's own child, so it lingers as a zombie
        # until reaped; wait() both reaps it and reports what ended it.
        assert squatter.wait(timeout=5) == -signal.SIGKILL
    finally:
        if squatter.poll() is None:
            squatter.kill()
            squatter.wait()


def test_a_free_port_is_left_in_peace():
    kill_port_listeners(_free_port())


# --- Group termination ------------------------------------------------------


def _spawn_shell_with_grandchild() -> tuple[subprocess.Popen, int]:
    """A wrapper shell and the pid of the sleeper it spawned, like npx/next."""
    process = subprocess.Popen(
        ["sh", "-c", "sleep 60 & echo $!; wait"],
        stdout=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    grandchild_pid = int(process.stdout.readline().strip())
    return process, grandchild_pid


def test_terminates_the_grandchild_not_just_the_wrapper():
    process, grandchild_pid = _spawn_shell_with_grandchild()

    terminate_process_group(process)

    assert not _is_alive(process.pid)
    assert _wait_until_gone(grandchild_pid)


def test_escalates_when_the_group_ignores_the_polite_signal():
    process = subprocess.Popen(
        ["sh", "-c", 'trap "" TERM; sleep 60'],
        start_new_session=True,
    )
    time.sleep(0.2)  # let the shell install its trap before signalling

    terminate_process_group(process, grace_seconds=1)

    assert not _is_alive(process.pid)


def test_an_already_finished_process_is_no_trouble():
    process = subprocess.Popen(["true"], start_new_session=True)
    process.wait()

    terminate_process_group(process)
