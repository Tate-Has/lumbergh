"""Hands the transcript to a viewer a page at a time, newest first.

The conversation view used to receive every event in the transcript, each as its
own websocket frame — two thousand of them for a long session, merged one at a
time by the client. Opening the tab cost a scroll through the entire history.
A page of the most recent events opens instantly; the rest stays one click away.
"""

from lumbergh.activity.events import ConversationEvent

DEFAULT_PAGE_SIZE = 500


class HistoryWindow:
    """A cursor over already-parsed events, walking backwards from the newest."""

    def __init__(self, events: list[ConversationEvent], page_size: int = DEFAULT_PAGE_SIZE):
        self._events = events
        self._page_size = page_size
        # Everything from here to the end has been sent; what is left is older.
        self._sent_from = len(events)

    @property
    def remaining(self) -> int:
        return self._sent_from

    def first_page(self) -> list[ConversationEvent]:
        return self._take(self._page_size)

    def older_page(self) -> list[ConversationEvent]:
        return self._take(self._page_size)

    def _take(self, count: int) -> list[ConversationEvent]:
        start = max(0, self._sent_from - count)
        page = self._events[start : self._sent_from]
        self._sent_from = start
        return page
