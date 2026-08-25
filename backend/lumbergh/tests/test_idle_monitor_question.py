import asyncio

import lumbergh.idle_monitor as im
from lumbergh.idle_detector import SessionState
from lumbergh.question_detector import Verdict


def _monitor(monkeypatch, *, enabled=True):
    monitor = im.IdleMonitor()
    monkeypatch.setattr(monitor, "_question_detection_enabled", lambda: enabled)
    return monitor


async def test_schedules_once_past_delay_and_not_before(monkeypatch):
    monitor = _monitor(monkeypatch)
    calls = []

    async def _spy(name):
        calls.append(name)

    monkeypatch.setattr(monitor, "_run_question_detection", _spy)

    monkeypatch.setattr(monitor, "state_since_seconds", lambda _n: 1.0)
    monitor._update_question_detection("s", SessionState.IDLE)
    await asyncio.sleep(0)
    assert calls == []

    monkeypatch.setattr(
        monitor, "state_since_seconds", lambda _n: monitor.QUESTION_CHECK_DELAY_SECONDS + 1
    )
    monitor._update_question_detection("s", SessionState.IDLE)
    await asyncio.sleep(0)
    assert calls == ["s"]

    # Same idle episode: not re-scheduled.
    monitor._update_question_detection("s", SessionState.IDLE)
    await asyncio.sleep(0)
    assert calls == ["s"]


async def test_disabled_never_schedules(monkeypatch):
    monitor = _monitor(monkeypatch, enabled=False)
    calls = []

    async def _spy(name):
        calls.append(name)

    monkeypatch.setattr(monitor, "_run_question_detection", _spy)
    monkeypatch.setattr(monitor, "state_since_seconds", lambda _n: 999)
    monitor._update_question_detection("s", SessionState.IDLE)
    await asyncio.sleep(0)
    assert calls == []


async def test_non_idle_does_not_schedule(monkeypatch):
    monitor = _monitor(monkeypatch)
    calls = []

    async def _spy(name):
        calls.append(name)

    monkeypatch.setattr(monitor, "_run_question_detection", _spy)
    monkeypatch.setattr(monitor, "state_since_seconds", lambda _n: 999)
    monitor._update_question_detection("s", SessionState.WORKING)
    await asyncio.sleep(0)
    assert calls == []


async def test_leaving_idle_clears_flag_and_resets_episode(monkeypatch):
    monitor = _monitor(monkeypatch)
    monitor._needs_answer["s"] = "pick a db"
    monitor._question_checked.add("s")
    monitor._update_question_detection("s", SessionState.WORKING)
    assert not monitor.needs_answer("s")
    assert "s" not in monitor._question_checked


async def test_run_sets_flag_when_waiting(monkeypatch):
    monitor = im.IdleMonitor()
    monitor._states["s"] = SessionState.IDLE
    monitor._question_inflight.add("s")
    monkeypatch.setattr(monitor, "_question_provider", object)
    monkeypatch.setattr(im, "capture_pane_text", lambda _name: "Which database should I use?")

    async def _detect(_text, _provider, **_k):
        return Verdict(True, "choose a database")

    monkeypatch.setattr(im.question_detector, "detect", _detect)

    await monitor._run_question_detection("s")
    assert monitor.needs_answer("s")
    assert monitor.needs_answer_reason("s") == "choose a database"
    assert "s" not in monitor._question_inflight


async def test_run_no_flag_when_not_waiting(monkeypatch):
    monitor = im.IdleMonitor()
    monitor._states["s"] = SessionState.IDLE
    monkeypatch.setattr(monitor, "_question_provider", object)
    monkeypatch.setattr(im, "capture_pane_text", lambda _name: "done, all tests pass")

    async def _detect(_text, _provider, **_k):
        return Verdict(False)

    monkeypatch.setattr(im.question_detector, "detect", _detect)

    await monitor._run_question_detection("s")
    assert not monitor.needs_answer("s")


async def test_run_aborts_when_no_longer_idle(monkeypatch):
    monitor = im.IdleMonitor()
    monitor._states["s"] = SessionState.WORKING

    called = []
    monkeypatch.setattr(
        monitor, "_question_provider", lambda: called.append("provider") or object()
    )

    await monitor._run_question_detection("s")
    assert called == []
    assert not monitor.needs_answer("s")


async def test_dead_session_clears_question_state(monkeypatch):
    monitor = im.IdleMonitor()
    monitor._fingerprints["dead"] = "fp"
    monitor._needs_answer["dead"] = "reason"
    monitor._question_checked.add("dead")
    monitor._question_inflight.add("dead")

    # discover_target_refs, not discover_live_targets: patching the name the poll
    # no longer calls let this test run a real poll against the developer's own
    # tmux server and repaint every live session green.
    monkeypatch.setattr(im, "discover_target_refs", dict)
    monkeypatch.setattr(im, "_live_session_names", list)
    monkeypatch.setattr(im.session_identity, "prune", lambda _s: None)

    await monitor._check_all_sessions()

    assert not monitor.needs_answer("dead")
    assert "dead" not in monitor._question_checked
    assert "dead" not in monitor._question_inflight
