"""Tests for inbox drag-to-board and drag-to-today functionality."""
import time
import pytest
from conftest import BASE_URL, seed_tasks, clear_tasks, clear_localstorage, make_task


INBOX_TASK = {"tasks": [
    {"id": "t1", "title": "Inbox drag test task", "project": "", "priority": "med", "status": "inbox", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
]}

INBOX_TWO_TASKS = {"tasks": [
    {"id": "t1", "title": "Inbox task one", "project": "", "priority": "med", "status": "inbox", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t2", "title": "Inbox task two", "project": "", "priority": "high", "status": "inbox", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
]}


class TestInboxDragToBoard:
    """Test dragging inbox items to board columns."""

    def test_drag_inbox_to_in_progress(self, page):
        """Dragging an inbox item to In Progress column changes its status."""
        seed_tasks(INBOX_TASK)
        page.goto(BASE_URL)
        page.wait_for_selector(".inbox-item")

        # Verify the inbox item exists
        inbox_item = page.locator(".inbox-item").first
        assert inbox_item.is_visible()

        # Expand backlog so we can see In Progress column clearly
        # Ensure board section is visible
        board_section = page.locator("#boardSection")
        if not board_section.locator(".board-columns").is_visible():
            page.locator("#boardHeader").click()
            page.wait_for_timeout(300)

        # Find the In Progress column by its data-status attribute
        target_col = page.locator('.col-cards[data-status="in-progress"]')
        if target_col.count() == 0:
            # Might need to look for the column container instead
            target_col = page.locator('.board-col').filter(has_text="In Progress")

        # Perform the drag
        inbox_item.drag_to(target_col)
        page.wait_for_timeout(600)

        # Verify the task is no longer in inbox
        assert page.locator(".inbox-item").count() == 0

        # Verify the task appears in the In Progress column
        in_progress_cards = page.locator('.col-cards[data-status="in-progress"] .kanban-card')
        assert in_progress_cards.count() == 1
        assert "Inbox drag test task" in in_progress_cards.first.text_content()

        clear_tasks()

    def test_drag_inbox_to_backlog(self, page):
        """Dragging an inbox item to the Backlog column changes its status."""
        seed_tasks(INBOX_TASK)
        page.goto(BASE_URL)
        # Expand backlog
        page.evaluate("localStorage.setItem('backlogCollapsed', 'false')")
        page.reload()
        page.wait_for_selector(".inbox-item")

        inbox_item = page.locator(".inbox-item").first

        # Find the Backlog column
        target_col = page.locator('.col-cards[data-status="backlog"]')
        if target_col.count() == 0:
            target_col = page.locator('.board-col').filter(has_text="Backlog")

        inbox_item.drag_to(target_col)
        page.wait_for_timeout(600)

        # Verify no inbox items remain
        assert page.locator(".inbox-item").count() == 0

        # Verify task is in backlog
        backlog_cards = page.locator('.col-cards[data-status="backlog"] .kanban-card')
        assert backlog_cards.count() == 1
        assert "Inbox drag test task" in backlog_cards.first.text_content()

        clear_tasks()


class TestInboxDragToToday:
    """Test dragging inbox items to the Today panel."""

    def test_drag_inbox_to_today(self, page):
        """Dragging an inbox item to Today panel changes its status to today."""
        seed_tasks(INBOX_TASK)
        page.goto(BASE_URL)
        page.wait_for_selector(".inbox-item")

        inbox_item = page.locator(".inbox-item").first
        today_panel = page.locator("#todayPanel")

        inbox_item.drag_to(today_panel)
        page.wait_for_timeout(600)

        # Verify inbox is empty
        assert page.locator(".inbox-item").count() == 0

        # Verify task appears in Today panel
        today_cards = page.locator(".today-card")
        assert today_cards.count() == 1
        assert "Inbox drag test task" in today_cards.first.text_content()

        clear_tasks()

    def test_drag_inbox_to_today_multiple(self, page):
        """Dragging one of two inbox items to Today leaves the other in inbox."""
        seed_tasks(INBOX_TWO_TASKS)
        page.goto(BASE_URL)
        page.wait_for_selector(".inbox-item")

        # Should start with 2 inbox items
        assert page.locator(".inbox-item").count() == 2

        # Drag the first one to Today
        inbox_item = page.locator(".inbox-item").first
        today_panel = page.locator("#todayPanel")

        inbox_item.drag_to(today_panel)
        page.wait_for_timeout(600)

        # One should remain in inbox
        assert page.locator(".inbox-item").count() == 1

        # One should be in Today
        assert page.locator(".today-card").count() == 1

        clear_tasks()


class TestInboxDragAffordance:
    """Test that inbox items have the drag grip visual affordance."""

    def test_grip_icon_present(self, page):
        """Inbox items should display a drag grip icon."""
        seed_tasks(INBOX_TASK)
        page.goto(BASE_URL)
        page.wait_for_selector(".inbox-item")

        grip = page.locator(".inbox-drag-grip")
        assert grip.count() >= 1
        assert grip.first.is_visible()

        clear_tasks()

    def test_inbox_item_is_draggable(self, page):
        """Inbox items should have the draggable attribute set."""
        seed_tasks(INBOX_TASK)
        page.goto(BASE_URL)
        page.wait_for_selector(".inbox-item")

        inbox_item = page.locator(".inbox-item").first
        assert inbox_item.get_attribute("draggable") == "true"

        clear_tasks()
