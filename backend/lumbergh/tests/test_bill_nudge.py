import asyncio
import time

import pytest

from lumbergh import bill_nudge
from lumbergh.idle_monitor import IdleMonitor


def _overseer(state, unseen=False, task="port"):
    return {"role": "overseer", "task": task, "state": state, "unseen": unseen}


def _worker(state, unseen=False, task="w", parent="port"):
    return {"role": "worker", "task": task, "parent": parent, "state": state, "unseen": unseen}


@pytest.mark.parametrize(
    ("bill_state", "rows", "expected"),
    [
        # Bill is re-armed only when an overseer needs him.
        ("idle", [_overseer("blocked")], True),
        ("idle", [_overseer("idle", unseen=True)], True),
        ("idle", [_overseer("working")], False),  # a busy overseer is not Bill's cue
        ("idle", [_overseer("idle", unseen=False)], False),
        ("idle", [_worker("blocked", unseen=True)], False),  # workers never nudge Bill
        ("idle", [], False),
        ("working", [_overseer("blocked")], False),  # Bill isn't idle
        ("blocked", [_overseer("blocked")], False),
    ],
)
def test_should_nudge(bill_state, rows, expected):
    from lumbergh.routers.bill import _overseer_acked

    _overseer_acked.clear()
    assert bill_nudge.should_nudge(bill_state, rows) is expected


def test_nudge_sends_one_short_line():
    sent = {}
    assert bill_nudge.nudge(send=lambda name, text: sent.update(name=name, text=text) or True)
    assert sent["name"] == "bill"
    assert "lb fleet" in sent["text"]
    assert "\n" not in sent["text"]


def test_heartbeat_nudge_sends_one_short_line():
    sent = {}
    assert bill_nudge.heartbeat_nudge(
        send=lambda name, text: sent.update(name=name, text=text) or True
    )
    assert sent["name"] == "bill"
    assert "lb fleet" in sent["text"]
    assert "\n" not in sent["text"]


def test_heartbeat_and_edge_messages_differ():
    edge, beat = {}, {}
    bill_nudge.nudge(send=lambda _n, text: edge.update(text=text) or True)
    bill_nudge.heartbeat_nudge(send=lambda _n, text: beat.update(text=text) or True)
    assert edge["text"] != beat["text"]


class _StubMonitor(IdleMonitor):
    """An IdleMonitor whose Bill-state lookup is replaced with a fixed fake."""

    def __init__(self, state: str):
        super().__init__()
        self._stub_state = state

    def get_state(self, _session_name):
        from lumbergh.idle_detector import SessionState

        return SessionState(self._stub_state)


@pytest.fixture
def sent_nudges(monkeypatch):
    sent = []
    monkeypatch.setattr(bill_nudge, "nudge", lambda **_kwargs: sent.append(1) or True)
    return sent


@pytest.fixture
def sent_heartbeats(monkeypatch):
    sent = []
    monkeypatch.setattr(bill_nudge, "heartbeat_nudge", lambda **_kwargs: sent.append(1) or True)
    return sent


@pytest.fixture
def stub_fleet_rows(monkeypatch):
    state = {"rows": [], "calls": 0}

    def _fake_fleet_rows(_origin, **_kwargs):
        state["calls"] += 1
        return state["rows"]

    monkeypatch.setattr("lumbergh.routers.bill._fleet_rows", _fake_fleet_rows)
    return state


def _idle_for(monitor: "_StubMonitor", seconds: float) -> None:
    """Backdate Bill's idle-since clock so state_since_seconds reads ``seconds``."""
    monitor._state_since[bill_nudge.BILL_SESSION] = time.time() - seconds


def _bypass_sweep_throttle(monitor: _StubMonitor) -> None:
    """Force the next call to re-run the (stubbed, so otherwise-cheap-in-test) sweep.

    Isolates the latch as the only thing that can still suppress a repeat send —
    without this, the throttle alone would explain a single send across repeated
    calls, making the latch assertions decorative.
    """
    monitor._bill_nudge_checked_at = 0.0


async def test_maybe_nudge_bill_fires_once_per_idle_stretch(sent_nudges, stub_fleet_rows):
    stub_fleet_rows["rows"] = [
        {"role": "overseer", "task": "port", "state": "blocked", "unseen": False}
    ]
    monitor = _StubMonitor("idle")
    loop = asyncio.get_event_loop()

    await monitor._maybe_nudge_bill(loop)
    _bypass_sweep_throttle(monitor)
    await monitor._maybe_nudge_bill(loop)
    _bypass_sweep_throttle(monitor)
    await monitor._maybe_nudge_bill(loop)

    assert len(sent_nudges) == 1


