"""Localhost, token-gated control surface for the `lb` agent CLI.

Serves live state from the in-memory monitor (no DB race), transcript content via
the activity adapters, and pane/send via tmux. Auth is enforced by AuthMiddleware
(the agent token); this router assumes an already-authorized request.
"""

import asyncio
import re
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lumbergh import session_attention
from lumbergh.activity.resolve import resolve_adapter
from lumbergh.activity.resolve import session_meta as _meta
from lumbergh.detect import regions
from lumbergh.idle_monitor import idle_monitor
from lumbergh.tmux_pty import capture_pane_text, send_text

router = APIRouter(prefix="/api/agent")

_REST = {"idle", "blocked", "error"}
BILL_SESSION = "bill"


def _live_names() -> list[str]:
    return idle_monitor.live_targets()


def _require(name: str) -> None:
    names = _live_names()
    if name not in names:
        raise HTTPException(
            status_code=404,
            detail={"error": f'no session named "{name}"', "sessions": names},
        )


def _state(name: str) -> str:
    return idle_monitor.get_state(name).value


def _trunc(text: str, limit: int | None) -> str:
    if limit is None or len(text) <= limit:
        return text
    return text[:limit] + f"… ({len(text)} chars total)"


def _oneline(text: str) -> str:
    """Collapse whitespace so a transcript event stays one clean TOON row."""
    return " ".join(text.split())


def _event_text(e, limit: int | None, full: bool) -> str:
    """The one-line text for a transcript event.

    A ``tool_result``'s raw body is command output — a git listing, a prior ``lb fleet``
    dump, a build log — and it is where a *stale* snapshot of another session's state
    bleeds in. A reader judging what a session is doing *now* (Bill, an overseer) read
    ``working, 1334s`` out of an old fleet dump embedded in a finished session's own
    transcript and concluded it was still working. So a tool_result shows only its
    ok/error marker by default; ``--full`` restores the body for genuine spelunking.
    The session's live STATE comes from ``lb fleet``/``lb state``, never from this text.
    """
    if e.type == "tool_result" and not full:
        return f"[{e.status or 'result'}]"
    return _trunc(_oneline(e.text or e.tool_summary or ""), limit)


@router.get("/sessions")
def sessions():
    names = _live_names()
    return {
        "total": len(names),
        "sessions": [
            {"name": n, "state": _state(n), "unseen": session_attention.is_unseen(n)} for n in names
        ],
    }


@router.get("/sessions/{name}/state")
def state(name: str):
    _require(name)
    return {
        "session": name,
        "state": _state(name),
        "unseen": session_attention.is_unseen(name),
        "since": idle_monitor.state_since_seconds(name),
    }


@router.get("/sessions/{name}/read")
def read(name: str, source: str = "transcript", last: int = 10, full: bool = False):
    _require(name)
    if source == "transcript":
        meta = _meta(name)
        cwd = Path(meta["workdir"]) if meta.get("workdir") else None
        adapter = resolve_adapter(name, cwd, meta.get("agent_provider"))
        if adapter is not None:
            events = adapter.read_new()
            recent = events[-last:]
            limit = None if full else 300
            return {
                "source": "transcript",
                "total": len(events),
                "events": [
                    {
                        "type": e.type,
                        "tool": e.tool_name or "",
                        "text": _event_text(e, limit, full),
                    }
                    for e in recent
                ],
            }
        text = capture_pane_text(name)
        return {
            "source": "pane",
            "pane": _trunc(text, None if full else 1500),
            "note": "no transcript for this session; showing the pane",
        }
    if source == "detection":
        text = "\n".join(regions.extract("recent", capture_pane_text(name), ""))
        return {"source": "detection", "pane": text}
    text = capture_pane_text(name)
    return {"source": "pane", "pane": _trunc(text, None if full else 1500)}


@router.get("/sessions/{name}/wait")
async def wait(name: str, until: str, timeout: float = 300.0):
    _require(name)
    targets = _REST if until == "rest" else {until}
    deadline = time.monotonic() + timeout
    start = time.monotonic()
    while True:
        st = _state(name)
        if st in targets:
            return {
                "session": name,
                "state": st,
                "waited": round(time.monotonic() - start, 1),
                "reached": True,
            }
        if time.monotonic() >= deadline:
            return {
                "session": name,
                "state": st,
                "waited": round(time.monotonic() - start, 1),
                "reached": False,
            }
        await asyncio.sleep(0.25)


def _output_matches(text: str, match: str | None, pattern: re.Pattern | None) -> bool:
    if match and match in text:
        return True
    return bool(pattern and pattern.search(text))


@router.get("/sessions/{name}/wait-output")
async def wait_output(
    name: str,
    match: str | None = None,
    regex: str | None = None,
    timeout: float = 300.0,
    lines: int = 200,
):
    """Block until the pane content contains ``match`` or matches ``regex``.

    The current snapshot is checked *before* the first sleep, so output that has
    already arrived still matches — no lost-wakeup race.
    """
    _require(name)
    if not match and not regex:
        raise HTTPException(status_code=400, detail={"error": "provide match or regex"})
    pattern = None
    if regex:
        try:
            pattern = re.compile(regex)
        except re.error as e:
            raise HTTPException(status_code=400, detail={"error": f"invalid regex: {e}"})

    deadline = time.monotonic() + timeout
    start = time.monotonic()
    while True:
        text = capture_pane_text(name, lines=lines)
        if _output_matches(text, match, pattern):
            return {"session": name, "matched": True, "waited": round(time.monotonic() - start, 1)}
        if time.monotonic() >= deadline:
            return {"session": name, "matched": False, "waited": round(time.monotonic() - start, 1)}
        await asyncio.sleep(0.25)


class PromptBody(BaseModel):
    text: str
    wait: bool = False
    # Who is sending. Bill prompting a session *is* the delegate shape, and that is the
    # only signal the server gets that an overseer is now his to supervise.
    as_session: str | None = None


@router.post("/sessions/{name}/prompt")
async def prompt(name: str, body: PromptBody):
    _require(name)
    if body.as_session == BILL_SESSION and name != BILL_SESSION:
        from lumbergh.routers.bill import engage_overseer

        engage_overseer(name)
    before = _state(name)
    if not send_text(name, body.text):
        raise HTTPException(status_code=500, detail={"error": f"failed to send to {name}"})
    changed = False
    if body.wait:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if _state(name) != before:
                changed = True
                break
            await asyncio.sleep(0.25)
    return {"session": name, "sent": body.text, "state": _state(name), "changed": changed}
