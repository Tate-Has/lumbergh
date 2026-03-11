"""Todo feature step definitions."""

from playwright.sync_api import Page, expect
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/session_todos.feature")


@when(parsers.parse('I type "{text}" in the todo input'))
def type_todo(page: Page, text: str):
    inp = page.locator('[data-testid="todo-input"]')
    inp.fill(text)


@when("I press Enter in the todo input")
def press_enter_todo(page: Page):
    inp = page.locator('[data-testid="todo-input"]')
    inp.press("Enter")
    page.wait_for_timeout(500)


@then(parsers.parse('I should see a todo item with text "{text}"'))
def see_todo_item(page: Page, text: str):
    items = page.locator('[data-testid="todo-item"]')
    expect(items.filter(has_text=text).first).to_be_visible(timeout=5000)


@given(parsers.parse('a todo "{text}" exists'))
def todo_exists(base_url: str, text: str):
    """Verify the todo exists via API (page may not be on the todo tab yet)."""
    import httpx

    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        r = client.get("/api/sessions/e2e-ui-session/todos")
        assert r.status_code == 200
        todos = r.json().get("todos", [])
        assert any(text in t.get("text", "") for t in todos), f"Todo '{text}' not found in {todos}"


@when(parsers.parse('I toggle the checkbox for "{text}"'))
def toggle_todo(page: Page, text: str):
    item = page.locator('[data-testid="todo-item"]').filter(has_text=text).first
    checkbox = item.locator('[data-testid="todo-checkbox"]')
    checkbox.click(force=True)
    # Wait for save to complete (toggle reorders items)
    page.wait_for_timeout(1500)


@then(parsers.parse('the todo "{text}" should be marked done'))
def todo_is_done(page: Page, base_url: str, text: str):
    """Verify via API since toggle reorders items in the DOM."""
    import httpx

    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        r = client.get("/api/sessions/e2e-ui-session/todos")
        todos = r.json().get("todos", [])
        matching = [t for t in todos if text in t.get("text", "")]
        assert matching, f"Todo '{text}' not found"
        assert matching[0]["done"], f"Todo '{text}' is not done: {matching[0]}"
