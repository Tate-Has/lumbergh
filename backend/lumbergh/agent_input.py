"""Deliver messages through the target agent's native input mechanism."""

from collections.abc import Callable
from pathlib import Path

from lumbergh import codex_queue
from lumbergh.tmux_pty import send_text


def send_prompt(
    target: str,
    text: str,
    provider: str | None,
    cwd: Path | None,
    *,
    send: Callable[[str, str], bool] = send_text,
) -> bool:
    """Send a prompt without changing the semantics of a running agent turn."""
    if (provider or "").lower() == "codex":
        return cwd is not None and codex_queue.queue_message(cwd, text)
    return send(target, text)
