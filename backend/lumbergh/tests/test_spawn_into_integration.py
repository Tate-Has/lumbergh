import shutil
import stat
import subprocess
import time

import pytest

from lumbergh.constants import TMUX_CMD

pytestmark = pytest.mark.skipif(shutil.which(TMUX_CMD) is None, reason="tmux not installed")


@pytest.fixture
def session_name():
    name = "lbtest-batch"
    subprocess.run([TMUX_CMD, "kill-session", "-t", name], capture_output=True)
    yield name
    subprocess.run([TMUX_CMD, "kill-session", "-t", name], capture_output=True)


@pytest.fixture
def fake_agent_bin(tmp_path):
    # A real binary named `claude`, so its /proc `comm` is `claude` — the process
    # signal discovery keys on. `exec`ing it replaces the window's shell with it.
    path = tmp_path / "claude"
    shutil.copy(shutil.which("sleep"), path)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def _wait_until(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not predicate():
        time.sleep(0.05)
    return predicate()


def test_two_window_workers_visible_and_reap_isolated(tmp_path, session_name, fake_agent_bin):
    # Three windows, not two: with only two, killing one leaves a single
    # remaining agent window, and targets.select_targets() deliberately
    # collapses a lone-window session back to its bare session name (see
    # targets.py's module docstring). That collapse is correct behavior but
    # would masquerade as a false negative here. A third sibling keeps the
    # session multi-window after the kill, so the assertions below exercise
    # window-level reap isolation on its own.
    from lumbergh.idle_monitor import discover_live_targets
    from lumbergh.tmux_pty import create_tmux_window, kill_tmux_window

    launch = f"exec {fake_agent_bin} 300"
    create_tmux_window(session_name, "fleet-643", tmp_path, launch)
    create_tmux_window(session_name, "fleet-644", tmp_path, launch)
    create_tmux_window(session_name, "fleet-645", tmp_path, launch)

    def all_three_visible():
        targets = discover_live_targets()
        return all(f"{session_name}:{w}" in targets for w in ("fleet-643", "fleet-644", "fleet-645"))

    assert _wait_until(all_three_visible)

    assert kill_tmux_window(f"{session_name}:fleet-644") is True

    def reaped_and_siblings_survive():
        remaining = discover_live_targets()
        return (
            f"{session_name}:fleet-643" in remaining
            and f"{session_name}:fleet-645" in remaining
            and f"{session_name}:fleet-644" not in remaining
        )

    assert _wait_until(reaped_and_siblings_survive)
