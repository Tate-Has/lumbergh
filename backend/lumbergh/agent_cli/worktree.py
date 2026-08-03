"""`lb worktree` — first-class worktree lifecycle over the REST surface."""

import json
import os
import re

from lumbergh.agent_cli.main import _emit, _err, _request
from lumbergh.agent_cli.toon import render_collection, render_object

_COLS = ["path", "repo", "branch", "session", "agent", "state"]
# Named so a drift test can check the subcommands Bill's AGENTS.md tells him to run
# against the ones this module actually dispatches.
SUBCOMMANDS = ("ls", "create", "reap", "adopt", "link", "unlink", "deps")


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
    if sub == "deps":
        return _deps(flags, positional)
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
            "lb worktree create --repo <path> --branch <name> [--new] [--base <b>] "
            "[--agent <provider> [--session <name>]]",
            2,
        )
    if flags.get("--agent"):
        return _create_driveable_session(flags, repo, branch)
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


def _session_slug(branch: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", branch).strip("-") or "session"


def _create_driveable_session(flags, repo: str, branch: str) -> int:
    """Create a worktree *and* an interactive session the user drives themselves.

    This is the hand-off shape: unlike `lb spawn`, there is no brief and no autonomous
    worker to supervise — just a worktree with the requested agent running in it, ready
    for the user at the keyboard. It reuses the session-create path (mode=worktree), so
    the worktree carries no `bill` origin and never enters Bill's supervision wait.
    """
    body = {
        "name": flags.get("--session") or _session_slug(branch),
        "mode": "worktree",
        "agent_provider": flags["--agent"],
        "worktree": {
            "parent_repo": repo,
            "branch": branch,
            "create_branch": "--new" in flags,
            "base_branch": flags.get("--base"),
        },
    }
    resp = _request("POST", "/api/sessions", json=body)
    d = resp.json()
    if resp.status_code >= 400 or d.get("error"):
        return _err(
            str(d.get("detail") or d.get("error") or "could not start the session"), None, 1
        )
    _emit(
        render_object(
            [
                ("session", d.get("name", body["name"])),
                ("path", d.get("workdir", "-")),
                ("agent", flags["--agent"]),
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
        "caller_pid": os.getpid(),
    }
    d = _request("POST", "/api/worktrees/reap", json=body).json()
    if d.get("error"):
        hint = (
            "re-run with --force to override"
            if d.get("reason") in ("dirty", "unlanded", "unknown")
            else None
        )
        return _err(d["error"], hint, 1)
    landed = d.get("landed")
    _emit(
        render_object(
            [
                ("reaped", d["path"]),
                ("landed", "unknown" if landed is None else landed),
                ("commits", d.get("commits")),
            ]
        )
    )
    for proc in d.get("processes_killed") or []:
        cmd = proc["cmd"]
        _emit(
            f"killed ({proc.get('signal', 'SIGTERM')}): "
            f"{proc['pid']} {cmd[:100]}{'…' * (len(cmd) > 100)}"
        )
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


def _deps(flags, positional) -> int:
    """Report whether this worktree's gate would run against the right dependencies.

    Exits 1 on drift so a worker can chain it in front of its own lint/test run: a
    green gate against the shared checkout's packages is worse than no gate at all.
    """
    if not positional:
        return _err("worktree path is required", "lb worktree deps <path> [--base <ref>]", 2)
    body = {"path": positional[0], "base": flags.get("--base")}
    d = _request("POST", "/api/worktrees/deps", json=body).json()
    drift = d.get("drift", [])
    if not drift:
        _emit(render_object([("deps", "ok"), ("path", positional[0])]))
        return 0
    _emit(
        render_collection(
            "drift",
            [{"link": r["link"], "manifests": " ".join(r["manifests"])} for r in drift],
            ["link", "manifests"],
        )
    )
    sync = d.get("dep_sync")
    fix = f"run `{sync}` in this worktree" if sync else "install this worktree's own dependencies"
    _emit(
        f"note: these are symlinked to the shared checkout, so lint and tests would pass "
        f"against dependencies this branch no longer declares — "
        f"`lb worktree unlink {positional[0]}`, then {fix}"
    )
    return 1


def _linkop(sub, positional) -> int:
    if not positional:
        return _err("worktree path is required", f"lb worktree {sub} <path>", 2)
    d = _request("POST", f"/api/worktrees/{sub}", json={"path": positional[0]}).json()
    _emit(render_object([(sub, positional[0]), ("result", str(d))]))
    return 0
