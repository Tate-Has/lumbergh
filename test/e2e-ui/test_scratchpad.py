"""Scratchpad feature step definitions."""

from playwright.sync_api import Page, expect
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/session_scratchpad.feature")


@given("a second test session exists")
def ensure_second_session(_ensure_second_session):
    """Relies on the session-scoped fixture from conftest."""
    pass


@when(parsers.parse('I type "{text}" in the scratchpad'))
def type_in_scratchpad(page: Page, text: str):
    textarea = page.locator('[data-testid="scratchpad-textarea"]')
    expect(textarea).to_be_visible(timeout=5000)
    textarea.fill(text)
    # Wait for debounced save to trigger (500ms debounce + buffer)
    page.wait_for_timeout(1000)


@then(parsers.parse('the scratchpad should contain "{text}"'))
def scratchpad_contains(page: Page, text: str):
    textarea = page.locator('[data-testid="scratchpad-textarea"]')
    expect(textarea).to_have_value(text, timeout=5000)


@then(parsers.parse('the scratchpad should not contain "{text}"'))
def scratchpad_not_contains(page: Page, text: str):
    textarea = page.locator('[data-testid="scratchpad-textarea"]')
    expect(textarea).to_be_visible(timeout=5000)
    expect(textarea).not_to_have_value(text, timeout=5000)
