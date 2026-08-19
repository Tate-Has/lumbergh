"""Panel focus step definitions."""

from playwright.sync_api import Page, expect
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/panel_focus.feature")

TERMINAL_WS_PATH = "/stream"


@given("I record terminal websocket connections", target_fixture="terminal_ws_connections")
def record_terminal_ws_connections(page: Page) -> list[str]:
    """Arm the recorder BEFORE navigation.

    The terminal socket opens as soon as the component mounts, so a listener
    attached afterwards sees nothing and the assertion passes vacuously.
    """
    seen: list[str] = []

    def record(ws) -> None:
        if TERMINAL_WS_PATH in ws.url:
            seen.append(ws.url)

    page.on("websocket", record)
    return seen


@when(parsers.parse('I click the "{tab}" tab'))
def click_tab(page: Page, tab: str):
    page.locator(f'[data-testid="tab-{tab}"]').click()


@when("I click the panel maximize button")
def click_panel_maximize(page: Page):
    page.locator('[data-testid="panel-maximize"]').click()


@then("I should see the file preview")
def see_file_preview(page: Page):
    expect(page.locator('[data-testid="file-preview"]')).to_be_visible(timeout=10000)


@then("the terminal container is present but hidden")
def terminal_present_but_hidden(page: Page):
    # Present AND hidden, not merely invisible: unmounting the terminal would
    # tear down xterm and its WebSocket, which is the regression being guarded.
    locator = page.locator('[data-testid="terminal-container"]')
    expect(locator).to_have_count(1, timeout=10000)
    expect(locator).not_to_be_visible(timeout=10000)


@then("the terminal websocket connected exactly once")
def terminal_ws_connected_once(terminal_ws_connections: list[str]):
    assert len(terminal_ws_connections) == 1, (
        f"expected exactly 1 terminal websocket, saw {len(terminal_ws_connections)}: "
        f"{terminal_ws_connections}"
    )
