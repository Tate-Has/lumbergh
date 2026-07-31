"""The `target` identifier: `session` (bare) or `session:window`.

A target is the unit Lumbergh observes and drives. A session with a single
agent window collapses to its bare name (preserving all prior single-session
behavior); a session with several agent windows — e.g. a fleet batch — expands
into one target per window.
"""

from collections.abc import Callable

from lumbergh.providers import PROVIDERS

# Process command names that mean "a coding agent is alive in this pane". Derived
# from the provider launch strings (their first token) so this set can never drift
# from what Lumbergh actually starts — add a provider and detection follows for free.
AGENT_COMMANDS = frozenset(entry["launch"].split()[0] for entry in PROVIDERS.values())


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


def window_runs_agent(pane_commands: set[str]) -> bool:
    """True when an agent process is alive in the pane's process tree.

    The pane's *processes* are the ground-truth signal, not its on-screen text:
    a coding agent's UI chrome (the welcome banner, the box-drawn input frame)
    is only rendered in some states, so sniffing pane text silently drops a busy
    or compact-mode agent. The process is there regardless of what is drawn.
    """
    return bool(pane_commands & AGENT_COMMANDS)


def discover_targets(
    session_names: list[str],
    list_windows: Callable[[str], list[str]],
    pane_commands: Callable[[str], set[str]],
) -> list[str]:
    windows_by_session: dict[str, list[str]] = {}
    for session in session_names:
        windows = list_windows(session)
        if len(windows) == 1:
            if window_runs_agent(pane_commands(session)):
                windows_by_session[session] = windows
            else:
                windows_by_session[session] = []
        else:
            agent_windows = [
                w for w in windows if window_runs_agent(pane_commands(format_target(session, w)))
            ]
            windows_by_session[session] = agent_windows
    return select_targets(windows_by_session)
