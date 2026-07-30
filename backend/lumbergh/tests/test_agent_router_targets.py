from fastapi.testclient import TestClient

from lumbergh.idle_detector import SessionState
from lumbergh.main import app


def test_sessions_endpoint_lists_each_agent_window(monkeypatch):
    targets = ["port:fleet-643", "port:fleet-644"]
    monkeypatch.setattr("lumbergh.routers.agent.idle_monitor.live_targets", lambda: targets)
    monkeypatch.setattr(
        "lumbergh.routers.agent.idle_monitor.get_state",
        lambda _t: SessionState.IDLE,
    )
    client = TestClient(app)
    resp = client.get("/api/agent/sessions")
    names = [s["name"] for s in resp.json()["sessions"]]
    assert names == ["port:fleet-643", "port:fleet-644"]


def test_state_endpoint_addresses_a_window(monkeypatch):
    monkeypatch.setattr(
        "lumbergh.routers.agent.idle_monitor.live_targets", lambda: ["port:fleet-644"]
    )
    monkeypatch.setattr(
        "lumbergh.routers.agent.idle_monitor.get_state",
        lambda _t: SessionState.WORKING,
    )
    client = TestClient(app)
    resp = client.get("/api/agent/sessions/port:fleet-644/state")
    assert resp.status_code == 200
    assert resp.json()["session"] == "port:fleet-644"
    assert resp.json()["state"] == "working"


def test_router_reads_cache_without_calling_discovery(monkeypatch):
    """Proves the request path reads idle_monitor's cache, not a live tmux sweep.

    discover_live_targets is deliberately left unpatched (and would raise if invoked
    here, since there's no real tmux server) so a passing test demonstrates the
    router never calls it directly.
    """
    import lumbergh.idle_monitor as idle_monitor_module

    def _boom():
        raise AssertionError("router must not call discover_live_targets directly")

    monkeypatch.setattr(idle_monitor_module, "discover_live_targets", _boom)
    monkeypatch.setattr(
        "lumbergh.routers.agent.idle_monitor.live_targets", lambda: ["port:cache-only"]
    )
    monkeypatch.setattr(
        "lumbergh.routers.agent.idle_monitor.get_state",
        lambda _t: SessionState.IDLE,
    )
    client = TestClient(app)

    resp = client.get("/api/agent/sessions")
    names = [s["name"] for s in resp.json()["sessions"]]
    assert names == ["port:cache-only"]

    resp = client.get("/api/agent/sessions/port:cache-only/state")
    assert resp.status_code == 200
    assert resp.json()["session"] == "port:cache-only"
