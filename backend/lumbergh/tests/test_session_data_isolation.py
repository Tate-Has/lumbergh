"""No test run may write into the developer's own session data.

A monitor built in a test has no prior state, so its first poll reads every real
tmux session as ``unknown -> working`` and persists that. The dashboard reads the
persisted row, and the monitor only rewrites it on a *transition* — so a session
that then stays quiet shows green for hours with nothing running. Same class as
the worktree registry leak in f724a9c.
"""

import pytest

from lumbergh.constants import SESSIONS_DATA_DIR as REAL_SESSION_DATA_DIR
from lumbergh.idle_detector import SessionState
from lumbergh.idle_monitor import IdleMonitor


def test_the_session_data_dir_under_test_is_not_the_real_one():
    from lumbergh import db_utils

    assert db_utils.SESSIONS_DATA_DIR != REAL_SESSION_DATA_DIR


@pytest.mark.asyncio
async def test_persisted_state_lands_in_the_isolated_dir(isolated_session_data):
    await IdleMonitor()._persist_state("port", SessionState.WORKING)

    assert (isolated_session_data / "port.json").exists()


@pytest.mark.asyncio
async def test_a_poll_of_the_real_tmux_server_writes_only_into_the_isolated_dir(
    isolated_session_data,
):
    """Looking at real tmux is harmless; leaving a row behind in the developer's
    config is not. A fresh monitor classifies every target it finds, and each of
    those classifications is a transition, so each one persists."""
    monitor = IdleMonitor()

    await monitor._check_all_sessions()

    written = {p.stem for p in isolated_session_data.glob("*.json")}
    assert written >= set(monitor.live_targets())
