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
from lumbergh.targets import parse_target

if TYPE_CHECKING:
    from collections.abc import Callable


def _resolved(path: str | None) -> str | None:
    if not path:
        return None
    try:
        return str(Path(path).resolve())
    except (OSError, ValueError):
        return path


# States where a live worker needs Bill and he can act on it (answer a prompt, report an
# error). These wake him on their state alone — he can never miss one. `dead` is deliberately
# not here: a dead worker is one he cannot resolve (its session is gone, and `reap` is the
# user's call), so it surfaces once via `unseen` and then stays quiet — see `needs_attention`.
ATTENTION_STATES = {"blocked", "error", "undelivered"}

# A worker that was stood up but never received its brief: its agent has consumed no
# context at all and its HEAD has not moved off the commit it was branched at. Quiescence
# cannot see this — the pane holds the unsubmitted brief and reads as `idle`, or twitches
# and reads as `working` — so it is judged here, from evidence the pane classifier
# doesn't have, and named rather than folded into a state that means something else.
UNDELIVERED = "undelivered"
_DELIVERY_UNPROVEN_STATES = {"idle", "working"}

# States in which a worker still needs its overseer's context. `working` is the obvious
# one; `blocked`/`error` count too, because answering them is exactly what that context is
# for. A delivered (`idle`) worker, or a `dead`/`orphan` row, holds nothing.
IN_FLIGHT_STATES = {"working", "blocked", "error", UNDELIVERED}

_OUTCOME = re.compile(r"^(DELIVERED|FAILED):\s*(.+)$")


def snapshot(
    live_sessions: dict[str, dict],
    state_of: Callable[[str], str],
    since_of: Callable[[str], float | None],
    unseen_of: Callable[[str], bool],
    origin: str | None = None,
    dead_acked: set[str] | None = None,
    live_targets: set[str] | None = None,
    overseer_exclude: set[str] | None = None,
    context_of: Callable[[str], float | None] | None = None,
    babysat_unresolved: set[str] | None = None,
) -> list[dict]:
    dead_acked = dead_acked or set()
    overseer_exclude = overseer_exclude or set()

    workers: list[dict] = []
    worker_sessions: set[str] = set()  # session names of workers + batch containers
    for row in worktrees.reconcile_all(live_sessions):
        entry = worktrees.get_entry(Path(row["path"])) or {}
        # `target` is the window-aware identity of a tracked worker (e.g. `port:fleet-644`
        # for one window of a batch, or a bare session name for a standalone worker).
        target = entry.get("target")
        # Record every worker/container session up front — before the origin filter —
        # so a worker hidden by --origin is still never mistaken for an overseer.
        if target:
            worker_sessions.add(parse_target(target)[0])
        if row["session"]:
            worker_sessions.add(row["session"])
        if origin is not None and entry.get("origin") != origin:
            continue
        tracked = target or row["session"]
        # A window worker (`--into`) is intentionally never stored in `live_sessions`, so
        # `row["session"]` is always None for one even while it's running — only the idle
        # monitor's live-target cache actually knows it's alive. Without this, every window
        # worker would report `dead` despite being fully monitored under its `target`.
        is_live = bool(row["session"]) or (target in (live_targets or set()))
        if is_live:
            state = state_of(tracked)
            since = since_of(tracked)
            unseen = unseen_of(tracked)
            if _never_started(state, tracked, row["path"], context_of):
                state = UNDELIVERED
        else:
            state = "dead" if entry.get("target") else "orphan"
            since = None
            # A dead task has no live session to carry the seen/unseen overlay, so its
            # attention is tracked by path in `dead_acked`: unseen until Bill has been
            # shown it once. (An orphan never needs attention, so its flag is moot.)
            unseen = state == "dead" and row["path"] not in dead_acked
        workers.append(
            {
                "task": tracked,
                # ``repo`` is only a basename (``reconcile`` fills it from ``repo.name``),
                # which is what a human wants to read but useless to ``lb spawn --repo``.
                # The registry holds the real path, so both travel on the row.
                "repo": row["repo"],
                "repo_path": entry.get("parent_repo"),
                "branch": row["branch"],
                "session": row["session"],
                "target": target,
                "run": entry.get("run"),
                "kind": entry.get("kind"),
                "origin": entry.get("origin"),
                "role": "worker",
                "parent": None,  # filled once overseers are known
                "state": state,
                "since": round(since) if since is not None else None,
                "unseen": unseen,
                "path": row["path"],
            }
        )

    overseers = _overseer_rows(
        live_sessions,
        worker_sessions,
        overseer_exclude,
        live_targets,
        state_of,
        since_of,
        unseen_of,
    )
    overseer_by_path = {_resolved(o["path"]): o["task"] for o in overseers if o["path"]}
    for w in workers:
        w["parent"] = overseer_by_path.get(_resolved(w["repo_path"]))

    named = {o["task"] for o in overseers}
    overseers.extend(
        _broken_babysit_row(session)
        for session in sorted(babysat_unresolved or set())
        if session not in named
    )

    return _as_tree(overseers, workers)


