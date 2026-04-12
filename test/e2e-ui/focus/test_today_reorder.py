"""Tests for Today panel drag-to-reorder functionality."""
import json
import pytest
from conftest import BASE_URL, seed_tasks, clear_tasks, read_tasks, make_task


THREE_TODAY_TASKS = {"tasks": [
    make_task("Task Alpha", priority="high", status="today", task_id="t1"),
    make_task("Task Beta", priority="med", status="today", task_id="t2"),
    make_task("Task Charlie", priority="low", status="today", task_id="t3"),
]}

TODAY_WITH_INBOX = {"tasks": [
    make_task("Inbox item", priority="med", status="inbox", task_id="t1"),
    make_task("Today item", priority="high", status="today", task_id="t2"),
]}

TODAY_WITH_METADATA = {"tasks": [
    make_task("Task with blocker", priority="high", status="today", task_id="t1",
              blocker="waiting on API key"),
    make_task("Task with subtasks", priority="med", status="today", task_id="t2",
              subtasks=[
                  {"text": "Step one", "done": False},
                  {"text": "Step two", "done": True},
              ]),
]}


def get_today_card_titles(page):
    """Return the titles of today cards in DOM order."""
    cards = page.locator(".today-card")
    count = cards.count()
    titles = []
    for i in range(count):
        title = cards.nth(i).locator(".today-card-title").text_content()
        titles.append(title.strip())
    return titles


class TestTodayReorderMouse:
    """Test drag-to-reorder within the Today panel using mouse."""

    def test_reorder_first_to_last(self, page):
        """Drag the first today card to the end — order should change."""
        seed_tasks(THREE_TODAY_TASKS)
        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        # Verify initial order
        titles = get_today_card_titles(page)
        assert titles == ["Task Alpha", "Task Beta", "Task Charlie"]

        # Drag Task Alpha (first) past Task Charlie (last)
        first_card = page.locator(".today-card").first
        last_card = page.locator(".today-card").last

        # Drag past the last card's bottom-right to place at end
        last_box = last_card.bounding_box()
        first_card.drag_to(last_card, target_position={
            "x": last_box["width"] - 5,
            "y": last_box["height"] - 5,
        })
        page.wait_for_timeout(600)

        # Verify new order: Beta, Charlie, Alpha
        titles = get_today_card_titles(page)
        assert titles == ["Task Beta", "Task Charlie", "Task Alpha"]

        clear_tasks()

    def test_reorder_last_to_first(self, page):
        """Drag the last today card to the beginning — order should change."""
        seed_tasks(THREE_TODAY_TASKS)
        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        # Drag Task Charlie (last) before Task Alpha (first)
        last_card = page.locator(".today-card").last
        first_card = page.locator(".today-card").first

        first_box = first_card.bounding_box()
        last_card.drag_to(first_card, target_position={
            "x": 5,
            "y": 5,
        })
        page.wait_for_timeout(600)

        # Verify new order: Charlie, Alpha, Beta
        titles = get_today_card_titles(page)
        assert titles == ["Task Charlie", "Task Alpha", "Task Beta"]

        clear_tasks()

    def test_reorder_persists_after_reload(self, page):
        """After reordering, reload the page and verify the new order persists."""
        seed_tasks(THREE_TODAY_TASKS)
        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        # Drag Task Alpha past Task Charlie
        first_card = page.locator(".today-card").first
        last_card = page.locator(".today-card").last
        last_box = last_card.bounding_box()
        first_card.drag_to(last_card, target_position={
            "x": last_box["width"] - 5,
            "y": last_box["height"] - 5,
        })
        page.wait_for_timeout(800)

        # Reload and verify order persists
        page.reload()
        page.wait_for_selector(".today-card")
        titles = get_today_card_titles(page)
        assert titles == ["Task Beta", "Task Charlie", "Task Alpha"]

        clear_tasks()


class TestTodayDropFromOtherPanel:
    """Regression: dropping from other panels into Today must still work."""

    def test_drag_inbox_to_today(self, page):
        """Drag an inbox task to Today — it should appear in the Today panel."""
        seed_tasks(TODAY_WITH_INBOX)
        page.goto(BASE_URL)
        page.wait_for_selector(".inbox-item")

        inbox_item = page.locator(".inbox-item").first
        today_panel = page.locator("#todayPanel")

        inbox_item.drag_to(today_panel)
        page.wait_for_timeout(600)

        # Inbox should be empty
        assert page.locator(".inbox-item").count() == 0

        # Today should now have 2 cards
        today_cards = page.locator(".today-card")
        assert today_cards.count() == 2

        # Both items should be present
        titles = get_today_card_titles(page)
        assert "Today item" in titles
        assert "Inbox item" in titles

        clear_tasks()


class TestTodayReorderPreservesData:
    """Reordering must not lose task metadata like blockers and subtasks."""

    def test_metadata_survives_reorder(self, page):
        """Reorder tasks with blockers/subtasks and verify metadata persists."""
        seed_tasks(TODAY_WITH_METADATA)
        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        titles = get_today_card_titles(page)
        assert titles == ["Task with blocker", "Task with subtasks"]

        # Drag second card before first
        second_card = page.locator(".today-card").nth(1)
        first_card = page.locator(".today-card").first
        first_box = first_card.bounding_box()
        second_card.drag_to(first_card, target_position={
            "x": 5,
            "y": 5,
        })
        page.wait_for_timeout(800)

        # Verify reorder happened
        titles = get_today_card_titles(page)
        assert titles == ["Task with subtasks", "Task with blocker"]

        # Read tasks and verify metadata survived
        data = read_tasks()

        # Blocker should still be present
        blocker_task = next(t for t in data['tasks'] if t['title'] == 'Task with blocker')
        assert blocker_task['blocker'] == 'waiting on API key'

        # Subtasks should still be present
        subtask_task = next(t for t in data['tasks'] if t['title'] == 'Task with subtasks')
        assert any(s['text'] == 'Step one' and not s['done'] for s in subtask_task['subtasks'])
        assert any(s['text'] == 'Step two' and s['done'] for s in subtask_task['subtasks'])

        clear_tasks()
