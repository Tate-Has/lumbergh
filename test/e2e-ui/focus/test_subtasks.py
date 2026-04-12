"""Tests for subtasks/checklist feature: parser, progress bar, and modal editing."""
import time
import pytest
from conftest import BASE_URL, seed_tasks, clear_tasks, read_tasks, make_task


SUBTASK_TASK = {"tasks": [
    make_task("Task with subtasks", project="TestProj", priority="med", status="backlog",
              task_id="t1", subtasks=[
                  {"text": "First subtask", "done": False},
                  {"text": "Second subtask done", "done": True},
                  {"text": "Third subtask", "done": False},
                  {"text": "Fourth subtask done", "done": True},
              ]),
]}

SUBTASK_TODAY = {"tasks": [
    make_task("Today task with subtasks", project="TestProj", priority="high", status="today",
              task_id="t1", subtasks=[
                  {"text": "Write tests", "done": False},
                  {"text": "Implement feature", "done": True},
                  {"text": "Code review", "done": True},
              ]),
]}

SUBTASK_ROUNDTRIP = {"tasks": [
    make_task("Roundtrip task", project="RoundTrip", priority="med", status="backlog",
              task_id="t1", blocker="someone", subtasks=[
                  {"text": "Unchecked item", "done": False},
                  {"text": "Checked item", "done": True},
              ]),
]}

NO_SUBTASK = {"tasks": [
    make_task("Task without subtasks", project="Proj", priority="med", status="backlog",
              task_id="t1"),
]}


class TestSubtaskParsing:
    """Test that subtasks are correctly parsed from task data and shown on cards."""

    def test_parse_subtasks_progress_bar_on_kanban(self, page):
        """Seed task with subtask lines, verify kanban card shows progress bar."""
        seed_tasks(SUBTASK_TASK)
        page.goto(BASE_URL)

        # Expand backlog so the card is visible
        page.evaluate("localStorage.setItem('backlogCollapsed', 'false')")
        page.reload()
        page.wait_for_selector('.kanban-card')

        # Find the progress bar on the kanban card
        progress = page.locator('.kanban-card .subtask-progress')
        assert progress.count() >= 1, "Expected at least one subtask progress bar on kanban card"
        assert progress.first.is_visible()

    def test_progress_bar_correct_fraction(self, page):
        """Seed task with 2/4 subtasks done, verify '2/4' text appears."""
        seed_tasks(SUBTASK_TASK)
        page.goto(BASE_URL)

        page.evaluate("localStorage.setItem('backlogCollapsed', 'false')")
        page.reload()
        page.wait_for_selector('.kanban-card')

        count_el = page.locator('.kanban-card .subtask-count')
        assert count_el.count() >= 1, "Expected subtask count element"
        count_text = count_el.first.text_content().strip()
        assert count_text == "2/4", f"Expected '2/4' but got '{count_text}'"

    def test_no_progress_bar_without_subtasks(self, page):
        """Task without subtasks should not show a progress bar."""
        seed_tasks(NO_SUBTASK)
        page.goto(BASE_URL)

        page.evaluate("localStorage.setItem('backlogCollapsed', 'false')")
        page.reload()
        page.wait_for_selector('.kanban-card')

        progress = page.locator('.kanban-card .subtask-progress')
        assert progress.count() == 0, "No progress bar expected for task without subtasks"

    def test_progress_bar_on_today_card(self, page):
        """Today card with subtasks should show progress bar."""
        seed_tasks(SUBTASK_TODAY)
        page.goto(BASE_URL)
        page.wait_for_selector('.today-card')

        progress = page.locator('.today-card .subtask-progress')
        assert progress.count() >= 1, "Expected subtask progress bar on today card"

        count_el = page.locator('.today-card .subtask-count')
        count_text = count_el.first.text_content().strip()
        assert count_text == "2/3", f"Expected '2/3' but got '{count_text}'"


