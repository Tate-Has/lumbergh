"""The `target` identifier: `session` (bare) or `session:window`.

A target is the unit Lumbergh observes and drives.

**A session's identity is the bare session name, and its agent is its first agent-running
window.** How many other windows are open — a dev server, an editor, a second Claude the
user opened to look something up — never changes what `port` means. Supervision is handed a
session; everything keyed to that name (a babysit, a fleet row, `lb state`) must keep
resolving no matter what else the user does in there. Inferring identity from a window
*count* is what once made a session vanish from `lb` mid-flight, taking its babysit with it.

Window-level targets (`port:issue-841`) exist only for windows something **registered** as
fleet work. A window is a worker because the worktree registry says so, never because
discovery guessed from what it saw. In a batch container every window is a registered
worker, so the container has no agent of its own and no bare target.

Every target also carries a **ref**: the tmux window id (`@n`) that *is* that target. Refs,
not target strings, are what reach tmux — a bare session name handed to `capture-pane` or
`send-keys` resolves to whichever window is currently *selected*, so a user switching
windows would otherwise redirect both the state read and the keystrokes.

Window *names* are the label in a windowed target because they carry meaning, but tmux
neither requires them to be unique nor forbids an empty one, and such a label would address
the wrong window. So a label falls back to the window index unless the name is unambiguous.
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


def is_worker_window(session: str, label: str, worker_targets: set[str]) -> bool:
    """Whether this window was registered as fleet work rather than being the session's own.

    Registration is the only evidence accepted. A window that merely *looks* like work —
    it runs an agent, it is named after an issue — is still the user's window.
    """
    return format_target(session, label) in worker_targets


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


def discover_target_refs(
    session_names: list[str],
    list_windows: Callable[[str], Sequence[Window]],
    pane_commands: Callable[[str], set[str]],
    worker_targets: set[str] | None = None,
) -> dict[str, str]:
    """Every live target mapped to the tmux window ref that *is* it.

    A session contributes its bare name, resolved to the first agent window it did not
    hand to fleet work, plus one target per registered worker window that is still alive.

    ``pane_commands`` is asked about window ids, never about a formatted target, so an
    unlucky window name can never make a running agent unaddressable.
    """
    registered = worker_targets or set()
    refs: dict[str, str] = {}
    for session in session_names:
        windows = list_windows(session)
        labels = window_labels(windows)
        own_ref: str | None = None
        worker_refs: dict[str, str] = {}
        for window in windows:
            if not window_runs_agent(pane_commands(window.id)):
                continue
            label = labels[window.id]
            if is_worker_window(session, label, registered):
                worker_refs[format_target(session, label)] = window.id
            elif own_ref is None:
                own_ref = window.id
        if own_ref is not None:
            refs[session] = own_ref
        refs.update(worker_refs)
    return refs


def discover_targets(
    session_names: list[str],
    list_windows: Callable[[str], Sequence[Window]],
    pane_commands: Callable[[str], set[str]],
    worker_targets: set[str] | None = None,
) -> list[str]:
    return list(discover_target_refs(session_names, list_windows, pane_commands, worker_targets))
