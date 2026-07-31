"""`lb batch` — stand up one window worker per brief, grouped by run."""

from pathlib import Path

from lumbergh.agent_cli.main import _COMMAND_HELP, _emit, _err, _request
from lumbergh.agent_cli.toon import render_collection, render_object
from lumbergh.bill import TASK_KINDS

_HELP = _COMMAND_HELP["batch"]


def _absolute(path: str) -> str:
    return str(Path(path).expanduser().resolve())


def run(flags: dict) -> int:
    missing = [f for f in ("--repo", "--run", "--briefs", "--kind") if not flags.get(f)]
    if missing:
        return _err(f"{', '.join(missing)} required", _HELP, 2)
    if flags["--kind"] not in TASK_KINDS:
        return _err(f"unknown kind `{flags['--kind']}`", "--kind must be ship or scout", 2)

    briefs = [_absolute(p) for p in flags["--briefs"].split(",") if p]
    body = {
        "repo": flags["--repo"],
        "run": flags["--run"],
        "briefs": briefs,
        "kind": flags["--kind"],
        "base": flags.get("--base"),
        "session": flags.get("--session"),
        "delivery": flags.get("--delivery"),
    }
    resp = _request("POST", "/api/bill/batch", json=body)
    if resp.status_code >= 400:
        d = resp.json().get("detail", {})
        return _err(
            f"{d.get('stage', 'batch')}: {d.get('error', 'batch failed')}", d.get("help"), 1
        )

    d = resp.json()
    _emit(
        render_object(
            [
                ("run", d["run"]),
                ("session", d["session"]),
                ("spawned", str(len(d["workers"]))),
                ("failed", str(len(d["failed"]))),
            ]
        )
    )
    if d["workers"]:
        _emit(render_collection("workers", d["workers"], ["session", "branch", "kind", "path"]))
    if d["failed"]:
        _emit(render_collection("failed", d["failed"], ["brief", "error"]))
    return 0