class TestSubtaskEditModal:
    """Test subtask editing in the task modal."""

    def test_modal_shows_subtasks(self, page):
        """Open edit modal for task with subtasks, verify subtask rows appear."""
        seed_tasks(SUBTASK_TASK)
        page.goto(BASE_URL)

        page.evaluate("localStorage.setItem('backlogCollapsed', 'false')")
        page.reload()
        page.wait_for_selector('.kanban-card')

        # Click the card to open the edit modal
        page.locator('.kanban-card').first.click()
        page.wait_for_selector('.modal-overlay.active')

        # Check that subtask rows exist in the modal
        subtask_rows = page.locator('.subtask-row')
        assert subtask_rows.count() == 4, f"Expected 4 subtask rows, got {subtask_rows.count()}"

        # Verify text of first subtask
        first_text = subtask_rows.nth(0).locator('.subtask-text').input_value()
        assert first_text == "First subtask", f"Expected 'First subtask', got '{first_text}'"

        # Verify checked state of second subtask (should be checked)
        second_check = subtask_rows.nth(1).locator('.subtask-check')
        assert second_check.is_checked(), "Second subtask should be checked"

        # Verify first subtask is unchecked
        first_check = subtask_rows.nth(0).locator('.subtask-check')
        assert not first_check.is_checked(), "First subtask should not be checked"

    def test_add_subtask_in_modal(self, page):
        """Add a new subtask in modal, save, verify it persists."""
        seed_tasks(SUBTASK_TASK)
        page.goto(BASE_URL)

        page.evaluate("localStorage.setItem('backlogCollapsed', 'false')")
        page.reload()
        page.wait_for_selector('.kanban-card')

        # Open the edit modal
        page.locator('.kanban-card').first.click()
        page.wait_for_selector('.modal-overlay.active')

        # Type a new subtask
        new_input = page.locator('#modalNewSubtask')
        new_input.fill('Brand new subtask')

        # Click the add button
        page.locator('#modalAddSubtask').click()
        page.wait_for_timeout(200)

        # Verify new row appeared
        subtask_rows = page.locator('.subtask-row')
        assert subtask_rows.count() == 5, f"Expected 5 subtask rows after adding, got {subtask_rows.count()}"

        # Save
        with page.expect_response(lambda r: '/api/focus/tasks' in r.url and r.request.method == 'POST', timeout=3000):
            page.locator('#modalSave').click()

        # Read tasks and verify
        data = read_tasks()
        task = next(t for t in data['tasks'] if 'Task with subtasks' in t['title'])
        assert any(s['text'] == 'Brand new subtask' and not s['done'] for s in task['subtasks']), \
            f"New subtask not found in tasks: {task['subtasks']}"

    def test_toggle_subtask_in_modal(self, page):
        """Check/uncheck a subtask, save, verify change persists."""
        seed_tasks(SUBTASK_TASK)
        page.goto(BASE_URL)

        page.evaluate("localStorage.setItem('backlogCollapsed', 'false')")
        page.reload()
        page.wait_for_selector('.kanban-card')

        # Open the edit modal
        page.locator('.kanban-card').first.click()
        page.wait_for_selector('.modal-overlay.active')

        # Toggle the first subtask (unchecked -> checked)
        first_check = page.locator('.subtask-row').nth(0).locator('.subtask-check')
        assert not first_check.is_checked()
        first_check.check()
        page.wait_for_timeout(100)

        # Save
        with page.expect_response(lambda r: '/api/focus/tasks' in r.url and r.request.method == 'POST', timeout=3000):
            page.locator('#modalSave').click()

        # Read tasks and verify the first subtask is now checked
        data = read_tasks()
        task = next(t for t in data['tasks'] if 'Task with subtasks' in t['title'])
        assert any(s['text'] == 'First subtask' and s['done'] for s in task['subtasks']), \
            f"First subtask should be checked: {task['subtasks']}"

    def test_delete_subtask_in_modal(self, page):
        """Delete a subtask, save, verify it's gone."""
        seed_tasks(SUBTASK_TASK)
        page.goto(BASE_URL)

        page.evaluate("localStorage.setItem('backlogCollapsed', 'false')")
        page.reload()
        page.wait_for_selector('.kanban-card')

        # Open the edit modal
        page.locator('.kanban-card').first.click()
        page.wait_for_selector('.modal-overlay.active')

        # Verify 4 rows initially
        assert page.locator('.subtask-row').count() == 4

        # Delete the first subtask
        page.locator('.subtask-row').nth(0).locator('.subtask-delete').click()
        page.wait_for_timeout(200)

        # Verify 3 rows remain
        assert page.locator('.subtask-row').count() == 3

        # Save
        with page.expect_response(lambda r: '/api/focus/tasks' in r.url and r.request.method == 'POST', timeout=3000):
            page.locator('#modalSave').click()

        # Read tasks and verify first subtask is gone
        data = read_tasks()
        task = next(t for t in data['tasks'] if 'Task with subtasks' in t['title'])
        assert not any(s['text'] == 'First subtask' for s in task['subtasks']), \
            f"First subtask should have been deleted: {task['subtasks']}"
        assert any(s['text'] == 'Second subtask done' and s['done'] for s in task['subtasks']), \
            "Second subtask should remain"

    def test_subtask_roundtrip(self, page):
        """Seed with subtasks + blocker, save, re-read, verify format preserved."""
        seed_tasks(SUBTASK_ROUNDTRIP)
        page.goto(BASE_URL)
        page.wait_for_timeout(300)

        # Clear any stale cache and expand backlog
        page.evaluate("localStorage.clear()")
        page.evaluate("localStorage.setItem('backlogCollapsed', 'false')")
        page.reload()
        page.wait_for_timeout(1000)

        # The task is in backlog; verify it shows up
        kanban_cards = page.locator('.kanban-card')
        kanban_cards.first.wait_for(state='visible', timeout=10000)

        # Open edit modal and save without changes to trigger a round-trip
        kanban_cards.first.click()
        page.wait_for_selector('.modal-overlay.active')
        with page.expect_response(lambda r: '/api/focus/tasks' in r.url and r.request.method == 'POST', timeout=3000):
            page.locator('#modalSave').click()

        # Read the saved tasks
        data = read_tasks()

        # Verify blocker is preserved
        task = next(t for t in data['tasks'] if t['title'] == 'Roundtrip task')
        assert task['blocker'] == 'someone', f"Blocker not preserved: {task}"

        # Verify subtasks are preserved with correct format
        assert any(s['text'] == 'Unchecked item' and not s['done'] for s in task['subtasks']), \
            f"Unchecked subtask not preserved: {task['subtasks']}"
        assert any(s['text'] == 'Checked item' and s['done'] for s in task['subtasks']), \
            f"Checked subtask not preserved: {task['subtasks']}"

        # Verify task title and priority are preserved
        assert task['project'] == 'RoundTrip', f"Project not preserved: {task}"
        assert task['priority'] == 'med', f"Priority not preserved: {task}"

    def test_add_multiple_subtasks_survives_poll(self, page):
        """Add two subtasks with a gap long enough for poll to fire; both must persist.

        Regression: poll replaced tasks array and regenerated IDs, orphaning
        editingTaskId so the second add silently failed.
        """
        seed_tasks(NO_SUBTASK)
        page.goto(BASE_URL)

        page.evaluate("localStorage.setItem('backlogCollapsed', 'false')")
        page.reload()
        page.wait_for_selector('.kanban-card')

        # Open edit modal
        page.locator('.kanban-card').first.click()
        page.wait_for_selector('.modal-overlay.active')

        # Add first subtask
        page.locator('#modalNewSubtask').fill('First subtask')
        page.locator('#modalAddSubtask').click()
        page.wait_for_timeout(200)
        assert page.locator('.subtask-row').count() == 1

        # Wait long enough for the 3s poll cycle to fire
        page.wait_for_timeout(4000)

        # Add second subtask
        page.locator('#modalNewSubtask').fill('Second subtask')
        page.locator('#modalAddSubtask').click()
        page.wait_for_timeout(200)
        assert page.locator('.subtask-row').count() == 2, "Second subtask row should appear"

        # Save and verify both persist
        with page.expect_response(lambda r: '/api/focus/tasks' in r.url and r.request.method == 'POST', timeout=3000):
            page.locator('#modalSave').click()

        data = read_tasks()
        task = next(t for t in data['tasks'] if 'Task without subtasks' in t['title'])
        assert any(s['text'] == 'First subtask' for s in task['subtasks']), \
            f"First subtask missing: {task['subtasks']}"
        assert any(s['text'] == 'Second subtask' for s in task['subtasks']), \
            f"Second subtask missing: {task['subtasks']}"
