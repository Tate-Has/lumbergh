"""A reshaped pane is not a working agent.

Attaching a viewer resizes the tmux window, the agent redraws itself at the new
width, and every content-based check sees that as activity. The session then
"finishes" once the repaint settles — after the viewer has gone — and gets
flagged as done while you were away. It never did anything.
"""

import lumbergh.idle_monitor as im
from lumbergh.idle_detector import SessionState


def _monitor_seeing(monkeypatch, geometry, *, frames=("frame",)):
    monitor = im.IdleMonitor()

    async def stub_capture(_name):
        return list(frames)

    monkeypatch.setattr(monitor, "_burst_capture", stub_capture)
    monkeypatch.setattr(monitor, "_persist_state", lambda *_a, **_k: _noop())
    monkeypatch.setattr(im, "capture_pane_title", lambda _name: "")
    monkeypatch.setattr(im, "capture_pane_geometry", lambda _name: geometry)
    monkeypatch.setattr(im.session_attention, "persist", _noop)
    return monitor


async def _noop(*_a, **_k):
    return None


async def test_a_resize_does_not_report_the_agent_as_working(monkeypatch):
    """The classifier will call it working; the reshape says why, so we do not."""
    monitor = _monitor_seeing(monkeypatch, "107x60")
    monkeypatch.setattr(monitor, "_classify_burst", lambda *_a, **_k: SessionState.IDLE)
    monkeypatch.setattr(im.session_attention, "mark_attention", lambda *_a: None)
    monkeypatch.setattr(im.session_attention, "clear_unseen", lambda _n: None)
    await monitor._check_session("s")
    assert monitor.get_state("s") is SessionState.IDLE

    # The viewer attaches: narrower pane, agent redraws, content churns.
    monkeypatch.setattr(im, "capture_pane_geometry", lambda _name: "80x60")
    monkeypatch.setattr(monitor, "_classify_burst", lambda *_a, **_k: SessionState.WORKING)
    await monitor._check_session("s")

    assert monitor.get_state("s") is SessionState.IDLE, "a repaint is not work"


async def test_a_resize_does_not_flag_done_while_you_were_away(monkeypatch):
    marked = {}
    monitor = _monitor_seeing(monkeypatch, "107x60")
    monkeypatch.setattr(im.session_attention, "mark_attention", lambda n, s: marked.update({n: s}))
    monkeypatch.setattr(im.session_attention, "clear_unseen", lambda _n: None)
    monkeypatch.setattr(monitor, "_classify_burst", lambda *_a, **_k: SessionState.WORKING)
    await monitor._check_session("s")
    marked.clear()

    # Resize, then the repaint settles into "idle" after the viewer has left.
    monkeypatch.setattr(im, "capture_pane_geometry", lambda _name: "80x60")
    await monitor._check_session("s")
    monkeypatch.setattr(monitor, "_classify_burst", lambda *_a, **_k: SessionState.IDLE)
    await monitor._check_session("s")

    assert marked == {}, "nothing happened, so nothing to come back to"


async def test_work_is_still_noticed_once_the_pane_has_settled(monkeypatch):
    """The reshape buys quiet for a moment, not forever."""
    clock = [1000.0]
    monkeypatch.setattr(im.time, "time", lambda: clock[0])
    marked = {}
    monitor = _monitor_seeing(monkeypatch, "107x60")
    monkeypatch.setattr(im.session_attention, "mark_attention", lambda n, s: marked.update({n: s}))
    monkeypatch.setattr(im.session_attention, "clear_unseen", lambda _n: None)
    monkeypatch.setattr(monitor, "_classify_burst", lambda *_a, **_k: SessionState.WORKING)
    await monitor._check_session("s")

    monkeypatch.setattr(im, "capture_pane_geometry", lambda _name: "80x60")
    await monitor._check_session("s")  # the reshape pass

    clock[0] += im.IdleMonitor.RESHAPE_SETTLE_SECONDS + 1
    await monitor._check_session("s")  # genuinely working again
    monkeypatch.setattr(monitor, "_classify_burst", lambda *_a, **_k: SessionState.IDLE)
    await monitor._check_session("s")

    assert marked == {"s": "idle"}


async def test_a_session_that_stops_while_settling_still_reads_as_idle(monkeypatch):
    """Only the flag is withheld — the state itself must stay honest."""
    monitor = _monitor_seeing(monkeypatch, "107x60")
    monkeypatch.setattr(im.session_attention, "mark_attention", lambda *_a: None)
    monkeypatch.setattr(im.session_attention, "clear_unseen", lambda _n: None)
    monkeypatch.setattr(monitor, "_classify_burst", lambda *_a, **_k: SessionState.WORKING)
    await monitor._check_session("s")

    monkeypatch.setattr(im, "capture_pane_geometry", lambda _name: "80x60")
    await monitor._check_session("s")
    monkeypatch.setattr(monitor, "_classify_burst", lambda *_a, **_k: SessionState.IDLE)
    await monitor._check_session("s")

    assert monitor.get_state("s") is SessionState.IDLE


async def test_an_unknown_geometry_never_looks_like_a_reshape(monkeypatch):
    """tmux failing to answer must not silently freeze state updates."""
    marked = {}
    monitor = _monitor_seeing(monkeypatch, "")
    monkeypatch.setattr(im.session_attention, "mark_attention", lambda n, s: marked.update({n: s}))
    monkeypatch.setattr(im.session_attention, "clear_unseen", lambda _n: None)
    monkeypatch.setattr(monitor, "_classify_burst", lambda *_a, **_k: SessionState.WORKING)
    await monitor._check_session("s")
    monkeypatch.setattr(monitor, "_classify_burst", lambda *_a, **_k: SessionState.IDLE)
    await monitor._check_session("s")

    assert marked == {"s": "idle"}
