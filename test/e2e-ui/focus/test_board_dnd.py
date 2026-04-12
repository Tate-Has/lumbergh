"""Tests for kanban board drag-and-drop between columns."""
from conftest import seed_tasks, read_tasks, make_task, BASE_URL


class TestBoardDnD:
    def test_drag_backlog_to_in_progress(self, page):
        """Drag a card from Backlog to In Progress and verify status update."""
        seed_tasks({"tasks": [make_task("DnD Task", status="backlog")]})
        page.goto(BASE_URL)
        # Expand backlog column
        page.evaluate("localStorage.setItem('backlogCollapsed', 'false')")
        page.reload()
        page.wait_for_timeout(500)

        source = page.locator('.kanban-card[data-task-id="test-dnd-task"]')
        source.wait_for(state='visible', timeout=5000)

        # Target: the col-cards div for in-progress column
        target = page.locator('[data-status="in-progress"].col-cards')
        source.drag_to(target)

        # Wait for save
        with page.expect_response(
            lambda r: '/api/focus/tasks' in r.url and r.request.method == 'POST',
            timeout=3000
        ):
            pass

        data = read_tasks()
        task = next(t for t in data['tasks'] if t['id'] == 'test-dnd-task')
        assert task['status'] == 'in-progress', \
            f"Expected status 'in-progress', got '{task['status']}'"

    def test_drag_in_progress_to_review(self, page):
        """Drag a card from In Progress to Review and verify status update."""
        seed_tasks({"tasks": [make_task("Review Task", status="in-progress")]})
        page.goto(BASE_URL)
        page.wait_for_timeout(500)

        source = page.locator('.kanban-card[data-task-id="test-review-task"]')
        source.wait_for(state='visible', timeout=5000)

        target = page.locator('[data-status="review"].col-cards')
        source.drag_to(target)

        with page.expect_response(
            lambda r: '/api/focus/tasks' in r.url and r.request.method == 'POST',
            timeout=3000
        ):
            pass

        data = read_tasks()
        task = next(t for t in data['tasks'] if t['id'] == 'test-review-task')
        assert task['status'] == 'review', \
            f"Expected status 'review', got '{task['status']}'"

    def test_drag_to_collapsed_backlog(self, page):
        """Dragging a card onto a collapsed backlog column moves it to backlog."""
        seed_tasks({"tasks": [make_task("Drop To Backlog", status="in-progress")]})
        page.goto(BASE_URL)
        # Keep backlog collapsed (default)
        page.evaluate("localStorage.setItem('backlogCollapsed', 'true')")
        page.reload()
        page.wait_for_timeout(500)

        source = page.locator('.kanban-card[data-task-id="test-drop-to-backlog"]')
        source.wait_for(state='visible', timeout=5000)

        # Collapsed column has data-status and class collapsed-col
        collapsed_backlog = page.locator('.collapsed-col[data-status="backlog"]')
        collapsed_backlog.wait_for(state='visible', timeout=3000)

        source.drag_to(collapsed_backlog)

        with page.expect_response(
            lambda r: '/api/focus/tasks' in r.url and r.request.method == 'POST',
            timeout=3000
        ):
            pass

        data = read_tasks()
        task = next(t for t in data['tasks'] if t['id'] == 'test-drop-to-backlog')
        assert task['status'] == 'backlog', \
            f"Expected status 'backlog', got '{task['status']}'"
