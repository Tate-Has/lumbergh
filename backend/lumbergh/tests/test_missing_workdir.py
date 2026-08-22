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
