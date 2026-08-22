"""Forking a session — a second agent that starts from another's conversation.

Claude Code can branch a conversation with `--resume <id> --fork-session`: the
new session inherits everything said so far and diverges from there, leaving
the original untouched. Everything here is about finding that id and turning it
into a launch command; where the fork runs (same repo, fresh worktree) is the
caller's choice.
"""

from pathlib import Path

from lumbergh import session_identity

# Only harnesses that can genuinely branch a conversation belong here. A harness
# that would silently start from nothing is worse than one that refuses.
FORK_COMMANDS: dict[str, str] = {
    "claude-code": "claude --resume {session_id} --fork-session",
}


def fork_launch_command(agent_provider: str | None, session_id: str | None) -> str | None:
    """The command that launches a fork, or None if this cannot be forked."""
    if not session_id:
        return None
    template = FORK_COMMANDS.get(agent_provider or "claude-code")
    return template.format(session_id=session_id) if template else None


def claude_session_id(name: str, cwd: Path | None, store: Path | None = None) -> str | None:
    """The Claude conversation id behind a session.

    The SessionStart hook records it; failing that, a transcript's filename is
    its session id, so the newest transcript for this cwd is the best guess.
    """
    identity = session_identity.read(name, store=store)
    if identity and identity.session_id:
        return identity.session_id

    from lumbergh.activity.claude_code import ClaudeCodeAdapter

    adapter = ClaudeCodeAdapter.for_cwd(cwd) if cwd else None
    return adapter.path.stem if adapter else None
