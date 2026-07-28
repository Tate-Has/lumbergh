"""Idempotent install of the Lumbergh SessionStart hook into ~/.claude/settings.json.

Env-gated silent no-op hook + versioned managed entry is a pattern adapted in
spirit from herdr (see ~/.config/lumbergh/shared/herdr-steal-list.md); no code
copied. The installer never overwrites a settings.json it cannot parse.
"""

import json
import logging
import os
import shlex
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_MARKER = "lumbergh_session_start.py"


def hook_script_path() -> Path:
    return Path(__file__).resolve().parent / "hooks" / _MARKER


def default_settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def desired_command(interpreter: str, script: Path) -> str:
    return f"{shlex.quote(interpreter)} {shlex.quote(str(script))}"


def _is_managed(group: dict) -> bool:
    return any(_MARKER in h.get("command", "") for h in group.get("hooks", []))


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def ensure_installed(
    settings_path: Path | None = None,
    interpreter: str | None = None,
    script: Path | None = None,
) -> bool:
    settings_path = settings_path or default_settings_path()
    interpreter = interpreter or sys.executable
    script = script or hook_script_path()
    command = desired_command(interpreter, script)

    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except ValueError:
            logger.warning(
                "settings.json is not valid JSON; leaving it untouched: %s", settings_path
            )
            return False
    else:
        settings = {}

    hooks = settings.setdefault("hooks", {})
    session_start = hooks.setdefault("SessionStart", [])

    managed = next((g for g in session_start if _is_managed(g)), None)
    if managed is not None:
        if managed["hooks"][0].get("command") == command:
            return True  # already correct — write nothing
        managed["hooks"] = [{"type": "command", "command": command}]
    else:
        session_start.append({"hooks": [{"type": "command", "command": command}]})

    _atomic_write(settings_path, settings)
    return True


def uninstall(settings_path: Path | None = None) -> bool:
    settings_path = settings_path or default_settings_path()
    if not settings_path.exists():
        return True
    try:
        settings = json.loads(settings_path.read_text())
    except ValueError:
        return False
    session_start = settings.get("hooks", {}).get("SessionStart")
    if not session_start:
        return True
    settings["hooks"]["SessionStart"] = [g for g in session_start if not _is_managed(g)]
    _atomic_write(settings_path, settings)
    return True
