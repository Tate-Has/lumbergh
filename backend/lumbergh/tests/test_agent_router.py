import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import lumbergh.routers.agent as agent
from lumbergh.idle_detector import SessionState


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(agent, "_live_names", lambda: ["s1"])
    monkeypatch.setattr(agent, "_meta", lambda _n: {"workdir": "/w", "agent_provider": "pi"})
    monkeypatch.setattr(agent.idle_monitor, "get_state", lambda _n: SessionState.BLOCKED)
    monkeypatch.setattr(agent.idle_monitor, "state_since_seconds", lambda _n: 12.0)
    monkeypatch.setattr(agent.session_attention, "is_unseen", lambda _n: True)
    app = FastAPI()
    app.include_router(agent.router)
    return TestClient(app)


def test_sessions_list(client):
    r = client.get("/api/agent/sessions").json()
    assert r["total"] == 1
    assert r["sessions"][0]["name"] == "s1"
    assert r["sessions"][0]["state"] == "blocked"


def test_state(client):
    r = client.get("/api/agent/sessions/s1/state").json()
    assert r["state"] == "blocked"
    assert r["unseen"] is True
    assert r["since"] == 12.0


def test_unknown_session_404(client):
    r = client.get("/api/agent/sessions/nope/state")
    assert r.status_code == 404
    assert "s1" in r.json()["detail"]["sessions"]


def test_wait_returns_immediately_when_already_in_state(client):
    r = client.get("/api/agent/sessions/s1/wait?until=blocked&timeout=1").json()
    assert r["reached"] is True
    assert r["state"] == "blocked"


def test_read_pane(client, monkeypatch):
    monkeypatch.setattr(agent, "capture_pane_text", lambda _n, lines=None: "hello\nworld")  # noqa: ARG005
    r = client.get("/api/agent/sessions/s1/read?source=pane").json()
    assert r["source"] == "pane"
    assert "hello" in r["pane"]


def test_prompt_sends(client, monkeypatch):
    sent = {}
    monkeypatch.setattr(agent, "send_text", lambda n, t: sent.update({n: t}) or True)
    r = client.post("/api/agent/sessions/s1/prompt", json={"text": "go"}).json()
    assert r["sent"] == "go"
    assert sent["s1"] == "go"
