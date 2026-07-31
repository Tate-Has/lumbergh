"""`lb init` — declare how `lb` treats a repo (its delivery policy) in .lumbergh.toml."""

from pathlib import Path

from lumbergh.agent_cli.main import _COMMAND_HELP, _emit, _err, _request
from lumbergh.agent_cli.toon import render_object

_HELP = _COMMAND_HELP["init"]


def run(flags: dict) -> int:
    if not flags.get("--repo"):
        return _err("--repo required", _HELP, 2)

    body = {
        "repo": str(Path(flags["--repo"]).expanduser().resolve()),
        "delivery": flags.get("--delivery"),
        "smoke": flags.get("--smoke"),
    }
    resp = _request("POST", "/api/bill/init", json=body)
    if resp.status_code >= 400:
        d = resp.json().get("detail", {})
        return _err(f"{d.get('stage', 'init')}: {d.get('error', 'init failed')}", d.get("help"), 1)

    d = resp.json()
    _emit(
        render_object(
            [
                ("path", d["path"]),
                ("created", "true" if d["created"] else "false"),
                ("added", ", ".join(d["added"]) or "(none)"),
                ("unchanged", "; ".join(d["unchanged"]) or "(none)"),
            ]
        )
    )
    return 0
