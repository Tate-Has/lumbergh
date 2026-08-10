"""`lb report` — file a scout's findings, and read them back, without a shared filesystem.

A scout's deliverable is prose, and prose is not something a supervisor can act on
programmatically. So a report carries a small contracted header above it: whether there is
work to do, what finishing looks like, what the scout needed and could not determine, and
how sure it is. The server renders that header from these flags rather than trusting the
scout to type YAML — the shape has to hold however weak the model driving it is.

``--open-question`` is the field that closes the user's feedback loop. A scout that has
read the code knows precisely which detail was missing; that list becomes the clarifying
question put to the user, instead of a supervisor guessing what to ask.
"""

import json

from lumbergh import bill as bill_bundle
from lumbergh.agent_cli.main import _COMMAND_HELP, _body_from, _emit, _err, _help_block, _request
from lumbergh.agent_cli.toon import render_block, render_collection, render_object
from lumbergh.bill import artifacts

_HELP = _COMMAND_HELP["report"]
SUBCOMMANDS = ("write", "read", "list")

_YES = {"yes", "true", "y"}
_NO = {"no", "false", "n"}


def run(positional: list[str], flags: dict) -> int:
    sub = positional[0] if positional else ""
    if sub == "write":
        return _write(flags)
    if sub == "read":
        return _read(positional[1] if len(positional) > 1 else flags.get("--name", ""), flags)
    if sub == "list":
        return _list(flags)
    return _err(f"unknown subcommand `{sub}`" if sub else "no subcommand given", _HELP, 2)


def _actionable(raw: str | None) -> bool | None:
    value = (raw or "").strip().lower()
    if value in _YES:
        return True
    if value in _NO:
        return False
    return None


def _write(flags: dict) -> int:
    """Checked here against the same constants the server uses, so a typo costs no round
    trip and the two sides can never disagree about what a valid report is."""
    name = flags.get("--name")
    if not name:
        return _err("--name required", _HELP, 2)
    if not bill_bundle.SLUG.match(name):
        return _err(f"`{name}` is not a slug", bill_bundle.SLUG_HELP, 2)

    actionable = _actionable(flags.get("--actionable"))
    if actionable is None:
        return _err(
            "--actionable yes|no required",
            "say whether this report describes work to do — it is what a supervisor "
            "dispatches (or does not) from",
            2,
        )

    confidence = (flags.get("--confidence") or "").strip().lower()
    done_when = flags.get("--done-when")
    error = artifacts.validate(actionable, done_when, confidence)
    if error:
        return _err(error, _HELP, 2)

    body = _body_from(flags.get("--file"), _HELP)
    if isinstance(body, int):
        return body
    if not body.strip():
        return _err("the report is empty", "the header summarizes findings, it is not them", 2)

    questions = flags.get("--open-question") or []
    resp = _request(
        "POST",
        "/api/bill/report",
        json={
            "name": name,
            "body": body,
            "actionable": actionable,
            "done_when": done_when,
            "open_questions": questions if isinstance(questions, list) else [questions],
            "confidence": confidence,
        },
    )
    if resp.status_code >= 400:
        d = resp.json().get("detail", {})
        return _err(d.get("error", "could not write the report"), d.get("help"), 1)

    d = resp.json()
    _emit(render_object([("path", d["path"]), ("name", d["name"]), ("bytes", d["bytes"])]))
    _emit(_help_block([f"Finish with exactly one line: `DELIVERED: report {d['name']}`"]))
    return 0


def _read(name: str, flags: dict) -> int:
    if not name:
        return _err("no report name given", _HELP, 2)
    resp = _request("GET", "/api/bill/report", params={"name": name})
    if resp.status_code >= 400:
        d = resp.json().get("detail", {})
        return _err(d.get("error", "could not read the report"), d.get("help"), 1)

    d = resp.json()
    if "--json" in flags:
        _emit(json.dumps({"frontmatter": d.get("frontmatter", {}), "body": d.get("body", "")}))
        return 0
    if not d["exists"]:
        return _err(f"no report named `{name}`", "run `lb report list` for the ones there are", 1)

    fm = d["frontmatter"]
    pairs = [("name", d["name"]), ("path", d["path"])]
    pairs += [(k, fm[k]) for k in ("actionable", "done_when", "confidence") if k in fm]
    _emit(render_object(pairs))
    questions = fm.get("open_questions") or []
    if questions:
        _emit(render_collection("open_questions", [{"q": q} for q in questions], ["q"]))
    _emit(render_block("report", d["body"].rstrip("\n")))
    return 0


def _list(flags: dict) -> int:
    rows = _request("GET", "/api/bill/reports").json()["reports"]
    if "--json" in flags:
        _emit(json.dumps(rows))
        return 0
    # The header fields ride along so a whole directory can be triaged here, without a
    # fetch per report — which is the reason the listing carries them at all.
    for row in rows:
        row["questions"] = len(row.get("open_questions") or [])
    _emit(
        render_collection(
            "reports", rows, ["name", "actionable", "confidence", "questions", "modified"]
        )
    )
    if rows:
        _emit(_help_block(["Run `lb report read <name>` for one of them"]))
    return 0
