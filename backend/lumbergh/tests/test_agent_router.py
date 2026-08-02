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


def _transcript(monkeypatch):
    """A transcript whose tool_result body embeds a stale `lb fleet` dump (the real
    failure: Bill read `working, 1334s` from an old fleet snapshot inside port's own
    transcript and concluded the finished overseer was still working)."""
    from lumbergh.activity.events import ConversationEvent

    events = [
        ConversationEvent(
            type="tool_result",
            id="t1",
            status="error",
            text="error: branch not found --- fleet --- port,overseer,port,working,1334s",
        ),
        ConversationEvent(type="agent_message", id="a1", text="Batch landed and deployed."),
    ]

    class FakeAdapter:
        def read_new(self):
            return events

    monkeypatch.setattr(agent, "resolve_adapter", lambda *_a, **_k: FakeAdapter())


def test_read_transcript_suppresses_tool_result_body_by_default(client, monkeypatch):
    _transcript(monkeypatch)
    r = client.get("/api/agent/sessions/s1/read?last=10").json()
    by_type = {e["type"]: e["text"] for e in r["events"]}
    assert "working" not in by_type["tool_result"]
    assert by_type["tool_result"] == "[error]"
    assert by_type["agent_message"] == "Batch landed and deployed."


def test_read_transcript_full_restores_tool_result_body(client, monkeypatch):
    _transcript(monkeypatch)
    r = client.get("/api/agent/sessions/s1/read?last=10&full=true").json()
    by_type = {e["type"]: e["text"] for e in r["events"]}
    assert "working" in by_type["tool_result"]


def test_prompt_sends(client, monkeypatch):
    sent = {}
    monkeypatch.setattr(agent, "send_text", lambda n, t: sent.update({n: t}) or True)
    r = client.post("/api/agent/sessions/s1/prompt", json={"text": "go"}).json()
    assert r["sent"] == "go"
    assert sent["s1"] == "go"


def test_a_prompt_from_bill_puts_the_session_under_his_watch(client, monkeypatch, tmp_path):
    """Bill prompting a session *is* the delegate shape, and it is the only signal the
    server gets that an overseer became his to supervise."""
    from lumbergh import babysit, bill_watch

    monkeypatch.setattr(bill_watch, "WATCH_PATH", tmp_path / "bill_watch.json")
    monkeypatch.setattr(babysit, "BABYSITS_PATH", tmp_path / "babysits.json")
    monkeypatch.setattr(agent, "send_text", lambda n, t: True)  # noqa: ARG005
    client.post("/api/agent/sessions/s1/prompt", json={"text": "go", "as_session": "bill"})
    assert bill_watch.watched() == {"s1"}


def test_a_prompt_from_anyone_else_watches_nothing(client, monkeypatch, tmp_path):
    # The user, or an overseer talking to its own worker, hands Bill nothing.
    from lumbergh import babysit, bill_watch

    monkeypatch.setattr(bill_watch, "WATCH_PATH", tmp_path / "bill_watch.json")
    monkeypatch.setattr(babysit, "BABYSITS_PATH", tmp_path / "babysits.json")
    monkeypatch.setattr(agent, "send_text", lambda n, t: True)  # noqa: ARG005
    client.post("/api/agent/sessions/s1/prompt", json={"text": "go", "as_session": "port"})
    client.post("/api/agent/sessions/s1/prompt", json={"text": "go"})
    assert bill_watch.watched() == set()


def test_wait_output_matches_existing_snapshot(client, monkeypatch):
    monkeypatch.setattr(agent, "capture_pane_text", lambda _n, lines=None: "BUILD DONE\n$ ")  # noqa: ARG005
    r = client.get("/api/agent/sessions/s1/wait-output?match=BUILD%20DONE&timeout=1").json()
    assert r["matched"] is True
    assert r["waited"] == 0.0


def test_wait_output_regex(client, monkeypatch):
    monkeypatch.setattr(agent, "capture_pane_text", lambda _n, lines=None: "exit code: 0")  # noqa: ARG005
    r = client.get("/api/agent/sessions/s1/wait-output?regex=exit%20code:%20%5Cd&timeout=1").json()
    assert r["matched"] is True


def test_wait_output_timeout(client, monkeypatch):
    monkeypatch.setattr(agent, "capture_pane_text", lambda _n, lines=None: "nothing here")  # noqa: ARG005
    r = client.get("/api/agent/sessions/s1/wait-output?match=absent&timeout=0").json()
    assert r["matched"] is False


def test_wait_output_requires_match_or_regex(client):
    r = client.get("/api/agent/sessions/s1/wait-output?timeout=1")
    assert r.status_code == 400


def test_wait_output_invalid_regex(client):
    r = client.get("/api/agent/sessions/s1/wait-output?regex=%5B&timeout=1")
    assert r.status_code == 400


def test_output_matches_helper():
    import re

    assert agent._output_matches("hello world", "world", None) is True
    assert agent._output_matches("hello world", "absent", None) is False
    assert agent._output_matches("code 42", None, re.compile(r"code \d+")) is True
    assert agent._output_matches("no digits", None, re.compile(r"\d+")) is False
    assert agent._output_matches("anything", None, None) is False
