import shutil
import subprocess

import pytest

from lumbergh.constants import TMUX_CMD

pytestmark = pytest.mark.skipif(shutil.which(TMUX_CMD) is None, reason="tmux not installed")

_MARKER = "╭─ Claude Code ─╮"


@pytest.fixture
def session_name():
    name = "lbtest-batch"
    subprocess.run([TMUX_CMD, "kill-session", "-t", name], capture_output=True)
    yield name
    subprocess.run([TMUX_CMD, "kill-session", "-t", name], capture_output=True)


def test_two_window_workers_visible_and_reap_isolated(tmp_path, session_name):
    # Three windows, not two: with only two, killing one leaves a single
    # remaining agent window, and targets.select_targets() deliberately
    # collapses a lone-window session back to its bare session name (see
    # targets.py's module docstring). That collapse is correct behavior but
    # would masquerade as a false negative here. A third sibling keeps the
    # session multi-window after the kill, so the assertions below exercise
    # window-level reap isolation on its own.
    from lumbergh.idle_monitor import discover_live_targets
    from lumbergh.tmux_pty import create_tmux_window, kill_tmux_window

    launch = f"printf %s '{_MARKER}'; sleep 300"
    create_tmux_window(session_name, "fleet-643", tmp_path, launch)
    create_tmux_window(session_name, "fleet-644", tmp_path, launch)
    create_tmux_window(session_name, "fleet-645", tmp_path, launch)

    targets = discover_live_targets()
    assert f"{session_name}:fleet-643" in targets
    assert f"{session_name}:fleet-644" in targets
    assert f"{session_name}:fleet-645" in targets

    assert kill_tmux_window(f"{session_name}:fleet-644") is True
    remaining = discover_live_targets()
    assert f"{session_name}:fleet-643" in remaining  # sibling survives
    assert f"{session_name}:fleet-645" in remaining  # sibling survives
    assert f"{session_name}:fleet-644" not in remaining  # only the reaped one is gone
