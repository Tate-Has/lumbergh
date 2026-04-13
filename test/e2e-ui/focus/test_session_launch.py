"""Tests for Phase 15: Production Session Bridge — CreateSessionModal UX.

Covers the new CreateSessionModal component (replaces the old SessionModal).
Mocks all calls to Lumbergh at http://localhost:8420 since it won't be running.
"""
import json
import pytest
from conftest import BASE_URL, seed_tasks, clear_tasks, read_tasks, make_task, wait_for_save


# ---------------------------------------------------------------------------
# Fixtures / shared mock helpers
# ---------------------------------------------------------------------------

SETTINGS_RESPONSE = {
    "repoSearchDir": "/home/user/src",
    "agentProviders": {},
    "defaultAgent": "",
    "tabVisibility": {
        "git": True,
        "files": True,
        "todos": True,
        "prompts": True,
        "shared": True,
    },
}


def setup_lumbergh_mocks(page, session_response=None):
    """Register route mocks for all Lumbergh API calls the modal makes.

    - GET  /api/settings        → SETTINGS_RESPONSE
    - GET  /directories/search  → empty list
    - GET  /api/directories/validate → {"exists": True}
    - POST /api/sessions        → session_response (default: {"name": "test-session"})
    """
    if session_response is None:
        session_response = {"name": "test-session", "existing": False}

    def handle_settings(route):
        if route.request.method == "GET":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(SETTINGS_RESPONSE),
            )
        else:
            route.continue_()

    def handle_dir_search(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"directories": []}),
        )

    def handle_dir_validate(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"exists": True}),
        )

    def handle_sessions(route):
        if route.request.method == "POST":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(session_response),
            )
        elif route.request.method == "GET":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"sessions": []}),
            )
        else:
            route.continue_()

    page.route("**/localhost:8420/api/settings**", handle_settings)
    page.route("**/localhost:8420/directories/search**", handle_dir_search)
    page.route("**/localhost:8420/api/directories/validate**", handle_dir_validate)
    page.route("**/localhost:8420/api/sessions**", handle_sessions)


def open_create_session_modal(page, task_index=0):
    """Hover the nth today card, click launch to open picker, then Create New to open modal."""
    cards = page.locator(".today-card")
    cards.nth(task_index).hover()
    page.wait_for_timeout(200)
    cards.nth(task_index).locator(".today-card-launch").click()
    # Wait for session picker to appear
    page.locator('.session-picker').wait_for(state="visible", timeout=3000)
    # Click "Create New Session..." in the picker
    page.locator('text=Create New Session').click()
    page.locator('[data-testid="create-session-modal-overlay"]').wait_for(state="visible")


# ---------------------------------------------------------------------------
# Sample task data
# ---------------------------------------------------------------------------

TASK_NO_SESSION = make_task(
    "Fix auth flow",
    project="WW",
    priority="high",
    status="today",
    task_id="t-no-session",
)

TASK_WITH_SESSION = make_task(
    "Ongoing refactor",
    project="Core",
    priority="med",
    status="today",
    session_name="my-session",
    session_status="working",
    task_id="t-with-session",
)


# ===========================================================================
# class TestCreateSessionModal
# ===========================================================================

