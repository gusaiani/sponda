"""Lifecycle helpers for the Next.js servers the browser suites spawn.

A leaked server is not hypothetical: a `next start` from an aborted run sat
on port 3097 burning a full CPU core for two days. In-process teardown cannot
survive pytest itself being killed, so no single guard is enough. Two layers,
for the two distinct failure modes:

* ``kill_port_listeners`` runs before a server starts. Whatever a killed run
  left squatting on the port is reaped by the next run · the only guard that
  works when teardown never got the chance to. It is the same idiom the
  Makefile's ``dev`` target applies to the development ports.
* ``terminate_process_group`` tears down the whole process group rather than
  signalling the ``npx`` wrapper alone. The wrapper usually forwards the
  signal to the ``next-server`` it spawned, but "usually" is how orphans
  happen; the group kill does not depend on it.

The pairing matters: a server must be started with ``start_new_session=True``
so it owns a group this module can address without touching pytest's own.
"""
import os
import signal
import subprocess

PORT_LOOKUP_TIMEOUT_SECONDS = 10
TERMINATION_GRACE_SECONDS = 5


def kill_port_listeners(port: int) -> None:
    """Kill whatever is listening on the port so the next server can have it.

    Straight to SIGKILL: anything holding one of the suites' dedicated ports
    is a leftover test server, and a squatter's graceful shutdown is worth
    nothing next to the certainty that the port is free.
    """
    listing = subprocess.run(
        ["lsof", "-ti", f"tcp:{port}"],
        capture_output=True,
        text=True,
        timeout=PORT_LOOKUP_TIMEOUT_SECONDS,
    )
    for pid in listing.stdout.split():
        _kill_quietly(int(pid))


def _kill_quietly(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def terminate_process_group(
    process: subprocess.Popen,
    grace_seconds: float = TERMINATION_GRACE_SECONDS,
) -> None:
    """Terminate a server and everything it spawned.

    SIGTERM to the group first, so the server can shut down cleanly; then
    SIGKILL to the group unconditionally. The second signal is not only an
    escalation for a hung server: ``wait`` observes the direct child alone,
    so a wrapper that exits while its child lingers would otherwise read as
    a clean shutdown and leak the very process this exists to reap.
    """
    group = _process_group(process)
    if group is None:
        return

    _signal_group_quietly(group, signal.SIGTERM)
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        pass
    _signal_group_quietly(group, signal.SIGKILL)
    process.wait(timeout=grace_seconds)


def _process_group(process: subprocess.Popen) -> int | None:
    try:
        return os.getpgid(process.pid)
    except ProcessLookupError:
        # Already gone; reap the zombie so the pid table stays clean.
        process.poll()
        return None


def _signal_group_quietly(group: int, signal_number: int) -> None:
    try:
        os.killpg(group, signal_number)
    except ProcessLookupError:
        pass
