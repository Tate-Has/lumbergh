"""
Regression test for send_to_session's text+Enter delivery.

A separate send-keys "Enter" call issued right after send-keys -l can race
with the target pane's own input handling and get dropped, leaving text
typed but unsubmitted (observed in practice: intermittent, not constant).
The fix bundles text+Enter into one atomic load-buffer/paste-buffer call
regardless of length, matching the large-text path's existing approach.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from lumbergh.main import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def _mock_copy_mode(mocker):
    # send_to_session always checks/exits copy-mode first; keep that a no-op
    # so tests only need to assert on the actual text-delivery calls.
    mocker.patch("lumbergh.main._exit_copy_mode", return_value=None)


def test_send_with_enter_uses_atomic_paste_buffer(client, mocker):
    run_tmux = mocker.patch("lumbergh.main._run_tmux", return_value="")

    response = client.post(
        "/api/session/my-session/send",
        json={"text": "short message", "send_enter": True},
    )

    assert response.status_code == 200
    calls = [c.args for c in run_tmux.call_args_list]
    # No standalone "Enter" key call — text+Enter is delivered as one buffer.
    assert ("send-keys", "-t", "my-session", "Enter") not in calls
    assert ("load-buffer", "-") in calls
    assert ("paste-buffer", "-t", "my-session", "-d", "-p") in calls

    load_buffer_call = next(c for c in run_tmux.call_args_list if c.args == ("load-buffer", "-"))
    assert load_buffer_call.kwargs["input_data"] == "short message\n"


def test_send_with_enter_uses_atomic_paste_buffer_for_long_text(client, mocker):
    run_tmux = mocker.patch("lumbergh.main._run_tmux", return_value="")
    long_text = "x" * 200

    response = client.post(
        "/api/session/my-session/send",
        json={"text": long_text, "send_enter": True},
    )

    assert response.status_code == 200
    load_buffer_call = next(c for c in run_tmux.call_args_list if c.args == ("load-buffer", "-"))
    assert load_buffer_call.kwargs["input_data"] == long_text + "\n"


def test_send_without_enter_uses_plain_send_keys(client, mocker):
    run_tmux = mocker.patch("lumbergh.main._run_tmux", return_value="")

    response = client.post(
        "/api/session/my-session/send",
        json={"text": "draft, not submitted", "send_enter": False},
    )

    assert response.status_code == 200
    calls = [c.args for c in run_tmux.call_args_list]
    assert ("send-keys", "-t", "my-session", "-l", "draft, not submitted") in calls
    # Nothing atomic-buffer related when we're not submitting.
    assert not any(c[0] == "load-buffer" for c in calls)
    assert not any(c[0] == "paste-buffer" for c in calls)
