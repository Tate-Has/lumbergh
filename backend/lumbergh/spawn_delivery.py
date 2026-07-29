"""Hand a spawned worker its brief only once it can actually receive it.

A fresh worktree launch is not ready the instant tmux accepts the launch command.
The harness takes seconds to boot, and Claude Code opens on a one-time folder-trust
dialog ("Is this a project you trust?") that ``--dangerously-skip-permissions`` does
not bypass. Typing the brief before the agent's input prompt exists drops it into the
booting shell or the trust dialog — yet ``send-keys`` still succeeds, so a naive spawn
reports success while the worker sits idle forever, and the human has to hand-drive
tmux to rescue it.

This waits for the agent to reach a ready input prompt, answers the folder-trust
dialog on the way (its default option is already "Yes, I trust this folder"), delivers
the brief, and confirms the worker actually started on it before calling it delivered.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lumbergh.idle_detector import SessionState, classify_overrides
from lumbergh.tmux_pty import capture_pane_text, send_key, send_text

if TYPE_CHECKING:
    from collections.abc import Callable

DEFAULT_READY_TIMEOUT = 60.0
DEFAULT_CONFIRM_TIMEOUT = 12.0
DEFAULT_POLL = 0.5
MAX_SEND_ATTEMPTS = 3

_TRUST_MARKER = "trust this folder"
_YES_OPTION = re.compile(r"^\s*❯?\s*\d+\.\s*yes\b", re.IGNORECASE | re.MULTILINE)  # noqa: RUF001

# Positive evidence that an agent TUI is on screen (ready or working), as opposed
# to a bare shell still about to launch it. Guards against the original bug —
# mistaking a quiescent shell prompt for a ready agent and typing the brief there.
_TUI_MARKERS = ("? for shortcuts", "auto mode", "esc to interrupt", "shift+tab to cycle")


@dataclass
class DeliveryResult:
    delivered: bool
    reason: str  # "" on success; why it failed otherwise, for the spawn error help


def _is_trust_dialog(content: str) -> bool:
    return _TRUST_MARKER in content.lower() and bool(_YES_OPTION.search(content))


def _is_agent_tui(content: str) -> bool:
    low = content.lower()
    return any(marker in low for marker in _TUI_MARKERS)


def _is_ready(content: str, prev: str | None) -> bool:
    """The agent's input prompt is up and settled, not a shell or a dialog."""
    return (
        content == prev
        and _is_agent_tui(content)
        and classify_overrides(content) != SessionState.BLOCKED
    )


def deliver_when_ready(
    name: str,
    text: str,
    *,
    capture: Callable[[str], str] = capture_pane_text,
    send: Callable[[str, str], bool] = send_text,
    press: Callable[[str, str], bool] = send_key,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    ready_timeout: float = DEFAULT_READY_TIMEOUT,
    confirm_timeout: float = DEFAULT_CONFIRM_TIMEOUT,
    poll: float = DEFAULT_POLL,
) -> DeliveryResult:
    deadline = clock() + ready_timeout
    answered_trust = False
    prev: str | None = None
    while clock() < deadline:
        content = capture(name) or ""
        if _is_trust_dialog(content):
            if not answered_trust:
                press(name, "Enter")  # default option is "Yes, I trust this folder"
                answered_trust = True
            prev = None
            sleep(poll)
            continue
        if _is_ready(content, prev):
            return _deliver_and_confirm(
                name,
                text,
                content,
                capture=capture,
                send=send,
                press=press,
                sleep=sleep,
                clock=clock,
                confirm_timeout=confirm_timeout,
                poll=poll,
            )
        prev = content
        sleep(poll)
    return DeliveryResult(
        False,
        f"worker never reached a ready input prompt within {ready_timeout:.0f}s "
        "(still booting, at a shell, or parked on a dialog)",
    )


def _deliver_and_confirm(
    name: str,
    text: str,
    ready_snapshot: str,
    *,
    capture: Callable[[str], str],
    send: Callable[[str, str], bool],
    press: Callable[[str, str], bool],
    sleep: Callable[[float], None],
    clock: Callable[[], float],
    confirm_timeout: float,
    poll: float,
) -> DeliveryResult:
    """Send the brief and confirm the worker moved off the ready prompt onto it.

    A ``send-keys`` that tmux accepts is not proof the harness consumed it, so
    success means the pane actually changed — the worker echoed the brief and
    started working. A stalled send is nudged with an Enter (in case the text
    landed in the input box but was never submitted) and retried.
    """
    for _ in range(MAX_SEND_ATTEMPTS):
        send(name, text)
        confirm_deadline = clock() + confirm_timeout
        while clock() < confirm_deadline:
            sleep(poll)
            if capture(name) != ready_snapshot:
                return DeliveryResult(True, "")
        press(name, "Enter")
    return DeliveryResult(
        False, f"worker did not start on the brief after {MAX_SEND_ATTEMPTS} attempts"
    )
