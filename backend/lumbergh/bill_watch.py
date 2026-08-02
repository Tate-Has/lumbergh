"""Which overseers are Bill's to watch.

An overseer row in the fleet is just "a live agent session that isn't a tracked worker" —
which includes every session the *user* opened for themselves. Those are not Bill's, and
treating them as his is how he ended up reading a scratch session's transcript and
reporting its findings back as supervised work.

Bill watches an overseer only when the user put it in his hands:

- a **babysit** (`lb babysit`) — standing, until the user cancels it;
- a **delegation** (Bill's own `lb prompt` to an overseer, the *delegate* shape) — one-shot,
  released once he has been shown the chunk it delivered.

Everything else is listed in `lb fleet` (he needs to see it to know a repo already has an
overseer to delegate to) but never wakes him and never reads as needing him.
"""

from __future__ import annotations

import json

from lumbergh import babysit
from lumbergh.constants import CONFIG_DIR

WATCH_PATH = CONFIG_DIR / "bill_watch.json"


def _load() -> dict[str, dict]:
    try:
        data = json.loads(WATCH_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(registry: dict[str, dict]) -> None:
    WATCH_PATH.parent.mkdir(parents=True, exist_ok=True)
    WATCH_PATH.write_text(json.dumps(registry, indent=2))


def engage(session: str, at: str) -> None:
    """Bill has delegated to ``session``, so it is his to watch until it reports back."""
    registry = _load()
    registry[session] = {"engaged_at": at}
    _save(registry)


def release(session: str) -> bool:
    """End a delegation. A babysit on the same session is untouched — it is the user's
    standing instruction, not this one-shot engagement."""
    registry = _load()
    existed = registry.pop(session, None) is not None
    if existed:
        _save(registry)
    return existed


def engaged() -> set[str]:
    return set(_load().keys())


def watched() -> set[str]:
    return engaged() | babysit.babysat_sessions()


def prune(live: set[str]) -> None:
    """Drop engagements for sessions that no longer exist, so the registry can't leak."""
    registry = _load()
    kept = {name: entry for name, entry in registry.items() if name in live}
    if len(kept) != len(registry):
        _save(kept)