class TestCreateSessionModal:
    """Verify the new CreateSessionModal opens, renders, and submits correctly."""

    def test_launch_opens_create_session_modal(self, page):
        """Clicking today-card-launch on an unlinked card opens the CreateSessionModal."""
        seed_tasks({"tasks": [TASK_NO_SESSION]})
        setup_lumbergh_mocks(page)
        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        open_create_session_modal(page)

        overlay = page.locator('[data-testid="create-session-modal-overlay"]')
        assert overlay.is_visible(), "CreateSessionModal overlay should be visible after clicking launch"

    def test_modal_shows_task_title(self, page):
        """The modal shows the task title in the session-task-name element."""
        seed_tasks({"tasks": [TASK_NO_SESSION]})
        setup_lumbergh_mocks(page)
        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        open_create_session_modal(page)

        task_name_el = page.locator(".session-task-name")
        assert task_name_el.is_visible(), ".session-task-name should be visible"
        content = task_name_el.text_content()
        assert "Fix auth flow" in content, f"Expected task title in .session-task-name, got: {content!r}"

    def test_modal_prefills_description(self, page):
        """Description input is pre-filled with the task title."""
        seed_tasks({"tasks": [TASK_NO_SESSION]})
        setup_lumbergh_mocks(page)
        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        open_create_session_modal(page)

        desc_value = page.locator('[data-testid="session-description-input"]').input_value()
        assert "Fix auth flow" in desc_value, (
            f"Expected task title pre-filled in description input, got: {desc_value!r}"
        )

    def test_mode_toggle_switches_forms(self, page):
        """Mode toggle buttons switch between Existing / New / Worktree form content."""
        seed_tasks({"tasks": [TASK_NO_SESSION]})
        setup_lumbergh_mocks(page)
        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        open_create_session_modal(page)

        # Default: existing mode — DirectoryPicker search input should be present
        existing_search = page.locator('input[placeholder="Search git repositories..."]')
        assert existing_search.count() > 0, "Existing mode should show directory search input"

        # Switch to New Repo
        page.locator('[data-mode="new"]').click()
        project_name_input = page.locator('[data-testid="project-name-input"]')
        assert project_name_input.is_visible(), "New mode should show project name input"

        # Switch to Worktree
        page.locator('[data-mode="worktree"]').click()
        # Worktree mode shows a "Parent Repository" label and DirectoryPicker
        parent_repo_label = page.locator("text=Parent Repository")
        assert parent_repo_label.is_visible(), "Worktree mode should show Parent Repository label"

        # Switch back to Existing
        page.locator('[data-mode="existing"]').click()
        assert existing_search.count() > 0, "Back to Existing mode should show directory search input"

    def test_session_name_field_hidden_for_new_repo(self, page):
        """Session Name input is hidden in New Repo mode but visible in Existing mode."""
        seed_tasks({"tasks": [TASK_NO_SESSION]})
        setup_lumbergh_mocks(page)
        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        open_create_session_modal(page)

        # Existing mode: session name input IS visible
        session_name_input = page.locator('[data-testid="session-name-input"]')
        assert session_name_input.is_visible(), "Session name field should be visible in Existing mode"

        # Switch to New Repo mode: session name input should NOT be visible
        page.locator('[data-mode="new"]').click()
        assert not session_name_input.is_visible(), (
            "Session name field should be hidden in New Repo mode"
        )

        # Switch back to Existing mode: visible again
        page.locator('[data-mode="existing"]').click()
        assert session_name_input.is_visible(), (
            "Session name field should reappear in Existing mode"
        )

    def test_submit_disabled_without_required_fields(self, page):
        """Submit button is disabled when no working directory has been entered."""
        seed_tasks({"tasks": [TASK_NO_SESSION]})
        setup_lumbergh_mocks(page)
        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        open_create_session_modal(page)

        submit_btn = page.locator('[data-testid="create-session-submit"]')
        assert submit_btn.is_disabled(), (
            "Submit button should be disabled before a working directory is entered"
        )

    def test_cancel_closes_modal(self, page):
        """Cancel button closes the modal and does not modify tasks."""
        seed_tasks({"tasks": [TASK_NO_SESSION]})
        setup_lumbergh_mocks(page)
        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        open_create_session_modal(page)

        # Click the Cancel button inside the modal
        page.locator('[data-testid="create-session-modal-overlay"]').locator(
            "text=Cancel"
        ).click()
        page.wait_for_timeout(300)

        overlay = page.locator('[data-testid="create-session-modal-overlay"]')
        assert not overlay.is_visible(), "Modal overlay should be hidden after Cancel"

        # Tasks should be unchanged
        data = read_tasks()
        task = next(t for t in data["tasks"] if t["id"] == "t-no-session")
        assert task["session_name"] == "", "session_name should still be empty after Cancel"
        assert task["session_status"] == "", "session_status should still be empty after Cancel"

    def test_overlay_click_closes_modal(self, page):
        """Clicking the overlay backdrop (outside modal content) closes the modal."""
        seed_tasks({"tasks": [TASK_NO_SESSION]})
        setup_lumbergh_mocks(page)
        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        open_create_session_modal(page)

        # Click top-left corner of overlay (outside the modal box)
        overlay = page.locator('[data-testid="create-session-modal-overlay"]')
        overlay.click(position={"x": 5, "y": 5})
        page.wait_for_timeout(300)

        assert not overlay.is_visible(), "Modal should close after clicking overlay backdrop"

    def test_submit_sends_correct_payload(self, page):
        """Submitting with a manual path sends the expected JSON payload to Lumbergh."""
        seed_tasks({"tasks": [TASK_NO_SESSION]})

        # Set up mocks, capturing the POST body
        captured_body = {}

        def handle_settings(route):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(SETTINGS_RESPONSE),
            )

        def handle_dir_search(route):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"directories": []}),
            )

        def handle_dir_validate(route):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"exists": True}),
            )

        def handle_sessions(route):
            if route.request.method == "POST":
                captured_body.update(json.loads(route.request.post_data or "{}"))
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"name": "fix-auth-flow", "existing": False}),
                )
            elif route.request.method == "GET":
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"sessions": []}),
                )
            else:
                route.continue_()

        page.route("**/localhost:8420/api/settings**", handle_settings)
        page.route("**/localhost:8420/directories/search**", handle_dir_search)
        page.route("**/localhost:8420/api/directories/validate**", handle_dir_validate)
        page.route("**/localhost:8420/api/sessions**", handle_sessions)

        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        open_create_session_modal(page)

        # Click "Enter path manually"
        page.locator("text=Enter path manually").click()

        # Fill in the workdir
        workdir_input = page.locator('[data-testid="workdir-input"]')
        workdir_input.fill("/home/user/src/myproject")

        # Wait for validation debounce
        page.wait_for_timeout(600)

        # Submit
        submit_btn = page.locator('[data-testid="create-session-submit"]')
        page.wait_for_function(
            "() => !document.querySelector('[data-testid=\"create-session-submit\"]')?.disabled",
            timeout=3000,
        )
        submit_btn.click()

        # Wait for sessions POST
        page.wait_for_timeout(1000)

        assert "name" in captured_body, f"Payload missing 'name': {captured_body}"
        assert captured_body.get("mode") == "direct", (
            f"Expected mode='direct', got: {captured_body.get('mode')!r}"
        )
        assert "workdir" in captured_body, f"Payload missing 'workdir': {captured_body}"
        assert "description" in captured_body, f"Payload missing 'description': {captured_body}"

    def test_successful_submit_links_session(self, page):
        """After a successful Lumbergh POST the task gets session_name and session_status='working'."""
        slug = "fix-auth-flow"
        seed_tasks({"tasks": [TASK_NO_SESSION]})

        def handle_settings(route):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(SETTINGS_RESPONSE),
            )

        def handle_dir_search(route):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"directories": []}),
            )

        def handle_dir_validate(route):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"exists": True}),
            )

        def handle_sessions(route):
            if route.request.method == "POST":
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"name": slug, "existing": False}),
                )
            elif route.request.method == "GET":
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"sessions": []}),
                )
            else:
                route.continue_()

        page.route("**/localhost:8420/api/settings**", handle_settings)
        page.route("**/localhost:8420/directories/search**", handle_dir_search)
        page.route("**/localhost:8420/api/directories/validate**", handle_dir_validate)
        page.route("**/localhost:8420/api/sessions**", handle_sessions)

        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        open_create_session_modal(page)

        # Enter manual path
        page.locator("text=Enter path manually").click()
        page.locator('[data-testid="workdir-input"]').fill("/home/user/src/myproject")
        page.wait_for_timeout(600)

        submit_btn = page.locator('[data-testid="create-session-submit"]')
        page.wait_for_function(
            "() => !document.querySelector('[data-testid=\"create-session-submit\"]')?.disabled",
            timeout=3000,
        )

        with page.expect_response(
            lambda r: "/api/focus/tasks" in r.url and r.request.method == "POST",
            timeout=5000,
        ):
            submit_btn.click()

        # Modal should close
        overlay = page.locator('[data-testid="create-session-modal-overlay"]')
        assert not overlay.is_visible(), "Modal should close after successful submit"

        # Task should have session fields set
        data = read_tasks()
        task = next(t for t in data["tasks"] if t["id"] == "t-no-session")
        assert task["session_name"] != "", f"session_name should be set after submit: {task}"
        # session_status is derived from live polling, not stored on creation
        assert task["session_status"] == "", (
            f"session_status should be empty after submit (not stored on creation): {task}"
        )


