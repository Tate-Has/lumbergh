"""`lb babysit` — keep an overseer cycling through its refresh ritual, hands-off.

Start it and the server drives the loop: each time the session goes idle having asked to
refresh, it is sent the `/clear` + restart it can't run for itself. Stop it before you take
the session over yourself.
"""

from lumbergh.agent_cli.main import _COMMAND_HELP, _emit, _err, _request, _target
from lumbergh.agent_cli.toon import render_collection, render_object

_HELP = _COMMAND_HELP["babysit"]


def run(flags: dict) -> int:
    if "--list" in flags:
        resp = _request("GET", "/api/bill/babysit")
        rows = resp.json().get("babysits", [])
        if not rows:
            _emit("babysits: none active")
            return 0
        _emit(render_collection("babysits", rows, ["session", "repo", "added_at"]))
        return 0

    session = _target(flags)
    if not session:
        return _err("no session given", "pass --session <name> or set $LUMBERGH_SESSION", 2)

    if "--refresh" in flags:
        resp = _request("POST", "/api/bill/babysit/refresh", json={"session": session})
        if resp.status_code >= 400:
            d = resp.json().get("detail", {})
            return _err(d.get("error", "could not refresh"), d.get("help"), 1)
        d = resp.json()
        _emit(render_object([("session", d["session"]), ("refreshed", "true")]))
        return 0

    if "--stop" in flags:
        resp = _request("DELETE", "/api/bill/babysit", params={"session": session})
        d = resp.json()
        _emit(render_object([("session", d["session"]), ("stopped", str(d["stopped"]).lower())]))
        return 0

    resp = _request("POST", "/api/bill/babysit", json={"session": session})
    if resp.status_code >= 400:
        d = resp.json().get("detail", {})
        return _err(d.get("error", "could not start babysit"), d.get("help"), 1)
    d = resp.json()
    _emit(render_object([("session", d["session"]), ("babysitting", "true")]))
    return 0
