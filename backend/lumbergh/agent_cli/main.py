"""`lb` — agent-facing control CLI for Lumbergh (AXI). Prints TOON to stdout.

Provenance: control-API surface adapted in spirit from herdr (see
~/.config/lumbergh/shared/herdr-steal-list.md); no code copied. Built to the AXI
standard (`.claude/skills/axi`).
"""

import os
import sys
from pathlib import Path

import httpx

from lumbergh import agent_token
from lumbergh.agent_cli.toon import render_block, render_collection, render_object

BASE = os.environ.get("LUMBERGH_URL", "http://127.0.0.1:8420")

FLAGS = {
    "": set(),
    "read": {"--session", "--source", "--last", "--full"},
    "state": {"--session"},
    "wait": {"--session", "--until", "--timeout"},
    "wait-output": {"--session", "--match", "--regex", "--timeout", "--lines"},
    "prompt": {"--session", "--wait"},
    "skill": {"--dir", "--check"},
    "worktree": {
        "--repo",
        "--branch",
        "--base",
        "--session",
        "--agent",
        "--intent",
        "--new",
        "--force",
        "--rm-branch",
        "--json",
    },
    "fleet": {"--wait", "--timeout", "--origin", "--json"},
    "spawn": {
        "--repo",
        "--branch",
        "--kind",
        "--brief",
        "--name",
        "--base",
        "--agent",
        "--intent",
        "--new",
        "--into",
        "--run",
        "--delivery",
    },
    "batch": {"--repo", "--run", "--briefs", "--kind", "--base", "--session", "--delivery"},
    "init": {"--repo", "--delivery", "--smoke"},
    "land": {"--run", "--onto", "--push", "--smoke", "--skip-smoke"},
    "teardown": {"--run", "--force"},
    "babysit": {"--session", "--stop", "--list"},
}
_BOOL_FLAGS = {
    "--full",
    "--wait",
    "--check",
    "--new",
    "--force",
    "--rm-branch",
    "--json",
    "--push",
    "--skip-smoke",
    "--stop",
    "--list",
}

# One usage line per command, so `lb <command> --help` is a real answer rather than a
# request the command runs anyway. Bill's AGENTS.md points him here when he is unsure of
# syntax, and a weak model that can self-serve syntax does not stall. Every key in FLAGS
# must appear here (a test pins that), and the error paths in `fleet`/`spawn` reuse these
# strings so a usage line can never drift from the help output.
_COMMAND_HELP = {
    "": "lb — live dashboard of every session Lumbergh supervises",
    "read": "lb read --session <name> [--last N] [--source transcript|pane|detection] [--full]",
    "state": "lb state --session <name>",
    "wait": "lb wait --session <name> --until idle|working|blocked|error|rest [--timeout <s>]",
    "wait-output": (
        'lb wait-output --session <name> --match "<text>" [--regex <re>] '
        "[--timeout <s>] [--lines <n>]"
    ),
    "prompt": 'lb prompt --session <name> "<text>" [--wait]',
    "skill": "lb skill [install] [--dir <path>] [--check]",
    "worktree": (
        "lb worktree ls --repo <path> [--json] | create --repo <path> --branch <b> [--new] "
        "[--base <b>] [--agent <provider> [--session <name>]] [--intent '...'] "
        "| reap <path> [--force] [--rm-branch] "
        "| adopt <path> [--session <name>] | link <path> | unlink <path>"
    ),
    "fleet": "lb fleet [--wait] [--timeout <s>] [--origin bill] [--json]",
    "spawn": (
        "lb spawn --repo <path> --branch <b> --kind ship|scout --brief <file> "
        "[--new] [--base <b>] [--name <n>] [--agent <provider>] [--intent '...'] "
        "[--into <session>] [--run <id>] [--delivery pr|branch|commit]"
    ),
    "batch": (
        "lb batch --repo <path> --run <id> --briefs <dir|a.md,b.md> --kind ship|scout "
        "[--base <b>] [--session <n>] [--delivery pr|branch|commit]"
    ),
    "land": "lb land --run <id> [--onto <base>] [--push] [--smoke '<cmd>'] [--skip-smoke]",
    "teardown": "lb teardown --run <id> [--force]",
    "init": "lb init --repo <path> [--delivery pr|branch|commit] [--smoke '<cmd>']",
    "babysit": "lb babysit --session <name> | --stop --session <name> | --list",
}


def _emit(s: str) -> None:
    print(s)


def _help_block(lines: list[str]) -> str:
    return "\n".join([f"help[{len(lines)}]:", *(f"  {ln}" for ln in lines)])


def _err(msg: str, help_line: str | None, code: int) -> int:
    _emit(f"error: {msg}")
    if help_line:
        _emit(f"help: {help_line}")
    return code


def _request(method: str, path: str, **kwargs):
    headers = {"X-Lumbergh-Agent-Token": agent_token.read_token() or ""}
    timeout = kwargs.pop("timeout", 320)
    return httpx.request(method, f"{BASE}{path}", headers=headers, timeout=timeout, **kwargs)


