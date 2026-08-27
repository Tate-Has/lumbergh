"""Git feature step definitions."""

from playwright.sync_api import Page, expect
from pytest_bdd import parsers, scenarios, then, when

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


@when(parsers.parse('I search the graph for "{text}"'))
def search_graph(page: Page, text: str):
    box = page.locator('[data-testid="graph-search-input"]')
    expect(box).to_be_visible(timeout=10000)
    box.fill(text)
    page.wait_for_timeout(300)


@when("I clear the graph search")
def clear_graph_search(page: Page):
    page.locator('[data-testid="graph-search-clear"]').click()
    page.wait_for_timeout(300)


@when("I click the all-history search button")
def click_history_search(page: Page):
    page.locator('[data-testid="graph-search-history"]').click()


@then("I should see a match count in the graph toolbar")
def see_match_count(page: Page):
    expect(page.locator('[data-testid="graph-search-count"]')).to_be_visible(timeout=5000)


@then("I should see at least one dimmed commit row")
def see_dimmed_row(page: Page):
    expect(page.locator('[data-testid="graph-row-dimmed"]').first).to_be_visible(timeout=5000)


@then("I should see no dimmed commit rows")
def see_no_dimmed_rows(page: Page):
    expect(page.locator('[data-testid="graph-row-dimmed"]')).to_have_count(0)


@then("I should see the history search panel")
def see_history_panel(page: Page):
    expect(page.locator('[data-testid="history-search-panel"]')).to_be_visible(timeout=10000)
