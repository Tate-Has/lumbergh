"""Tests for SessionManager — specifically the copy-mode poll cleanup.

Regression: the 250ms copy-mode polling loop used to swallow subprocess
failures without killing the child, leaking stdout/stderr pipes until the
backend hit EMFILE. These tests lock down the kill+reap contract.
"""

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from lumbergh.session_manager import ManagedSession, SessionManager, TerminalClient


def _make_proc(stdout: bytes = b"", returncode: int | None = None) -> MagicMock:
    """Build a mock asyncio subprocess. returncode=None means 'still running'."""
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(stdout, b""))
    proc.wait = AsyncMock(return_value=0)
    proc.kill = MagicMock()
    proc.returncode = returncode
    return proc


async def test_poll_copy_mode_returns_true_when_pane_in_copy_mode(mocker: MockerFixture) -> None:
    proc = _make_proc(stdout=b"copy-mode\n")
    mocker.patch("asyncio.create_subprocess_exec", return_value=proc)

    result = await SessionManager()._poll_copy_mode("s1")

    assert result is True
    proc.kill.assert_not_called()


async def test_poll_copy_mode_returns_false_for_normal_pane(mocker: MockerFixture) -> None:
    proc = _make_proc(stdout=b"\n")
    mocker.patch("asyncio.create_subprocess_exec", return_value=proc)

    result = await SessionManager()._poll_copy_mode("s1")

    assert result is False
    proc.kill.assert_not_called()


def _fail_wait_for(exc: BaseException):
    """wait_for side_effect that closes the awaited coroutine before raising,
    so AsyncMock-produced coroutines don't linger as un-awaited warnings."""

    async def _raise(coro, timeout):  # noqa: ARG001 — signature must match asyncio.wait_for
        coro.close()
        raise exc

    return _raise


async def test_poll_copy_mode_reaps_proc_on_timeout(mocker: MockerFixture) -> None:
    """TimeoutError during communicate() must kill and await the proc so pipes close."""
    proc = _make_proc(returncode=None)
    mocker.patch("asyncio.create_subprocess_exec", return_value=proc)
    mocker.patch("asyncio.wait_for", side_effect=_fail_wait_for(TimeoutError()))

    result = await SessionManager()._poll_copy_mode("s1")

    assert result is None
    proc.kill.assert_called_once()
    proc.wait.assert_called_once()


async def test_poll_copy_mode_reaps_proc_on_oserror(mocker: MockerFixture) -> None:
    """OSError (e.g. EMFILE) during communicate() must also reap the proc."""
    proc = _make_proc(returncode=None)
    mocker.patch("asyncio.create_subprocess_exec", return_value=proc)
    mocker.patch(
        "asyncio.wait_for",
        side_effect=_fail_wait_for(OSError(24, "Too many open files")),
    )

    result = await SessionManager()._poll_copy_mode("s1")

    assert result is None
    proc.kill.assert_called_once()
    proc.wait.assert_called_once()


async def test_poll_copy_mode_skips_kill_if_proc_already_exited(mocker: MockerFixture) -> None:
    """If returncode is set, proc has exited — don't try to kill it again."""
    proc = _make_proc(returncode=0)
    mocker.patch("asyncio.create_subprocess_exec", return_value=proc)
    mocker.patch("asyncio.wait_for", side_effect=_fail_wait_for(TimeoutError()))

    result = await SessionManager()._poll_copy_mode("s1")

    assert result is None
    proc.kill.assert_not_called()


async def test_poll_copy_mode_returns_none_when_spawn_itself_fails(
    mocker: MockerFixture,
) -> None:
    """If subprocess spawn raises OSError (EMFILE), there's no proc to reap — just bail."""
    mocker.patch(
        "asyncio.create_subprocess_exec",
        side_effect=OSError(24, "Too many open files"),
    )

    result = await SessionManager()._poll_copy_mode("s1")

    assert result is None


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:
    """SessionManager is a singleton — clear _sessions between tests."""
    mgr = SessionManager()
    mgr._sessions.clear()


def _fake_pty() -> MagicMock:
    pty = MagicMock()
    pty.cols = 80
    pty.rows = 24

    def resize(cols: int, rows: int) -> None:
        pty.cols, pty.rows = cols, rows

    pty.resize.side_effect = resize
    return pty


def _register(mgr: SessionManager, name: str, *clients: AsyncMock) -> ManagedSession:
    managed = ManagedSession(pty=_fake_pty())
    managed.clients.update(cast("tuple[TerminalClient, ...]", clients))
    mgr._sessions[name] = managed
    return managed


def _last_sync(client: AsyncMock) -> tuple[int, int] | None:
    """Return (cols, rows) of the most recent resize_sync sent to a client."""
    for call in reversed(client.send_json.call_args_list):
        msg = call.args[0]
        if msg.get("type") == "resize_sync":
            return (msg["cols"], msg["rows"])
    return None


async def test_latest_active_device_wins_shared_size() -> None:
    """Desktop is active first; then the phone activates. The phone (latest
    active) drives the shared window and every client is synced to its size."""
    mgr = SessionManager()
    desktop, phone = AsyncMock(), AsyncMock()
    managed = _register(mgr, "s", desktop, phone)

    await mgr.handle_client_message("s", {"type": "activate", "cols": 200, "rows": 50}, desktop)
    await mgr.handle_client_message("s", {"type": "activate", "cols": 48, "rows": 40}, phone)

    assert (managed.pty.cols, managed.pty.rows) == (48, 40)
    assert _last_sync(desktop) == (48, 40)


async def test_backgrounded_device_yields_window_to_remaining_device() -> None:
    """When the active phone backgrounds, the desktop reclaims the window and
    all clients are resized back to the desktop's size."""
    mgr = SessionManager()
    desktop, phone = AsyncMock(), AsyncMock()
    managed = _register(mgr, "s", desktop, phone)

    await mgr.handle_client_message("s", {"type": "activate", "cols": 200, "rows": 50}, desktop)
    await mgr.handle_client_message("s", {"type": "activate", "cols": 48, "rows": 40}, phone)
    await mgr.handle_client_message("s", {"type": "deactivate"}, phone)

    assert (managed.pty.cols, managed.pty.rows) == (200, 50)
    assert _last_sync(phone) == (200, 50)


async def test_background_resize_does_not_steal_window() -> None:
    """A resize from a backgrounded device updates its stored size but must not
    yank the window away from the active device."""
    mgr = SessionManager()
    desktop, phone = AsyncMock(), AsyncMock()
    managed = _register(mgr, "s", desktop, phone)

    await mgr.handle_client_message("s", {"type": "activate", "cols": 48, "rows": 40}, phone)
    # Desktop never activated (background tab) but reports a layout change.
    await mgr.handle_client_message("s", {"type": "resize", "cols": 200, "rows": 50}, desktop)

    assert (managed.pty.cols, managed.pty.rows) == (48, 40)


async def test_disconnect_lets_remaining_device_reclaim_window() -> None:
    """Unregistering the active device hands the window to whoever is left."""
    mgr = SessionManager()
    desktop, phone = AsyncMock(), AsyncMock()
    managed = _register(mgr, "s", desktop, phone)

    await mgr.handle_client_message("s", {"type": "activate", "cols": 200, "rows": 50}, desktop)
    await mgr.handle_client_message("s", {"type": "activate", "cols": 48, "rows": 40}, phone)

    await mgr.unregister_client("s", phone)

    assert (managed.pty.cols, managed.pty.rows) == (200, 50)
    assert _last_sync(desktop) == (200, 50)
