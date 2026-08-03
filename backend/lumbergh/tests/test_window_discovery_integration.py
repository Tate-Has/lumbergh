import shutil
import stat
import subprocess
import time

import pytest

from lumbergh.constants import TMUX_CMD
from lumbergh.idle_monitor import discover_live_targets, discover_target_refs, tmux_ref
from lumbergh.tmux_pty import capture_pane_content

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


def _window_indices(session: str) -> list[str]:
    """The session's real window indices, in order.

    Read rather than assumed: tmux numbers from `base-index`, which is 1 in many user
    configs and 0 by default — hardcoding either makes a test that only passes on the
    machine it was written on.
    """
    out = subprocess.run(
        [TMUX_CMD, "list-windows", "-t", session, "-F", "#{window_index}"],
        capture_output=True,
        encoding="utf-8",
    )
    return out.stdout.split()


def _start_agent_session(name: str, window_names: list[str], agent_bin, marker: bool = False):
    subprocess.run([TMUX_CMD, "kill-session", "-t", name], capture_output=True)
    _tmux("new-session", "-d", "-s", name, "-n", window_names[0])
    for window in window_names[1:]:
        _tmux("new-window", "-t", name, "-n", window)
    for position, index in enumerate(_window_indices(name), start=1):
        prefix = f"echo MARKER-WINDOW-{position}; " if marker else ""
        _tmux("send-keys", "-t", f"{name}:{index}", f"{prefix}exec {agent_bin} 60", "Enter")


def _register_workers(monkeypatch, targets: set[str]) -> None:
    """Claim windows as fleet work, the way `lb spawn --into` records them."""
    monkeypatch.setattr("lumbergh.idle_monitor._registered_worker_targets", lambda: targets)


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
def killable():
    made: list[str] = []
    yield made
    for name in made:
        subprocess.run([TMUX_CMD, "kill-session", "-t", name], capture_output=True)


def test_an_extra_agent_window_never_changes_the_session_identity(fake_agent_bin, killable):
    """The overnight outage: a second Claude opened in `port` to look something up made
    `port` itself stop existing, so the babysit keyed to that name drove nothing."""
    name = "lbtest-extra"
    killable.append(name)
    _start_agent_session(name, ["claude", "claude"], fake_agent_bin)
    assert _await_targets(name, {name}) == {name}


def test_registered_worker_windows_are_discovered(fake_agent_bin, killable, monkeypatch):
    name = "lbtest-fleet"
    killable.append(name)
    _start_agent_session(name, ["fleet-643", "fleet-644"], fake_agent_bin)
    _register_workers(monkeypatch, {f"{name}:fleet-643", f"{name}:fleet-644"})
    expected = {f"{name}:fleet-643", f"{name}:fleet-644"}
    assert _await_targets(name, expected) == expected


def test_registered_workers_resolve_even_when_their_names_collide(
    fake_agent_bin, killable, monkeypatch
):
    """tmux allows two windows to share a name, and an ambiguous `session:name` ref is one
    tmux refuses to act on — which once made both windows read as agent-less."""
    name = "lbtest-dupe"
    killable.append(name)
    _start_agent_session(name, ["claude", "claude"], fake_agent_bin)
    # Colliding names mean the labels are the windows' own indices, whatever tmux's
    # `base-index` happens to be.
    expected = {f"{name}:{i}" for i in _window_indices(name)}
    _register_workers(monkeypatch, expected)
    assert _await_targets(name, expected) == expected


def test_the_session_target_points_at_its_first_window_not_the_selected_one(
    fake_agent_bin, killable
):
    """A bare session name handed to tmux resolves to whichever window is *selected*, so
    switching windows would redirect both the state read and any keystrokes sent."""
    name = "lbtest-selected"
    killable.append(name)
    _start_agent_session(name, ["claude", "scratch"], fake_agent_bin, marker=True)
    _await_targets(name, {name})
    first, second = _window_indices(name)
    _tmux("select-window", "-t", f"{name}:{second}")

    first_window_id = subprocess.run(
        [TMUX_CMD, "display-message", "-p", "-t", f"{name}:{first}", "#{window_id}"],
        capture_output=True,
        encoding="utf-8",
    ).stdout.strip()
    assert discover_target_refs()[name] == first_window_id

    content = capture_pane_content(tmux_ref(name))
    assert "MARKER-WINDOW-1" in content
    assert "MARKER-WINDOW-2" not in content


def test_tmux_ref_falls_back_to_the_first_window_for_an_unknown_target():
    """Whatever discovery hasn't cached still resolves to window 1, never to the
    session's active window."""
    assert tmux_ref("never-discovered") == "never-discovered:{start}"


@pytest.mark.usefixtures("killable")
def test_every_discovered_target_resolves_in_tmux(fake_agent_bin, killable):
    """The invariant the old tests never checked: a target string Lumbergh hands out
    must be one tmux can act on. Every read, capture and nudge goes through one."""
    killable.append("lbtest-resolve")
    _start_agent_session("lbtest-resolve", ["claude", "claude"], fake_agent_bin)
    _await_targets("lbtest-resolve", {"lbtest-resolve"})
    unresolvable = [
        target
        for target in discover_live_targets()
        if subprocess.run(
            [TMUX_CMD, "list-panes", "-t", tmux_ref(target), "-F", "#{pane_pid}"],
            capture_output=True,
        ).returncode
        != 0
    ]
    assert unresolvable == []
