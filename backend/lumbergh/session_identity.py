"""Per-session Claude transcript identity, written by the SessionStart hook.

The hook (backend/lumbergh/hooks/lumbergh_session_start.py) writes these files;
the backend reads them to locate a session's transcript authoritatively instead
of guessing from the cwd. Keep key()/paths in lockstep with the hook — the
hook is self-contained and cannot import this module, so a round-trip test pins
the contract.
"""

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from lumbergh.constants import SESSION_IDENTITY_DIR


@dataclass
class Identity:
    session_id: str
    transcript_path: str
    cwd: str
    source: str
    written_at: float


def key(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


def store_dir() -> Path:
    return SESSION_IDENTITY_DIR


def _path(name: str, store: Path | None) -> Path:
    return (store or store_dir()) / f"{key(name)}.json"


def write(name: str, identity: Identity, store: Path | None = None) -> None:
    target = _path(name, store)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(asdict(identity), f)
    os.replace(tmp, target)


def read(name: str, store: Path | None = None) -> Identity | None:
    try:
        data = json.loads(_path(name, store).read_text())
        return Identity(
            session_id=data.get("session_id", ""),
            transcript_path=data.get("transcript_path", ""),
            cwd=data.get("cwd", ""),
            source=data.get("source", ""),
            written_at=float(data.get("written_at", 0.0)),
        )
    except (OSError, ValueError):
        return None


def prune(live_names: set[str], store: Path | None = None) -> None:
    directory = store or store_dir()
    if not directory.is_dir():
        return
    live_keys = {key(n) for n in live_names}
    for path in directory.glob("*.json"):
        if path.stem not in live_keys:
            path.unlink(missing_ok=True)
