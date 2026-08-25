"""The dashboard's state for a live session comes from the monitor, not from disk.

The persisted row is only rewritten on a state *transition*, so one bad write —
a test that escaped its sandbox, a crash mid-episode — pins a quiet session at
whatever it last said. Green for hours with nothing running, while ``lb state``
reports idle from the same monitor the dashboard could have asked.
"""

import pytest

from lumbergh.db_utils import get_session_data_db
from lumbergh.idle_detector import SessionState
from lumbergh.idle_monitor import idle_monitor
from lumbergh.routers.sessions import get_session_status


@pytest.fixture
def persisted_working():
    def _write(name):
        table = get_session_data_db(name).table("idle_state")
        table.truncate()
        table.insert({"state": "working", "updatedAt": "2026-01-01T00:00:00+00:00"})

    return _write


@pytest.fixture(autouse=True)
def clean_monitor():
    yield
    idle_monitor._states.clear()
    idle_monitor._state_since.clear()
    idle_monitor._live_targets = []


class TestLiveStateWins:
    def test_a_live_target_reports_what_the_monitor_sees_now(self, persisted_working):
        persisted_working("watched")
        idle_monitor._live_targets = ["watched"]
        idle_monitor._record_state_change("watched", SessionState.IDLE)

        assert get_session_status("watched")["idleState"] == "idle"

    def test_the_timestamp_follows_the_live_episode_not_the_stale_row(self, persisted_working):
        persisted_working("watched")
        idle_monitor._live_targets = ["watched"]
        idle_monitor._record_state_change("watched", SessionState.IDLE)

        assert get_session_status("watched")["idleStateUpdatedAt"] > "2026-01-01T00:00:00+00:00"

    def test_a_session_the_monitor_is_not_watching_keeps_its_last_known_row(
        self, persisted_working
    ):
        """A dead or paused session still shows how it ended, which is the whole
        point of persisting the row."""
        persisted_working("gone")
        idle_monitor._live_targets = []

        assert get_session_status("gone")["idleState"] == "working"

    def test_an_unclassified_live_target_falls_back_to_the_row(self, persisted_working):
        """UNKNOWN is 'not judged yet', not 'nothing is happening' — a session
        discovered seconds ago must not blank out what it last reported."""
        persisted_working("fresh")
        idle_monitor._live_targets = ["fresh"]

        assert get_session_status("fresh")["idleState"] == "working"
