"""Pick the transcript adapter for a session by its agent provider."""

from pathlib import Path

from lumbergh.activity.adapter import AgentAdapter
from lumbergh.activity.claude_code import ClaudeCodeAdapter
from lumbergh.activity.pi import PiAdapter


def session_meta(name: str) -> dict:
    """Stored session metadata (workdir, agent_provider, ...) used to resolve an adapter.

    Shared by every caller of ``resolve_adapter`` (the agent router's ``read`` endpoint
    and Bill's fleet outcome enrichment) so the lookup lives in one place.
    Prefers session store; falls back to worktree registry for window targets.
    """
    from lumbergh.routers.sessions import get_stored_sessions

    stored = get_stored_sessions().get(name, {})
    if stored:
        return stored
    from lumbergh import worktrees

    for row in worktrees.all_entries():
        if row.get("target") == name and row.get("path"):
            return {"workdir": row["path"], "agent_provider": None}
    return {}


def resolve_adapter(
    session_name: str, cwd: Path | None, provider: str | None
) -> AgentAdapter | None:
    if (provider or "").lower() == "pi":
        order = [PiAdapter, ClaudeCodeAdapter]
    else:
        order = [ClaudeCodeAdapter, PiAdapter]
    for cls in order:
        adapter = cls.resolve(session_name, cwd)  # type: ignore[attr-defined]
        if adapter is not None:
            return adapter
    return None
