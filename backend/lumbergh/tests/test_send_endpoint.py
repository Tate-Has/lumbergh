"""Tests for the /session/{name}/send tmux delivery paths."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from lumbergh.main import app

    return TestClient(app)


@pytest.fixture
def tmux_calls(monkeypatch):
    """Record tmux invocations and stub them out so no real tmux runs."""
    calls = []

    async def fake_run_tmux(*args, input_data=None, timeout=5.0):  # noqa: ARG001
        calls.append({"args": args, "input_data": input_data})
        if args[:1] == ("display-message",):
            return ""  # pane is not in copy-mode
        return ""

    import lumbergh.main as main

    monkeypatch.setattr(main, "_run_tmux", fake_run_tmux)
    return calls


def _paste_and_key_calls(calls):
    paste = next((c for c in calls if c["args"][:1] == ("paste-buffer",)), None)
    load = next((c for c in calls if c["args"][:1] == ("load-buffer",)), None)
    enter_key = any(c["args"][:1] == ("send-keys",) and "Enter" in c["args"] for c in calls)
    return load, paste, enter_key


class TestSendLongText:
    def test_enter_is_a_separate_key_not_buried_in_paste(self, client, tmux_calls):
        """Long text must submit: the Enter arrives as a real key press outside the
        bracketed paste, otherwise Claude Code treats a trailing newline in the paste
        as a literal newline and never submits."""
        long_text = "x" * 200
        resp = client.post(
            "/api/session/mysession/send",
            json={"text": long_text, "send_enter": True},
        )
        assert resp.status_code == 200

        load, paste, enter_key = _paste_and_key_calls(tmux_calls)
        assert paste is not None, "long text should use paste-buffer"

        # The trailing newline must NOT be embedded in the pasted buffer.
        assert load is not None
        assert not load["input_data"].endswith("\n"), (
            "newline embedded in bracketed paste is swallowed as a literal newline"
        )

        # Enter must be delivered as its own send-keys key press.
        assert enter_key, "Enter must be sent as a separate key to actually submit"


class TestSendShortText:
    def test_short_text_sends_separate_enter(self, client, tmux_calls):
        resp = client.post(
            "/api/session/mysession/send",
            json={"text": "hello", "send_enter": True},
        )
        assert resp.status_code == 200
        _, _, enter_key = _paste_and_key_calls(tmux_calls)
        assert enter_key, "Enter must be sent as a separate key to actually submit"
