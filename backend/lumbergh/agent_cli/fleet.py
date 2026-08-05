"""`lb fleet` — the whole crew in one table, with a token-free long poll."""

import json
import os

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
    "needs",
    # `dirty` + `commits` are the "is this safe to tear down?" pair. An idle worker with
    # `dirty: 7` / `commits: 0` looks finished and is the one state where reap destroys
    # work — the overseer used to have to poll git per worker to find it.
    "dirty",
    "commits",
    "outcome",
    "repo_path",
    "path",
]
_HELP = _COMMAND_HELP["fleet"]


def _params(flags: dict, waiting: bool) -> dict:
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
    # Who is watching: Bill wakes on his overseers; an overseer running this wakes on its
    # own workers. The caller's session is its identity in the tree, so pass it through.
    caller = os.environ.get("LUMBERGH_SESSION")
    if caller:
        params["as_session"] = caller
    if waiting:
        params["timeout"] = flags.get("--timeout") or "300"
    return params


def run(flags: dict) -> int:
    timeout_flag = flags.get("--timeout")
    if timeout_flag is not None:
        try:
            float(timeout_flag)
        except ValueError:
            return _err("--timeout must be a number", _HELP, 2)

    waiting = "--wait" in flags
    params = _params(flags, waiting)
    path = "/api/bill/fleet/wait" if waiting else "/api/bill/fleet"

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
        # A wake that returns in 0.0s is normal — a report was already waiting — but it
        # reads as a broken poll unless the line says which one, so name them here.
        woken_by = [r.get("task") for r in rows if r.get("attention")]
        _emit(
            render_object(
                [
                    ("woke", "true" if woke else "false"),
                    ("waited", f"{d.get('waited', 0)}s"),
                    (
                        "note",
                        f"needs you: {', '.join(woken_by)}"
                        if woke
                        else "no task needs you yet — re-run to keep waiting",
                    ),
                ]
            )
        )

    if "--heal" in flags:
        _heal(rows)

    if not rows:
        _emit("fleet: 0 tasks")
        return 0

    _emit(render_collection("fleet", [_display(r) for r in rows], _COLS))
    return 0


def _heal(rows: list[dict]) -> None:
    """Re-send the brief to every worker that never took it.

    The repair for `undelivered` is the one the overseer used to perform by hand, so it
    belongs behind a flag rather than in the read path: `lb fleet` must stay a question,
    not something that types into a worker's terminal as a side effect of being asked.
    """
    stuck = [r["task"] for r in rows if r.get("state") == "undelivered"]
    if not stuck:
        _emit("heal: no undelivered workers")
        return
    healed = []
    for task in stuck:
        resp = _request("POST", "/api/bill/redeliver", json={"target": task})
        detail = resp.json().get("detail", {}) if resp.status_code >= 400 else {}
        healed.append({"task": task, "result": detail.get("error", "brief re-sent")})
    _emit(render_collection("healed", healed, ["task", "result"]))
    # The table below was read before the repair, and a worker's context readout only
    # moves on the monitor's next poll — so say that, rather than print a stale board
    # as if it were the outcome.
    _emit("note: the fleet below predates the repair — re-run `lb fleet` to confirm")


def _display(row: dict) -> dict:
    shown = {c: row.get(c) for c in _COLS}
    # Workers arrive ordered under their overseer; indent them so the tree reads at a
    # glance (`port` \n `  ↳ issue-668`). Overseers and orphans render flush-left.
    if row.get("role") == "worker" and row.get("parent"):
        shown["task"] = f"  ↳ {row.get('task')}"
    shown["role"] = row.get("role") or "-"
    shown["since"] = f"{row['since']}s" if row.get("since") is not None else "-"
    shown["kind"] = row.get("kind") or "-"
    # `needs`, not the raw `unseen` overlay: a session the *user* left mid-thought is
    # unseen too, and a table that shows that in the "does this want me?" column is how
    # Bill ends up supervising sessions nobody handed him. The server decides.
    shown["needs"] = "yes" if row.get("attention") else ""
    shown["outcome"] = row.get("outcome") or "-"
    # `-`, never `0`: git declining to answer must not render as "nothing at stake".
    shown["dirty"] = "-" if row.get("dirty") is None else str(row["dirty"])
    shown["commits"] = "-" if row.get("commits") is None else str(row["commits"])
    # A missing path renders as a visible gap rather than an empty cell: Bill is told to
    # copy these into `lb spawn --repo` / `lb worktree reap`, and "" reads like a value.
    shown["repo_path"] = row.get("repo_path") or "-"
    shown["path"] = row.get("path") or "-"
    return shown


def _client_timeout(params: dict) -> float:
    """Outlive the server's own long poll so the client never times out first."""
    return float(params.get("timeout", 300)) + 20
