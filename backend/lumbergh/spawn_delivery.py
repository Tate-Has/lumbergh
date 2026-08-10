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

# The agent's own context readout, e.g. `41k (21%)`. Zero means it has not taken a
# single turn, which is the whole signature of a brief that was never submitted. Both
# halves are captured: the percent is what says whether a session is near a hand-off,
# and it was already being matched here purely to anchor the `k`.
_CONTEXT_USED = re.compile(r"(\d+(?:\.\d+)?)k\s*\(\s*(\d+)\s*%\s*\)")

# The agent's input line, whichever way its TUI draws one: boxed, or ruled off above
# and below with a bare prompt character.
_INPUT_BOX = re.compile(r"^\s*(?:[│┃|]\s*)?[>❯]\s?(.*?)\s*(?:[│┃|]\s*)?$", re.MULTILINE)  # noqa: RUF001


@dataclass
class DeliveryResult:
    delivered: bool
    reason: str  # "" on success; why it failed otherwise, for the spawn error help


def _is_trust_dialog(content: str) -> bool:
    return _TRUST_MARKER in content.lower() and bool(_YES_OPTION.search(content))


def _is_agent_tui(content: str) -> bool:
    low = content.lower()
    return any(marker in low for marker in _TUI_MARKERS)


def context_used(content: str) -> tuple[float, float] | None:
    """``(thousands of tokens, percent of the window)``, or None if the pane doesn't say.

    The two always travel together because they come from one match, so they can never
    disagree about whether there is a readout at all — which is the distinction every
    caller here depends on.

    Above zero is the one unambiguous proof that an agent took a turn — it cannot be
    faked by text merely appearing on screen. Zero proves nothing on its own: a pane
    can sit at ``0k`` for the whole of a first turn, so this is only ever read as
    positive evidence.
    """
    matches = _CONTEXT_USED.findall(content or "")
    if not matches:
        return None
    used_k, pct = matches[-1]
    return float(used_k), float(pct)


def context_used_k(content: str) -> float | None:
    """Just the thousands of tokens — the delivery check's half of ``context_used``."""
    used = context_used(content)
    return None if used is None else used[0]


def _input_box_text(content: str) -> str | None:
    """What is typed in the agent's input box, or None if no box is on screen."""
    matches = _INPUT_BOX.findall(content or "")
    return matches[-1] if matches else None


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
    # Imported here because the idle monitor imports this module: a session's agent is its
    # first window, and a bare session ref would type the brief into whichever window the
    # user has selected. See ``lumbergh.targets``.
    from lumbergh.idle_monitor import tmux_ref

    ref = tmux_ref(name)
    deadline = clock() + ready_timeout
    answered_trust = False
    prev: str | None = None
    while clock() < deadline:
        content = capture(ref) or ""
        if _is_trust_dialog(content):
            if not answered_trust:
                press(ref, "Enter")  # default option is "Yes, I trust this folder"
                answered_trust = True
            prev = None
            sleep(poll)
            continue
        if _is_ready(content, prev):
            return _deliver_and_confirm(
                ref,
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
    ref: str,
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
    """Send the brief and confirm the worker actually started on it.

    A ``send-keys`` that tmux accepts is not proof the harness consumed it — and
    neither is a pane that merely changed, which was the bug: text typed into the
    input box and never submitted changes the pane, so spawn reported a worker whose
    brief was sitting there unsent and whose agent never ran. Success now means
    positive evidence of a turn (see :func:`_started`). Failing that, the pending
    brief is nudged with an Enter before the whole text is retyped, because the
    manual recovery for this is a single keystroke, not a second copy of the brief.
    """
    for _ in range(MAX_SEND_ATTEMPTS):
        send(ref, text)
        if _confirm_started(
            ref,
            ready_snapshot,
            capture=capture,
            sleep=sleep,
            clock=clock,
            confirm_timeout=confirm_timeout,
            poll=poll,
        ):
            return DeliveryResult(True, "")
        press(ref, "Enter")
        if _confirm_started(
            ref,
            ready_snapshot,
            capture=capture,
            sleep=sleep,
            clock=clock,
            confirm_timeout=confirm_timeout,
            poll=poll,
        ):
            return DeliveryResult(True, "")
    return DeliveryResult(
        False,
        f"worker never started on the brief after {MAX_SEND_ATTEMPTS} attempts "
        "(context still 0k and the pane never moved — the brief may be sitting "
        "unsubmitted in its input box)",
    )


def _confirm_started(
    ref: str,
    ready_snapshot: str,
    *,
    capture: Callable[[str], str],
    sleep: Callable[[float], None],
    clock: Callable[[], float],
    confirm_timeout: float,
    poll: float,
) -> bool:
    deadline = clock() + confirm_timeout
    prev: str | None = None
    while clock() < deadline:
        sleep(poll)
        content = capture(ref) or ""
        if _started(content, ready_snapshot, prev):
            return True
        prev = content
    return False


def _started(content: str, ready_snapshot: str, prev: str | None) -> bool:
    """Whether the pane shows an agent that took the brief, rather than one holding it.

    Any of three positive signals settles it: the context readout moved off zero, the
    pane is animating (a working agent's spinner and timer never hold still), or the
    input box is empty again, which only happens once the text in it was submitted.
    """
    used = context_used_k(content)
    if used is not None and used > 0:
        return True
    if content == ready_snapshot:
        return False
    if prev is not None and content != prev:
        return True
    return _input_box_text(content) == ""
