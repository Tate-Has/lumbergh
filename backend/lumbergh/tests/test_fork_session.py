"""Forking a session: a new agent that starts from another one's conversation."""

import json
import re

import pytest

from lumbergh import session_identity
from lumbergh.fork import claude_session_id, fork_launch_command


def test_claude_code_forks_by_resuming_into_a_new_conversation():
    command = fork_launch_command("claude-code", "abc-123")

    assert command == "claude --resume abc-123 --fork-session"


def test_a_harness_that_cannot_fork_says_so():
    assert fork_launch_command("gemini-cli", "abc-123") is None
    assert fork_launch_command("codex", "abc-123") is None


def test_the_hook_identity_is_the_authority(tmp_path, monkeypatch):
    monkeypatch.setattr(session_identity, "store_dir", lambda: tmp_path)
    session_identity.write(
        "worker",
        session_identity.Identity(
            session_id="from-the-hook",
            transcript_path=str(tmp_path / "guessed-id.jsonl"),
            cwd=str(tmp_path),
            source="startup",
            written_at=1.0,
        ),
        store=tmp_path,
    )

    assert claude_session_id("worker", tmp_path, store=tmp_path) == "from-the-hook"


def test_falls_back_to_the_transcript_on_disk(tmp_path, monkeypatch):
    """No hook identity — the transcript's filename is the session id."""
    monkeypatch.setattr(session_identity, "store_dir", lambda: tmp_path / "empty")
    cwd = tmp_path / "repo"
    cwd.mkdir()
    encoded = re.sub(r"[^a-zA-Z0-9]", "-", str(cwd))
    project_dir = tmp_path / "home" / ".claude" / "projects" / encoded
    project_dir.mkdir(parents=True)
    (project_dir / "cafe-babe.jsonl").write_text(json.dumps({"type": "user"}) + "\n")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    assert claude_session_id("worker", cwd, store=tmp_path / "empty") == "cafe-babe"


def test_a_session_that_never_talked_has_nothing_to_fork(tmp_path):
    assert claude_session_id("worker", tmp_path / "nowhere", store=tmp_path / "empty") is None


@pytest.mark.parametrize("session_id", ["", None])
def test_no_id_means_no_command(session_id):
    assert fork_launch_command("claude-code", session_id) is None


class TestForkThroughTheApi:
    """The create endpoint, asked to fork."""

    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient

        from lumbergh.main import app
        from lumbergh.routers import sessions as sessions_router

        source = {"name": "worker", "workdir": str(tmp_path / "repo"), "agent_provider": None}
        monkeypatch.setattr(sessions_router, "get_stored_sessions", lambda: {"worker": source})
        monkeypatch.setattr(sessions_router, "get_live_sessions", dict)
        return TestClient(app)

    def test_forking_a_session_nobody_has_heard_of_is_a_404(self, client, tmp_path):
        response = client.post(
            "/api/sessions",
            json={"name": "fork1", "workdir": str(tmp_path), "fork_from": "ghost"},
        )

        assert response.status_code == 404
        assert "ghost" in response.json()["detail"]

    def test_forking_a_session_that_never_talked_explains_itself(self, client, tmp_path):
        (tmp_path / "repo").mkdir()

        response = client.post(
            "/api/sessions",
            json={"name": "fork2", "workdir": str(tmp_path), "fork_from": "worker"},
        )

        assert response.status_code == 400
        assert "no conversation to fork" in response.json()["detail"]

    def test_a_fork_launches_the_resumed_conversation(self, client, tmp_path, monkeypatch):
        from lumbergh.routers import sessions as sessions_router

        (tmp_path / "repo").mkdir()
        monkeypatch.setattr("lumbergh.fork.claude_session_id", lambda *_a, **_k: "conversation-42")
        launched = {}
        monkeypatch.setattr(
            sessions_router,
            "create_tmux_session",
            lambda name, _workdir, launch_command: launched.update(
                name=name, command=launch_command
            ),
        )

        response = client.post(
            "/api/sessions",
            json={"name": "fork3", "workdir": str(tmp_path), "fork_from": "worker"},
        )

        assert response.status_code == 200, response.text
        assert launched["command"] == "claude --resume conversation-42 --fork-session"