async def test_maybe_nudge_bill_rearms_after_bill_becomes_active(sent_nudges, stub_fleet_rows):
    stub_fleet_rows["rows"] = [
        {"role": "overseer", "task": "port", "state": "blocked", "unseen": False}
    ]
    monitor = _StubMonitor("idle")
    loop = asyncio.get_event_loop()

    await monitor._maybe_nudge_bill(loop)
    _bypass_sweep_throttle(monitor)
    await monitor._maybe_nudge_bill(loop)
    assert len(sent_nudges) == 1

    monitor._stub_state = "working"
    _bypass_sweep_throttle(monitor)
    await monitor._maybe_nudge_bill(loop)
    assert len(sent_nudges) == 1
    assert monitor._bill_nudged is False

    monitor._stub_state = "idle"
    _bypass_sweep_throttle(monitor)
    await monitor._maybe_nudge_bill(loop)
    assert len(sent_nudges) == 2


async def test_maybe_nudge_bill_stays_quiet_when_nothing_needs_attention(
    sent_nudges, stub_fleet_rows
):
    stub_fleet_rows["rows"] = [{"state": "idle", "unseen": False}]
    monitor = _StubMonitor("idle")
    loop = asyncio.get_event_loop()

    await monitor._maybe_nudge_bill(loop)

    assert sent_nudges == []


@pytest.mark.usefixtures("sent_nudges")
async def test_maybe_nudge_bill_throttles_the_sweep_itself(stub_fleet_rows):
    """The expensive sweep (tmux + TinyDB + per-repo git) must not re-run on every
    poll while Bill sits idle — only the latch-reset-triggering test helper above
    should be able to force a fresh sweep within the throttle window."""
    stub_fleet_rows["rows"] = [
        {"role": "overseer", "task": "port", "state": "blocked", "unseen": False}
    ]
    monitor = _StubMonitor("idle")
    loop = asyncio.get_event_loop()

    await monitor._maybe_nudge_bill(loop)
    assert stub_fleet_rows["calls"] == 1

    monitor._bill_nudged = False
    await monitor._maybe_nudge_bill(loop)

    assert stub_fleet_rows["calls"] == 1


async def test_maybe_nudge_bill_retries_after_a_failed_send(stub_fleet_rows, monkeypatch):
    """Setting the latch unconditionally disarmed the backstop for good: if the tmux send
    fails, nothing retries, and Bill never leaves `idle` because he was never woken."""
    sends = []

    def failing_nudge(**_kwargs):
        sends.append(1)
        return False

    monkeypatch.setattr(bill_nudge, "nudge", failing_nudge)
    stub_fleet_rows["rows"] = [
        {"role": "overseer", "task": "port", "state": "blocked", "unseen": False}
    ]
    monitor = _StubMonitor("idle")
    loop = asyncio.get_event_loop()

    await monitor._maybe_nudge_bill(loop)
    assert monitor._bill_nudged is False, "a failed send must leave the backstop armed"

    _bypass_sweep_throttle(monitor)
    await monitor._maybe_nudge_bill(loop)

    assert len(sends) == 2


async def test_maybe_nudge_bill_filters_the_sweep_by_origin_not_by_session_name(
    sent_nudges, monkeypatch
):
    """``_fleet_rows``'s first parameter is the registry `origin` filter. It only worked
    because the origin and the session name happen to share a value, so a rename would
    have made the backstop sweep an empty fleet forever, silently."""
    from lumbergh.routers import bill as bill_router

    captured = []
    monkeypatch.setattr(
        bill_router,
        "_fleet_rows",
        lambda origin, **_kwargs: (
            captured.append(origin)
            or [{"role": "overseer", "task": "port", "state": "blocked", "unseen": False}]
        ),
    )
    monkeypatch.setattr(bill_nudge, "BILL_SESSION", "bill-renamed")
    monitor = _StubMonitor("idle")

    await monitor._maybe_nudge_bill(asyncio.get_event_loop())

    assert captured == [bill_router.BILL_ORIGIN]
    assert len(sent_nudges) == 1


