"""Tests for DesktopActivityBroker: multi-session discovery, tagging, and teardown.

Uses fake session-listing/workdir callables and a fake adapter (monkeypatched
in place of ClaudeCodeAdapter) so nothing here touches real tmux or transcript
files.
"""

import asyncio
from pathlib import Path

import pytest

from lumbergh.activity import desktop as desktop_module
from lumbergh.activity.desktop import DesktopActivityBroker
from lumbergh.activity.events import ConversationEvent


class FakeAdapter:
    """Stands in for ClaudeCodeAdapter: a canned backlog plus canned live events."""

    instances: dict[str, "FakeAdapter"] = {}

    def __init__(self, name: str, backlog: list[ConversationEvent], live: list[ConversationEvent]):
        self.name = name
        self._backlog = backlog
        self._live = list(live)
        self.read_new_calls = 0
        FakeAdapter.instances[name] = self

    def read_new(self) -> list[ConversationEvent]:
        self.read_new_calls += 1
        if self.read_new_calls == 1:
            return self._backlog
        return []

    async def tail(self, stop: asyncio.Event, poll_interval: float = 0.4):  # noqa: ARG002 -- must match AgentAdapter.tail's signature; broker calls it as a keyword arg
        for event in self._live:
            if stop.is_set():
                return
            yield event
        # Idle until told to stop, mirroring the real adapter's polling loop.
        await stop.wait()


@pytest.fixture(autouse=True)
def _clear_fake_instances():
    FakeAdapter.instances.clear()
    yield
    FakeAdapter.instances.clear()


def _make_event(id_: str) -> ConversationEvent:
    return ConversationEvent(type="agent_message", id=id_, text=f"text-{id_}")


@pytest.mark.asyncio
async def test_discovers_session_and_tags_live_events(monkeypatch):
    """A newly-live session gets an adapter; its backlog is dropped, its
    subsequent events are tagged with the session name."""
    live_events = [_make_event("e1"), _make_event("e2")]
    backlog = [_make_event("old-1")]

    def fake_for_cwd(_cwd: Path):
        return FakeAdapter("solo", backlog=backlog, live=live_events)

    monkeypatch.setattr(desktop_module.ClaudeCodeAdapter, "for_cwd", staticmethod(fake_for_cwd))

    broker = DesktopActivityBroker(
        get_live_sessions=lambda: {"solo": {}},
        get_session_workdir=lambda _name: Path("/fake/workdir"),
        discover_interval=100,  # single discovery pass is enough for this test
        poll_interval=0.01,
    )

    stop = asyncio.Event()
    received = []

    async def consume():
        async for session_name, event in broker.stream(stop):
            received.append((session_name, event))
            if len(received) == len(live_events):
                stop.set()

    await asyncio.wait_for(consume(), timeout=5)

    assert received == [("solo", ev) for ev in live_events]
    # Backlog must never reach the queue -- only live-forward events do.
    assert all(ev.id != "old-1" for _, ev in received)
    assert broker.active_sessions() == set()  # torn down after stream() exits


@pytest.mark.asyncio
async def test_skips_session_without_resolvable_workdir(monkeypatch):
    monkeypatch.setattr(
        desktop_module.ClaudeCodeAdapter,
        "for_cwd",
        staticmethod(lambda _cwd: pytest.fail("should not be called when workdir is None")),
    )

    broker = DesktopActivityBroker(
        get_live_sessions=lambda: {"ghost": {}},
        get_session_workdir=lambda _name: None,
        discover_interval=100,
    )

    await broker._sync_sessions()

    assert broker.active_sessions() == set()


@pytest.mark.asyncio
async def test_skips_session_without_claude_transcript(monkeypatch):
    monkeypatch.setattr(
        desktop_module.ClaudeCodeAdapter, "for_cwd", staticmethod(lambda _cwd: None)
    )

    broker = DesktopActivityBroker(
        get_live_sessions=lambda: {"no-transcript": {}},
        get_session_workdir=lambda _name: Path("/fake/workdir"),
        discover_interval=100,
    )

    await broker._sync_sessions()

    assert broker.active_sessions() == set()


@pytest.mark.asyncio
async def test_removes_task_when_session_stops(monkeypatch):
    def fake_for_cwd(_cwd: Path):
        return FakeAdapter("bye", backlog=[], live=[])

    monkeypatch.setattr(desktop_module.ClaudeCodeAdapter, "for_cwd", staticmethod(fake_for_cwd))

    live = {"bye": {}}
    broker = DesktopActivityBroker(
        get_live_sessions=lambda: dict(live),
        get_session_workdir=lambda _name: Path("/fake/workdir"),
        discover_interval=100,
    )

    await broker._sync_sessions()
    assert broker.active_sessions() == {"bye"}

    live.clear()
    await broker._sync_sessions()
    assert broker.active_sessions() == set()


@pytest.mark.asyncio
async def test_multiple_sessions_tagged_independently(monkeypatch):
    events_by_session = {
        "alpha": [_make_event("a1")],
        "beta": [_make_event("b1")],
    }

    def fake_for_cwd(cwd: Path):
        # cwd encodes which session asked, since get_session_workdir is keyed by name.
        name = str(cwd)
        return FakeAdapter(name, backlog=[], live=events_by_session[name])

    monkeypatch.setattr(desktop_module.ClaudeCodeAdapter, "for_cwd", staticmethod(fake_for_cwd))

    broker = DesktopActivityBroker(
        get_live_sessions=lambda: {"alpha": {}, "beta": {}},
        get_session_workdir=lambda name: Path(name),
        discover_interval=100,
        poll_interval=0.01,
    )

    stop = asyncio.Event()
    received = []

    async def consume():
        async for session_name, event in broker.stream(stop):
            received.append((session_name, event))
            if len(received) == 2:
                stop.set()

    await asyncio.wait_for(consume(), timeout=5)

    received_by_session = dict(received)
    assert received_by_session["alpha"] == events_by_session["alpha"][0]
    assert received_by_session["beta"] == events_by_session["beta"][0]
