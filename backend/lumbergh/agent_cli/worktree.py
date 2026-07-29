"""`lb worktree` — first-class worktree lifecycle over the REST surface."""

import json

from lumbergh.agent_cli.main import _emit, _err, _request
from lumbergh.agent_cli.toon import render_collection, render_object

_COLS = ["path", "repo", "branch", "session", "agent", "state"]
# Named so a drift test can check the subcommands Bill's AGENTS.md tells him to run
# against the ones this module actually dispatches.
SUBCOMMANDS = ("ls", "create", "reap", "adopt", "link", "unlink")


def run(sub: str, flags: dict, positional: list) -> int:
    if sub in ("", "ls"):
        return _ls(flags)
    if sub == "create":
        return _create(flags)
    if sub == "reap":
        return _reap(flags, positional)
    if sub == "adopt":
        return _adopt(flags, positional)
    if sub in ("link", "unlink"):
        return _linkop(sub, positional)
    return _err(
        f"unknown worktree subcommand `{sub}`",
        f"lb worktree {'|'.join(SUBCOMMANDS)}",
        2,
    )


def _ls(flags) -> int:
    repo = flags.get("--repo")
    if not repo:
        return _err("--repo is required", "lb worktree ls --repo <path> [--json]", 2)
    data = _request("GET", "/api/worktrees", params={"repo": repo}).json()
    rows = data["worktrees"]
    if "--json" in flags:
        _emit(json.dumps(rows))
        return 0
    _emit(render_collection("worktrees", rows, _COLS))
    return 0


def _create(flags) -> int:
    repo, branch = flags.get("--repo"), flags.get("--branch")
    if not repo or not branch:
        return _err(
            "--repo and --branch are required",
            "lb worktree create --repo <path> --branch <name> [--new] [--base <b>]",
            2,
        )
    body = {
        "repo": repo,
        "branch": branch,
        "create_branch": "--new" in flags,
        "base_branch": flags.get("--base"),
        "session": flags.get("--session"),
        "task_intent": flags.get("--intent"),
    }
    d = _request("POST", "/api/worktrees", json=body).json()
    if d.get("error"):
        return _err(d["error"], None, 1)
    _emit(
        render_object(
            [
                ("path", d["path"]),
                ("linked", ", ".join(r["path"] for r in d.get("links_applied", [])) or "-"),
            ]
        )
    )
    return 0


def _reap(flags, positional) -> int:
    if not positional:
        return _err(
            "worktree path is required", "lb worktree reap <path> [--force] [--rm-branch]", 2
        )
    body = {
        "path": positional[0],
        "force": "--force" in flags,
        "rm_branch": "--rm-branch" in flags,
    }
    d = _request("POST", "/api/worktrees/reap", json=body).json()
    if d.get("error"):
        hint = (
            "re-run with --force to override" if d.get("reason") in ("dirty", "unpushed") else None
        )
        return _err(d["error"], hint, 1)
    _emit(render_object([("reaped", d["path"])]))
    return 0


def _adopt(flags, positional) -> int:
    if not positional:
        return _err("worktree path is required", "lb worktree adopt <path> [--session <name>]", 2)
    body = {"path": positional[0], "session": flags.get("--session")}
    d = _request("POST", "/api/worktrees/adopt", json=body).json()
    _emit(
        render_object([("adopted", d.get("path", positional[0])), ("branch", d.get("branch", "-"))])
    )
    return 0


def _linkop(sub, positional) -> int:
    if not positional:
        return _err("worktree path is required", f"lb worktree {sub} <path>", 2)
    d = _request("POST", f"/api/worktrees/{sub}", json={"path": positional[0]}).json()
    _emit(render_object([(sub, positional[0]), ("result", str(d))]))
    return 0
