import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from lumbergh.activity.events import ConversationEvent


class AgentAdapter(ABC):
    """Turns one agent's native transcript into normalized ConversationEvents.

    A concrete adapter answers three questions: where is the transcript, what
    happened so far (read_new from offset 0), and what happens next (tail).
    """

    @abstractmethod
    def read_new(self) -> list[ConversationEvent]:
        """Return events appended since the last call; advance internal offset."""

    async def tail(
        self, stop: asyncio.Event, poll_interval: float = 0.4
    ) -> AsyncIterator[ConversationEvent]:
        """Yield all existing events immediately, then poll for new ones.

        The first iteration reads from offset 0, so history streams before any
        wait. Polls file changes until `stop` is set.
        """
        last_signature: tuple[int, float] | None = None
        while not stop.is_set():
            signature = self._source_signature()
            if signature != last_signature:
                last_signature = signature
                for event in await asyncio.to_thread(self.read_new):
                    yield event
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_interval)
            except TimeoutError:
                pass

    @abstractmethod
    def _source_signature(self) -> tuple[int, float]:
        """Cheap change-detection token, e.g. (size, mtime). (-1, -1) if absent."""
