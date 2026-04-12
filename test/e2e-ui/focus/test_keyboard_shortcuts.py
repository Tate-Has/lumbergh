"""Tests for Phase 03: Keyboard Shortcuts."""
import time
import pytest
from conftest import BASE_URL, seed_tasks, clear_tasks, clear_localstorage, make_task


SAMPLE_TASKS = {"tasks": [
    {"id": "t1", "title": "Inbox item", "project": "", "priority": "med", "status": "inbox", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t2", "title": "Today task", "project": "", "priority": "high", "status": "today", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t3", "title": "Running task", "project": "", "priority": "med", "status": "running", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t4", "title": "Backlog task", "project": "Alpha", "priority": "med", "status": "backlog", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
]}


class TestShortcutN:
    def test_n_focuses_inbox(self, page):
        """Pressing 'n' opens inbox if collapsed and focuses input."""
        seed_tasks(SAMPLE_TASKS)
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        # Inbox starts collapsed — press n
        page.keyboard.press("n")
        page.wait_for_timeout(200)

        # Inbox should be expanded
        strip = page.locator("#inboxStrip")
        assert "expanded" in strip.get_attribute("class")

        # Input should be focused
        focused_id = page.evaluate("document.activeElement.id")
        assert focused_id == "inboxInput"

    def test_n_suppressed_in_input(self, page):
        """Pressing 'n' while typing in an input should type the character, not trigger shortcut."""
        seed_tasks(SAMPLE_TASKS)
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        # First open inbox and focus input
        page.keyboard.press("n")
        page.wait_for_timeout(200)

        # Now type 'n' — it should appear in the input, not re-trigger shortcut
        page.keyboard.type("hello n world")
        value = page.locator("#inboxInput").input_value()
        assert "n" in value


class TestShortcutT:
    def test_t_scrolls_to_today(self, page):
        """Pressing 't' scrolls the Today panel into view."""
        seed_tasks(SAMPLE_TASKS)
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        # Scroll to bottom first
        page.evaluate("document.querySelector('.main-content').scrollTop = 99999")
        page.wait_for_timeout(100)

        page.keyboard.press("t")
        page.wait_for_timeout(500)

        # Today panel should be visible
        box = page.locator("#todayPanel").bounding_box()
        viewport = page.viewport_size
        assert box is not None
        assert box["y"] < viewport["height"]


class TestShortcutD:
    def test_d_toggles_theme(self, page):
        """Pressing 'd' toggles the theme."""
        seed_tasks(SAMPLE_TASKS)
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        initial = page.evaluate("document.documentElement.classList.contains('dark')")
        page.keyboard.press("d")
        page.wait_for_timeout(100)

        after = page.evaluate("document.documentElement.classList.contains('dark')")
        assert initial != after


class TestEscape:
    def test_escape_closes_task_modal(self, page):
        """Escape closes the task edit modal."""
        seed_tasks(SAMPLE_TASKS)
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        # Open a task modal via the + Add button
        page.locator("#addTodayBtn").click()
        page.wait_for_selector("#taskModal.active")

        page.keyboard.press("Escape")
        page.wait_for_timeout(100)

        assert "active" not in page.locator("#taskModal").get_attribute("class")

    def test_escape_closes_help_overlay(self, page):
        """Escape closes the shortcut help overlay."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        # Open help overlay
        page.keyboard.press("?")
        page.wait_for_timeout(100)
        assert "active" in page.locator("#shortcutOverlay").get_attribute("class")

        page.keyboard.press("Escape")
        page.wait_for_timeout(100)
        assert "active" not in page.locator("#shortcutOverlay").get_attribute("class")

    def test_escape_closes_filter_dropdown(self, page):
        """Escape closes open filter dropdowns."""
        seed_tasks(SAMPLE_TASKS)
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        # Open project filter dropdown
        page.locator("#projectFilterBtn").click()
        page.wait_for_timeout(100)
        assert "open" in page.locator("#projectFilterMenu").get_attribute("class")

        page.keyboard.press("Escape")
        page.wait_for_timeout(100)
        assert "open" not in (page.locator("#projectFilterMenu").get_attribute("class") or "")


class TestShortcutHelp:
    def test_question_mark_toggles_overlay(self, page):
        """Pressing '?' toggles the help overlay open and closed."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        # Open
        page.keyboard.press("?")
        page.wait_for_timeout(100)
        assert "active" in page.locator("#shortcutOverlay").get_attribute("class")

        # Close
        page.keyboard.press("?")
        page.wait_for_timeout(100)
        assert "active" not in page.locator("#shortcutOverlay").get_attribute("class")

    def test_topbar_button_opens_overlay(self, page):
        """Clicking the '?' button in topbar opens the help overlay."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        page.locator("#shortcutHelpBtn").click()
        page.wait_for_timeout(100)
        assert "active" in page.locator("#shortcutOverlay").get_attribute("class")

    def test_backdrop_click_closes_overlay(self, page):
        """Clicking the backdrop closes the help overlay."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        # Open overlay
        page.keyboard.press("?")
        page.wait_for_timeout(100)
        assert "active" in page.locator("#shortcutOverlay").get_attribute("class")

        # Click backdrop (the overlay element itself, not the modal)
        page.locator("#shortcutOverlay").click(position={"x": 10, "y": 10})
        page.wait_for_timeout(100)
        assert "active" not in page.locator("#shortcutOverlay").get_attribute("class")


class TestModifierGuard:
    def test_ctrl_n_does_not_trigger_shortcut(self, page):
        """Ctrl+n should not trigger the inbox shortcut."""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        page.keyboard.press("Control+n")
        page.wait_for_timeout(200)

        focused_id = page.evaluate("document.activeElement.id")
        assert focused_id != "inboxInput"