async def test_maybe_nudge_bill_heartbeats_a_calm_long_idle_bill(
    sent_heartbeats, sent_nudges, stub_fleet_rows
):
    """Nothing needs attention, but Bill has sat idle past the cadence: tap him to walk
    the fleet on his own so he never goes permanently deaf once everything's been acked."""
    stub_fleet_rows["rows"] = []
    monitor = _StubMonitor("idle")
    _idle_for(monitor, monitor.BILL_HEARTBEAT_INTERVAL_SECONDS + 10)

    await monitor._maybe_nudge_bill(asyncio.get_event_loop())

    assert len(sent_heartbeats) == 1
    assert sent_nudges == [], "a calm fleet must not fire the urgent edge nudge"


async def test_maybe_nudge_bill_does_not_heartbeat_a_freshly_idle_bill(
    sent_heartbeats, stub_fleet_rows
):
    stub_fleet_rows["rows"] = []
    monitor = _StubMonitor("idle")
    _idle_for(monitor, monitor.BILL_HEARTBEAT_INTERVAL_SECONDS - 30)

    await monitor._maybe_nudge_bill(asyncio.get_event_loop())

    assert sent_heartbeats == []


async def test_maybe_nudge_bill_spaces_out_its_heartbeats(sent_heartbeats, stub_fleet_rows):
    stub_fleet_rows["rows"] = []
    monitor = _StubMonitor("idle")
    loop = asyncio.get_event_loop()
    _idle_for(monitor, monitor.BILL_HEARTBEAT_INTERVAL_SECONDS + 10)

    await monitor._maybe_nudge_bill(loop)
    assert len(sent_heartbeats) == 1

    _bypass_sweep_throttle(monitor)
    await monitor._maybe_nudge_bill(loop)
    assert len(sent_heartbeats) == 1, "a second check-in within the window must not fire"

    _bypass_sweep_throttle(monitor)
    monitor._last_bill_nudge_at -= monitor.BILL_HEARTBEAT_INTERVAL_SECONDS + 5
    await monitor._maybe_nudge_bill(loop)
    assert len(sent_heartbeats) == 2, "once the cadence elapses, the next check-in fires"


async def test_maybe_nudge_bill_prefers_the_edge_nudge_over_a_heartbeat(
    sent_nudges, sent_heartbeats, stub_fleet_rows
):
    """A real blocker must win: an idle-past-cadence Bill with a blocked overseer gets the
    urgent nudge, never the softer routine check-in."""
    from lumbergh.routers.bill import _overseer_acked

    _overseer_acked.clear()
    stub_fleet_rows["rows"] = [
        {"role": "overseer", "task": "port", "state": "blocked", "unseen": False}
    ]
    monitor = _StubMonitor("idle")
    _idle_for(monitor, monitor.BILL_HEARTBEAT_INTERVAL_SECONDS * 3)

    await monitor._maybe_nudge_bill(asyncio.get_event_loop())

    assert len(sent_nudges) == 1
    assert sent_heartbeats == []


async def test_maybe_nudge_bill_heartbeat_stays_off_the_event_loop(stub_fleet_rows, monkeypatch):
    """Like the edge nudge, the heartbeat shells out to tmux; it must not run on the loop."""
    ran_on_loop = []

    def recording_heartbeat(**_kwargs):
        try:
            asyncio.get_running_loop()
            ran_on_loop.append(True)
        except RuntimeError:
            ran_on_loop.append(False)
        return True

    monkeypatch.setattr(bill_nudge, "heartbeat_nudge", recording_heartbeat)
    stub_fleet_rows["rows"] = []
    monitor = _StubMonitor("idle")
    _idle_for(monitor, monitor.BILL_HEARTBEAT_INTERVAL_SECONDS + 10)

    await monitor._maybe_nudge_bill(asyncio.get_event_loop())

    assert ran_on_loop == [False]


async def test_maybe_nudge_bill_keeps_the_tmux_send_off_the_event_loop(
    stub_fleet_rows, monkeypatch
):
    """``nudge`` shells out to tmux twice; on the loop that stalls every terminal socket."""
    ran_on_loop = []

    def recording_nudge(**_kwargs):
        try:
            asyncio.get_running_loop()
            ran_on_loop.append(True)
        except RuntimeError:
            ran_on_loop.append(False)
        return True

    monkeypatch.setattr(bill_nudge, "nudge", recording_nudge)
    stub_fleet_rows["rows"] = [
        {"role": "overseer", "task": "port", "state": "blocked", "unseen": False}
    ]

    await _StubMonitor("idle")._maybe_nudge_bill(asyncio.get_event_loop())

    assert ran_on_loop == [False]
