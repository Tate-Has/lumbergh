"""Tests for Phase 15: Production Session Bridge — live session status badges.

Tests verify that the useSessionStatus hook polls the Lumbergh API and
renders the correct badge color/label on TodayCards based on session state.
"""
import json
from conftest import BASE_URL, seed_tasks, make_task

LUMBERGH_SESSIONS_URL = '**/api/sessions'

TASK_WITH_SESSION = make_task(
    "Fix auth flow",
    project="WW",
    priority="high",
    status="today",
    session_name="test-sess",
    session_status="working",
    task_id="t-session-1",
)

TASK_NO_SESSION = make_task(
    "Plain task",
    priority="med",
    status="today",
    task_id="t-no-session",
)


def _mock_sessions(page, sessions: list):
    """Register a Playwright route that intercepts Lumbergh /api/sessions."""
    body = json.dumps(sessions)

    def handler(route):
        route.fulfill(
            status=200,
            content_type='application/json',
            body=body,
        )

    page.route(LUMBERGH_SESSIONS_URL, handler)


class TestSessionStatusBadge:
    """Verify session status badge rendering for various idleState values."""

    def test_working_status_badge(self, page):
        """Working session shows green dot and 'Working' label."""
        seed_tasks({"tasks": [TASK_WITH_SESSION]})
        _mock_sessions(page, [
            {"name": "test-sess", "alive": True, "idleState": "working", "displayName": None}
        ])
        page.goto(BASE_URL)

        page.wait_for_selector('.session-badge', timeout=8000)

        dot = page.locator('.session-dot').first
        assert dot.evaluate("el => el.classList.contains('bg-green-500')"), \
            "Working dot should have bg-green-500 class"
        assert not dot.evaluate("el => el.classList.contains('animate-pulse')"), \
            "Working dot should NOT pulse"

        label = page.locator('.session-label').first.text_content()
        assert label == 'Working', f"Expected label 'Working', got '{label}'"

    def test_idle_status_badge(self, page):
        """Idle session shows yellow pulsing dot and 'Waiting for input' label."""
        seed_tasks({"tasks": [TASK_WITH_SESSION]})
        _mock_sessions(page, [
            {"name": "test-sess", "alive": True, "idleState": "idle", "displayName": None}
        ])
        page.goto(BASE_URL)

        page.wait_for_selector('.session-badge', timeout=8000)

        dot = page.locator('.session-dot').first
        assert dot.evaluate("el => el.classList.contains('bg-yellow-400')"), \
            "Idle dot should have bg-yellow-400 class"
        assert dot.evaluate("el => el.classList.contains('animate-pulse')"), \
            "Idle dot should have animate-pulse class"

        label = page.locator('.session-label').first.text_content()
        assert label == 'Waiting for input', \
            f"Expected label 'Waiting for input', got '{label}'"

    def test_error_status_badge(self, page):
        """Error session shows red pulsing dot and 'Error' label."""
        seed_tasks({"tasks": [TASK_WITH_SESSION]})
        _mock_sessions(page, [
            {"name": "test-sess", "alive": True, "idleState": "error", "displayName": None}
        ])
        page.goto(BASE_URL)

        page.wait_for_selector('.session-badge', timeout=8000)

        dot = page.locator('.session-dot').first
        assert dot.evaluate("el => el.classList.contains('bg-red-500')"), \
            "Error dot should have bg-red-500 class"
        assert dot.evaluate("el => el.classList.contains('animate-pulse')"), \
            "Error dot should have animate-pulse class"

        label = page.locator('.session-label').first.text_content()
        assert label == 'Error', f"Expected label 'Error', got '{label}'"

    def test_offline_status_badge(self, page):
        """Session not found in Lumbergh response shows gray dot and 'Offline' label."""
        seed_tasks({"tasks": [TASK_WITH_SESSION]})
        # Return empty array — session not found
        _mock_sessions(page, [])
        page.goto(BASE_URL)

        page.wait_for_selector('.session-badge', timeout=8000)

        dot = page.locator('.session-dot').first
        assert dot.evaluate("el => el.classList.contains('bg-gray-500')"), \
            "Offline dot should have bg-gray-500 class"
        assert not dot.evaluate("el => el.classList.contains('animate-pulse')"), \
            "Offline dot should NOT pulse"

        label = page.locator('.session-label').first.text_content()
        assert label == 'Offline', f"Expected label 'Offline', got '{label}'"

    def test_no_badge_without_session(self, page):
        """Tasks with no session_name render no session badge."""
        seed_tasks({"tasks": [TASK_NO_SESSION]})
        _mock_sessions(page, [])
        page.goto(BASE_URL)

        page.wait_for_selector('.today-card', timeout=5000)
        # Give the hook time to fire and render
        page.wait_for_timeout(500)

        badge_count = page.locator('.session-badge').count()
        assert badge_count == 0, \
            f"Expected 0 session badges for a task with no session, got {badge_count}"

    def test_badge_click_navigates_to_session(self, page):
        """Clicking the session badge navigates to the session detail page."""
        seed_tasks({"tasks": [TASK_WITH_SESSION]})
        _mock_sessions(page, [
            {"name": "test-sess", "alive": True, "idleState": "working", "displayName": None}
        ])
        page.goto(BASE_URL)
        page.wait_for_selector('.session-badge', timeout=8000)
        page.locator('.session-badge').first.click()
        page.wait_for_url('**/session/test-sess', timeout=3000)

    def test_lumbergh_offline_shows_gray(self, page):
        """When Lumbergh API is unreachable, badge shows gray 'Offline' state."""
        seed_tasks({"tasks": [TASK_WITH_SESSION]})
        # Route the sessions endpoint to fail (simulate Lumbergh being down)
        page.route(LUMBERGH_SESSIONS_URL, lambda route: route.abort())
        page.goto(BASE_URL)

        page.wait_for_selector('.session-badge', timeout=8000)

        dot = page.locator('.session-dot').first
        assert dot.evaluate("el => el.classList.contains('bg-gray-500')"), \
            "Offline (Lumbergh unreachable) dot should have bg-gray-500 class"

        label = page.locator('.session-label').first.text_content()
        assert label == 'Offline', \
            f"Expected label 'Offline' when Lumbergh is unreachable, got '{label}'"


