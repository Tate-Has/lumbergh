"""`lb teardown` — kill a run's windows and reap its worktrees, refusing dirty work."""

from lumbergh.agent_cli.main import _COMMAND_HELP, _emit, _err, _request
from lumbergh.agent_cli.toon import render_collection, render_object

_HELP = _COMMAND_HELP["teardown"]


def run(flags: dict) -> int:
    if not flags.get("--run"):
        return _err("--run required", _HELP, 2)

    body = {"run": flags["--run"], "force": "--force" in flags}
    resp = _request("POST", "/api/bill/teardown", json=body)
    if resp.status_code >= 400:
        d = resp.json().get("detail", {})
        return _err(
            f"{d.get('stage', 'teardown')}: {d.get('error', 'teardown failed')}", d.get("help"), 1
        )

    d = resp.json()
    _emit(render_object([("run", d["run"]), ("refused", str(len(d["refused"])))]))
    if d["results"]:
        _emit(render_collection("results", d["results"], ["target", "killed", "reaped"]))
    if d["refused"]:
        _emit(
            "note: "
            + ", ".join(d["refused"])
            + " left running — dirty/unpushed work; commit+push or pass --force"
        )
    return 0
