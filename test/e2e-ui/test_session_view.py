"""Term/Conv session view step definitions."""

from playwright.sync_api import Page, expect
from pytest_bdd import scenarios, then, when

scenarios("features/session_view.feature")


@when("I click the view toggle")
def click_view_toggle(page: Page):
    page.locator('[data-testid="view-toggle"]').click()


@when("I reload the page")
def reload_page(page: Page):
    page.reload()
    page.wait_for_load_state("networkidle")


@then("I should see the terminal container")
def see_terminal_container(page: Page):
    expect(page.locator('[data-testid="terminal-container"]')).to_be_visible(timeout=10000)


@then("I should not see the terminal container")
def no_terminal_container(page: Page):
    expect(page.locator('[data-testid="terminal-container"]')).not_to_be_visible(timeout=10000)


@then("I should see the conversation view")
def see_conversation_view(page: Page):
    expect(page.locator('[data-testid="conversation-view"]')).to_be_visible(timeout=10000)


@then("the terminal is connected")
def terminal_connected(page: Page):
    expect(page.locator('[data-testid="xterm-container"]')).to_be_visible(timeout=10000)