# ===========================================================================
# class TestDetachSession
# ===========================================================================

class TestDetachSession:
    """Verify the session-detach button clears session fields."""

    def test_detach_clears_session_fields(self, page):
        """Clicking .session-detach on a linked card clears session_name and session_status."""
        seed_tasks({"tasks": [TASK_WITH_SESSION]})
        setup_lumbergh_mocks(page)
        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        # Hover to reveal the detach button
        page.locator(".today-card").first.hover()
        page.wait_for_timeout(200)

        detach_btn = page.locator(".session-detach").first
        detach_btn.wait_for(state="visible", timeout=2000)

        with page.expect_response(
            lambda r: "/api/focus/tasks" in r.url and r.request.method == "POST",
            timeout=3000,
        ):
            detach_btn.click()

        data = read_tasks()
        task = next(t for t in data["tasks"] if t["id"] == "t-with-session")
        assert task["session_name"] == "", (
            f"session_name should be empty after detach, got: {task['session_name']!r}"
        )
        assert task["session_status"] == "", (
            f"session_status should be empty after detach, got: {task['session_status']!r}"
        )

    def test_detach_shows_launch_button(self, page):
        """After detaching, the card shows the launch button again and no session badge."""
        seed_tasks({"tasks": [TASK_WITH_SESSION]})
        setup_lumbergh_mocks(page)
        page.goto(BASE_URL)
        page.wait_for_selector(".today-card")

        # Before detach: linked card hides the launch button and shows a session badge
        launch_before = page.locator(".today-card-launch")
        assert launch_before.count() == 0, (
            f"Expected 0 launch buttons before detach (linked card hides it), got {launch_before.count()}"
        )
        badges_before = page.locator(".session-badge")
        assert badges_before.count() >= 1, (
            f"Expected at least 1 session badge before detach, got {badges_before.count()}"
        )

        # Hover and detach
        page.locator(".today-card").first.hover()
        page.wait_for_timeout(200)
        detach_btn = page.locator(".session-detach").first
        detach_btn.wait_for(state="visible", timeout=2000)

        with page.expect_response(
            lambda r: "/api/focus/tasks" in r.url and r.request.method == "POST",
            timeout=3000,
        ):
            detach_btn.click()

        # After detach: unlinked card shows the launch button, no session badge
        page.wait_for_timeout(300)
        launch_after = page.locator(".today-card-launch")
        assert launch_after.count() >= 1, (
            f"Expected at least 1 launch button after detach (unlinked card shows it), got {launch_after.count()}"
        )
        badges_after = page.locator(".session-badge")
        assert badges_after.count() == 0, (
            f"Expected 0 session badges after detach, got {badges_after.count()}"
        )
