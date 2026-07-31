import shutil
import subprocess

import pytest

from lumbergh.constants import TMUX_CMD


def _run(*args):
    subprocess.run([TMUX_CMD, *args], check=True, capture_output=True)


def _windows(session):
    out = subprocess.run(
        [TMUX_CMD, "list-windows", "-t", session, "-F", "#{window_name}"],
        capture_output=True,
        encoding="utf-8",
    )
    return out.stdout.split()


pytestmark = pytest.mark.skipif(shutil.which(TMUX_CMD) is None, reason="tmux not installed")


@pytest.fixture
def cleanup_sessions():
    made = []
    yield made
    for s in made:
        subprocess.run([TMUX_CMD, "kill-session", "-t", s], capture_output=True)


def test_create_tmux_window_auto_creates_missing_session(tmp_path, cleanup_sessions):
    from lumbergh.tmux_pty import create_tmux_window

    made = cleanup_sessions
    made.append("lbtest-into")
    target = create_tmux_window("lbtest-into", "w1", tmp_path, "true")
    assert target == "lbtest-into:w1"
    assert "w1" in _windows("lbtest-into")


def test_create_tmux_window_adds_to_existing_session(tmp_path, cleanup_sessions):
    from lumbergh.tmux_pty import create_tmux_window

    made = cleanup_sessions
    made.append("lbtest-into2")
    _run("new-session", "-d", "-s", "lbtest-into2", "-n", "first")
    create_tmux_window("lbtest-into2", "w2", tmp_path, "true")
    assert set(_windows("lbtest-into2")) >= {"first", "w2"}


def test_kill_tmux_window_removes_only_that_window(tmp_path, cleanup_sessions):
    from lumbergh.tmux_pty import create_tmux_window, kill_tmux_window

    made = cleanup_sessions
    made.append("lbtest-into3")
    create_tmux_window("lbtest-into3", "keep", tmp_path, "true")
    create_tmux_window("lbtest-into3", "drop", tmp_path, "true")
    assert kill_tmux_window("lbtest-into3:drop") is True
    remaining = _windows("lbtest-into3")
    assert "keep" in remaining
    assert "drop" not in remaining
