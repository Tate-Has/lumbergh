"""`lb brief` — file a brief in Bill's briefs/, and read one back, without his filesystem.

Bill's home lives next to the server. An occupant of the Bill role on another host speaks
only HTTP, so it sends a slug and the server resolves it against its own home: the caller
never learns a path here, and a slug cannot escape ``briefs/``. What ``write`` returns is
the server-side path, which is exactly what `lb spawn --brief` wants — spawn sends
``brief_path`` and the *server* opens it.

``read`` is the half that makes the loop two-way. A babysat session is ``/clear``ed every
refresh cycle and a remote Bill runs a fresh session per wake, so neither can remember what
it asked for; a fleet row carries only slug, kind, state and outcome. Intent has to be
re-readable rather than remembered.
"""

import json

from lumbergh import bill as bill_bundle
from lumbergh.agent_cli.main import _COMMAND_HELP, _body_from, _emit, _err, _help_block, _request
from lumbergh.agent_cli.toon import render_block, render_collection, render_object

_HELP = _COMMAND_HELP["brief"]
SUBCOMMANDS = ("write", "read", "list")


def run(positional: list[str], flags: dict) -> int:
    sub = positional[0] if positional else ""
    if sub == "write":
        return _write(flags)
    if sub == "read":
        return _read(positional[1] if len(positional) > 1 else flags.get("--name", ""), flags)
    if sub == "list":
        return _list(flags)
    return _err(f"unknown subcommand `{sub}`" if sub else "no subcommand given", _HELP, 2)


def _write(flags: dict) -> int:
    name = flags.get("--name")
    if not name:
        return _err("--name required", _HELP, 2)
    if not bill_bundle.SLUG.match(name):
        return _err(f"`{name}` is not a slug", bill_bundle.SLUG_HELP, 2)

    body = _body_from(flags.get("--file"), _HELP)
    if isinstance(body, int):
        return body
    if not body.strip():
        return _err("the brief is empty", "a worker cannot act on an empty brief", 2)

    resp = _request("POST", "/api/bill/brief", json={"name": name, "body": body})
    if resp.status_code >= 400:
        d = resp.json().get("detail", {})
        return _err(d.get("error", "could not write the brief"), d.get("help"), 1)

    d = resp.json()
    _emit(render_object([("path", d["path"]), ("name", d["name"]), ("bytes", d["bytes"])]))
    _emit(
        _help_block(
            [f"Run `lb spawn --name {d['name']} --brief {d['path']} …` to dispatch this brief"]
        )
    )
    return 0


def _read(name: str, flags: dict) -> int:
    if not name:
        return _err("no brief name given", _HELP, 2)
    resp = _request("GET", "/api/bill/brief", params={"name": name})
    if resp.status_code >= 400:
        d = resp.json().get("detail", {})
        return _err(d.get("error", "could not read the brief"), d.get("help"), 1)

    d = resp.json()
    if "--json" in flags:
        _emit(json.dumps(d))
        return 0
    if not d["exists"]:
        # Exit 1, not 0: a Bill asking for a brief that is not there has been told
        # something went wrong, and an empty success reads as "the brief was blank".
        return _err(f"no brief named `{name}`", "run `lb brief list` for the ones there are", 1)
    _emit(render_object([("name", d["name"]), ("path", d["path"])]))
    _emit(render_block("brief", d["body"].rstrip("\n")))
    return 0


def _list(flags: dict) -> int:
    rows = _request("GET", "/api/bill/briefs").json()["briefs"]
    if "--json" in flags:
        _emit(json.dumps(rows))
        return 0
    _emit(render_collection("briefs", rows, ["name", "bytes", "modified"]))
    if rows:
        _emit(_help_block(["Run `lb brief read <name>` for one of them"]))
    return 0
