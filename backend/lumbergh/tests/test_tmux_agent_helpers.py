import subprocess
from unittest.mock import patch

from lumbergh.tmux_pty import capture_pane_text, send_text


def _ok(stdout=""):
    return subprocess.CompletedProcess([], 0, stdout=stdout)


def test_capture_pane_text_returns_plain():
    with patch("lumbergh.tmux_pty.subprocess.run", return_value=_ok("line1\nline2\n")):
        assert capture_pane_text("s") == "line1\nline2"


def test_capture_pane_text_failure_returns_empty():
    with patch("lumbergh.tmux_pty.subprocess.run", side_effect=OSError):
        assert capture_pane_text("s") == ""


def test_send_text_sends_literal_then_enter():
    calls = []
    with patch(
        "lumbergh.tmux_pty.subprocess.run",
        side_effect=lambda cmd, **_k: calls.append(cmd) or _ok(),
    ):
        assert send_text("s", "hello world") is True
    assert any("-l" in c and "hello world" in c for c in calls)
    assert any(c[-1] == "Enter" for c in calls)
