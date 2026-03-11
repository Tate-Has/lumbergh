"""Terminal feature step definitions."""

from playwright.sync_api import Page, expect
from pytest_bdd import parsers, scenarios, then, when

scenarios("features/session_terminal.feature")


@when(parsers.parse('I click on the session "{name}"'))
def click_session_card(page: Page, name: str):
    card = page.locator(f'[data-testid="session-card-{name}"]')
    card.click()
    page.wait_for_load_state("networkidle")


@then("I should see the terminal container")
def see_terminal_container(page: Page):
    container = page.locator('[data-testid="terminal-container"]')
    expect(container).to_be_visible(timeout=10000)


@then("I should see the xterm terminal")
def see_xterm(page: Page):
    xterm = page.locator('[data-testid="xterm-container"]')
    expect(xterm).to_be_visible(timeout=10000)


@then("I should see the git tab content")
def see_git_tab(page: Page):
    git_tab = page.locator('[data-testid="git-tab"]')
    expect(git_tab).to_be_visible(timeout=10000)


@then("I should see the todo input")
def see_todo_input(page: Page):
    inp = page.locator('[data-testid="todo-input"]')
    expect(inp).to_be_visible(timeout=10000)
