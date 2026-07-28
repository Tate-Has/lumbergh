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
DESCRIPTION = "Observe and coordinate Lumbergh agent sessions from the shell"

FLAGS = {
    "": set(),
    "read": {"--session", "--source", "--last", "--full"},
    "state": {"--session"},
    "wait": {"--session", "--until", "--timeout"},
    "wait-output": {"--session", "--match", "--regex", "--timeout", "--lines"},
    "prompt": {"--session", "--wait"},
    "skill": {"--dir", "--check"},
}
_BOOL_FLAGS = {"--full", "--wait", "--check"}


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


def _bin() -> str:
    return str(Path(sys.argv[0]).resolve()).replace(str(Path.home()), "~")


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

    try:
        if command == "":
            return _cmd_home()
        if command == "state":
            return _cmd_state(_target(flags))
        if command == "read":
            return _cmd_read(_target(flags), flags)
        if command == "wait":
            return _cmd_wait(_target(flags), flags)
        if command == "wait-output":
            return _cmd_wait_output(_target(flags), flags)
        if command == "prompt":
            return _cmd_prompt(_target(flags), positional, flags)
        if command == "skill":
            return _cmd_skill(positional, flags)
    except httpx.ConnectError:
        return _err("Lumbergh server is not running", "start it with `lumbergh`, then retry", 1)
    return _err(f"unknown command `{command}`", "run `lb` for the home view", 2)


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
    _emit(
        render_object(
            [
                ("bin", _bin()),
                ("description", DESCRIPTION),
                ("count", f"{data['total']} of {data['total']} total"),
            ]
        )
    )
    if data["total"] == 0:
        _emit("sessions: 0 live sessions")
        return 0
    _emit(render_collection("sessions", data["sessions"], ["name", "state", "unseen"]))
    _emit(
        _help_block(
            [
                "Run `lb read --session <name>` to see a session",
                "Run `lb wait --session <name> --until idle` to block until it finishes",
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


if __name__ == "__main__":
    sys.exit(main())
