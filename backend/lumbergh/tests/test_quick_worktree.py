"""One-click worktree: a second agent on the same repo, nothing to fill in.

The full create flow asks for a branch, a session name and a description. When
you just want another agent working somewhere else, all three are ceremony.
"""

import pytest
from fastapi.testclient import TestClient
from tinydb import TinyDB

from lumbergh.main import app
from lumbergh.quick_worktree import next_quick_name
from lumbergh.routers import sessions as sessions_router


class TestNaming:
    def test_the_first_quick_worktree_is_number_one(self):
        assert next_quick_name(set(), set()) == ("quick/1", "quick-1")

    def test_it_steps_past_a_branch_that_already_exists(self):
        assert next_quick_name({"quick/1", "quick/2"}, set()) == ("quick/3", "quick-3")

    def test_a_taken_session_name_moves_the_branch_too(self):
        """Branch and session stay a matching pair, so one name describes both."""
        assert next_quick_name(set(), {"quick-1"}) == ("quick/2", "quick-2")


@pytest.fixture
def client(tmp_path, monkeypatch):
    table = TinyDB(tmp_path / "sessions.json").table("sessions")
    monkeypatch.setattr(sessions_router, "sessions_table", table)
    monkeypatch.setattr(sessions_router, "get_live_sessions", dict)
    monkeypatch.setattr(sessions_router, "create_tmux_session", lambda *_a, **_k: None)
    monkeypatch.setattr(sessions_router, "_resolve_launch_command", lambda _provider: "claude")
    from lumbergh.routers import settings as settings_router

    monkeypatch.setattr(
        settings_router,
        "get_settings",
        lambda: {"worktree": {"base_dir": str(tmp_path / "worktrees")}},
    )
    return TestClient(app)


class TestEndpoint:
    def test_it_creates_a_worktree_session_on_a_fresh_branch(self, client, mock_git_repo):
        response = client.post(
            "/api/sessions/quick-worktree", json={"parent_repo": str(mock_git_repo)}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "quick-1"
        assert body["type"] == "worktree"
        assert body["worktreeBranch"] == "quick/1"
        assert body["worktreeParentRepo"] == str(mock_git_repo)

    def test_the_second_one_does_not_collide_with_the_first(self, client, mock_git_repo):
        first = client.post(
            "/api/sessions/quick-worktree", json={"parent_repo": str(mock_git_repo)}
        )
        second = client.post(
            "/api/sessions/quick-worktree", json={"parent_repo": str(mock_git_repo)}
        )

        assert first.json()["name"] == "quick-1"
        assert second.json()["name"] == "quick-2"
        assert second.json()["worktreeBranch"] == "quick/2"

    def test_a_directory_that_is_not_a_repo_is_a_plain_400(self, client, tmp_path):
        plain = tmp_path / "not-a-repo"
        plain.mkdir()

        response = client.post("/api/sessions/quick-worktree", json={"parent_repo": str(plain)})

        assert response.status_code == 400
        assert "git repository" in response.json()["detail"]
