import lumbergh.idle_monitor as im


def test_state_since_tracked_on_change(monkeypatch):
    monitor = im.IdleMonitor()
    t = [1000.0]
    monkeypatch.setattr(im.time, "time", lambda: t[0])
    monitor._record_state_change("s", im.SessionState.WORKING)
    t[0] = 1005.0
    assert 4.9 < monitor.state_since_seconds("s") < 5.1
    assert monitor.state_since_seconds("unknown") is None
