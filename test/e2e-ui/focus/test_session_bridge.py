"""Tests for Phase 15: Production Session Bridge."""
import pytest
from conftest import BASE_URL, seed_tasks, clear_tasks, read_tasks, make_task


# Sample data: today task with no session
TASKS_NO_SESSION = {"tasks": [
    make_task("Fix auth flow", project="WW", priority="high", status="today", task_id="t1"),
    make_task("Quick task", priority="med", status="today", task_id="t2"),
    make_task("Background indexing", project="DLL", priority="med", status="running",
              check_in_note="running fine", task_id="t3"),
    make_task("Waiting on API key", project="Mitsui", priority="low", status="waiting",
              blocker="Sandeep has the key", task_id="t4"),
]}

# Sample data: today task with session linked
TASKS_WITH_SESSION = {"tasks": [
    make_task("Fix auth flow", project="WW", priority="high", status="today",
              session_name="fix-auth-flow", session_status="working", task_id="t1"),
    make_task("Quick task", priority="med", status="today", task_id="t2"),
    make_task("Background indexing", project="DLL", priority="med", status="running",
              check_in_note="running fine", session_name="dll-indexing",
              session_status="idle", task_id="t3"),
]}


class TestSessionDataRoundTrip:
    """Verify session fields persist through parse/serialize cycle."""

    def test_session_name_roundtrip(self, page):
        """session_name field survives save/reload."""
        seed_tasks(TASKS_WITH_SESSION)
        page.goto(BASE_URL)
        page.wait_for_selector('.today-card')
        # Wait for auto-save
        page.wait_for_timeout(1000)

        data = read_tasks()
        task = next(t for t in data['tasks'] if 'Fix auth flow' in t['title'])
        assert task['session_name'] == 'fix-auth-flow', f"session_name missing: {task}"

    def test_session_status_roundtrip(self, page):
        """session_status field survives save/reload."""
        seed_tasks(TASKS_WITH_SESSION)
        page.goto(BASE_URL)
        page.wait_for_selector('.today-card')
        page.wait_for_timeout(1000)

        data = read_tasks()
        task = next(t for t in data['tasks'] if 'Fix auth flow' in t['title'])
        assert task['session_status'] == 'working', f"session_status missing: {task}"

    def test_session_fields_on_inflight_card(self, page):
        """session fields on running tasks survive roundtrip."""
        seed_tasks(TASKS_WITH_SESSION)
        page.goto(BASE_URL)
        page.wait_for_selector('.session-card')
        page.wait_for_timeout(1000)

        data = read_tasks()
        task = next(t for t in data['tasks'] if 'Background indexing' in t['title'])
        assert task['session_name'] == 'dll-indexing', f"session on inflight missing: {task}"
        assert task['session_status'] == 'idle', f"session_status on inflight missing: {task}"

    def test_tasks_without_session_unaffected(self, page):
        """Tasks without session fields don't get empty session lines."""
        seed_tasks(TASKS_NO_SESSION)
        page.goto(BASE_URL)
        page.wait_for_selector('.today-card')
        page.wait_for_timeout(1000)

        data = read_tasks()
        today_tasks = [t for t in data['tasks'] if t['status'] == 'today']
        assert all(t['session_name'] == '' for t in today_tasks), \
            f"Unexpected session field: {today_tasks}"
        assert all(t['session_status'] == '' for t in today_tasks), \
            f"Unexpected session_status field: {today_tasks}"


class TestLaunchButtonRendering:
    """Verify launch buttons appear on cards."""

    def test_launch_button_on_today_card(self, page):
        """Today cards should have a launch button."""
        seed_tasks(TASKS_NO_SESSION)
        page.goto(BASE_URL)
        page.wait_for_selector('.today-card')

        buttons = page.locator('.today-card-launch')
        assert buttons.count() == 2, f"Expected 2 launch buttons, got {buttons.count()}"

    def test_launch_button_on_inflight_card(self, page):
        """In-Flight cards should have a launch button."""
        seed_tasks(TASKS_NO_SESSION)
        page.goto(BASE_URL)
        page.wait_for_selector('.session-card')

        buttons = page.locator('.session-card-launch')
        assert buttons.count() == 2, f"Expected 2 launch buttons (running+waiting), got {buttons.count()}"

    def test_launch_button_linked_class(self, page):
        """Launch button gets 'linked' class when session is set."""
        seed_tasks(TASKS_WITH_SESSION)
        page.goto(BASE_URL)
        page.wait_for_selector('.today-card')

        linked = page.locator('.today-card-launch.linked')
        assert linked.count() == 1, f"Expected 1 linked launch button, got {linked.count()}"

    def test_launch_button_visible_on_hover(self, page):
        """Launch button becomes visible when hovering a today card."""
        seed_tasks(TASKS_NO_SESSION)
        page.goto(BASE_URL)
        page.wait_for_selector('.today-card')

        btn = page.locator('.today-card-launch').first
        # Initially hidden (opacity 0)
        opacity_before = btn.evaluate("el => getComputedStyle(el).opacity")
        assert opacity_before == '0', f"Button should be hidden initially, got opacity {opacity_before}"

        # Hover the card
        page.locator('.today-card').first.hover()
        page.wait_for_timeout(200)
        opacity_after = btn.evaluate("el => getComputedStyle(el).opacity")
        assert opacity_after == '1', f"Button should be visible on hover, got opacity {opacity_after}"


