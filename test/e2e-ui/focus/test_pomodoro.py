"""Tests for Pomodoro Timer feature."""
import time
import urllib.request

import pytest
from conftest import BASE_URL, seed_tasks, clear_tasks, clear_localstorage, make_task


class TestPomoStartFromTodayCard:
    """Test 1: Start timer from Today card."""

    def test_start_timer_shows_topbar_and_highlights_card(self, page):
        clear_tasks()
        seed_tasks({"tasks": [{"id": "t1", "title": "Focus Task", "project": "", "priority": "med", "status": "today", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []}]})
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        # Hover over the today card to reveal the play button
        card = page.locator(".today-card").first
        card.hover()
        page.wait_for_timeout(200)

        # Click the play button
        page.click(".today-card-pomo")
        page.wait_for_timeout(500)

        # Verify topbar timer is visible
        timer = page.locator("#pomoTimer")
        assert timer.is_visible()

        # Verify card has pomo-active class
        assert "pomo-active" in card.get_attribute("class")

        # Verify countdown shows 25:00
        countdown = page.locator("#pomoCountdown").text_content()
        assert countdown == "25:00"

        # Verify task title is shown in timer
        task_title = page.locator("#pomoTaskTitle").text_content()
        assert "Focus Task" in task_title

        # Verify phase is "work"
        phase = page.locator("#pomoPhase").text_content()
        assert phase == "work"


class TestPomoPauseResume:
    """Test 2: Pause and resume timer."""

    def test_pause_and_resume(self, page):
        clear_tasks()
        seed_tasks({"tasks": [{"id": "t1", "title": "Pause Task", "project": "", "priority": "med", "status": "today", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []}]})
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        # Start timer
        card = page.locator(".today-card").first
        card.hover()
        page.wait_for_timeout(200)
        page.click(".today-card-pomo")
        page.wait_for_timeout(500)

        # Verify timer is running
        assert page.evaluate("pomo.running") is True

        # Click pause
        page.click("#pomoPauseBtn")
        page.wait_for_timeout(200)

        # Verify paused state
        assert page.evaluate("pomo.running") is False
        assert page.evaluate("pomo.active") is True

        # Verify pause button changed to resume (play icon)
        pause_btn = page.locator("#pomoPauseBtn")
        assert pause_btn.get_attribute("title") == "Resume"

        # Read remaining while paused
        paused_remaining = page.evaluate("pomo.remaining")

        # Wait 2 seconds and verify remaining hasn't changed
        page.wait_for_timeout(2000)
        assert page.evaluate("pomo.remaining") == paused_remaining

        # Click resume
        page.click("#pomoPauseBtn")
        page.wait_for_timeout(200)

        # Verify resumed state
        assert page.evaluate("pomo.running") is True
        assert pause_btn.get_attribute("title") == "Pause"

        # Wait and verify remaining has decremented
        page.wait_for_timeout(2500)
        assert page.evaluate("pomo.remaining") < paused_remaining


class TestPomoStop:
    """Test 3: Stop timer."""

    def test_stop_hides_timer_and_removes_highlight(self, page):
        clear_tasks()
        seed_tasks({"tasks": [{"id": "t1", "title": "Stop Task", "project": "", "priority": "med", "status": "today", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []}]})
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        # Start timer
        card = page.locator(".today-card").first
        card.hover()
        page.wait_for_timeout(200)
        page.click(".today-card-pomo")
        page.wait_for_timeout(500)

        # Verify timer is active
        assert page.locator("#pomoTimer").is_visible()

        # Click stop
        page.click("#pomoStopBtn")
        page.wait_for_timeout(500)

        # Verify topbar timer is hidden
        assert not page.locator("#pomoTimer").is_visible()

        # Verify card no longer has pomo-active class
        card = page.locator(".today-card").first
        card_class = card.get_attribute("class") or ""
        assert "pomo-active" not in card_class


class TestPomoOnlyOneTimer:
    """Test 4: Only one timer at a time."""

    def test_starting_new_timer_switches(self, page):
        clear_tasks()
        seed_tasks({"tasks": [
            {"id": "t1", "title": "Task A", "project": "", "priority": "high", "status": "today", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
            {"id": "t2", "title": "Task B", "project": "", "priority": "med", "status": "today", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
        ]})
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        cards = page.locator(".today-card")

        # Start timer on Task A
        cards.first.hover()
        page.wait_for_timeout(200)
        cards.first.locator(".today-card-pomo").click()
        page.wait_for_timeout(500)

        # Verify Task A is active
        assert "pomo-active" in (cards.first.get_attribute("class") or "")
        title_a = page.locator("#pomoTaskTitle").text_content()
        assert "Task A" in title_a

        # Start timer on Task B
        cards.nth(1).hover()
        page.wait_for_timeout(200)
        cards.nth(1).locator(".today-card-pomo").click()
        page.wait_for_timeout(500)

        # Verify timer switched to Task B
        title_b = page.locator("#pomoTaskTitle").text_content()
        assert "Task B" in title_b

        # Verify Task A no longer has pomo-active
        card_a_class = cards.first.get_attribute("class") or ""
        assert "pomo-active" not in card_a_class

        # Verify Task B has pomo-active
        card_b_class = cards.nth(1).get_attribute("class") or ""
        assert "pomo-active" in card_b_class


class TestPomoPhaseTransition:
    """Test 5: Phase transition from work to break."""

    def test_work_to_break_transition(self, page):
        clear_tasks()
        seed_tasks({"tasks": [{"id": "t1", "title": "Phase Task", "project": "", "priority": "med", "status": "today", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []}]})
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        # Start timer
        card = page.locator(".today-card").first
        card.hover()
        page.wait_for_timeout(200)
        page.click(".today-card-pomo")
        page.wait_for_timeout(500)

        # Force remaining to 2 seconds to trigger quick transition
        page.evaluate("pomo.remaining = 2")
        page.wait_for_timeout(3000)

        # Verify phase changed to break
        phase = page.locator("#pomoPhase").text_content()
        assert phase == "break"

        # Verify timer bar has .break class
        timer = page.locator("#pomoTimer")
        timer_class = timer.get_attribute("class") or ""
        assert "break" in timer_class
