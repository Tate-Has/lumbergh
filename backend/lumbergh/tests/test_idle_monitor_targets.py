import asyncio

from lumbergh.idle_detector import SessionState
from lumbergh.idle_monitor import IdleMonitor


def test_two_agent_windows_get_independent_state(monkeypatch):
    monitor = IdleMonitor()
    discovered = ["port:fleet-643", "port:fleet-644"]

    monkeypatch.setattr("lumbergh.idle_monitor.discover_live_targets", lambda: discovered)

    async def fake_check(target):
        monitor._record_state_change(
            target,
            SessionState.IDLE if target.endswith("644") else SessionState.WORKING,
        )

    monkeypatch.setattr(monitor, "_check_session", fake_check)

    asyncio.run(monitor._check_all_sessions())

    assert monitor.get_state("port:fleet-644") == SessionState.IDLE
    assert monitor.get_state("port:fleet-643") == SessionState.WORKING


def test_check_all_sessions_caches_discovered_targets(monkeypatch):
    monitor = IdleMonitor()
    discovered = ["port:fleet-643", "port:fleet-644"]

    monkeypatch.setattr("lumbergh.idle_monitor.discover_live_targets", lambda: discovered)

    async def fake_check(_target):
        return None

    monkeypatch.setattr(monitor, "_check_session", fake_check)

    assert monitor.live_targets() == []

    asyncio.run(monitor._check_all_sessions())

    assert monitor.live_targets() == discovered
