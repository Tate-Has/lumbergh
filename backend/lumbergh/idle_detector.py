"""Manifest-driven overrides for session state detection.

The primary idle/working classifier is in :mod:`idle_monitor` and uses
pane-content quiescence (the agent's spinner / timer / token counter
animates continuously while working, so a frozen pane means idle).

This module provides :func:`classify_overrides` for cases where quiescence is
not enough: approval/question/login UIs (a pane parked on a prompt is quiescent
and would otherwise read as idle).  The patterns live in data — priority-ordered
TOML manifests under ``detect/manifests/`` — evaluated by :mod:`lumbergh.detect`.

There is intentionally no content-derived ERROR: "the agent died" is a process
fact (:mod:`lumbergh.idle_monitor`), not something to scrape from pane text.
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
    ERROR = "error"  # Agent process exited/died (derived from the process signal, not pane text)


# Only BLOCKED is derived from pane content. ERROR is *not* a content verdict:
# "the agent died" comes from the process signal in idle_monitor, because matching
# error words on screen flags displayed text, not a stopped agent.
_STATE_MAP = {"blocked": SessionState.BLOCKED}


def manifests_dir() -> Path:
    return Path(__file__).resolve().parent / "detect" / "manifests"


@lru_cache(maxsize=1)
def _manifests():
    return load_manifests(manifests_dir())


def classify_overrides(content: str, osc_title: str = "") -> SessionState | None:
    """Return a BLOCKED override, or None to defer to quiescence.

    Delegates to the manifest engine; the string result is mapped to the app's
    :class:`SessionState`.  A veto rule and a no-match both yield None.
    """
    state = _engine_classify(content, osc_title, _manifests())
    return _STATE_MAP.get(state) if state else None
