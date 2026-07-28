from types import SimpleNamespace

import lumbergh.session_manager as sm


class _WS:
    async def send_json(self, *_a, **_k):
        return None


async def _noop(*_a, **_k):
    return None


async def test_register_marks_seen(monkeypatch):
    calls = []
    monkeypatch.setattr(sm.session_attention, "set_viewing", lambda n, v: calls.append((n, v)))
    monkeypatch.setattr(sm.session_attention, "persist", _noop)

    manager = sm.SessionManager()
    monkeypatch.setattr(manager, "_send_initial_repaint", _noop)
    managed = SimpleNamespace(clients=set(), pane_state=None)
    manager._sessions["attn-test"] = managed

    await manager.register_client("attn-test", _WS())
    assert ("attn-test", True) in calls


async def test_last_unregister_marks_unseen_eligible(monkeypatch):
    calls = []
    monkeypatch.setattr(sm.session_attention, "set_viewing", lambda n, v: calls.append((n, v)))
    monkeypatch.setattr(sm.session_attention, "persist", _noop)

    manager = sm.SessionManager()
    ws = _WS()
    managed = SimpleNamespace(
        clients={ws},
        client_sizes={},
        active_clients=set(),
        activity_seq={},
        read_task=None,
        pane_state_task=None,
        pty=SimpleNamespace(close=lambda: None),
    )
    manager._sessions["attn-unreg"] = managed

    await manager.unregister_client("attn-unreg", ws)
    assert ("attn-unreg", False) in calls
