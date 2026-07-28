"""Combined live activity feed — one WebSocket aggregating every running session.

Unlike a per-session activity stream, this endpoint takes no session name: it
discovers whatever sessions are currently running and multiplexes their
Claude Code transcript events onto a single connection, tagged with the
originating session name.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from lumbergh.activity.desktop import DesktopActivityBroker
from lumbergh.routers.sessions import get_live_sessions, get_session_workdir

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/activity", tags=["activity"])


def _safe_session_workdir(name: str) -> Path | None:
    """`get_session_workdir` raises HTTPException(404) for unknown sessions;
    the broker just wants None so it can skip and retry on the next pass."""
    try:
        return get_session_workdir(name)
    except Exception:
        return None


# Module-level singleton so the discovery/tail tasks are shared across
# concurrently-connected clients rather than duplicated per connection.
broker = DesktopActivityBroker(
    get_live_sessions=get_live_sessions,
    get_session_workdir=_safe_session_workdir,
)


@router.websocket("/stream")
async def activity_stream(websocket: WebSocket):
    import asyncio

    await websocket.accept()
    stop = asyncio.Event()

    async def drain_client():
        # We don't expect inbound frames, but reading detects disconnect promptly.
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            stop.set()

    reader = asyncio.create_task(drain_client())
    try:
        async for session_name, event in broker.stream(stop):
            await websocket.send_json({"session": session_name, "event": event.model_dump()})
    except WebSocketDisconnect:
        pass
    finally:
        stop.set()
        reader.cancel()
