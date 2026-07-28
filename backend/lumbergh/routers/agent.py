"""Localhost, token-gated control surface for the `lb` agent CLI.

Serves live state from the in-memory monitor (no DB race), transcript content via
the activity adapters, and pane/send via tmux. Auth is enforced by AuthMiddleware
(the agent token); this router assumes an already-authorized request.
"""

import asyncio
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lumbergh import session_attention
from lumbergh.activity.resolve import resolve_adapter
from lumbergh.detect import regions
from lumbergh.idle_monitor import idle_monitor
from lumbergh.tmux_pty import capture_pane_text, send_text

router = APIRouter(prefix="/api/agent")

_REST = {"idle", "blocked", "error"}


def _live_names() -> list[str]:
    from lumbergh.routers.sessions import get_live_sessions

    return list(get_live_sessions().keys())


def _meta(name: str) -> dict:
    from lumbergh.routers.sessions import get_stored_sessions

    return get_stored_sessions().get(name, {})


def _require(name: str) -> None:
    if name not in _live_names():
        raise HTTPException(
            status_code=404,
            detail={"error": f'no session named "{name}"', "sessions": _live_names()},
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
            limit = None if full else 500
            return {
                "source": "transcript",
                "total": len(events),
                "events": [
                    {
                        "type": e.type,
                        "tool": e.tool_name or "",
                        "text": _trunc(_oneline(e.text or e.tool_summary or ""), limit),
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


class PromptBody(BaseModel):
    text: str
    wait: bool = False


@router.post("/sessions/{name}/prompt")
async def prompt(name: str, body: PromptBody):
    _require(name)
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
