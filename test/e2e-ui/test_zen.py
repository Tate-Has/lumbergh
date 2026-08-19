"""Zen mode feature step definitions."""

import httpx
from playwright.sync_api import Page, expect
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/session_zen.feature")

SESSION = "e2e-ui-session"


@when(parsers.parse('I press "{chord}"'))
def press_chord(page: Page, chord: str):
    page.keyboard.press(chord)


@then("I should see the git tab button")
def see_git_tab_button(page: Page):
    expect(page.locator('[data-testid="tab-git"]')).to_be_visible(timeout=10000)


@then("I should not see the git tab button")
def no_git_tab_button(page: Page):
    expect(page.locator('[data-testid="tab-git"]')).to_have_count(0, timeout=10000)


@then("I should see the terminal container")
def see_terminal_container(page: Page):
    container = page.locator('[data-testid="terminal-container"]')
    expect(container).to_be_visible(timeout=10000)


@when("the network is idle")
def wait_for_network_idle(page: Page):
    page.wait_for_load_state("networkidle")


KNOWN_TAB_VISIBILITY = {"git": True, "files": False, "todos": True}


def _saved_tab_visibility(base_url: str):
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        r = client.get("/api/sessions")
        r.raise_for_status()
        for session in r.json()["sessions"]:
            if session.get("name") == SESSION:
                return session.get("tabVisibility")
    raise AssertionError(f"session {SESSION} not found")


# All tabs visible: same effective state as the session's default (unset)
# tabVisibility, since the frontend treats an absent key as visible too. The
# PATCH endpoint drops `None`/null fields rather than clearing them, so this
# is the only way to restore "all visible" through the API.
ALL_TABS_VISIBLE = {"git": True, "files": True, "todos": True, "prompts": True, "shared": True}


@given("I record the session's saved tab visibility", target_fixture="saved_tab_visibility")
def record_tab_visibility(base_url: str):
    # The session fixture is session-scoped and shared across every test file in
    # the run, so hiding "files" here to get a known baseline must be undone —
    # otherwise it leaks into whichever test happens to run next and hides its
    # Files tab too.
    original = _saved_tab_visibility(base_url)
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        r = client.patch(f"/api/sessions/{SESSION}", json={"tabVisibility": KNOWN_TAB_VISIBILITY})
        r.raise_for_status()
    yield _saved_tab_visibility(base_url)
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        restore = original if original is not None else ALL_TABS_VISIBLE
        client.patch(f"/api/sessions/{SESSION}", json={"tabVisibility": restore}).raise_for_status()


@then("the session's saved tab visibility is unchanged")
def tab_visibility_unchanged(base_url: str, saved_tab_visibility):
    assert _saved_tab_visibility(base_url) == saved_tab_visibility
