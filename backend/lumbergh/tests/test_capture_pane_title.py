import subprocess
from unittest.mock import patch

from lumbergh.tmux_pty import capture_pane_title


def _completed(stdout="", returncode=0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout)


def test_returns_stripped_title():
    with patch("lumbergh.tmux_pty.subprocess.run", return_value=_completed("✻ Baking\n")):
        assert capture_pane_title("sess") == "✻ Baking"


def test_nonzero_exit_returns_empty():
    with patch("lumbergh.tmux_pty.subprocess.run", return_value=_completed("x", returncode=1)):
        assert capture_pane_title("sess") == ""


def test_exception_returns_empty():
    with patch("lumbergh.tmux_pty.subprocess.run", side_effect=OSError("boom")):
        assert capture_pane_title("sess") == ""
