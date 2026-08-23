"""Naming for one-click worktrees — the "just give me another agent" spawn.

The deliberate spawn paths name their branch after the work. A quick worktree has
no work yet, so it gets the next free number, and the branch and session share it
so one number identifies both.
"""

from pathlib import Path

from lumbergh.git_utils import get_repo


def next_quick_name(taken_branches: set[str], taken_sessions: set[str]) -> tuple[str, str]:
    """The next free (branch, session) pair — `quick/3` alongside `quick-3`."""
    n = 1
    while f"quick/{n}" in taken_branches or f"quick-{n}" in taken_sessions:
        n += 1
    return f"quick/{n}", f"quick-{n}"


def branch_names(repo: Path) -> set[str]:
    return {head.name for head in get_repo(repo).heads}
