"""`lb fleet` — the whole crew in one table, with a token-free long poll."""

import json

from lumbergh.agent_cli.main import _COMMAND_HELP, _emit, _err, _request
from lumbergh.agent_cli.toon import render_collection, render_object

# The two path columns are load-bearing, not decoration: `lb spawn --repo` needs a
# filesystem path (REPO is only a basename) and `lb worktree reap` needs the worktree
# path, so without them Bill has no source for either and would invent one.
_COLS = [
    "task",
    "role",
    "repo",
    "branch",
    "kind",
    "state",
    "since",
    "unseen",
    "outcome",
    "repo_path",
    "path",
]
_HELP = _COMMAND_HELP["fleet"]


def run(flags: dict) -> int:
    timeout_flag = flags.get("--timeout")
    if timeout_flag is not None:
        try:
            float(timeout_flag)
        except ValueError:
            return _err("--timeout must be a number", _HELP, 2)

    waiting = "--wait" in flags
    params = {}
    origin = flags.get("--origin")
    # Supervision watches only Bill's own crew by default: a hand-off the user drives
    # (a non-`bill` origin) must never wake him. `--origin all` widens it back to every
    # task; an explicit `--origin <name>` narrows to that one. The plain listing stays
    # unscoped so `lb fleet` still shows the whole board.
    if waiting and origin is None:
        origin = "bill"
    if origin and origin != "all":
        params["origin"] = origin
    if waiting:
        params["timeout"] = timeout_flag or "300"
        path = "/api/bill/fleet/wait"
    else:
        path = "/api/bill/fleet"

    resp = _request("GET", path, params=params, timeout=_client_timeout(params))
    if resp.status_code >= 400:
        return _err(f"fleet request failed ({resp.status_code})", _HELP, 1)
    d = resp.json()
    rows = d.get("tasks", [])

    if "--json" in flags:
        _emit(json.dumps(rows))
        return 0

    if waiting:
        woke = d.get("woke")
        _emit(
            render_object(
                [
                    ("woke", "true" if woke else "false"),
                    ("waited", f"{d.get('waited', 0)}s"),
                    ("note", "" if woke else "no task needs you yet — re-run to keep waiting"),
                ]
            )
        )

    if not rows:
        _emit("fleet: 0 tasks")
        return 0

    _emit(render_collection("fleet", [_display(r) for r in rows], _COLS))
    return 0


def _display(row: dict) -> dict:
    shown = {c: row.get(c) for c in _COLS}
    # Workers arrive ordered under their overseer; indent them so the tree reads at a
    # glance (`port` \n `  ↳ issue-668`). Overseers and orphans render flush-left.
    if row.get("role") == "worker" and row.get("parent"):
        shown["task"] = f"  ↳ {row.get('task')}"
    shown["role"] = row.get("role") or "-"
    shown["since"] = f"{row['since']}s" if row.get("since") is not None else "-"
    shown["kind"] = row.get("kind") or "-"
    shown["unseen"] = "yes" if row.get("unseen") else ""
    shown["outcome"] = row.get("outcome") or "-"
    # A missing path renders as a visible gap rather than an empty cell: Bill is told to
    # copy these into `lb spawn --repo` / `lb worktree reap`, and "" reads like a value.
    shown["repo_path"] = row.get("repo_path") or "-"
    shown["path"] = row.get("path") or "-"
    return shown


def _client_timeout(params: dict) -> float:
    """Outlive the server's own long poll so the client never times out first."""
    return float(params.get("timeout", 300)) + 20
