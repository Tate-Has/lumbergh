from lumbergh.idle_detector import SessionState
from lumbergh.idle_monitor import IdleMonitor


def test_classify_burst_forwards_osc_title(monkeypatch):
    captured = {}

    def fake_classify(_content, osc_title=""):
        captured["osc_title"] = osc_title
        return

    monkeypatch.setattr("lumbergh.idle_monitor.classify_overrides", fake_classify)
    monitor = IdleMonitor()
    monitor._classify_burst("sess", ["stable frame"], now=1000.0, osc_title="✻ waiting")
    assert captured["osc_title"] == "✻ waiting"


def test_classify_burst_default_title_is_empty(monkeypatch):
    captured = {}

    def fake_classify(_content, osc_title=""):
        captured["osc_title"] = osc_title
        return SessionState.BLOCKED

    monkeypatch.setattr("lumbergh.idle_monitor.classify_overrides", fake_classify)
    monitor = IdleMonitor()
    result = monitor._classify_burst("sess", ["frame"], now=1000.0)
    assert result == SessionState.BLOCKED
    assert captured["osc_title"] == ""
