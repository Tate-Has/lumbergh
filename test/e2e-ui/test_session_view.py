"""Term/Conv session view step definitions."""

from playwright.sync_api import Page, expect
from pytest_bdd import given, scenarios, then, when

scenarios("features/session_view.feature")

# The terminal's own WebSocket connects to `/session/{name}/stream` (see
# useTerminalSocket.ts). The conversation feed opens a separate socket to
# `/session/{name}/activity` (see useConversationSocket.ts). Both sockets can
# be open on the session page at once, so the recorder below matches on
# "/stream" specifically to count only terminal connections.
TERMINAL_WS_PATH = "/stream"


@given("I record terminal websocket connections", target_fixture="terminal_ws_connections")
def record_terminal_ws_connections(page: Page) -> list[str]:
    """Attach a WebSocket connection recorder before the terminal mounts.

    Must run before navigating to the session page: the terminal's WebSocket
    opens as soon as the Terminal component mounts, and a listener attached
    afterwards misses that first connection.
    """
    connections: list[str] = []

    def record(ws) -> None:
        if TERMINAL_WS_PATH in ws.url:
            connections.append(ws.url)

    page.on("websocket", record)
    return connections


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
    """The terminal must remain in the DOM, merely hidden.

    Unmounting it would tear down xterm and its WebSocket, which is exactly
    the regression this feature must not reintroduce. `not_to_be_visible`
    alone also passes for a fully detached element, so it does not by itself
    prove the node survived - the count assertion is what enforces "hidden,
    not removed".
    """
    locator = page.locator('[data-testid="terminal-container"]')
    expect(locator).to_have_count(1, timeout=10000)
    expect(locator).not_to_be_visible(timeout=10000)


@then("I should see the conversation view")
def see_conversation_view(page: Page):
    expect(page.locator('[data-testid="conversation-view"]')).to_be_visible(timeout=10000)


@then("the terminal websocket connected exactly once")
def terminal_ws_connected_once(terminal_ws_connections: list[str]):
    assert len(terminal_ws_connections) == 1, (
        f"expected exactly one terminal websocket connection, got {terminal_ws_connections}"
    )
