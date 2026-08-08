"""`lb prefs` — read the user's standing preferences, or add one, over HTTP.

``AGENTS.md`` has Bill read `preferences.md` before answering any worker's question and
append a dated bullet whenever the user states a standing preference. A Bill occupying
the role from another host cannot open the file, so these two verbs are the whole of it.

There is no verb that replaces the file. It is the user's, hand-edited, and append-only
is the contract — the server stamps the date and formats the bullet so the shape holds
however weak the model driving this is.
"""

from lumbergh.agent_cli.main import _COMMAND_HELP, _emit, _err, _request
from lumbergh.agent_cli.toon import render_block, render_object

_HELP = _COMMAND_HELP["prefs"]
SUBCOMMANDS = ("read", "add")


def run(positional: list[str], flags: dict) -> int:
    sub = positional[0] if positional else ""
    if sub == "read":
        return _read()
    if sub == "add":
        return _add(positional[1] if len(positional) > 1 else "", flags)
    return _err(f"unknown subcommand `{sub}`" if sub else "no subcommand given", _HELP, 2)


def _read() -> int:
    resp = _request("GET", "/api/bill/preferences")
    d = resp.json()
    if not d.get("exists"):
        _emit("preferences: no preferences recorded yet")
        return 0
    _emit(render_object([("path", d["path"])]))
    _emit(render_block("preferences", d["body"].rstrip("\n")))
    return 0


def _add(text: str, flags: dict) -> int:
    if not text.strip():
        return _err("preference text is required", _HELP, 2)
    reason = flags.get("--reason")
    if not reason or not reason.strip():
        return _err("--reason required", "record why the preference exists, not just what", 2)

    resp = _request("POST", "/api/bill/preferences", json={"text": text, "reason": reason})
    if resp.status_code >= 400:
        d = resp.json().get("detail", {})
        return _err(d.get("error", "could not add the preference"), d.get("help"), 1)

    d = resp.json()
    _emit(render_object([("path", d["path"]), ("added", d["bullet"])]))
    return 0
