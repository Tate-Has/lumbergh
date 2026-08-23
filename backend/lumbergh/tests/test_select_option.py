"""Tests for /session/{name}/select-option — answering an on-screen picker."""

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


def _keys(calls):
    return next(c for c in calls if c[:1] == ("send-keys",) and "Enter" in c)


class TestSelectOption:
    def test_first_option_just_confirms_the_highlight(self, client, tmux_calls):
        resp = client.post("/api/session/mysession/select-option", json={"index": 0})

        assert resp.status_code == 200
        assert _keys(tmux_calls) == ("send-keys", "-t", "mysession", "Enter")

    def test_later_option_walks_the_highlight_down_first(self, client, tmux_calls):
        """Arrow keys, not digit shortcuts: a picker that ignores an unsupported
        digit would take the following Enter as 'confirm the highlighted row' and
        silently answer the wrong thing."""
        resp = client.post("/api/session/mysession/select-option", json={"index": 2})

        assert resp.status_code == 200
        assert _keys(tmux_calls) == ("send-keys", "-t", "mysession", "Down", "Down", "Enter")

    @pytest.mark.parametrize("index", [-1, 999])
    def test_rejects_an_index_no_picker_could_have(self, client, tmux_calls, index):
        resp = client.post("/api/session/mysession/select-option", json={"index": index})

        assert resp.status_code == 400
        assert not tmux_calls
