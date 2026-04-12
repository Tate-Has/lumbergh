"""Tests for Phase 07: Archive Improvements."""
import pytest
from conftest import BASE_URL, seed_tasks, seed_archive, clear_tasks, clear_archive, clear_localstorage, read_archive


SEED_DONE_TASKS = {"tasks": [
    {"id": "t1", "title": "Build widget", "project": "Alpha", "priority": "high", "status": "done", "completed": True, "completed_date": "", "blocker": "waiting on API", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t2", "title": "Fix login", "project": "Beta", "priority": "med", "status": "done", "completed": True, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
    {"id": "t3", "title": "Deploy hotfix", "project": "", "priority": "med", "status": "done", "completed": True, "completed_date": "", "blocker": "", "check_in_note": "", "session_name": "", "session_status": "", "subtasks": []},
]}

SEED_ARCHIVE_WITH_TODAY = lambda date: {"tasks": [
    {"title": "Existing task", "project": "OldProject", "priority": "med", "blocker": "", "check_in_note": "", "archived_date": date},
], "notes": []}

SEED_ARCHIVE_MULTI_DATE = {"tasks": [
    {"title": "Task A", "project": "Alpha", "priority": "high", "blocker": "", "check_in_note": "", "archived_date": "2026-04-07"},
    {"title": "Task B", "project": "Beta", "priority": "med", "blocker": "", "check_in_note": "", "archived_date": "2026-04-07"},
    {"title": "Task C", "project": "Alpha", "priority": "low", "blocker": "", "check_in_note": "", "archived_date": "2026-04-05"},
    {"title": "Task D", "project": "Gamma", "priority": "med", "blocker": "", "check_in_note": "", "archived_date": "2026-04-05"},
    {"title": "Solo Task", "project": "", "priority": "med", "blocker": "", "check_in_note": "", "archived_date": "2026-04-01"},
], "notes": []}

SEED_ARCHIVE_OLD_FORMAT = {"tasks": [
    {"title": "Old format task", "project": "Mitsui", "priority": "high", "blocker": "", "check_in_note": "", "archived_date": "2026-03-24"},
    {"title": "Another old task", "project": "", "priority": "med", "blocker": "", "check_in_note": "", "archived_date": "2026-03-24"},
], "notes": []}


class TestArchiveDateDedup:
    """Test 1: Archiving tasks on the same day merges under a single date header."""

    def test_archive_dedup_date_headers(self, page):
        from datetime import date
        today = date.today().isoformat()

        # Seed archive with an existing section for today
        seed_archive(SEED_ARCHIVE_WITH_TODAY(today))

        # Seed done tasks
        clear_tasks()
        seed_tasks(SEED_DONE_TASKS)
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        # Expand the Done column
        done_collapsed = page.locator('.board-col.collapsed-col >> text=Done')
        if done_collapsed.count() > 0:
            done_collapsed.click()
            page.wait_for_timeout(300)

        # Click archive button and confirm via React ConfirmDialog
        archive_btn = page.locator('#archiveDoneBtn')
        archive_btn.wait_for(state='visible', timeout=3000)
        archive_btn.click()

        confirm_dialog = page.locator('#confirmDialog')
        confirm_dialog.wait_for(state='visible', timeout=3000)
        page.locator('#confirmDialogConfirm').click()
        page.wait_for_timeout(1000)

        # Read the archive and verify tasks for today exist and existing task is preserved
        data = read_archive()
        assert "Existing task" in [t['title'] for t in data['tasks']]
        assert "Build widget" in [t['title'] for t in data['tasks']]
        assert "Fix login" in [t['title'] for t in data['tasks']]
        assert "Deploy hotfix" in [t['title'] for t in data['tasks']]


class TestArchiveButtonCount:
    """Test 2: Archive button shows count of done tasks."""

    def test_button_shows_count(self, page):
        clear_tasks()
        seed_tasks(SEED_DONE_TASKS)
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        # Expand the Done column
        done_collapsed = page.locator('.board-col.collapsed-col >> text=Done')
        if done_collapsed.count() > 0:
            done_collapsed.click()
            page.wait_for_timeout(300)

        archive_btn = page.locator('#archiveDoneBtn')
        archive_btn.wait_for(state='visible', timeout=3000)
        text = archive_btn.text_content()
        assert "(3)" in text, f"Expected count (3) in button text, got: {text}"


class TestArchiveConfirmation:
    """Test 3: Confirm dialog appears before archiving, and dismissing cancels the archive."""

    def test_dismiss_cancels_archive(self, page):
        clear_tasks()
        seed_tasks(SEED_DONE_TASKS)
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        # Expand Done column
        done_collapsed = page.locator('.board-col.collapsed-col >> text=Done')
        if done_collapsed.count() > 0:
            done_collapsed.click()
            page.wait_for_timeout(300)

        archive_btn = page.locator('#archiveDoneBtn')
        archive_btn.wait_for(state='visible', timeout=3000)
        archive_btn.click()

        # Wait for the React ConfirmDialog to appear and click Cancel
        confirm_dialog = page.locator('#confirmDialog')
        confirm_dialog.wait_for(state='visible', timeout=3000)
        page.locator('#confirmDialogCancel').click()
        page.wait_for_timeout(500)

        # Tasks should still be in the Done column
        done_cards = page.locator('.done-col .kanban-card')
        assert done_cards.count() == 3, f"Expected 3 done cards after cancel, got {done_cards.count()}"

    def test_accept_archives_tasks(self, page):
        clear_tasks()
        seed_tasks(SEED_DONE_TASKS)
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        # Expand Done column
        done_collapsed = page.locator('.board-col.collapsed-col >> text=Done')
        if done_collapsed.count() > 0:
            done_collapsed.click()
            page.wait_for_timeout(300)

        archive_btn = page.locator('#archiveDoneBtn')
        archive_btn.wait_for(state='visible', timeout=3000)
        archive_btn.click()

        # Wait for the React ConfirmDialog to appear
        confirm_dialog = page.locator('#confirmDialog')
        confirm_dialog.wait_for(state='visible', timeout=3000)

        # Verify the dialog message contains the task count
        dialog_message = page.locator('#confirmDialogMessage').text_content()
        assert "3" in dialog_message, f"Dialog message should contain count 3, got: {dialog_message}"

        # Click Confirm to proceed with archiving
        page.locator('#confirmDialogConfirm').click()
        page.wait_for_timeout(1000)

        # Done column should now be empty or collapsed
        done_cards = page.locator('.done-col .kanban-card')
        assert done_cards.count() == 0, f"Expected 0 done cards after archive, got {done_cards.count()}"


class TestArchiveSearchFilters:
    """Test 4: Search filters results in archive modal."""

    def test_search_filters_by_project(self, page):
        seed_archive(SEED_ARCHIVE_MULTI_DATE)
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        # Open archive modal
        page.click('#archiveBtn')
        page.wait_for_timeout(500)

        # Initially all tasks should be visible
        stats = page.locator('#archiveStats')
        initial_text = stats.text_content()
        assert "5 archived" in initial_text, f"Expected '5 archived' in stats, got: {initial_text}"

        # Search for "Alpha"
        search = page.locator('#archiveSearch')
        search.fill('Alpha')
        page.wait_for_timeout(400)  # Wait for debounce

        # Only Alpha tasks should show
        stats_text = stats.text_content()
        assert "2 of 5" in stats_text, f"Expected '2 of 5' in stats, got: {stats_text}"

        # Date sections without Alpha should be hidden
        visible_sections = page.locator('.archive-date-section:visible')
        assert visible_sections.count() == 2, f"Expected 2 visible date sections, got {visible_sections.count()}"


class TestArchiveSearchHighlight:
    """Test 5: Search highlights matches with <mark> tags."""

    def test_highlight_marks(self, page):
        seed_archive(SEED_ARCHIVE_MULTI_DATE)
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        page.click('#archiveBtn')
        page.wait_for_timeout(500)

        search = page.locator('#archiveSearch')
        search.fill('Beta')
        page.wait_for_timeout(400)

        # Check for mark elements
        marks = page.locator('mark.archive-highlight')
        assert marks.count() > 0, "Expected at least one <mark> highlight element"
        mark_text = marks.first.text_content()
        assert mark_text.lower() == 'beta', f"Expected highlighted text 'Beta', got: {mark_text}"


class TestCollapsibleDateSections:
    """Test 6: Click a date header to collapse/expand its task list."""

    def test_collapse_expand(self, page):
        seed_archive(SEED_ARCHIVE_MULTI_DATE)
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        page.click('#archiveBtn')
        page.wait_for_timeout(500)

        # Get the first date header
        first_header = page.locator('.archive-date-header').first
        first_list_key = first_header.get_attribute('data-toggle')

        # Task list should be visible initially
        task_list = page.locator(f'[data-list="{first_list_key}"]')
        assert task_list.is_visible(), "Task list should be visible initially"

        # Click to collapse
        first_header.click()
        page.wait_for_timeout(200)

        # Task list should be hidden
        assert not task_list.is_visible(), "Task list should be hidden after collapse"

        # Chevron should have collapsed class
        chevron = first_header.locator('.chevron')
        assert 'collapsed' in chevron.get_attribute('class'), "Chevron should have 'collapsed' class"

        # Click again to expand
        first_header.click()
        page.wait_for_timeout(200)
        assert task_list.is_visible(), "Task list should be visible after re-expand"


class TestBackwardCompatOldFormat:
    """Test 7: Old format archive (e.g., 'Tuesday, March 24, 2026') renders correctly."""

    def test_old_format_renders(self, page):
        seed_archive(SEED_ARCHIVE_OLD_FORMAT)
        clear_localstorage(page)
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        page.click('#archiveBtn')
        page.wait_for_timeout(500)

        # Should render without errors
        body = page.locator('#archiveBody')
        assert body.is_visible()

        # Should show the tasks
        tasks_visible = page.locator('.archive-task')
        assert tasks_visible.count() == 2, f"Expected 2 tasks from old format, got {tasks_visible.count()}"

        # Stats should show correct count
        stats = page.locator('#archiveStats').text_content()
        assert "2" in stats, f"Expected '2' in stats, got: {stats}"

        # Should show date section with the date parsed
        date_labels = page.locator('.archive-date-label')
        assert date_labels.count() > 0, "Expected at least one date label"
