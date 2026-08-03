"""The `target` identifier: `session` (bare) or `session:window`.

A target is the unit Lumbergh observes and drives. A session with a single
agent window collapses to its bare name (preserving all prior single-session
behavior); a session with several agent windows — e.g. a fleet batch — expands
into one target per window.

Window *names* are the label in a target because they carry meaning (`port:issue-841`),
but tmux does not require them to be unique, and an ambiguous `session:name` ref is one
tmux refuses to act on. So a window's identity for lookups is its tmux window id, and
the label falls back to the window index whenever a name is shared.
"""

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from lumbergh.providers import PROVIDERS

# Process command names that mean "a coding agent is alive in this pane". Derived
# from the provider launch strings (their first token) so this set can never drift
# from what Lumbergh actually starts — add a provider and detection follows for free.
AGENT_COMMANDS = frozenset(entry["launch"].split()[0] for entry in PROVIDERS.values())


@dataclass(frozen=True)
class Window:
    """A tmux window as discovery sees it.

    ``id`` is tmux's own ``@n`` handle — unique within the server and the only ref
    guaranteed to address exactly this window. ``index`` and ``name`` are the two
    candidate labels for the target string.
    """

    id: str
    index: str
    name: str


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


def window_labels(windows: Sequence[Window]) -> dict[str, str]:
    """window id → the label its target uses: the name when usable, else the index.

    A name is usable only when it is unique in the session and non-empty — tmux permits
    both a shared name and an empty one, and either would yield a target string that
    addresses the wrong window (or, for an empty name, the bare session itself).
    """
    shared = Counter(w.name for w in windows)
    return {w.id: (w.name if w.name and shared[w.name] == 1 else w.index) for w in windows}


def discover_targets(
    session_names: list[str],
    list_windows: Callable[[str], Sequence[Window]],
    pane_commands: Callable[[str], set[str]],
) -> list[str]:
    """Every target with a live agent, given a per-session window listing.

    ``pane_commands`` is asked about window *ids*, never about a formatted target,
    so an unlucky window name can never make a running agent unaddressable.
    """
    windows_by_session: dict[str, list[str]] = {}
    for session in session_names:
        windows = list_windows(session)
        labels = window_labels(windows)
        agent_windows = [labels[w.id] for w in windows if window_runs_agent(pane_commands(w.id))]
        windows_by_session[session] = agent_windows
    return select_targets(windows_by_session)
