"""A container session's state is the state of its window workers."""

import json

import pytest

import lumbergh.session_attention as sa
from lumbergh.routers.sessions import get_session_status


@pytest.fixture(autouse=True)
def session_data_dir(tmp_path, monkeypatch):
    from lumbergh import constants, db_utils

    monkeypatch.setattr(constants, "SESSIONS_DATA_DIR", tmp_path)
    monkeypatch.setattr(db_utils, "SESSIONS_DATA_DIR", tmp_path)
    db_utils._db_cache.clear()
    sa.reset()
    return tmp_path


def write_idle_state(session_data_dir, target, state, updated_at="2026-08-20T23:35:56+00:00"):
    path = session_data_dir / f"{target}.json"
    path.write_text(json.dumps({"idle_state": {"1": {"state": state, "updatedAt": updated_at}}}))


def test_empty_container_db_reports_its_windows_state(session_data_dir):
    (session_data_dir / "port-b9-1187.json").write_text("")
    write_idle_state(session_data_dir, "port-b9-1187:1187", "idle")

    result = get_session_status("port-b9-1187")

    assert result["idleState"] == "idle"
    assert result["idleStateUpdatedAt"] == "2026-08-20T23:35:56+00:00"


def test_a_working_window_keeps_the_container_working(session_data_dir):
    write_idle_state(session_data_dir, "batch:1", "idle")
    write_idle_state(session_data_dir, "batch:2", "working")

    assert get_session_status("batch")["idleState"] == "working"


def test_a_blocked_window_outranks_a_working_one(session_data_dir):
    write_idle_state(session_data_dir, "batch:1", "working")
    write_idle_state(session_data_dir, "batch:2", "blocked", "2026-08-20T23:40:00+00:00")

    result = get_session_status("batch")

    assert result["idleState"] == "blocked"
    assert result["idleStateUpdatedAt"] == "2026-08-20T23:40:00+00:00"


def test_the_containers_own_state_wins_over_its_windows(session_data_dir):
    write_idle_state(session_data_dir, "port", "working")
    write_idle_state(session_data_dir, "port:2", "idle")

    assert get_session_status("port")["idleState"] == "working"


def test_a_session_with_no_windows_still_reports_nothing():
    assert get_session_status("nobody")["idleState"] is None


def test_a_sibling_whose_name_merely_shares_a_prefix_is_not_a_window(session_data_dir):
    write_idle_state(session_data_dir, "port-b9-1187-other", "working")

    assert get_session_status("port-b9-1187")["idleState"] is None
