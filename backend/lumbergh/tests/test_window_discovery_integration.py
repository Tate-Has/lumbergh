import shutil
import subprocess

import pytest

from lumbergh.constants import TMUX_CMD
from lumbergh.idle_monitor import discover_live_targets

pytestmark = pytest.mark.skipif(shutil.which(TMUX_CMD) is None, reason="tmux not installed")

_MARKER = "╭─ Claude Code ─╮"  # what window_runs_agent looks for


def _tmux(*args):
    subprocess.run([TMUX_CMD, *args], check=True, capture_output=True)


@pytest.fixture
def two_window_session():
    name = "lbtest-fleet"
    subprocess.run([TMUX_CMD, "kill-session", "-t", name], capture_output=True)
    _tmux("new-session", "-d", "-s", name, "-n", "fleet-643")
    _tmux("new-window", "-t", name, "-n", "fleet-644")
    for window in ("fleet-643", "fleet-644"):
        _tmux("send-keys", "-t", f"{name}:{window}", f"printf %s '{_MARKER}'", "Enter")
    yield name
    subprocess.run([TMUX_CMD, "kill-session", "-t", name], capture_output=True)


def test_both_fleet_windows_are_discovered(two_window_session):
    targets = discover_live_targets()
    assert f"{two_window_session}:fleet-643" in targets
    assert f"{two_window_session}:fleet-644" in targets
