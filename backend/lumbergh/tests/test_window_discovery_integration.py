import shutil
import stat
import subprocess
import time

import pytest

from lumbergh.constants import TMUX_CMD
from lumbergh.idle_monitor import discover_live_targets

pytestmark = pytest.mark.skipif(shutil.which(TMUX_CMD) is None, reason="tmux not installed")


def _tmux(*args):
    subprocess.run([TMUX_CMD, *args], check=True, capture_output=True)


@pytest.fixture
def fake_agent_bin(tmp_path):
    # A real binary named `claude`, so its /proc `comm` is `claude` — the process
    # signal discovery keys on. A shebang script would report the interpreter, not
    # the script name, so a plain copy of a long-lived binary is what we need.
    path = tmp_path / "claude"
    shutil.copy(shutil.which("sleep"), path)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


@pytest.fixture
def two_window_session(fake_agent_bin):
    name = "lbtest-fleet"
    subprocess.run([TMUX_CMD, "kill-session", "-t", name], capture_output=True)
    _tmux("new-session", "-d", "-s", name, "-n", "fleet-643")
    _tmux("new-window", "-t", name, "-n", "fleet-644")
    for window in ("fleet-643", "fleet-644"):
        _tmux("send-keys", "-t", f"{name}:{window}", f"exec {fake_agent_bin} 60", "Enter")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not _both_discovered(name):
        time.sleep(0.05)
    yield name
    subprocess.run([TMUX_CMD, "kill-session", "-t", name], capture_output=True)


def _both_discovered(name: str) -> bool:
    targets = discover_live_targets()
    return f"{name}:fleet-643" in targets and f"{name}:fleet-644" in targets


def test_both_fleet_windows_are_discovered(two_window_session):
    assert _both_discovered(two_window_session)
