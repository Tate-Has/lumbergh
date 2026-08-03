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


def _start_agent_session(name: str, window_names: list[str], agent_bin) -> None:
    subprocess.run([TMUX_CMD, "kill-session", "-t", name], capture_output=True)
    _tmux("new-session", "-d", "-s", name, "-n", window_names[0])
    for window in window_names[1:]:
        _tmux("new-window", "-t", name, "-n", window)
    for index in range(1, len(window_names) + 1):
        _tmux("send-keys", "-t", f"{name}:{index}", f"exec {agent_bin} 60", "Enter")


def _await_targets(name: str, expected: set[str]) -> set[str]:
    deadline = time.monotonic() + 5
    found: set[str] = set()
    while time.monotonic() < deadline:
        found = {t for t in discover_live_targets() if t.split(":")[0] == name}
        if found >= expected:
            break
        time.sleep(0.05)
    return found


@pytest.fixture
def two_window_session(fake_agent_bin):
    name = "lbtest-fleet"
    _start_agent_session(name, ["fleet-643", "fleet-644"], fake_agent_bin)
    _await_targets(name, {f"{name}:fleet-643", f"{name}:fleet-644"})
    yield name
    subprocess.run([TMUX_CMD, "kill-session", "-t", name], capture_output=True)


@pytest.fixture
def duplicate_window_name_session(fake_agent_bin):
    """Two agent windows that share a name — what `port` looked like when it vanished.

    tmux allows it (nothing dedupes window names), so discovery has to survive it.
    """
    name = "lbtest-dupe"
    _start_agent_session(name, ["claude", "claude"], fake_agent_bin)
    yield name
    subprocess.run([TMUX_CMD, "kill-session", "-t", name], capture_output=True)


def test_both_fleet_windows_are_discovered(two_window_session):
    name = two_window_session
    assert _await_targets(name, {f"{name}:fleet-643", f"{name}:fleet-644"}) == {
        f"{name}:fleet-643",
        f"{name}:fleet-644",
    }


def test_session_with_duplicate_window_names_is_still_discovered(duplicate_window_name_session):
    """Regression: an ambiguous `session:name` ref made *both* windows look agent-less,
    so the session dropped out of `lb` entirely and Bill had nothing to babysit."""
    name = duplicate_window_name_session
    assert _await_targets(name, {f"{name}:1", f"{name}:2"}) == {f"{name}:1", f"{name}:2"}


@pytest.mark.usefixtures("duplicate_window_name_session", "two_window_session")
def test_every_discovered_target_resolves_in_tmux():
    """The invariant the old tests never checked: a target string Lumbergh hands out
    must be one tmux can act on. Every read, capture and nudge goes through one."""
    unresolvable = [
        target
        for target in discover_live_targets()
        if subprocess.run(
            [TMUX_CMD, "list-panes", "-t", target, "-F", "#{pane_pid}"],
            capture_output=True,
        ).returncode
        != 0
    ]
    assert unresolvable == []