def _parse(argv):
    command = argv[0] if argv and not argv[0].startswith("-") else ""
    rest = argv[1:] if command else argv
    known = FLAGS.get(command)
    if known is None:
        return command, None, None, f"unknown command `{command}`"
    flags: dict = {}
    positional: list = []
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--help":
            flags["--help"] = True
            i += 1
        elif a.startswith("--"):
            if a not in known:
                return command, None, None, f"unknown flag {a} for `{command or 'lb'}`"
            if a in _BOOL_FLAGS:
                flags[a] = True
                i += 1
            else:
                flags[a] = rest[i + 1] if i + 1 < len(rest) else ""
                i += 2
        else:
            positional.append(a)
            i += 1
    return command, flags, positional, None


def _print_help(command: str) -> int:
    _emit(_COMMAND_HELP[command])
    _emit(f"flags: {' '.join(sorted(FLAGS[command])) or '(none)'} --help")
    return 0


def _target(flags):
    return flags.get("--session") or os.environ.get("LUMBERGH_SESSION")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    command, flags, positional, perr = _parse(argv)
    if perr:
        valid = " ".join(sorted(FLAGS.get(command, []))) or "(none)"
        return _err(
            perr, f"valid flags for `{command or 'lb'}`: {valid} (--help always allowed)", 2
        )

    if "--help" in flags:
        return _print_help(command)

    dispatch = {
        "": lambda: _cmd_home(),
        "state": lambda: _cmd_state(_target(flags)),
        "read": lambda: _cmd_read(_target(flags), flags),
        "wait": lambda: _cmd_wait(_target(flags), flags),
        "wait-output": lambda: _cmd_wait_output(_target(flags), flags),
        "prompt": lambda: _cmd_prompt(_target(flags), positional, flags),
        "skill": lambda: _cmd_skill(positional, flags),
        "worktree": lambda: _cmd_worktree(positional, flags),
        "fleet": lambda: _cmd_fleet(flags),
        "spawn": lambda: _cmd_spawn(flags),
        "batch": lambda: _cmd_batch(flags),
        "land": lambda: _cmd_land(flags),
        "teardown": lambda: _cmd_teardown(flags),
        "init": lambda: _cmd_init(flags),
        "babysit": lambda: _cmd_babysit(flags),
    }
    handler = dispatch.get(command)
    if handler is None:
        return _err(f"unknown command `{command}`", "run `lb` for the home view", 2)
    try:
        return handler()
    except httpx.ConnectError:
        return _err("Lumbergh server is not running", "start it with `lumbergh`, then retry", 1)


def _need_session(session) -> int | None:
    if not session:
        return _err("no session given", "pass --session <name> or set $LUMBERGH_SESSION", 2)
    return None


def _session_404(resp) -> int:
    detail = resp.json().get("detail", {})
    _emit(f"error: {detail.get('error', 'unknown session')}")
    _emit(
        render_collection("sessions", [{"name": n} for n in detail.get("sessions", [])], ["name"])
    )
    _emit("help: run `lb` to list sessions")
    return 1


def _cmd_home() -> int:
    data = _request("GET", "/api/agent/sessions").json()
    if data["total"] == 0:
        _emit("sessions: 0 live sessions")
        return 0
    _emit(render_collection("sessions", data["sessions"], ["name", "state", "unseen"]))
    _emit(
        _help_block(
            [
                "Run `lb read --session <name>` to see a session",
                "Run `lb wait --session <name> --until idle` to block until it finishes",
                "Run `lb fleet --wait` to block until a task needs you",
            ]
        )
    )
    return 0


def _cmd_state(session) -> int:
    if (e := _need_session(session)) is not None:
        return e
    resp = _request("GET", f"/api/agent/sessions/{session}/state")
    if resp.status_code == 404:
        return _session_404(resp)
    d = resp.json()
    _emit(
        render_object(
            [
                ("session", d["session"]),
                ("state", d["state"]),
                ("unseen", d["unseen"]),
                ("since", f"{round(d['since'])}s" if d.get("since") else ""),
            ]
        )
    )
    return 0


def _cmd_read(session, flags) -> int:
    if (e := _need_session(session)) is not None:
        return e
    params = {
        "source": flags.get("--source", "transcript"),
        "last": flags.get("--last", "10"),
        "full": str("--full" in flags).lower(),
    }
    resp = _request("GET", f"/api/agent/sessions/{session}/read", params=params)
    if resp.status_code == 404:
        return _session_404(resp)
    d = resp.json()
    if d["source"] == "transcript":
        _emit(
            render_object(
                [
                    ("session", session),
                    ("source", "transcript"),
                    ("count", f"{len(d['events'])} of {d['total']} events"),
                ]
            )
        )
        _emit(render_collection("events", d["events"], ["type", "tool", "text"]))
    else:
        pairs = [("session", session), ("source", d["source"])]
        if d.get("note"):
            pairs.append(("note", d["note"]))
        _emit(render_object(pairs))
        _emit(render_block("pane", d.get("pane", "")))
    return 0


