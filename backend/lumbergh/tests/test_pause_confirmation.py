"""Tests for the extra-process confirmation on POST /api/sessions/{name}/pause.

Pausing kills every child of the pane shell, so it warns first when the pane
holds more than the agent. Some shell setups park a second, idle login shell
next to the agent in every pane, which made that warning unconditional.
"""

import pytest
from fastapi.testclient import TestClient
from tinydb import TinyDB


@pytest.fixture
def client():
    from lumbergh.main import app

    return TestClient(app)


@pytest.fixture
def pane(monkeypatch, tmp_path):
    """Wire a live session named `port` whose process tree the test declares."""
    from lumbergh.routers import sessions

    db = TinyDB(tmp_path / "sessions.json")
    monkeypatch.setattr(sessions, "sessions_table", db.table("sessions"))
    monkeypatch.setattr(sessions, "get_live_sessions", lambda: {"port": {}})
    monkeypatch.setattr(sessions, "_get_pane_pid", lambda _name: "100")
    monkeypatch.setattr(sessions, "_kill_pane_children", lambda _pid: None)

    def set_tree(tree: dict[str, list[dict]]):
        monkeypatch.setattr(sessions, "_list_pane_children", lambda pid: tree.get(str(pid), []))

    yield set_tree
    db.close()


AGENT = {"pid": 102, "command": "claude"}
IDLE_SHELL = {"pid": 101, "command": "-zsh"}
BUSY_SHELL = {"pid": 103, "command": "-zsh"}


def test_pauses_without_confirmation_when_only_the_agent_is_running(client, pane):
    pane({"100": [AGENT], "102": []})

    resp = client.post("/api/sessions/port/pause")

    assert resp.status_code == 200


def test_ignores_an_idle_shell_parked_beside_the_agent(client, pane):
    pane({"100": [IDLE_SHELL, AGENT], "101": [], "102": []})

    resp = client.post("/api/sessions/port/pause")

    assert resp.status_code == 200


def test_confirms_when_a_shell_is_running_something(client, pane):
    pane(
        {
            "100": [IDLE_SHELL, AGENT, BUSY_SHELL],
            "101": [],
            "102": [],
            "103": [{"pid": 104, "command": "npm"}],
        }
    )

    resp = client.post("/api/sessions/port/pause")

    assert resp.status_code == 409
    listed = resp.json()["detail"]["children"]
    assert listed == [AGENT, BUSY_SHELL]


def test_force_skips_the_confirmation(client, pane):
    pane({"100": [IDLE_SHELL, AGENT, BUSY_SHELL], "103": [{"pid": 104, "command": "npm"}]})

    resp = client.post("/api/sessions/port/pause?force=true")

    assert resp.status_code == 200
