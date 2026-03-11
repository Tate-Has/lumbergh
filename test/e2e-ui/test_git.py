"""Git feature step definitions."""

from playwright.sync_api import Page, expect
from pytest_bdd import scenarios, then

scenarios("features/session_git.feature")


@then("I should see the git tab content")
def see_git_tab(page: Page):
    tab = page.locator('[data-testid="git-tab"]')
    expect(tab).to_be_visible(timeout=10000)


@then("I should see at least one diff file item")
def see_diff_files(page: Page):
    # Wait for diff data to load
    page.wait_for_timeout(2000)
    items = page.locator('[data-testid="diff-file-item"]')
    expect(items.first).to_be_visible(timeout=10000)
