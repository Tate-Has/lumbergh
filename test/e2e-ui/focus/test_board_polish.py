"""Tests for Phase 02: Board & Workflow Polish features."""
import time
import pytest
from conftest import BASE_URL, seed_tasks, clear_tasks, clear_localstorage, make_task


MULTI_PROJECT_TASKS = {"tasks": [
    {"id": "t1", "title": "Task A1", "project": "Alpha", "priority": "high", "status": "backlog", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t2", "title": "Task A2", "project": "Alpha", "priority": "med", "status": "backlog", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t3", "title": "Task B1", "project": "Beta", "priority": "med", "status": "backlog", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t4", "title": "Task A3", "project": "Alpha", "priority": "high", "status": "in-progress", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t5", "title": "Task B2", "project": "Beta", "priority": "med", "status": "in-progress", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t6", "title": "Task G1", "project": "Gamma", "priority": "low", "status": "in-progress", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t7", "title": "Task B3", "project": "Beta", "priority": "med", "status": "waiting", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t8", "title": "Task G2", "project": "Gamma", "priority": "low", "status": "review", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t9", "title": "Task A done", "project": "Alpha", "priority": "med", "status": "done", "completed": True, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
]}


# ===== Feature 1: Project Dropdown =====

class TestProjectDropdown:
    def test_datalist_populated_on_edit_modal(self, page):
        """Opening edit modal populates the datalist with existing projects."""
        seed_tasks(MULTI_PROJECT_TASKS)
        page.goto(BASE_URL)
        page.wait_for_selector(".kanban-card")

        # Click a kanban card to open edit modal
        page.locator(".kanban-card").first.click()
        page.wait_for_selector(".modal-overlay.active")

        # Check datalist has options
        options = page.locator("#projectSuggestions option").all()
        values = sorted([o.get_attribute("value") for o in options])
        assert "Alpha" in values
        assert "Beta" in values
        assert "Gamma" in values
        page.locator("#modalCancel").click()
        clear_tasks()

    def test_datalist_populated_on_new_modal(self, page):
        """Opening new task modal populates the datalist."""
        seed_tasks(MULTI_PROJECT_TASKS)
        page.goto(BASE_URL)
        page.wait_for_selector(".kanban-card")

        # Click add button on a column
        page.locator(".col-add-btn").first.click()
        page.wait_for_selector(".modal-overlay.active")

        options = page.locator("#projectSuggestions option").all()
        values = [o.get_attribute("value") for o in options]
        assert len(values) >= 3
        page.locator("#modalCancel").click()
        clear_tasks()

    def test_free_text_still_works(self, page):
        """Can type a new project name not in the datalist."""
        seed_tasks(MULTI_PROJECT_TASKS)
        page.goto(BASE_URL)
        page.wait_for_selector(".kanban-card")

        page.locator(".col-add-btn").first.click()
        page.wait_for_selector(".modal-overlay.active")

        page.fill("#modalTaskTitle", "New task with new project")
        page.fill("#modalTaskProject", "BrandNewProject")
        page.locator("#modalSave").click()

        # Wait for modal to close and re-render
        page.wait_for_selector(".modal-overlay.active", state="detached", timeout=3000)
        time.sleep(0.6)  # debounce save

        # Reopen modal to verify the new project is now in the datalist
        page.locator(".col-add-btn").first.click()
        page.wait_for_selector(".modal-overlay.active")
        options = page.locator("#projectSuggestions option").all()
        values = [o.get_attribute("value") for o in options]
        assert "BrandNewProject" in values
        page.locator("#modalCancel").click()
        clear_tasks()


# ===== Feature 2: Task Count Badges =====

class TestCountBadges:
    def test_swimlane_column_header_counts(self, page):
        """Swimlane column headers show task count badges."""
        seed_tasks(MULTI_PROJECT_TASKS)
        page.goto(BASE_URL)
        page.wait_for_selector(".kanban-card")

        # Switch to swimlane view
        page.locator("#swimlaneToggle").click()
        page.wait_for_selector(".swimlane-board")

        # Check column header counts
        headers = page.locator(".swimlane-col-label").all()
        assert len(headers) == 5  # backlog, in-progress, waiting, review, done

        # Each header should contain a .col-count span
        for h in headers:
            count_span = h.locator(".col-count")
            assert count_span.count() == 1
            text = count_span.text_content()
            assert text.strip().split("/")[0].isdigit()

        clear_tasks()

    def test_swimlane_row_label_counts(self, page):
        """Swimlane row labels show total task count for that project."""
        seed_tasks(MULTI_PROJECT_TASKS)
        page.goto(BASE_URL)
        page.wait_for_selector(".kanban-card")

        page.locator("#swimlaneToggle").click()
        page.wait_for_selector(".swimlane-board")

        # Check row labels have counts
        row_counts = page.locator(".swimlane-row-count").all()
        assert len(row_counts) > 0

        # Each count should be a positive number
        for rc in row_counts:
            text = rc.text_content().strip()
            assert text.isdigit() and int(text) > 0

        clear_tasks()

    def test_column_view_counts_still_work(self, page):
        """Column view header counts still display correctly."""
        seed_tasks(MULTI_PROJECT_TASKS)
        page.goto(BASE_URL)
        page.wait_for_selector(".kanban-card")

        counts = page.locator(".col-count").all()
        assert len(counts) > 0
        clear_tasks()


# ===== Feature 3: Collapsed Done Column =====

class TestCollapsedDone:
    def test_done_starts_collapsed(self, page):
        """Done column starts collapsed by default."""
        seed_tasks(MULTI_PROJECT_TASKS)
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_selector(".board-col")

        # Should see two collapsed columns (backlog + done)
        collapsed = page.locator(".board-col.collapsed-col").all()
        assert len(collapsed) == 2

        # One should have "Done" label
        labels = [c.locator(".collapsed-col-label").text_content() for c in collapsed]
        assert "Done" in labels
        clear_tasks()

    def test_done_expands_on_click(self, page):
        """Clicking collapsed Done column expands it."""
        seed_tasks(MULTI_PROJECT_TASKS)
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_selector(".board-col")

        # Find the Done collapsed column and click it
        collapsed = page.locator(".board-col.collapsed-col")
        for i in range(collapsed.count()):
            el = collapsed.nth(i)
            if el.locator(".collapsed-col-label").text_content() == "Done":
                el.click()
                break

        # Wait for re-render
        page.wait_for_selector(".board-col.done-col")
        assert page.locator(".board-col.done-col").count() == 1
        clear_tasks()

    def test_done_persists_expanded(self, page):
        """Done stays expanded after page reload when localStorage says so."""
        seed_tasks(MULTI_PROJECT_TASKS)
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_selector(".board-col")

        # Expand done
        collapsed = page.locator(".board-col.collapsed-col")
        for i in range(collapsed.count()):
            el = collapsed.nth(i)
            if el.locator(".collapsed-col-label").text_content() == "Done":
                el.click()
                break

        page.wait_for_selector(".board-col.done-col")

        # Reload and verify still expanded
        page.reload()
        page.wait_for_selector(".board-col")
        assert page.locator(".board-col.done-col").count() == 1
        clear_tasks()

    def test_done_collapse_button(self, page):
        """Collapse button in Done header re-collapses the column."""
        seed_tasks(MULTI_PROJECT_TASKS)
        page.goto(BASE_URL)
        page.evaluate("localStorage.setItem('doneCollapsed', 'false')")
        page.reload()
        page.wait_for_selector(".board-col.done-col")

        # Click collapse button
        page.locator("#collapseDone").click()

        # Should be collapsed now
        page.wait_for_selector(".board-col.done-col", state="detached", timeout=3000)
        # Verify localStorage
        val = page.evaluate("localStorage.getItem('doneCollapsed')")
        assert val == "true"
        clear_tasks()

    def test_collapsed_done_shows_count(self, page):
        """Collapsed Done column shows correct task count."""
        seed_tasks(MULTI_PROJECT_TASKS)
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_selector(".board-col")

        # Find the Done collapsed column
        collapsed = page.locator(".board-col.collapsed-col")
        for i in range(collapsed.count()):
            el = collapsed.nth(i)
            if el.locator(".collapsed-col-label").text_content() == "Done":
                count_text = el.locator(".collapsed-col-count").text_content().strip()
                assert count_text == "1"  # one done task in seed data
                break
        clear_tasks()

    def test_backlog_persists_state(self, page):
        """Backlog collapse state persists in localStorage."""
        seed_tasks(MULTI_PROJECT_TASKS)
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_selector(".board-col")

        # Backlog starts collapsed by default
        # Expand it by clicking
        collapsed = page.locator(".board-col.collapsed-col")
        for i in range(collapsed.count()):
            el = collapsed.nth(i)
            if el.locator(".collapsed-col-label").text_content() == "Backlog":
                el.click()
                break

        # Verify localStorage was set
        val = page.evaluate("localStorage.getItem('backlogCollapsed')")
        assert val == "false"

        # Reload - should stay expanded
        page.reload()
        page.wait_for_selector(".board-col")
        # Should not find backlog in collapsed columns
        collapsed = page.locator(".board-col.collapsed-col")
        labels = []
        for i in range(collapsed.count()):
            labels.append(collapsed.nth(i).locator(".collapsed-col-label").text_content())
        assert "Backlog" not in labels
        clear_tasks()


# ===== Feature 4: WIP Limit Warnings =====

WIP_OVER_TASKS = {"tasks": [
    {"id": "t1", "title": "Task IP1", "project": "Alpha", "priority": "high", "status": "in-progress", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t2", "title": "Task IP2", "project": "Alpha", "priority": "med", "status": "in-progress", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t3", "title": "Task IP3", "project": "Beta", "priority": "med", "status": "in-progress", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t4", "title": "Task IP4", "project": "Gamma", "priority": "high", "status": "in-progress", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
]}

WIP_AT_LIMIT_TASKS = {"tasks": [
    {"id": "t1", "title": "Task IP1", "project": "Alpha", "priority": "high", "status": "in-progress", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t2", "title": "Task IP2", "project": "Alpha", "priority": "med", "status": "in-progress", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t3", "title": "Task IP3", "project": "Beta", "priority": "med", "status": "in-progress", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
]}


class TestWipLimits:
    def test_wip_warning_over_limit(self, page):
        """In Progress column shows warning when over WIP limit."""
        seed_tasks(WIP_OVER_TASKS)
        page.goto(BASE_URL)
        page.wait_for_selector(".kanban-card")

        # Find the In Progress column header
        wip_header = page.locator(".col-header.wip-warning")
        assert wip_header.count() == 1

        # Check count badge shows 4/3 format
        wip_count = wip_header.locator(".col-count.wip-over")
        assert wip_count.count() == 1
        assert "4/3" in wip_count.text_content()
        clear_tasks()

    def test_no_warning_at_limit(self, page):
        """In Progress at exactly the WIP limit has no warning."""
        seed_tasks(WIP_AT_LIMIT_TASKS)
        page.goto(BASE_URL)
        page.wait_for_selector(".kanban-card")

        # Should have no wip-warning class
        assert page.locator(".col-header.wip-warning").count() == 0
        # Count should show "3/3" but no wip-over
        assert page.locator(".col-count.wip-over").count() == 0
        clear_tasks()

    def test_wip_count_format_with_limit(self, page):
        """Columns with WIP limits show count/limit format."""
        seed_tasks(WIP_AT_LIMIT_TASKS)
        page.goto(BASE_URL)
        page.wait_for_selector(".kanban-card")

        # Find In Progress col-count - should show "3/3"
        # Get all col-counts and check one has "/3"
        counts = page.locator(".col-count").all()
        found = False
        for c in counts:
            text = c.text_content().strip()
            if "/3" in text:
                found = True
                break
        assert found, "Expected a count with '/3' format for In Progress column"
        clear_tasks()

    def test_no_limit_format_for_other_columns(self, page):
        """Columns without WIP limits show plain count (no slash)."""
        seed_tasks(MULTI_PROJECT_TASKS)
        page.goto(BASE_URL)
        page.wait_for_selector(".kanban-card")

        # Expand done to check its header
        page.evaluate("localStorage.setItem('doneCollapsed', 'false')")
        page.reload()
        page.wait_for_selector(".kanban-card")

        # Review column count should not have a slash
        # We can check by finding col-headers and their titles
        headers = page.locator(".col-header").all()
        for h in headers:
            title = h.locator(".col-title").text_content().strip()
            count = h.locator(".col-count").text_content().strip()
            if title == "Review":
                assert "/" not in count, f"Review count should be plain, got '{count}'"
            elif title == "Waiting On":
                assert "/" not in count, f"Waiting On count should be plain, got '{count}'"
        clear_tasks()

    def test_wip_warning_in_swimlane_view(self, page):
        """WIP warning appears in swimlane column headers too."""
        seed_tasks(WIP_OVER_TASKS)
        page.goto(BASE_URL)
        page.wait_for_selector(".kanban-card")

        page.locator("#swimlaneToggle").click()
        page.wait_for_selector(".swimlane-board")

        # Check for wip-over class in swimlane column headers
        wip_counts = page.locator(".swimlane-col-label .col-count.wip-over")
        assert wip_counts.count() == 1
        assert "4/3" in wip_counts.text_content()
        clear_tasks()
