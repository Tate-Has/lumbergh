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

ATTENTION_STATES = {"blocked", "error", "dead"}

_OUTCOME = re.compile(r"^(DELIVERED|FAILED):\s*(.+)$")


def snapshot(
    live_sessions: dict[str, dict],
    state_of: Callable[[str], str],
    since_of: Callable[[str], float | None],
    unseen_of: Callable[[str], bool],
    origin: str | None = None,
) -> list[dict]:
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
            unseen = False
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
    return row["state"] == "idle" and bool(row.get("unseen"))


def any_needs_attention(rows: list[dict]) -> bool:
    return any(needs_attention(r) for r in rows)


def parse_outcome(text: str) -> str | None:
    """The worker's contracted final line, so an outcome is read rather than inferred."""
    for line in reversed((text or "").splitlines()):
        match = _OUTCOME.match(line.strip())
        if match:
            return f"{match.group(1)}: {match.group(2).strip()}"
    return None
