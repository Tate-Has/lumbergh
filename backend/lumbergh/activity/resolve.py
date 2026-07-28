"""Pick the transcript adapter for a session by its agent provider."""

from pathlib import Path

from lumbergh.activity.adapter import AgentAdapter
from lumbergh.activity.claude_code import ClaudeCodeAdapter
from lumbergh.activity.pi import PiAdapter


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
