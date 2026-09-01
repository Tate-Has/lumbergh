"""Provider-native delivery for Codex CLI sessions.

Typing into a Codex TUI while it is executing interrupts the current turn.  Codex
ships ``codex queue`` specifically for adding a message to an existing thread, so
Lumbergh must use it instead of emulating keyboard input.
"""

import json
import subprocess
from pathlib import Path

SESSIONS_DIR = Path.home() / ".codex" / "sessions"


def find_thread(cwd: Path, sessions_dir: Path = SESSIONS_DIR) -> str | None:
    """Return the newest Codex thread recorded for ``cwd``.

    Lumbergh gives each Bill home and spawned worker its own working directory,
    making the newest matching transcript the thread that owns that terminal.
    A missing or malformed transcript is deliberately not guessed at.
    """
    try:
        wanted = cwd.expanduser().resolve()
    except OSError:
        return None
    try:
        candidates = sorted(
            sessions_dir.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
        )
    except OSError:
        return None
    for path in candidates:
        try:
            with path.open(encoding="utf-8") as source:
                record = json.loads(source.readline())
            payload = record.get("payload") or {}
            if record.get("type") != "session_meta" or not payload.get("session_id"):
                continue
            if Path(payload.get("cwd", "")).expanduser().resolve() == wanted:
                return str(payload["session_id"])
        except (OSError, ValueError, TypeError):
            continue
    return None


def queue_message(cwd: Path, text: str, *, run=subprocess.run, find=find_thread) -> bool:
    """Queue ``text`` onto the Codex thread for ``cwd`` without interrupting it."""
    thread = find(cwd)
    if not thread:
        return False
    try:
        result = run(
            ["codex", "queue", "--thread", thread, "--message", text],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0
