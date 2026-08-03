"""A babysit whose session has no live agent must be loud, not quiet.

A babysit is a standing instruction the user walked away from. Once its target stops
resolving there is nothing to drive and nothing to fail — the loop simply does nothing,
which is indistinguishable from "all quiet" and is exactly how a whole night went by with
`port` unsupervised. So the condition is surfaced three ways: an attention overlay (which
reaches the user's browser even with Bill switched off), a fleet row Bill wakes on, and a
nudge that tells him what to say.
"""

import asyncio
from importlib import reload

import pytest

from lumbergh import bill_nudge, constants, fleet, session_attention


@pytest.fixture
def babysit(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMBERGH_DATA_DIR", str(tmp_path))
    reload(constants)
    from lumbergh import babysit as mod

    reload(mod)
    return mod


class TestUnresolved:
    def test_a_babysit_whose_agent_is_live_is_fine(self, babysit):
        babysit.start("port", None, "t")
        assert babysit.unresolved({"port", "aio"}) == []

    def test_a_babysit_with_no_live_target_is_reported(self, babysit):
        babysit.start("port", None, "t")
        assert babysit.unresolved({"aio"}) == ["port"]

    def test_a_babysit_on_a_window_target_resolves_on_that_target(self, babysit):
        babysit.start("batch:838", None, "t")
        assert babysit.unresolved({"batch:838"}) == []

    def test_nothing_babysat_is_never_a_problem(self, babysit):
        assert babysit.unresolved(set()) == []


@pytest.fixture
def empty_registry(tmp_path, monkeypatch):
    """A worktree registry with nothing in it, so the only rows are the ones under test."""
    from tinydb import TinyDB

    from lumbergh import worktrees

    db = TinyDB(tmp_path / "worktrees.json")
    monkeypatch.setattr(worktrees, "get_worktrees_db", lambda: db)
    yield db
    db.close()


@pytest.mark.usefixtures("empty_registry")
class TestFleetRow:
    def _rows(self, babysat: set[str]) -> list[dict]:
        return fleet.snapshot(
            {},
            state_of=lambda _n: "unknown",
            since_of=lambda _n: None,
            unseen_of=lambda _n: False,
            live_targets=set(),
            babysat_unresolved=babysat,
        )

    def test_an_unresolved_babysit_gets_a_row_bill_can_see(self):
        rows = self._rows({"port"})
        assert [(r["task"], r["state"], r["role"]) for r in rows] == [("port", "error", "overseer")]

    def test_the_row_needs_attention(self):
        """`error` is what makes `lb fleet --wait` return and the edge nudge fire."""
        assert fleet.needs_attention(self._rows({"port"})[0]) is True

    def test_the_row_says_what_is_wrong(self):
        assert "no live agent" in self._rows({"port"})[0]["problem"]

    def test_a_healthy_fleet_adds_no_rows(self):
        assert self._rows(set()) == []


class TestAttentionOverlay:
    def test_an_unresolved_babysit_marks_attention_for_the_user(self, babysit, monkeypatch):
        """The path that reaches the browser/phone. It must not depend on Bill: the user
        can have him switched off, which is when a silent babysit hurts most."""
        from lumbergh.idle_monitor import IdleMonitor

        session_attention.reset()
        babysit.start("port", None, "t")
        monkeypatch.setattr("lumbergh.babysit.babysat_sessions", lambda: {"port"})

        async def _noop_persist():
            return None

        monkeypatch.setattr("lumbergh.session_attention.persist", _noop_persist)
        asyncio.run(IdleMonitor()._check_babysit_health({"aio"}))

        assert session_attention.get("port") == "error"

    def test_a_resolving_babysit_marks_nothing(self, babysit, monkeypatch):
        from lumbergh.idle_monitor import IdleMonitor

        session_attention.reset()
        babysit.start("port", None, "t")
        monkeypatch.setattr("lumbergh.babysit.babysat_sessions", lambda: {"port"})

        async def _noop_persist():
            return None

        monkeypatch.setattr("lumbergh.session_attention.persist", _noop_persist)
        asyncio.run(IdleMonitor()._check_babysit_health({"port"}))

        assert session_attention.get("port") is None


class TestNudge:
    def _taps(self, monkeypatch, broken: set[str], nudged: set[str] | None = None) -> list[str]:
        from lumbergh.idle_detector import SessionState
        from lumbergh.idle_monitor import IdleMonitor

        monitor = IdleMonitor()
        monitor._babysit_broken = broken
        monitor._babysit_broken_nudged = nudged or set()
        monitor._record_state_change("bill", SessionState.IDLE)
        monkeypatch.setattr("lumbergh.routers.bill._fleet_rows", lambda _origin: [])

        taps: list[str] = []

        def tap(label: str) -> bool:
            taps.append(label)
            return True

        monkeypatch.setattr(bill_nudge, "broken_babysit_nudge", lambda s: tap(f"broken:{s}"))
        monkeypatch.setattr(bill_nudge, "nudge", lambda: tap("generic"))
        monkeypatch.setattr(bill_nudge, "heartbeat_nudge", lambda: tap("heartbeat"))

        async def run():
            await monitor._maybe_nudge_bill(asyncio.get_running_loop())

        asyncio.run(run())
        return taps

    def test_a_broken_babysit_taps_bill_about_that_fault(self, monkeypatch):
        assert self._taps(monkeypatch, {"port"}) == ["broken:port"]

    def test_bill_is_told_once_per_fault_not_every_sweep(self, monkeypatch):
        """The fault persists until the user acts, so re-taping every sweep would be noise."""
        assert self._taps(monkeypatch, {"port"}, nudged={"port"}) != ["broken:port"]

    def test_the_nudge_names_the_session_and_asks_him_to_tell_the_user(self):
        sent = {}
        assert bill_nudge.broken_babysit_nudge(
            "port", send=lambda name, text: sent.update(name=name, text=text) or True
        )
        assert "port" in sent["text"]
        assert "user" in sent["text"]
        assert sent["name"] == "bill:{start}"
