import lumbergh.idle_monitor as im
from lumbergh.idle_detector import SessionState


async def _stub_capture(_name):
    return ["frame"]


async def _noop_persist_state(_name, _state):
    return None


async def _noop_persist():
    return None


async def _run_transition(monitor, name, state, monkeypatch):
    monkeypatch.setattr(monitor, "_burst_capture", _stub_capture)
    monkeypatch.setattr(monitor, "_classify_burst", lambda *_a, **_k: state)
    monkeypatch.setattr(monitor, "_persist_state", _noop_persist_state)
    monkeypatch.setattr(im, "capture_pane_title", lambda _name: "")
    monkeypatch.setattr(im.session_attention, "persist", _noop_persist)
    await monitor._check_session(name)


async def test_transition_to_idle_marks_attention(monkeypatch):
    monitor = im.IdleMonitor()
    marked = {}
    monkeypatch.setattr(im.session_attention, "mark_attention", lambda n, s: marked.update({n: s}))
    monkeypatch.setattr(im.session_attention, "clear_unseen", lambda _n: None)
    await _run_transition(monitor, "s", SessionState.IDLE, monkeypatch)
    assert marked == {"s": "idle"}


async def test_transition_to_working_clears_attention(monkeypatch):
    monitor = im.IdleMonitor()
    cleared = []
    monkeypatch.setattr(im.session_attention, "mark_attention", lambda _n, _s: None)
    monkeypatch.setattr(im.session_attention, "clear_unseen", lambda n: cleared.append(n))
    await _run_transition(monitor, "s", SessionState.WORKING, monkeypatch)
    assert cleared == ["s"]
