"""What the monitor tells you when it goes wrong.

A silent state machine is the expensive kind: chasing a stuck session once cost
an afternoon because per-poll reasoning went nowhere and a failing check was
swallowed whole by `gather(return_exceptions=True)`.
"""

import asyncio
import logging

import pytest

import lumbergh.idle_monitor as im
from lumbergh.idle_detector import SessionState


class TestFailingChecksAreReported:
    async def _run(self, monitor, monkeypatch, checks):
        async def fake_check(target):
            return await checks[target]()

        monkeypatch.setattr(monitor, "_check_session", fake_check)
        monkeypatch.setattr(
            im, "discover_target_refs", lambda: {t: f"@{i}" for i, t in enumerate(checks)}
        )
        monkeypatch.setattr(im, "_live_session_names", lambda: list(checks))
        monkeypatch.setattr(monitor, "_reap_dead_targets", lambda *_a: _noop())
        monkeypatch.setattr(monitor, "_check_babysit_health", lambda *_a: _noop())
        monkeypatch.setattr(monitor, "_maybe_nudge_bill", lambda *_a: _noop())
        monkeypatch.setattr(im.session_identity, "prune", lambda *_a: None)
        await monitor._check_all_sessions()

    async def test_one_broken_session_does_not_stop_the_others(self, monkeypatch):
        seen = []

        async def boom():
            raise RuntimeError("tmux went away")

        async def fine():
            seen.append("ok")

        await self._run(im.IdleMonitor(), monkeypatch, {"broken": boom, "healthy": fine})

        assert seen == ["ok"]

    async def test_the_failure_is_logged_with_the_session_that_caused_it(self, monkeypatch, caplog):
        async def boom():
            raise RuntimeError("tmux went away")

        with caplog.at_level(logging.WARNING, logger="lumbergh.idle_monitor"):
            await self._run(im.IdleMonitor(), monkeypatch, {"broken": boom})

        assert "broken" in caplog.text
        assert "tmux went away" in caplog.text

    async def test_cancellation_is_not_mistaken_for_a_failure(self, monkeypatch):
        async def cancelled():
            raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            await self._run(im.IdleMonitor(), monkeypatch, {"stopping": cancelled})


class TestPerPollTrace:
    """The trace that finally explained a stuck session: what was seen, and why."""

    async def _poll(self, monkeypatch, monitor):
        async def stub_capture(_name):
            return ["frame"]

        monkeypatch.setattr(monitor, "_burst_capture", stub_capture)
        monkeypatch.setattr(monitor, "_persist_state", lambda *_a, **_k: _noop())
        monkeypatch.setattr(monitor, "_classify_burst", lambda *_a, **_k: SessionState.IDLE)
        monkeypatch.setattr(im, "capture_pane_title", lambda _n: "")
        monkeypatch.setattr(im, "capture_pane_geometry", lambda _n: "107x60")
        monkeypatch.setattr(im.session_attention, "persist", _noop)
        monkeypatch.setattr(im.session_attention, "mark_attention", lambda *_a: None)
        monkeypatch.setattr(im.session_attention, "clear_unseen", lambda _n: None)
        await monitor._check_session("s")

    async def test_debug_shows_what_the_poll_saw(self, monkeypatch, caplog):
        with caplog.at_level(logging.DEBUG, logger="lumbergh.idle_monitor"):
            await self._poll(monkeypatch, im.IdleMonitor())

        assert "107x60" in caplog.text, "geometry — a reshape is why content churns"
        assert "idle" in caplog.text
        assert "quiet=" in caplog.text, "how long the pane has been still"

    async def test_it_stays_quiet_at_the_default_level(self, monkeypatch, caplog):
        with caplog.at_level(logging.INFO, logger="lumbergh.idle_monitor"):
            await self._poll(monkeypatch, im.IdleMonitor())

        assert "quiet=" not in caplog.text


async def _noop(*_a, **_k):
    return None
