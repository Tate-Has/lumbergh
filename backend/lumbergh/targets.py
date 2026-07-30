"""The `target` identifier: `session` (bare) or `session:window`.

A target is the unit Lumbergh observes and drives. A session with a single
agent window collapses to its bare name (preserving all prior single-session
behavior); a session with several agent windows — e.g. a fleet batch — expands
into one target per window.
"""

from collections.abc import Callable

_AGENT_MARKERS = ("Claude Code", "╭─ Claude")  # box-drawn Claude Code prompt frame


def parse_target(target: str) -> tuple[str, str | None]:
    session, sep, window = target.partition(":")
    return (session, window) if sep else (session, None)


def format_target(session: str, window: str | None) -> str:
    return f"{session}:{window}" if window else session


def select_targets(windows_by_session: dict[str, list[str]]) -> list[str]:
    targets: list[str] = []
    for session, windows in windows_by_session.items():
        if not windows:
            continue
        if len(windows) == 1:
            targets.append(session)
        else:
            targets.extend(format_target(session, w) for w in sorted(windows))
    return targets


def window_runs_agent(pane_text: str) -> bool:
    return any(marker in pane_text for marker in _AGENT_MARKERS)


def discover_targets(
    session_names: list[str],
    list_windows: Callable[[str], list[str]],
    capture: Callable[[str], str],
) -> list[str]:
    windows_by_session: dict[str, list[str]] = {}
    for session in session_names:
        windows = list_windows(session)
        if len(windows) == 1:
            pane_text = capture(session)
            if window_runs_agent(pane_text):
                windows_by_session[session] = windows
            else:
                windows_by_session[session] = []
        else:
            agent_windows = [
                w for w in windows if window_runs_agent(capture(format_target(session, w)))
            ]
            windows_by_session[session] = agent_windows
    return select_targets(windows_by_session)
