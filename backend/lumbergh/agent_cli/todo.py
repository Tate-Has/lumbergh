"""`lb todo` — the repo's backlog, from inside the repo.

Todos live in the project DB rather than in a context window, so they are the one piece
of state that survives a `/clear`. That makes them the handoff between one babysit cycle
and the next, and this is the agent's only way to reach them.

`next` is the load-bearing verb: it answers "what should I work on" in one call, and its
empty case — no output, exit 1 — is what tells the `next` skill the backlog is done.
"""

from pathlib import Path

from lumbergh.agent_cli.main import _COMMAND_HELP, _emit, _err, _request
from lumbergh.agent_cli.toon import render_collection, render_object

_HELP = _COMMAND_HELP["todo"]
SUBCOMMANDS = ("next", "done", "undo", "add")


def run(positional: list[str], flags: dict) -> int:
    sub = positional[0] if positional else ""
    rest = positional[1:]
    repo = str(Path(flags.get("--repo") or Path.cwd()).expanduser().resolve())

    if not sub:
        return _list(repo)
    if sub == "next":
        return _next(repo)
    if sub == "done":
        return _set_done(repo, rest[0] if rest else "", done=True)
    if sub == "undo":
        return _set_done(repo, rest[0] if rest else "", done=False)
    if sub == "add":
        return _add(repo, rest[0] if rest else "", flags)
    return _err(f"unknown subcommand `{sub}`", _HELP, 2)


def _fetch(repo: str) -> list[dict] | int:
    resp = _request("GET", "/api/bill/todos", params={"repo": repo})
    if resp.status_code >= 400:
        return _refused(resp)
    return resp.json()["todos"]


def _refused(resp) -> int:
    d = resp.json().get("detail", {})
    return _err(d.get("error", "the server refused the request"), d.get("help"), 1)


def _rows(todos: list[dict]) -> list[dict]:
    return [
        {"n": i, "done": t.get("done", False), "text": t.get("text", "")}
        for i, t in enumerate(todos, 1)
    ]


def _list(repo: str) -> int:
    todos = _fetch(repo)
    if isinstance(todos, int):
        return todos
    if not todos:
        _emit("todos: no todos for this repo")
        return 0
    _emit(render_collection("todos", _rows(todos), ["n", "done", "text"]))
    return 0


def _next(repo: str) -> int:
    """The first undone item, or nothing at all and exit 1.

    Silence on an empty backlog is deliberate: the caller branches on the exit code, so
    there is nothing to parse and nothing to mistake for work.
    """
    todos = _fetch(repo)
    if isinstance(todos, int):
        return todos
    for index, todo in enumerate(todos, 1):
        if not todo.get("done"):
            _emit(
                render_object(
                    [
                        ("index", index),
                        ("text", todo.get("text", "")),
                        ("description", todo.get("description") or ""),
                    ]
                )
            )
            return 0
    return 1


def _set_done(repo: str, raw_index: str, *, done: bool) -> int:
    """`done <n>` and `undo <n>` — the same call with the flag flipped."""
    if not raw_index:
        return _err("which todo? pass its number", _HELP, 2)
    if not raw_index.lstrip("-").isdigit():
        return _err(f"`{raw_index}` is not a number", "run `lb todo` for the numbering", 2)

    path = "/api/bill/todos/done" if done else "/api/bill/todos/undo"
    resp = _request("POST", path, json={"repo": repo, "index": int(raw_index)})
    if resp.status_code >= 400:
        return _refused(resp)
    d = resp.json()
    _emit(render_object([("index", d["index"]), ("done", done), ("text", d["todo"]["text"])]))
    return 0


def _add(repo: str, text: str, flags: dict) -> int:
    if not text.strip():
        return _err("todo text is required", _HELP, 2)
    body = {"repo": repo, "text": text, "description": flags.get("--description")}
    resp = _request("POST", "/api/bill/todos/add", json=body)
    if resp.status_code >= 400:
        return _refused(resp)
    d = resp.json()
    _emit(render_object([("index", d["index"]), ("added", d["todo"]["text"])]))
    return 0
