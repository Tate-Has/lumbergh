"""Lumbergh SessionStart hook — reports transcript identity + injects ambient context.

Self-contained (stdlib only): it must NOT import the lumbergh package, so no
unrelated import error can degrade the Claude session it runs inside. Best-effort
throughout — any problem exits 0 (with identity best-effort written first). Silent
unless LUMBERGH_SESSION is set (only Lumbergh-launched panes set it), which is what
makes a global install in ~/.claude/settings.json harmless everywhere else.

On startup/resume it also emits a compact, READ-ONLY dashboard of peer Lumbergh
sessions as `additionalContext`, so an agent opens already aware of its peers. The
full driving surface (incl. sending prompts to peers) lives in the on-demand `lb`
skill, not here — coordinating a peer is a deliberate act, never a reflex.

Store path + key mirror lumbergh.session_identity; a round-trip test pins them.
"""

import json
import os
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

_AMBIENT_SOURCES = ("startup", "resume")


def _config_root() -> Path:
    base = os.environ.get("LUMBERGH_DATA_DIR")
    return Path(base) if base else Path.home() / ".config" / "lumbergh"


def _store_dir() -> Path:
    return _config_root() / "session_identity"


def _key(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


def _write_identity(session: str, data: dict) -> None:
    record = {
        "session_id": data.get("session_id", ""),
        "transcript_path": data.get("transcript_path", ""),
        "cwd": data.get("cwd", ""),
        "source": data.get("source", ""),
        "written_at": time.time(),
    }
    try:
        directory = _store_dir()
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{_key(session)}.json"
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(record, f)
        os.replace(tmp, target)
    except Exception:  # noqa: S110 - best-effort; the hook must never crash the agent
        pass


def _ambient_context(source: str, self_name: str) -> str | None:
    """A compact, read-only peer dashboard for startup/resume; None otherwise."""
    if source not in _AMBIENT_SOURCES:
        return None
    try:
        token = (_config_root() / "agent-token").read_text().strip()
    except OSError:
        return None
    if not token:
        return None
    base = os.environ.get("LUMBERGH_URL", "http://127.0.0.1:8420")
    try:
        req = urllib.request.Request(  # noqa: S310 - fixed localhost scheme
            base + "/api/agent/sessions", headers={"X-Lumbergh-Agent-Token": token}
        )
        with urllib.request.urlopen(req, timeout=2) as resp:  # noqa: S310
            data = json.load(resp)
    except Exception:
        return None
    peers = [s for s in data.get("sessions", []) if s.get("name") != self_name]
    if not peers:
        return None
    lines = [f"  {s.get('name')} — {s.get('state')}" for s in peers]
    return (
        "Lumbergh sessions running alongside you (read-only view; inspect with the `lb` CLI):\n"
        + "\n".join(lines)
    )


def main() -> int:
    session = os.environ.get("LUMBERGH_SESSION")
    if not session:
        return 0
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    _write_identity(session, data)
    context = _ambient_context(data.get("source", ""), session)
    if context:
        try:
            print(json.dumps({"additionalContext": context}))
        except Exception:  # noqa: S110 - best-effort; the hook must never crash the agent
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
