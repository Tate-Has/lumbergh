"""File browser feature step definitions."""

from playwright.sync_api import Page, expect
from pytest_bdd import parsers, scenarios, then

scenarios("features/session_files.feature")


@then("I should see at least one file entry")
def see_file_entries(page: Page):
    page.wait_for_timeout(2000)
    entries = page.locator('[data-testid="file-entry"]')
    expect(entries.first).to_be_visible(timeout=10000)


@then(parsers.parse('I should see a file named "{filename}"'))
def see_named_file(page: Page, filename: str):
    entries = page.locator('[data-testid="file-entry"]')
    expect(entries.filter(has_text=filename).first).to_be_visible(timeout=10000)
