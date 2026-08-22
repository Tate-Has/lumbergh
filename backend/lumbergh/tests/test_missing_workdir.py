"""A session whose directory is gone — a reaped worktree — must say so plainly.

The git endpoints used to answer 500 with the bare path as the detail, which
told the UI nothing it could show a person.
"""

import pytest
from fastapi.testclient import TestClient

from lumbergh.main import app
from lumbergh.routers import sessions as sessions_router


@pytest.fixture
def client(tmp_path, monkeypatch):
    gone = tmp_path / "worktrees" / "1187"
    monkeypatch.setattr(
        sessions_router,
        "get_stored_sessions",
        lambda: {"reaped": {"name": "reaped", "workdir": str(gone)}},
    )
    return TestClient(app)


@pytest.mark.parametrize("endpoint", ["graph", "diff", "branches", "remote-status"])
def test_git_endpoints_report_the_missing_directory(client, endpoint):
    response = client.get(f"/api/sessions/reaped/git/{endpoint}")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert "no longer exists" in detail
    assert "1187" in detail, "name the directory so the message is actionable"


class TestOpeningASessionMarksItSeen:
    """`/touch` fires when a session page opens — including for a dead session,
    which has no terminal socket to announce a viewer."""

    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        from tinydb import TinyDB

        import lumbergh.session_attention as sa

        sa.reset()
        table = TinyDB(tmp_path / "sessions.json").table("sessions")
        table.insert({"name": "batch", "workdir": str(tmp_path)})
        monkeypatch.setattr(sessions_router, "sessions_table", table)
        monkeypatch.setattr(sessions_router, "get_live_sessions", dict)
        return TestClient(app)

    def test_touch_clears_the_flag_and_its_windows(self, client):
        import lumbergh.session_attention as sa

        sa.mark_attention("batch", "idle")
        sa.mark_attention("batch:1187", "idle")

        assert client.post("/api/sessions/batch/touch").status_code == 200

        assert sa.unseen_count() == 0
