"""Runtime 'seen/unseen' attention overlay for sessions.

A session becomes *unseen* when it enters an attention state (idle/blocked/error)
while nobody is viewing it, and *seen* again when a viewer opens it. This powers
the "finished while you were away" distinction (pattern adapted in spirit from
herdr; no code copied — see ~/.config/lumbergh/shared/herdr-steal-list.md).

The maps are mutated only on the asyncio event loop with no await between
read-modify-write, so no locking is needed. Persistence is a single small JSON
file, written offloaded and best-effort; viewers are never persisted.
"""

import json
import logging
import os
import tempfile
from pathlib import Path

from lumbergh.constants import SESSION_ATTENTION_FILE

logger = logging.getLogger(__name__)

_viewing: set[str] = set()
_unseen: dict[str, str] = {}  # name -> attentionState


def reset() -> None:
    _viewing.clear()
    _unseen.clear()


def _session_of(target: str) -> str:
    """The session a target belongs to: `batch:1187` is work inside `batch`."""
    return target.split(":", 1)[0]


def clear_session(name: str) -> None:
    """Mark a session seen, windows included.

    Work inside a batch session is flagged per window (`batch:1187`), but there is
    only one thing to open — the session. Clearing just the bare name left those
    window flags standing for good.
    """
    for target in [t for t in _unseen if _session_of(t) == name]:
        _unseen.pop(target, None)


def set_viewing(name: str, viewing: bool) -> None:
    if viewing:
        _viewing.add(name)
        clear_session(name)
    else:
        _viewing.discard(name)


def forget_missing(live_sessions: set[str]) -> None:
    """Drop flags for sessions that no longer exist.

    Nothing ever removed these, so every finished batch left its windows behind:
    a "while you were away" that no click could ever answer, because the session
    it pointed at was long gone.
    """
    for target in [t for t in _unseen if _session_of(t) not in live_sessions]:
        _unseen.pop(target, None)


def mark_attention(name: str, state: str) -> None:
    if name in _viewing:
        return
    _unseen[name] = state


def clear_unseen(name: str) -> None:
    _unseen.pop(name, None)


def is_unseen(name: str) -> bool:
    return name in _unseen


def get(name: str) -> str | None:
    return _unseen.get(name)


def unseen_count() -> int:
    return len(_unseen)


def snapshot() -> dict[str, dict]:
    return {name: {"unseen": True, "attentionState": state} for name, state in _unseen.items()}


def _write(path: Path | None = None) -> None:
    target = path or SESSION_ATTENTION_FILE
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(_unseen, f)
        os.replace(tmp, target)
    except OSError as exc:
        logger.warning("Could not persist session attention: %s", exc)


def load(path: Path | None = None) -> None:
    target = path or SESSION_ATTENTION_FILE
    try:
        data = json.loads(target.read_text())
        if isinstance(data, dict):
            _unseen.clear()
            _unseen.update({str(k): str(v) for k, v in data.items()})
    except (OSError, ValueError):
        return


async def persist() -> None:
    import asyncio

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _write)
