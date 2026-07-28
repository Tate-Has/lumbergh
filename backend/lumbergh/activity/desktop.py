"""Aggregates activity across every currently-running session into one feed.

`DesktopActivityBroker` periodically rediscovers which tmux sessions are
alive, spins up a `ClaudeCodeAdapter` (and a background tail task) per
session, and funnels `(session_name, ConversationEvent)` tuples from all of
them into a single shared queue. This is deliberately *live-only*: each
adapter's pre-existing backlog is drained and discarded before we start
forwarding events, so a client connecting to the feed never sees history —
only what happens from the moment it starts watching onward.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from pathlib import Path

from lumbergh.activity.claude_code import ClaudeCodeAdapter
from lumbergh.activity.events import ConversationEvent

logger = logging.getLogger(__name__)


class DesktopActivityBroker:
    """Discovers live sessions and streams their Claude Code activity as one feed."""

    def __init__(
        self,
        get_live_sessions,
        get_session_workdir,
        discover_interval: float = 3.0,
        poll_interval: float = 0.4,
    ):
        """
        Args:
            get_live_sessions: zero-arg callable returning dict[str, dict] of
                currently-running tmux sessions, keyed by session name
                (e.g. `lumbergh.routers.sessions.get_live_sessions`).
            get_session_workdir: callable(name) -> Path | None resolving a
                session's working directory (e.g.
                `lumbergh.routers.sessions.get_session_workdir`, wrapped to
                swallow its 404 HTTPException as None).
            discover_interval: seconds between re-scans for new/stopped sessions.
            poll_interval: seconds between transcript polls per session, passed
                through to each adapter's `tail()`.
        """
        self._get_live_sessions = get_live_sessions
        self._get_session_workdir = get_session_workdir
        self.discover_interval = discover_interval
        self.poll_interval = poll_interval

        self._queue: asyncio.Queue[tuple[str, ConversationEvent]] = asyncio.Queue()
        self._tasks: dict[str, asyncio.Task] = {}
        self._stops: dict[str, asyncio.Event] = {}

    def active_sessions(self) -> set[str]:
        """Names of sessions currently being tailed. Exposed for tests/introspection."""
        return set(self._tasks.keys())

    async def _discover_loop(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                await self._sync_sessions()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Activity broker: discovery pass failed")
            try:
                await asyncio.wait_for(stop.wait(), timeout=self.discover_interval)
            except TimeoutError:
                pass

    async def _sync_sessions(self) -> None:
        live = set(await asyncio.to_thread(self._get_live_sessions))

        # Drop tasks for sessions that stopped running.
        for name in set(self._tasks) - live:
            self._remove_session(name)

        # Add tasks for newly-seen sessions.
        for name in live - set(self._tasks):
            await self._add_session(name)

    async def _add_session(self, name: str) -> None:
        workdir = await asyncio.to_thread(self._get_session_workdir, name)
        if not workdir:
            return
        adapter = ClaudeCodeAdapter.for_cwd(Path(workdir))
        if adapter is None:
            return

        session_stop = asyncio.Event()
        self._stops[name] = session_stop
        self._tasks[name] = asyncio.create_task(self._tail_session(name, adapter, session_stop))

    def _remove_session(self, name: str) -> None:
        task = self._tasks.pop(name, None)
        stop = self._stops.pop(name, None)
        if stop:
            stop.set()
        if task:
            task.cancel()

    async def _tail_session(
        self, name: str, adapter: ClaudeCodeAdapter, stop: asyncio.Event
    ) -> None:
        try:
            # Fast-forward past any existing backlog: this feed is live-only
            # by design, so history is discarded rather than emitted.
            await asyncio.to_thread(adapter.read_new)
            async for event in adapter.tail(stop, poll_interval=self.poll_interval):
                await self._queue.put((name, event))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Activity broker: tail failed for session %s", name)

    async def stream(self, stop: asyncio.Event) -> AsyncIterator[tuple[str, ConversationEvent]]:
        """Yield `(session_name, event)` for every running session until `stop` is set."""
        discover_task = asyncio.create_task(self._discover_loop(stop))
        try:
            while not stop.is_set():
                get_item = asyncio.ensure_future(self._queue.get())
                wait_stop = asyncio.ensure_future(stop.wait())
                done, pending = await asyncio.wait(
                    {get_item, wait_stop}, return_when=asyncio.FIRST_COMPLETED
                )
                for pending_task in pending:
                    pending_task.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
                if get_item in done:
                    yield get_item.result()
                if wait_stop in done:
                    break
        finally:
            stop.set()
            discover_task.cancel()
            for name in list(self._tasks):
                self._remove_session(name)
