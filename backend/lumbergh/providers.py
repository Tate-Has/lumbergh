"""
Agent provider registry for multi-agent support.
Maps provider keys to their launch commands and display labels.
"""

PROVIDERS: dict[str, dict[str, str]] = {
    "claude-code": {
        "launch": "claude --continue || claude",
        "fresh": "claude",
        "label": "Claude Code",
    },
    "cursor": {"launch": "agent --continue || agent", "fresh": "agent", "label": "Cursor"},
    "opencode": {"launch": "opencode", "label": "OpenCode"},
    "gemini-cli": {"launch": "gemini", "label": "Gemini CLI"},
    "aider": {"launch": "aider", "label": "Aider"},
    "codex": {"launch": "codex", "label": "Codex CLI"},
    "pi": {"launch": "pi", "label": "Pi"},
}

DEFAULT_PROVIDER = "claude-code"


def get_launch_command(
    agent_provider: str | None, default_agent: str | None = None, *, fresh: bool = False
) -> str:
    """Resolve the launch command for a given provider.

    ``fresh`` asks for a command that starts a new conversation instead of resuming the
    harness's last one in that directory. Resuming is right for a human reattaching to
    their own session, and wrong for a worker: a harness keys its history on the working
    directory, so a spawn into a path some earlier worker used inherits that worker's
    conversation — and replays its stale `DELIVERED:` line as if it were fresh work.

    Args:
        agent_provider: Provider key from the session, or None to use default.
        default_agent: Global default provider from settings, or None for DEFAULT_PROVIDER.
        fresh: Start a new conversation rather than resuming the directory's last one.

    Returns:
        The shell command string to launch the agent.
    """
    provider = agent_provider or default_agent or DEFAULT_PROVIDER
    entry = PROVIDERS.get(provider) or PROVIDERS[DEFAULT_PROVIDER]
    return (entry.get("fresh") or entry["launch"]) if fresh else entry["launch"]
