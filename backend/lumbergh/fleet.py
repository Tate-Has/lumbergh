"""Cross-repo fleet view: every tracked worktree as one task row.

``worktrees.reconcile_all`` already flattens the registry across every repo; this
module turns that flattened view plus injected live-state lookups into task rows
and judges which of them need attention.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from lumbergh import worktrees

if TYPE_CHECKING:
    from collections.abc import Callable

# States where a live worker needs Bill and he can act on it (answer a prompt, report an
# error). These wake him on their state alone — he can never miss one. `dead` is deliberately
# not here: a dead worker is one he cannot resolve (its session is gone, and `reap` is the
# user's call), so it surfaces once via `unseen` and then stays quiet — see `needs_attention`.
ATTENTION_STATES = {"blocked", "error"}

_OUTCOME = re.compile(r"^(DELIVERED|FAILED):\s*(.+)$")


def snapshot(
    live_sessions: dict[str, dict],
    state_of: Callable[[str], str],
    since_of: Callable[[str], float | None],
    unseen_of: Callable[[str], bool],
    origin: str | None = None,
    dead_acked: set[str] | None = None,
) -> list[dict]:
    dead_acked = dead_acked or set()
    rows: list[dict] = []
    for row in worktrees.reconcile_all(live_sessions):
        entry = worktrees.get_entry(Path(row["path"])) or {}
        if origin is not None and entry.get("origin") != origin:
            continue
        session = row.get("session") or entry.get("associated_session")
        if row["session"]:
            state = state_of(row["session"])
            since = since_of(row["session"])
            unseen = unseen_of(row["session"])
        else:
            state = "dead" if entry.get("associated_session") else "orphan"
            since = None
            # A dead task has no live session to carry the seen/unseen overlay, so its
            # attention is tracked by path in `dead_acked`: unseen until Bill has been
            # shown it once. (An orphan never needs attention, so its flag is moot.)
            unseen = state == "dead" and row["path"] not in dead_acked
        rows.append(
            {
                "task": session,
                # ``repo`` is only a basename (``reconcile`` fills it from ``repo.name``),
                # which is what a human wants to read but useless to ``lb spawn --repo``.
                # The registry holds the real path, so both travel on the row.
                "repo": row["repo"],
                "repo_path": entry.get("parent_repo"),
                "branch": row["branch"],
                "session": row["session"],
                "kind": entry.get("kind"),
                "state": state,
                "since": round(since) if since is not None else None,
                "unseen": unseen,
                "path": row["path"],
            }
        )
    return rows


def needs_attention(row: dict) -> bool:
    if row["state"] in ATTENTION_STATES:
        return True
    # A finished worker (`idle`) and one Bill cannot resolve (`dead`) both surface once,
    # then go quiet: showing Bill the fleet clears `unseen`. Waking on `dead` every poll
    # was the reap-refused loop the user hit.
    return row["state"] in ("idle", "dead") and bool(row.get("unseen"))


def any_needs_attention(rows: list[dict]) -> bool:
    return any(needs_attention(r) for r in rows)


def parse_outcome(text: str) -> str | None:
    """The worker's contracted final line, so an outcome is read rather than inferred."""
    for line in reversed((text or "").splitlines()):
        match = _OUTCOME.match(line.strip())
        if match:
            return f"{match.group(1)}: {match.group(2).strip()}"
    return None
