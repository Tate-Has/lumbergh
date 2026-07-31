"""Query the registry for the members of a run group."""

from lumbergh import worktrees


def run_members(run_id: str) -> list[dict]:
    rows = [r for r in worktrees.all_entries() if r.get("run") == run_id]
    return sorted(rows, key=lambda r: r.get("target") or "")
