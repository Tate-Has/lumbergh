"""Tests for task deletion via the task modal."""
from conftest import seed_tasks, read_tasks, make_task, BASE_URL


class TestTaskDeletion:
    def test_delete_from_modal_backlog(self, page):
        """Delete a backlog task using the modal Delete button."""
        seed_tasks({"tasks": [make_task("Delete Me", status="backlog")]})
        page.goto(BASE_URL)
        # Expand backlog so the card is visible
        page.evaluate("localStorage.setItem('backlogCollapsed', 'false')")
        page.reload()
        page.wait_for_timeout(500)

        # Click the kanban card to open the edit modal
        card = page.locator('.kanban-card[data-task-id="test-delete-me"]')
        card.wait_for(state='visible', timeout=5000)
        card.click()
        page.wait_for_selector('.modal-overlay.active', timeout=3000)

        # Click Delete — no confirm dialog for task deletion
        with page.expect_response(
            lambda r: '/api/focus/tasks' in r.url and r.request.method == 'POST',
            timeout=3000
        ):
            page.click('#modalDelete')

        page.wait_for_timeout(300)
        data = read_tasks()
        ids = [t['id'] for t in data['tasks']]
        assert 'test-delete-me' not in ids, \
            f"Task 'test-delete-me' should have been deleted, but still in tasks: {ids}"

    def test_delete_only_task(self, page):
        """Deleting the only task should leave an empty task list."""
        seed_tasks({"tasks": [make_task("Only One", status="backlog")]})
        page.goto(BASE_URL)
        page.evaluate("localStorage.setItem('backlogCollapsed', 'false')")
        page.reload()
        page.wait_for_timeout(500)

        card = page.locator('.kanban-card[data-task-id="test-only-one"]')
        card.wait_for(state='visible', timeout=5000)
        card.click()
        page.wait_for_selector('.modal-overlay.active', timeout=3000)

        with page.expect_response(
            lambda r: '/api/focus/tasks' in r.url and r.request.method == 'POST',
            timeout=3000
        ):
            page.click('#modalDelete')

        page.wait_for_timeout(300)
        data = read_tasks()
        assert len(data['tasks']) == 0, \
            f"Expected empty task list after deleting only task, got: {data['tasks']}"

    def test_delete_preserves_other_tasks(self, page):
        """Deleting one task should leave other tasks intact."""
        seed_tasks({"tasks": [
            make_task("Keep Me", status="backlog"),
            make_task("Delete Me Too", status="backlog"),
        ]})
        page.goto(BASE_URL)
        page.evaluate("localStorage.setItem('backlogCollapsed', 'false')")
        page.reload()
        page.wait_for_timeout(500)

        card = page.locator('.kanban-card[data-task-id="test-delete-me-too"]')
        card.wait_for(state='visible', timeout=5000)
        card.click()
        page.wait_for_selector('.modal-overlay.active', timeout=3000)

        with page.expect_response(
            lambda r: '/api/focus/tasks' in r.url and r.request.method == 'POST',
            timeout=3000
        ):
            page.click('#modalDelete')

        page.wait_for_timeout(300)
        data = read_tasks()
        ids = [t['id'] for t in data['tasks']]
        assert 'test-delete-me-too' not in ids, "Deleted task should be gone"
        assert 'test-keep-me' in ids, "Other task should still exist"

    def test_cancel_delete_keeps_task(self, page):
        """Cancelling the modal should not delete the task."""
        seed_tasks({"tasks": [make_task("Dont Delete", status="backlog")]})
        page.goto(BASE_URL)
        page.evaluate("localStorage.setItem('backlogCollapsed', 'false')")
        page.reload()
        page.wait_for_timeout(500)

        card = page.locator('.kanban-card[data-task-id="test-dont-delete"]')
        card.wait_for(state='visible', timeout=5000)
        card.click()
        page.wait_for_selector('.modal-overlay.active', timeout=3000)

        # Cancel instead of deleting
        page.click('#modalCancel')
        page.wait_for_timeout(300)

        data = read_tasks()
        ids = [t['id'] for t in data['tasks']]
        assert 'test-dont-delete' in ids, \
            "Task should still exist after cancelling the modal"
