"""`lb land` — assemble a run's branches, smoke-test, and (on --push) single-push."""

from lumbergh.agent_cli.main import _COMMAND_HELP, _emit, _err, _request
from lumbergh.agent_cli.toon import render_object

_HELP = _COMMAND_HELP["land"]


def run(flags: dict) -> int:
    if not flags.get("--run"):
        return _err("--run required", _HELP, 2)

    body = {
        "run": flags["--run"],
        "onto": flags.get("--onto"),
        "push": "--push" in flags,
        "smoke": flags.get("--smoke"),
        "skip_smoke": "--skip-smoke" in flags,
    }
    resp = _request("POST", "/api/bill/land", json=body)
    if resp.status_code >= 400:
        d = resp.json().get("detail", {})
        return _err(f"{d.get('stage', 'land')}: {d.get('error', 'land failed')}", d.get("help"), 1)

    d = resp.json()
    pairs = [
        ("run", d["run"]),
        ("batch", d["batch"]),
        ("base", d["base"]),
        ("pushed", "true" if d["pushed"] else "false"),
        ("smoke", d["smoke"]),
    ]
    if d.get("sha"):
        pairs.append(("sha", d["sha"]))
    if d.get("next"):
        pairs.append(("next", d["next"]))
    _emit(render_object(pairs))
    return 0