class TestSessionStatusPolling:
    """Verify that the session status badge updates on subsequent polls."""

    def test_status_updates_on_poll(self, page):
        """Badge label transitions from 'Working' to 'Waiting for input' after a poll cycle."""
        seed_tasks({"tasks": [TASK_WITH_SESSION]})

        # Phase 1: return working status
        call_count = {"n": 0}

        def dynamic_handler(route):
            call_count["n"] += 1
            if call_count["n"] == 1:
                body = json.dumps([
                    {"name": "test-sess", "alive": True, "idleState": "working", "displayName": None}
                ])
            else:
                body = json.dumps([
                    {"name": "test-sess", "alive": True, "idleState": "idle", "displayName": None}
                ])
            route.fulfill(status=200, content_type='application/json', body=body)

        page.route(LUMBERGH_SESSIONS_URL, dynamic_handler)
        page.goto(BASE_URL)

        # Wait for initial "Working" label
        page.wait_for_selector('.session-badge', timeout=8000)
        label_locator = page.locator('.session-label').first
        label_locator.wait_for(timeout=8000)

        initial_label = label_locator.text_content()
        assert initial_label == 'Working', \
            f"Expected initial label 'Working', got '{initial_label}'"

        # Wait up to 6s for the next poll to flip the label to idle
        page.wait_for_function(
            "() => document.querySelector('.session-label') && "
            "document.querySelector('.session-label').textContent === 'Waiting for input'",
            timeout=7000,
        )

        updated_label = label_locator.text_content()
        assert updated_label == 'Waiting for input', \
            f"Expected updated label 'Waiting for input' after poll, got '{updated_label}'"