def _cmd_wait(session, flags) -> int:
    if (e := _need_session(session)) is not None:
        return e
    until = flags.get("--until")
    if not until:
        return _err(
            "--until is required",
            "lb wait --until idle|working|blocked|error|rest [--timeout <s>]",
            2,
        )
    timeout = flags.get("--timeout", "300")
    resp = _request(
        "GET", f"/api/agent/sessions/{session}/wait", params={"until": until, "timeout": timeout}
    )
    if resp.status_code == 404:
        return _session_404(resp)
    d = resp.json()
    if not d["reached"]:
        return _err(
            f"timed out after {timeout}s waiting for {session} to reach `{until}` (still `{d['state']}`)",
            f"raise --timeout or check `lb read --session {session}`",
            1,
        )
    _emit(
        render_object([("session", session), ("state", d["state"]), ("waited", f"{d['waited']}s")])
    )
    return 0


def _cmd_wait_output(session, flags) -> int:
    if (e := _need_session(session)) is not None:
        return e
    match = flags.get("--match")
    regex = flags.get("--regex")
    if not match and not regex:
        return _err(
            "--match or --regex is required",
            'lb wait-output --match "<text>" [--regex <re>] [--timeout <s>] [--lines <n>]',
            2,
        )
    timeout = flags.get("--timeout", "300")
    params = {"timeout": timeout, "lines": flags.get("--lines", "200")}
    if match:
        params["match"] = match
    if regex:
        params["regex"] = regex
    resp = _request("GET", f"/api/agent/sessions/{session}/wait-output", params=params)
    if resp.status_code == 404:
        return _session_404(resp)
    if resp.status_code == 400:
        return _err(resp.json().get("detail", {}).get("error", "bad request"), None, 2)
    d = resp.json()
    if not d["matched"]:
        needle = match or regex
        return _err(
            f"timed out after {timeout}s waiting for `{needle}` in {session}",
            f"raise --timeout or check `lb read --session {session}`",
            1,
        )
    _emit(render_object([("session", session), ("matched", "true"), ("waited", f"{d['waited']}s")]))
    return 0


def _cmd_prompt(session, positional, flags) -> int:
    if (e := _need_session(session)) is not None:
        return e
    if not positional:
        return _err("prompt text is required", 'lb prompt "<text>" [--wait] [--session <name>]', 2)
    body = {"text": positional[0], "wait": "--wait" in flags}
    resp = _request("POST", f"/api/agent/sessions/{session}/prompt", json=body)
    if resp.status_code == 404:
        return _session_404(resp)
    d = resp.json()
    _emit(render_object([("session", session), ("sent", d["sent"]), ("state", d["state"])]))
    return 0


def _cmd_skill(positional, flags) -> int:
    from lumbergh.agent_cli import skill

    if "--check" in flags:
        if skill.check():
            _emit("skill: committed SKILL.md is up to date")
            return 0
        return _err("committed SKILL.md is out of date", "regenerate it from `lb skill` output", 1)
    if positional and positional[0] == "install":
        dir_flag = flags.get("--dir")
        dirs = [Path(dir_flag)] if dir_flag else skill.detect_dirs()
        if not dirs:
            _emit("skill: no agent skill directories found to install into")
            return 0
        written = skill.install(dirs)
        _emit(render_collection("installed", [{"path": str(p)} for p in written], ["path"]))
        return 0
    _emit(skill.SKILL_MD)
    return 0


def _cmd_worktree(positional, flags) -> int:
    from lumbergh.agent_cli import worktree as wt

    sub = positional[0] if positional else ""
    rest = positional[1:] if positional else []
    return wt.run(sub, flags, rest)


def _cmd_fleet(flags) -> int:
    from lumbergh.agent_cli import fleet as fleet_cli

    return fleet_cli.run(flags)


def _cmd_spawn(flags) -> int:
    from lumbergh.agent_cli import spawn as spawn_cli

    return spawn_cli.run(flags)


def _cmd_batch(flags) -> int:
    from lumbergh.agent_cli import batch as batch_cli

    return batch_cli.run(flags)


def _cmd_land(flags) -> int:
    from lumbergh.agent_cli import land as land_cli

    return land_cli.run(flags)


def _cmd_teardown(flags) -> int:
    from lumbergh.agent_cli import teardown as teardown_cli

    return teardown_cli.run(flags)


def _cmd_init(flags) -> int:
    from lumbergh.agent_cli import init as init_cli

    return init_cli.run(flags)


def _cmd_babysit(flags) -> int:
    from lumbergh.agent_cli import babysit as babysit_cli

    return babysit_cli.run(flags)


if __name__ == "__main__":
    sys.exit(main())
