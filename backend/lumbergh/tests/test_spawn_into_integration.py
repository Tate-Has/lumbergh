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


def test_two_window_workers_visible_and_reap_isolated(
    tmp_path, session_name, fake_agent_bin, monkeypatch
):
    # Two windows is enough now: a registered worker keeps its own `session:window`
    # target however many siblings it has. Discovery used to collapse a lone remaining
    # agent window back to the bare session name, which forced a third sibling in here
    # purely to keep that collapse from masquerading as a reap failure.
    from lumbergh.idle_monitor import discover_live_targets
    from lumbergh.tmux_pty import create_tmux_window, kill_tmux_window

    workers = {f"{session_name}:fleet-643", f"{session_name}:fleet-644"}
    monkeypatch.setattr(
        "lumbergh.idle_monitor._registered_worker_targets",
        lambda: workers,
    )

    launch = f"exec {fake_agent_bin} 300"
    create_tmux_window(session_name, "fleet-643", tmp_path, launch)
    create_tmux_window(session_name, "fleet-644", tmp_path, launch)

    def both_visible():
        targets = discover_live_targets()
        return all(f"{session_name}:{w}" in targets for w in ("fleet-643", "fleet-644"))

    assert _wait_until(both_visible)

    assert kill_tmux_window(f"{session_name}:fleet-644") is True

    def reaped_and_sibling_survives():
        remaining = discover_live_targets()
        return (
            f"{session_name}:fleet-643" in remaining
            and f"{session_name}:fleet-644" not in remaining
        )

    assert _wait_until(reaped_and_sibling_survives)
