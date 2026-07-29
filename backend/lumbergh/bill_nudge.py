"""Wake Bill when he goes quiet with live work.

A model that ends its turn without re-arming ``lb fleet --wait`` would stall the whole
crew silently. The server already knows both facts, so it can just tap him on the shoulder.
"""

from collections.abc import Callable

from lumbergh import fleet
from lumbergh.tmux_pty import send_text

BILL_SESSION = "bill"
_WAKE = "A task needs you — run `lb fleet` and handle it, then re-arm `lb fleet --wait`."


def should_nudge(bill_state: str, rows: list[dict]) -> bool:
    if bill_state != "idle":
        return False
    return any(r["state"] == "working" for r in rows) or fleet.any_needs_attention(rows)


def nudge(send: Callable[[str, str], bool] = send_text) -> bool:
    return bool(send(BILL_SESSION, _WAKE))
