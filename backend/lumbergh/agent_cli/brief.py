"""`lb brief write` — file a brief in Bill's briefs/ without touching his filesystem.

Bill's home lives next to the server. An occupant of the Bill role on another host
speaks only HTTP, so it sends a slug and the server resolves it against its own home:
the caller never learns a path here, and a slug cannot escape ``briefs/``. What comes
back is the server-side path, which is exactly what `lb spawn --brief` wants — spawn
sends ``brief_path`` and the *server* opens it.
"""

import sys
from pathlib import Path

from lumbergh import bill as bill_bundle
from lumbergh.agent_cli.main import _COMMAND_HELP, _emit, _err, _help_block, _request
from lumbergh.agent_cli.toon import render_object

_HELP = _COMMAND_HELP["brief"]
SUBCOMMANDS = ("write",)


def _body_from(file_flag: str | None) -> str | int:
    """The brief's text, or the exit code of the usage error printed instead.

    ``--file -`` and a bare pipe are the same thing. A terminal on stdin is refused
    rather than read: blocking on a tty is indistinguishable from a hung command.
    """
    if file_flag and file_flag != "-":
        path = Path(file_flag).expanduser()
        if not path.is_file():
            return _err(f"no file at {path}", _HELP, 2)
        return path.read_text()
    if sys.stdin.isatty():
        return _err("no brief body given", _HELP, 2)
    return sys.stdin.read()


def run(positional: list[str], flags: dict) -> int:
    sub = positional[0] if positional else ""
    if sub not in SUBCOMMANDS:
        return _err(f"unknown subcommand `{sub}`" if sub else "no subcommand given", _HELP, 2)

    name = flags.get("--name")
    if not name:
        return _err("--name required", _HELP, 2)
    if not bill_bundle.SLUG.match(name):
        return _err(f"`{name}` is not a slug", bill_bundle.SLUG_HELP, 2)

    body = _body_from(flags.get("--file"))
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
