"""Wake Bill when he goes quiet with live work.

A model that ends its turn without re-arming ``lb fleet --wait`` would stall the whole
crew silently. The server already knows both facts, so it can just tap him on the shoulder.
"""

from collections.abc import Callable

from lumbergh.tmux_pty import send_text

BILL_SESSION = "bill"
_WAKE = "A task needs you — run `lb fleet` and handle it, then re-arm `lb fleet --wait`."


def should_nudge(bill_state: str, rows: list[dict]) -> bool:
    if bill_state != "idle":
        return False
    # Only an overseer needing Bill re-arms him — not mere worker activity (that's the
    # overseer's job). Routed through bill_woke so the private idle+unseen ack is honored.
    from lumbergh.routers.bill import bill_woke

    return bill_woke(rows)


def nudge(send: Callable[[str, str], bool] = send_text) -> bool:
    return bool(send(BILL_SESSION, _WAKE))
