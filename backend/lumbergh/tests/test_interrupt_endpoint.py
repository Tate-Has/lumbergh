"""Tests for /session/{name}/interrupt — stopping the agent without the terminal socket.

The Esc button used to write a raw 0x1b down the terminal WebSocket, so a phone
whose socket was reconnecting (rotation, PWA resume, network flip) had no way to
stop a running agent. Interrupting is a control action; it goes over HTTP.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from lumbergh.main import app

    return TestClient(app)


@pytest.fixture
def tmux_calls(monkeypatch):
    calls = []

    async def fake_run_tmux(*args, input_data=None, timeout=5.0):  # noqa: ARG001
        calls.append(args)
        return ""

    import lumbergh.main as main

    monkeypatch.setattr(main, "_run_tmux", fake_run_tmux)
    return calls


class TestInterrupt:
    def test_sends_a_real_escape_key_to_the_session(self, client, tmux_calls):
        resp = client.post("/api/session/mysession/interrupt")

        assert resp.status_code == 200
        assert ("send-keys", "-t", "mysession", "Escape") in tmux_calls

    def test_leaves_copy_mode_first(self, client, monkeypatch):
        """A pane scrolled into copy-mode eats the Escape instead of the agent."""
        calls = []

        async def fake_run_tmux(*args, input_data=None, timeout=5.0):  # noqa: ARG001
            calls.append(args)
            if args[:1] == ("display-message",):
                return "copy-mode"
            return ""

        import lumbergh.main as main

        monkeypatch.setattr(main, "_run_tmux", fake_run_tmux)

        resp = client.post("/api/session/mysession/interrupt")

        assert resp.status_code == 200
        sent = [c for c in calls if c[:1] == ("send-keys",)]
        assert sent == [
            ("send-keys", "-t", "mysession", "q"),
            ("send-keys", "-t", "mysession", "Escape"),
        ]
