"""Playwright E2E test configuration and shared step definitions."""

import httpx
import pytest
from playwright.sync_api import Browser, BrowserContext, Page, expect, sync_playwright
from pytest_bdd import given, parsers, when


def pytest_addoption(parser):
    parser.addoption(
        "--base-url",
        default="http://localhost:8420",
        help="Base URL for the Lumbergh UI",
    )
    parser.addoption(
        "--repo-dir",
        default="/home/test",
        help="Directory containing test-repo, test-repo-2, git-test-repo",
    )


@pytest.fixture(scope="session")
def base_url(request):
    return request.config.getoption("--base-url")


@pytest.fixture(scope="session")
def repo_dir(request):
    return request.config.getoption("--repo-dir")


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture(scope="function")
def context(browser: Browser):
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    yield ctx
    ctx.close()


@pytest.fixture(scope="function")
def page(context: BrowserContext, base_url: str):
    pg = context.new_page()
    pg.goto(base_url)
    yield pg
    pg.close()


@pytest.fixture(scope="session")
def _ensure_test_session(base_url, repo_dir):
    """Create a test session via API so UI tests have something to interact with."""
    session_name = "e2e-ui-session"
    with httpx.Client(base_url=base_url, timeout=30.0) as client:
        # Delete if exists from a previous run
        client.delete(f"/api/sessions/{session_name}")

        r = client.post(
            "/api/sessions",
            json={"name": session_name, "workdir": f"{repo_dir}/test-repo"},
        )
        assert r.status_code == 200, f"Failed to create test session: {r.text}"

        yield session_name

        client.delete(f"/api/sessions/{session_name}")


@pytest.fixture(scope="session")
def _ensure_second_session(base_url, repo_dir):
    """Create a second test session for multi-session UI tests."""
    session_name = "e2e-ui-session-2"
    with httpx.Client(base_url=base_url, timeout=30.0) as client:
        client.delete(f"/api/sessions/{session_name}")

        r = client.post(
            "/api/sessions",
            json={"name": session_name, "workdir": f"{repo_dir}/test-repo-2"},
        )
        assert r.status_code == 200, f"Failed to create second session: {r.text}"

        yield session_name

        client.delete(f"/api/sessions/{session_name}")


# ── Shared Step Definitions (available to all feature files) ──────────


@given("I am on the dashboard")
def go_to_dashboard(page: Page, base_url: str):
    page.goto(base_url)
    page.wait_for_load_state("networkidle")


@given("a test session exists")
def ensure_test_session(_ensure_test_session):
    """Relies on the session-scoped fixture from conftest."""
    pass


@given(parsers.parse('a session "{name}" exists'))
def ensure_named_session(base_url: str, name: str):
    """Verify session exists via API."""
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        r = client.get("/api/sessions")
        names = [s["name"] for s in r.json()["sessions"]]
        assert name in names, f"Session '{name}' not found in {names}"


@given(parsers.parse('I am on the session page for "{name}"'))
def go_to_session_page(page: Page, base_url: str, _ensure_test_session, name: str):
    page.goto(f"{base_url}/session/{name}")
    page.wait_for_load_state("networkidle")


@when(parsers.parse('I click the "{tab_name}" tab'))
def click_tab(page: Page, tab_name: str):
    tab = page.locator(f'[data-testid="tab-{tab_name}"]')
    tab.click()
    page.wait_for_timeout(500)


@when(parsers.parse('I navigate to the session page for "{name}"'))
def navigate_to_session(page: Page, base_url: str, name: str):
    page.goto(f"{base_url}/session/{name}")
    page.wait_for_load_state("networkidle")
