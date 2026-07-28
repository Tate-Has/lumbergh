"""Manifest-driven overrides for session state detection.

The primary idle/working classifier is in :mod:`idle_monitor` and uses
pane-content quiescence (the agent's spinner / timer / token counter
animates continuously while working, so a frozen pane means idle).

This module provides :func:`classify_overrides` for cases where quiescence
is not enough: rate-limit errors, crashes, shell prompts (agent exited), and
approval/question/login UIs (a pane parked on a prompt is quiescent and would
otherwise read as idle).  The patterns live in data — priority-ordered TOML
manifests under ``detect/manifests/`` — evaluated by :mod:`lumbergh.detect`.
"""

from enum import Enum
from functools import lru_cache
from pathlib import Path

from lumbergh.detect.engine import classify as _engine_classify
from lumbergh.detect.manifest import load_manifests


class SessionState(Enum):
    UNKNOWN = "unknown"
    IDLE = "idle"  # Waiting for user input
    WORKING = "working"
    BLOCKED = "blocked"  # Stopped on an approval / question / login — waiting on the human
    ERROR = "error"  # Agent exited, crashed, or hit a rate limit
    STALLED = "stalled"  # Working for too long without progress


_STATE_MAP = {"blocked": SessionState.BLOCKED, "error": SessionState.ERROR}


def manifests_dir() -> Path:
    return Path(__file__).resolve().parent / "detect" / "manifests"


@lru_cache(maxsize=1)
def _manifests():
    return load_manifests(manifests_dir())


def classify_overrides(content: str, osc_title: str = "") -> SessionState | None:
    """Return a BLOCKED/ERROR override, or None to defer to quiescence.

    Delegates to the manifest engine; the string result is mapped to the app's
    :class:`SessionState`.  A veto rule and a no-match both yield None.
    """
    state = _engine_classify(content, osc_title, _manifests())
    return _STATE_MAP.get(state) if state else None