class TestSessionModal:
    """Verify the session creation modal."""

    def test_launch_opens_session_modal(self, page):
        """Clicking launch on a card without session opens the session modal."""
        seed_tasks(TASKS_NO_SESSION)
        page.goto(BASE_URL)
        page.wait_for_selector('.today-card')

        page.locator('.today-card').first.hover()
        page.wait_for_timeout(200)
        page.locator('.today-card-launch').first.click()
        page.wait_for_selector('[data-testid="create-session-modal-overlay"].active')

        modal = page.locator('[data-testid="create-session-modal-overlay"]')
        assert modal.is_visible(), "Session modal should be visible"

    def test_session_modal_prefills_task_title(self, page):
        """Session modal description should be pre-filled with task title."""
        seed_tasks(TASKS_NO_SESSION)
        page.goto(BASE_URL)
        page.wait_for_selector('.today-card')

        page.locator('.today-card').first.hover()
        page.wait_for_timeout(200)
        page.locator('.today-card-launch').first.click()
        page.wait_for_selector('[data-testid="create-session-modal-overlay"].active')

        desc = page.locator('[data-testid="session-description-input"]').input_value()
        assert 'Fix auth flow' in desc, f"Expected task title in description, got: {desc}"

        task_name = page.locator('.session-task-name').text_content()
        assert 'Fix auth flow' in task_name, f"Expected task name display, got: {task_name}"

    def test_mode_toggle_shows_correct_fields(self, page):
        """Mode toggle switches between existing/new/worktree forms."""
        seed_tasks(TASKS_NO_SESSION)
        page.goto(BASE_URL)
        page.wait_for_selector('.today-card')

        page.locator('.today-card').first.hover()
        page.wait_for_timeout(200)
        page.locator('.today-card-launch').first.click()
        page.wait_for_selector('[data-testid="create-session-modal-overlay"].active')

        # Existing mode is active by default — button should exist and show "Existing Repo"
        existing_btn = page.locator('[data-mode="existing"]')
        assert existing_btn.count() == 1, "Existing mode button should be present"
        assert 'Existing Repo' in existing_btn.text_content()

        # Click new mode — project name input should appear
        page.locator('[data-mode="new"]').click()
        page.wait_for_timeout(200)
        assert page.locator('[data-testid="project-name-input"]').is_visible(), \
            "Project name input should appear in New Repo mode"

        # Click worktree mode — "Parent Repository" label should appear
        page.locator('[data-mode="worktree"]').click()
        page.wait_for_timeout(200)
        assert page.locator('text=Parent Repository').is_visible(), \
            "Parent Repository label should appear in Worktree mode"

        # Click back to existing — "Working Directory" label should appear
        page.locator('[data-mode="existing"]').click()
        page.wait_for_timeout(200)
        assert page.locator('text=Working Directory').is_visible(), \
            "Working Directory label should appear in Existing mode"

    def test_create_session_links_task(self, page):
        """Clicking Create Session sets session_name on the task."""
        # Mock Lumbergh API endpoints
        page.route('**localhost:8420/api/settings', lambda route: route.fulfill(
            status=200,
            content_type='application/json',
            body='{"repoSearchDir": "/home/user/src", "agentProviders": {}, "defaultAgent": "", "tabVisibility": {}}'
        ))
        page.route('**localhost:8420/api/sessions', lambda route: route.fulfill(
            status=200,
            content_type='application/json',
            body='{"name": "fix-auth-flow", "status": "working"}'
        ) if route.request.method == 'POST' else route.continue_())
        page.route('**localhost:8420/api/directories/validate**', lambda route: route.fulfill(
            status=200,
            content_type='application/json',
            body='{"exists": true}'
        ))

        seed_tasks(TASKS_NO_SESSION)
        page.goto(BASE_URL)
        page.wait_for_selector('.today-card')

        page.locator('.today-card').first.hover()
        page.wait_for_timeout(200)
        page.locator('.today-card-launch').first.click()
        page.wait_for_selector('[data-testid="create-session-modal-overlay"].active')

        # Switch to manual entry and enter a path
        page.locator('text=Enter path manually').click()
        page.wait_for_timeout(200)
        page.locator('[data-testid="workdir-input"]').fill('/home/user/src/fix-auth-flow')
        page.wait_for_timeout(600)  # Wait for debounced validation

        with page.expect_response(lambda r: '/api/focus/tasks' in r.url and r.request.method == 'POST', timeout=5000):
            page.locator('[data-testid="create-session-submit"]').click()

        # Modal should close
        page.wait_for_timeout(300)
        assert not page.locator('[data-testid="create-session-modal-overlay"]').is_visible()

        # Session name should be saved on the task
        data = read_tasks()
        task = next(t for t in data['tasks'] if 'Fix auth flow' in t['title'])
        assert task['session_name'] != '', f"session_name not saved: {task}"

    def test_cancel_closes_modal(self, page):
        """Cancel button closes the session modal without changes."""
        seed_tasks(TASKS_NO_SESSION)
        page.goto(BASE_URL)
        page.wait_for_selector('.today-card')

        page.locator('.today-card').first.hover()
        page.wait_for_timeout(200)
        page.locator('.today-card-launch').first.click()
        page.wait_for_selector('[data-testid="create-session-modal-overlay"].active')

        page.locator('[data-testid="create-session-modal-overlay"] button:has-text("Cancel")').click()
        page.wait_for_timeout(300)

        assert not page.locator('[data-testid="create-session-modal-overlay"]').is_visible()
        data = read_tasks()
        today_tasks = [t for t in data['tasks'] if t['status'] == 'today']
        assert all(t['session_name'] == '' for t in today_tasks), \
            "No session should be created on cancel"


class TestStatusDisplay:
    """Verify session status badges render correctly."""

    def test_no_status_without_session(self, page):
        """Cards without session_name show no session badge."""
        seed_tasks(TASKS_NO_SESSION)
        page.goto(BASE_URL)
        page.wait_for_selector('.today-card')

        badges = page.locator('.session-badge')
        assert badges.count() == 0, f"Expected 0 session badges, got {badges.count()}"
