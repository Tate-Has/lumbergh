"""Wake Bill when he goes quiet — either with live work, or just to check in.

A model that ends its turn without re-arming ``lb fleet --wait`` would stall the whole
crew silently. The server already knows both facts, so it can just tap him on the shoulder.

Two taps, both a single tmux line (a newline would submit early and split the send):

- ``nudge`` — the *edge*: a report crossed into needing attention now. Urgent, fires once
  per idle episode.
- ``heartbeat_nudge`` — the *level*: nothing's flagged, but Bill has sat idle past his
  cadence. A routine "walk the fleet" so he never goes permanently deaf once everything has
  been acked. The idle monitor owns *when*; this owns only *what to say*.
- ``broken_babysit_nudge`` — a *fault*: a babysit is registered over a session with no live
  agent, so its loop is quietly driving nothing. He cannot fix it, so the tap tells him to
  say so to the user rather than to go poke at it.
- ``advance_nudge`` — the *level*, but pointed: a specific babysat overseer has gone plain
  idle with no sentinel, so nothing auto-refreshed it. An imperative to advance *that*
  session, not a generic check-in Bill can answer with "all quiet". The idle monitor owns
  *when* and *which*; this owns only *what to say*.
"""

from collections.abc import Callable

from lumbergh.tmux_pty import send_text

BILL_SESSION = "bill"
_WAKE = "A task needs you — run `lb fleet` and handle it, then re-arm `lb fleet --wait`."
_HEARTBEAT = (
    "Routine check-in: run `lb fleet`, then `lb read` any session that's gone quiet or "
    "looks stuck, nudge or hand it back as needed, and re-arm `lb fleet --wait`."
)
_BROKEN_BABYSIT = (
    "Babysat `{s}` has no live agent — nothing is driving it, so its keep-alive loop is "
    "doing nothing. You cannot fix this yourself: tell the user plainly that `{s}` is "
    "babysat but not running, and ask whether to restart it or "
    "`lb babysit --stop --session {s}`. Then re-arm `lb fleet --wait`."
)
_ADVANCE = (
    "Babysat `{s}` is idle and not blocked — advance it, don't just note it: "
    "`lb read --session {s}`, then `lb babysit --refresh --session {s}` (clean handoff or "
    "context bloat), or `lb prompt --session {s}` to land delivered work and pull the next "
    "item; if it's waiting on the user or its backlog is dry, report to the user and "
    "`lb babysit --stop --session {s}`. Then re-arm `lb fleet --wait`."
)


def should_nudge(bill_state: str, rows: list[dict]) -> bool:
    if bill_state != "idle":
        return False
    # Only an overseer needing Bill re-arms him — not mere worker activity (that's the
    # overseer's job). Routed through bill_woke so the private idle+unseen ack is honored.
    from lumbergh.routers.bill import bill_woke

    return bill_woke(rows)


def _bill_ref() -> str:
    """Bill's own agent window. A bare session ref would type into whatever window of his
    session is selected."""
    from lumbergh.idle_monitor import tmux_ref

    return tmux_ref(BILL_SESSION)


def nudge(send: Callable[[str, str], bool] = send_text) -> bool:
    return bool(send(_bill_ref(), _WAKE))


def heartbeat_nudge(send: Callable[[str, str], bool] = send_text) -> bool:
    return bool(send(_bill_ref(), _HEARTBEAT))


def advance_nudge(session: str, send: Callable[[str, str], bool] = send_text) -> bool:
    return bool(send(_bill_ref(), _ADVANCE.format(s=session)))


def broken_babysit_nudge(session: str, send: Callable[[str, str], bool] = send_text) -> bool:
    return bool(send(_bill_ref(), _BROKEN_BABYSIT.format(s=session)))
