"""Paging the transcript instead of firing all of it at the browser.

Opening the conversation view replayed every event in the transcript as its own
websocket frame — 2086 of them for a long session — which the client merged one
at a time. The window keeps the open cheap while leaving the rest reachable.
"""

from lumbergh.activity.events import ConversationEvent
from lumbergh.activity.history import HistoryWindow


def events(count: int) -> list[ConversationEvent]:
    return [
        ConversationEvent(type="agent_message", id=str(i), text=f"line {i}") for i in range(count)
    ]


class TestFirstPage:
    def test_sends_only_the_tail_of_a_long_transcript(self):
        window = HistoryWindow(events(2086), page_size=500)

        page = window.first_page()

        assert len(page) == 500
        assert page[0].id == "1586", "the page ends at the newest event"
        assert page[-1].id == "2085"

    def test_a_short_transcript_arrives_whole(self):
        window = HistoryWindow(events(12), page_size=500)

        assert len(window.first_page()) == 12

    def test_an_empty_transcript_is_not_an_error(self):
        window = HistoryWindow([], page_size=500)

        assert window.first_page() == []
        assert window.remaining == 0


class TestRemaining:
    def test_reports_what_is_still_behind(self):
        window = HistoryWindow(events(2086), page_size=500)
        window.first_page()

        assert window.remaining == 1586

    def test_nothing_is_behind_a_whole_transcript(self):
        window = HistoryWindow(events(12), page_size=500)
        window.first_page()

        assert window.remaining == 0


class TestOlderPages:
    def test_walks_backwards_a_page_at_a_time(self):
        window = HistoryWindow(events(1200), page_size=500)
        window.first_page()

        older = window.older_page()

        assert [older[0].id, older[-1].id] == ["200", "699"]
        assert window.remaining == 200

    def test_the_last_page_is_whatever_is_left(self):
        window = HistoryWindow(events(1200), page_size=500)
        window.first_page()
        window.older_page()

        older = window.older_page()

        assert [older[0].id, older[-1].id] == ["0", "199"]
        assert window.remaining == 0

    def test_asking_past_the_beginning_gives_nothing(self):
        window = HistoryWindow(events(3), page_size=500)
        window.first_page()

        assert window.older_page() == []
        assert window.remaining == 0

    def test_pages_do_not_overlap_or_skip(self):
        window = HistoryWindow(events(1100), page_size=500)
        seen = [e.id for e in window.first_page()]
        while window.remaining:
            seen = [e.id for e in window.older_page()] + seen

        assert seen == [str(i) for i in range(1100)]
