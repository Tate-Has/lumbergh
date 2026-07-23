"""Tests for tmux PTY I/O — short-write handling and child-exec env setup."""

import os
from unittest.mock import MagicMock

from fastapi import WebSocketDisconnect

from lumbergh import tmux_pty
from lumbergh.tmux_pty import TmuxPtySession


def _fake_tmux_run(pane_lines, display_stdout):
    """Build a subprocess.run stand-in that answers capture-pane / display-message.

    Mirrors what tmux returns for a single-pane session: capture-pane emits only
    the pane content (no status bar), and display-message emits the cursor +
    status geometry we ask for.
    """

    def fake_run(argv, **_kwargs):
        result = MagicMock()
        result.returncode = 0
        if "capture-pane" in argv:
            result.stdout = "\n".join(pane_lines) + "\n"
        elif "display-message" in argv:
            result.stdout = display_stdout
        else:
            result.stdout = ""
        return result

    return fake_run


def _fake_tmux_clients(ttys, *, list_rc=0, refresh_rc=0, refresh_calls=None):
    """subprocess.run stand-in for list-clients + refresh-client.

    list-clients returns one client_tty per line; refresh-client records the
    tty it was asked to redraw so tests can assert every attached client got
    a repaint.
    """

    def fake_run(argv, **_kwargs):
        result = MagicMock()
        if "list-clients" in argv:
            result.returncode = list_rc
            result.stdout = "".join(f"{t}\n" for t in ttys)
        elif "refresh-client" in argv:
            result.returncode = refresh_rc
            result.stdout = ""
            if refresh_calls is not None:
                refresh_calls.append(argv[argv.index("-t") + 1])
        else:
            result.returncode = 0
            result.stdout = ""
        return result

    return fake_run


def test_refresh_client_redraws_every_attached_client(monkeypatch):
    """A session with two attached clients (e.g. the web bridge plus a real
    terminal) must have refresh-client issued for each tty so decorations
    repaint everywhere the session is visible."""
    calls: list[str] = []
    monkeypatch.setattr(
        tmux_pty.subprocess,
        "run",
        _fake_tmux_clients(["/dev/pts/3", "/dev/pts/7"], refresh_calls=calls),
    )

    assert tmux_pty.refresh_client("probe") is True
    assert calls == ["/dev/pts/3", "/dev/pts/7"]


def test_refresh_client_reports_failure_when_no_clients(monkeypatch):
    """No attached clients means nothing was redrawn — refresh_client must
    report False so the caller falls back to the capture-pane snapshot."""
    monkeypatch.setattr(tmux_pty.subprocess, "run", _fake_tmux_clients([]))

    assert tmux_pty.refresh_client("probe") is False


def test_refresh_client_reports_failure_when_list_clients_errors(monkeypatch):
    monkeypatch.setattr(tmux_pty.subprocess, "run", _fake_tmux_clients(["/dev/pts/3"], list_rc=1))

    assert tmux_pty.refresh_client("probe") is False


def test_capture_pane_offsets_lines_for_top_status_bar(monkeypatch):
    """Regression: with `status-position top`, tmux gives the pane one fewer
    row (the top status bar) and capture-pane returns only those pane lines.
    The snapshot must position pane content starting at row 2 to match tmux's
    live screen — anchoring at row 1 shifts every row up by one, so subsequent
    incremental redraws (which use tmux's real coordinates) land off by one.
    """
    pane_lines = [f"line{i}" for i in range(23)]  # 23-row pane in a 24-row client
    # cursor on the last pane row (0-indexed 22); status on, at top; client 24, window 23
    monkeypatch.setattr(
        tmux_pty.subprocess, "run", _fake_tmux_run(pane_lines, "0,22,1,on,top,24,23")
    )

    out = tmux_pty.capture_pane_content("probe")

    assert "\x1b[2;1Hline0" in out, "first pane line must sit below the top status bar"
    assert "\x1b[1;1Hline0" not in out, "pane content must not clobber the status row"
    # Cursor restored at screen row 24 = top offset (1) + pane row (22) + 1
    assert "\x1b[24;1H" in out


def test_capture_pane_no_offset_for_bottom_status_bar(monkeypatch):
    """With the status bar at the bottom, the pane starts at screen row 1, so
    no offset must be applied (guards against over-correcting the top-status fix).
    """
    pane_lines = [f"line{i}" for i in range(23)]
    monkeypatch.setattr(
        tmux_pty.subprocess, "run", _fake_tmux_run(pane_lines, "0,22,1,on,bottom,24,23")
    )

    out = tmux_pty.capture_pane_content("probe")

    assert "\x1b[1;1Hline0" in out, "bottom-status pane content starts at row 1"
    assert "\x1b[23;1H" in out, "cursor restored at pane row with no status offset"


async def test_write_loop_handles_short_writes(monkeypatch):
    """Regression for issue #14: pastes larger than the PTY input buffer
    cause os.write to do a short write. The WS input handler must retry
    until all bytes are written, otherwise xterm.js's bracketed-paste end
    marker (ESC[201~) is silently dropped and Claude Code submits early.
    """
    client = TmuxPtySession.__new__(TmuxPtySession)
    client.master_fd = 999  # fake fd; never actually written to

    payload = "X" * 8192
    written = bytearray()
    call_count = [0]

    def fake_os_write(_fd, data):
        call_count[0] += 1
        # First call accepts only half — simulates a full PTY input buffer
        n = len(data) // 2 if call_count[0] == 1 else len(data)
        written.extend(data[:n])
        return n

    monkeypatch.setattr(tmux_pty.os, "write", fake_os_write)

    class FakeWS:
        def __init__(self):
            self.calls = 0

        async def receive_json(self):
            self.calls += 1
            if self.calls == 1:
                return {"type": "input", "data": payload}
            raise WebSocketDisconnect()

    await client._write_loop(FakeWS())

    assert bytes(written) == payload.encode("utf-8")
    assert call_count[0] >= 2, "expected retry after short write"


def test_exec_tmux_attach_sets_term_when_unset(monkeypatch):
    """Regression: daemon-launched parents (systemd, docker, cron) have no
    TERM in env. Without one, tmux exits at startup with `open terminal
    failed: terminal does not support clear`. The child must set TERM
    before exec'ing tmux.
    """
    monkeypatch.delenv("TERM", raising=False)

    captured: dict[str, object] = {}

    def fake_execlp(*args):
        captured["args"] = args
        captured["TERM"] = os.environ.get("TERM")

    monkeypatch.setattr(tmux_pty.os, "execlp", fake_execlp)

    tmux_pty._exec_tmux_attach("mysession")

    assert captured["TERM"] == "xterm-256color"
    assert captured["args"][-1] == "mysession"


def test_exec_tmux_attach_preserves_explicit_term(monkeypatch):
    """Operators running custom xterm.js builds (or different terminfo)
    must be able to override TERM via the inherited environment.
    setdefault — not assignment — keeps that escape hatch open.
    """
    monkeypatch.setenv("TERM", "screen-256color")

    captured: dict[str, object] = {}

    def fake_execlp(*_args):
        captured["TERM"] = os.environ.get("TERM")

    monkeypatch.setattr(tmux_pty.os, "execlp", fake_execlp)

    tmux_pty._exec_tmux_attach("mysession")

    assert captured["TERM"] == "screen-256color"
