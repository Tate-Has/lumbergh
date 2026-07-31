"""`lb spawn` — one call for worktree + worker + brief delivery."""

from pathlib import Path

from lumbergh.agent_cli.main import _COMMAND_HELP, _emit, _err, _request
from lumbergh.agent_cli.toon import render_object
from lumbergh.bill import TASK_KINDS

_HELP = _COMMAND_HELP["spawn"]


def _absolute(path: str) -> str:
    """A path the server can open regardless of its own cwd.

    The caller's relative path is relative to the *caller's* cwd — Bill's home, for
    the invocation ``AGENTS.md`` documents — so it has to be resolved here, before it
    goes on the wire. ``resolve`` is safe on a path that doesn't exist yet; whether
    the brief is really there is the server's call to make and report.
    """
    return str(Path(path).expanduser().resolve())


def run(flags: dict) -> int:
    missing = [f for f in ("--repo", "--branch", "--kind", "--brief") if not flags.get(f)]
    if missing:
        return _err(f"{', '.join(missing)} required", _HELP, 2)
    if flags["--kind"] not in TASK_KINDS:
        return _err(f"unknown kind `{flags['--kind']}`", "--kind must be ship or scout", 2)

    body = {
        "repo": flags["--repo"],
        "branch": flags["--branch"],
        "kind": flags["--kind"],
        "brief_path": _absolute(flags["--brief"]),
        "name": flags.get("--name"),
        "create_branch": "--new" in flags,
        "base_branch": flags.get("--base"),
        "agent_provider": flags.get("--agent"),
        "task_intent": flags.get("--intent"),
        "into": flags.get("--into"),
        "run": flags.get("--run"),
        "delivery": flags.get("--delivery"),
    }
    resp = _request("POST", "/api/bill/spawn", json=body)
    if resp.status_code >= 400:
        d = resp.json().get("detail", {})
        return _err(
            f"{d.get('stage', 'spawn')}: {d.get('error', 'spawn failed')}", d.get("help"), 1
        )
    d = resp.json()
    _emit(
        render_object(
            [
                ("session", d["session"]),
                ("kind", d["kind"]),
                ("branch", d["branch"]),
                ("path", d["path"]),
            ]
        )
    )
    return 0