def _broken_babysit_row(session: str) -> dict:
    """A babysit with nothing behind it, as a row that wakes its watcher.

    ``error`` rather than a state of its own: the whole point is to reach every path that
    already means "this needs a human" — ``needs_attention``, ``lb fleet --wait``, the edge
    nudge — instead of adding a state each of them would have to learn.
    """
    return {
        "task": session,
        "repo": None,
        "repo_path": None,
        "branch": None,
        "session": None,
        "target": None,
        "run": None,
        "kind": None,
        "origin": None,
        "role": "overseer",
        "parent": None,
        "state": "error",
        "since": None,
        "unseen": True,
        "path": None,
        "problem": "babysat but has no live agent — nothing is driving it",
    }


def _never_started(
    state: str,
    tracked: str,
    path: str,
    context_of: Callable[[str], float | None] | None,
) -> bool:
    """Whether this live worker was stood up and never actually took its brief.

    Both halves are required. Zero consumed context alone would flag a worker in the
    first seconds of its opening turn, before its readout moves; an untouched HEAD alone
    describes every worker still reading. A pane that reports no context at all (a
    provider whose TUI doesn't show one) is never accused — the absence of evidence
    cannot be the evidence.
    """
    if context_of is None or state not in _DELIVERY_UNPROVEN_STATES:
        return False
    used = context_of(tracked)
    return used == 0 and worktrees.head_untouched(Path(path))


def _overseer_rows(
    live_sessions: dict[str, dict],
    worker_sessions: set[str],
    overseer_exclude: set[str],
    live_targets: set[str] | None,
    state_of: Callable[[str], str],
    since_of: Callable[[str], float | None],
    unseen_of: Callable[[str], bool],
) -> list[dict]:
    """One row per live overseer: a direct session that isn't a worker, a batch
    container (its name owns worker windows), or Bill. Gated on actually running an
    agent when a live-target set is supplied."""
    agent_sessions = {parse_target(t)[0] for t in (live_targets or set())}
    rows: list[dict] = []
    for name, meta in live_sessions.items():
        if name in overseer_exclude or name in worker_sessions:
            continue
        if meta.get("type") == "worktree":
            continue
        if live_targets is not None and name not in agent_sessions:
            continue
        workdir = meta.get("workdir")
        since = since_of(name)
        rows.append(
            {
                "task": name,
                "repo": Path(workdir).name if workdir else None,
                "repo_path": workdir,
                "branch": None,
                "session": name,
                "target": None,
                "run": None,
                "kind": None,
                "role": "overseer",
                "parent": None,
                "state": state_of(name),
                "since": round(since) if since is not None else None,
                "unseen": unseen_of(name),
                "path": workdir,
            }
        )
    return rows


def _as_tree(overseers: list[dict], workers: list[dict]) -> list[dict]:
    """Flatten to one list ordered overseer-then-its-workers, orphans last."""
    workers_by_parent: dict[str | None, list[dict]] = {}
    for w in workers:
        workers_by_parent.setdefault(w["parent"], []).append(w)
    ordered: list[dict] = []
    for o in overseers:
        ordered.append(o)
        ordered.extend(workers_by_parent.pop(o["task"], []))
    for leftover in workers_by_parent.values():  # orphans + any unmatched parent
        ordered.extend(leftover)
    return ordered


def needs_attention(row: dict) -> bool:
    """Whether this row has an unhandled action for whoever watches it.

    Intrinsic to the row: it is stuck (blocked/error) or finished a chunk unseen
    (idle+unseen). *Which* watcher it wakes — Bill for an overseer, an overseer for
    its own worker — is a scoping decision the caller makes (see ``bill._direct_reports``),
    not something baked in here.
    """
    if row["state"] in ATTENTION_STATES:
        return True
    return row["state"] == "idle" and bool(row.get("unseen"))


def workers_in_flight(rows: list[dict], overseer: str) -> list[str]:
    """The overseer's own workers that still need it, so nothing wipes its context under
    them. An overseer waiting on a running batch is *idle* — indistinguishable, by state
    alone, from one that has stalled. This is the difference."""
    return [
        r["task"]
        for r in rows
        if r.get("role") == "worker"
        and r.get("parent") == overseer
        and r["state"] in IN_FLIGHT_STATES
    ]


def any_needs_attention(rows: list[dict]) -> bool:
    return any(needs_attention(r) for r in rows)


def parse_outcome(text: str) -> str | None:
    """The worker's contracted final line, so an outcome is read rather than inferred."""
    for line in reversed((text or "").splitlines()):
        match = _OUTCOME.match(line.strip())
        if match:
            return f"{match.group(1)}: {match.group(2).strip()}"
    return None
