"""Tests for Phase 05: Activity Log — completed_date field and archive date grouping."""
import time

import pytest
from conftest import BASE_URL, seed_tasks, seed_archive, clear_tasks, clear_archive, clear_localstorage, read_tasks, read_archive


class TestCompletedDateSetOnDone:
    """Test 1: completed_date is set when task status changes to done via edit modal."""

    def test_completed_date_set_via_edit_modal(self, page):
        clear_tasks()
        seed_tasks({"tasks": [{"id": "t1", "title": "Test Task", "project": "", "priority": "med", "status": "inbox", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []}]})
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        # Open the inbox to see the task
        page.click(".inbox-header")
        page.wait_for_timeout(300)

        # Click the promote arrow to open edit modal
        page.click('.promote-btn')
        page.wait_for_timeout(300)

        # Change status to done
        page.select_option("#modalTaskStatus", "done")
        page.wait_for_timeout(100)

        # Save
        with page.expect_response(lambda r: '/api/focus/tasks' in r.url and r.request.method == 'POST', timeout=3000):
            page.click("#modalSave")

        # Check tasks JSON
        data = read_tasks()
        done_tasks = [t for t in data['tasks'] if t['status'] == 'done']
        assert len(done_tasks) > 0
        today = time.strftime("%Y-%m-%d")
        assert done_tasks[0]['completed_date'] == today


class TestCompletedDateClearedOnUndone:
    """Test 2: completed_date is cleared when task moves out of done."""

    def test_completed_date_cleared_via_edit_modal(self, page):
        today = time.strftime("%Y-%m-%d")
        clear_tasks()
        seed_tasks({"tasks": [{"id": "t1", "title": "Done Task", "project": "", "priority": "med", "status": "done", "completed": True, "completed_date": today, "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []}]})
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        # Expand the done column by clicking it
        # The done column is collapsed by default, click to expand
        done_col = page.locator('.board-col.collapsed-col').last
        done_col.click()
        page.wait_for_timeout(300)

        # Click the task card to open edit modal
        page.click('.kanban-card')
        page.wait_for_timeout(300)

        # Change status to backlog
        page.select_option("#modalTaskStatus", "backlog")
        page.wait_for_timeout(100)

        # Save
        with page.expect_response(lambda r: '/api/focus/tasks' in r.url and r.request.method == 'POST', timeout=3000):
            page.click("#modalSave")

        # Check tasks JSON
        data = read_tasks()
        task = data['tasks'][0]
        assert task['completed_date'] == ''


class TestArchiveDateGrouping:
    """Test 3: Archive creates date-grouped output."""

    def test_archive_groups_by_completed_date(self, page):
        clear_tasks()
        clear_archive()
        seed_tasks({"tasks": [
            {"id": "t1", "title": "Task A", "project": "ProjectA", "priority": "high", "status": "done", "completed": True, "completed_date": "2026-04-05", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
            {"id": "t2", "title": "Task B", "project": "ProjectB", "priority": "med", "status": "done", "completed": True, "completed_date": "2026-04-06", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
        ]})
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        # Expand the done column
        done_col = page.locator('.board-col.collapsed-col').last
        done_col.click()
        page.wait_for_timeout(300)

        # Click the archive button (triggers a custom ConfirmDialog, not a native browser dialog)
        page.click('#archiveDoneBtn')
        page.wait_for_selector('#confirmDialogConfirm', state='visible', timeout=2000)

        # Confirm via the custom dialog
        with page.expect_response(lambda r: '/api/focus/archive' in r.url and r.request.method in ('POST', 'PUT'), timeout=3000):
            page.click('#confirmDialogConfirm')

        # Read archive JSON
        data = read_archive()
        dates = set(t['archived_date'] for t in data['tasks'])
        assert '2026-04-06' in dates
        assert '2026-04-05' in dates
        assert any(t['title'] == 'Task A' for t in data['tasks'])
        assert any(t['title'] == 'Task B' for t in data['tasks'])
        # Task B (2026-04-06) should come before Task A (2026-04-05) since newer tasks are prepended
        task_b_idx = next(i for i, t in enumerate(data['tasks']) if t['title'] == 'Task B')
        task_a_idx = next(i for i, t in enumerate(data['tasks']) if t['title'] == 'Task A')
        assert task_b_idx < task_a_idx


class TestArchiveViewerRendersHTML:
    """Test 4: Archive viewer renders structured HTML, not raw text."""

    def test_archive_viewer_has_structured_elements(self, page):
        clear_tasks()
        clear_archive()

        # Write new-format archive content
        seed_archive({"tasks": [
            {"title": "Some Task", "project": "Project", "priority": "high", "blocker": "", "check_in_note": "", "archived_date": "2026-04-07"},
            {"title": "Another Task", "project": "Project", "priority": "med", "blocker": "", "check_in_note": "", "archived_date": "2026-04-07"},
        ], "notes": []})

        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        # Open archive modal
        page.click("#archiveBtn")
        page.wait_for_timeout(500)

        # Verify structured HTML elements exist (Phase 07 redesigned modal)
        assert page.locator(".archive-date-header").count() >= 1
        assert page.locator(".archive-task").count() >= 2


class TestArchiveViewerBackwardCompat:
    """Test 5: Archive viewer handles old format gracefully."""

    def test_old_format_renders_without_errors(self, page):
        clear_tasks()
        clear_archive()

        # Seed with JSON archive data (what was previously old-format markdown)
        seed_archive({"tasks": [
            {"title": "Old task one", "project": "ProjectX", "priority": "", "blocker": "", "check_in_note": "", "archived_date": "2026-04-01"},
            {"title": "Old task two", "project": "ProjectY", "priority": "", "blocker": "", "check_in_note": "", "archived_date": "2026-04-01"},
        ], "notes": []})

        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        # Open archive modal
        page.click("#archiveBtn")
        page.wait_for_timeout(500)

        # Should render date sections and tasks without error (Phase 07 redesigned modal)
        assert page.locator(".archive-date-header").count() >= 1
        assert page.locator(".archive-task").count() >= 2


class TestTodayCheckCircleSetsDate:
    """Test 6: Today check circle sets completed_date."""

    def test_check_circle_sets_completed_date(self, page):
        clear_tasks()
        seed_tasks({"tasks": [{"id": "t1", "title": "Check Me", "project": "", "priority": "med", "status": "today", "completed": False, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []}]})
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        # Click the check circle on the today card
        with page.expect_response(lambda r: '/api/focus/tasks' in r.url and r.request.method == 'POST', timeout=3000):
            page.click(".today-card .check-icon")

        # Check tasks JSON
        data = read_tasks()
        done_tasks = [t for t in data['tasks'] if t['status'] == 'done']
        assert len(done_tasks) > 0
        today = time.strftime("%Y-%m-%d")
        assert done_tasks[0]['completed_date'] == today
