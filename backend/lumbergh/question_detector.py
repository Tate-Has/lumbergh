"""Cheap-LLM "is this agent waiting on the user?" detector.

Structural manifest detection (:data:`SessionState.BLOCKED`) recognizes an agent
parked on an approval or structured-question UI — a shape to match. It cannot
recognize a *free-text* question: Pi asking "Which database should I use?"
renders no UI shape, the pane is quiescent, and quiescence classifies it as
``IDLE``. Screen-scraping patterns will never catch that; the only tractable
path is to *read* the screen with a model.

This module asks a cheap local LLM, once per idle episode, whether the last
thing on screen is the agent waiting for the human to answer something. A
positive verdict sets a soft, advisory ``needs_answer`` flag (distinct from the
high-confidence structural BLOCKED state). Everything here fails safe: a
timeout, a provider error, or an unparseable answer all read as "not waiting" —
a supervision dashboard must not cry wolf.
"""

import asyncio
import re
from dataclasses import dataclass

from lumbergh.detect.engine import _FOOTER_MARKERS

TAIL_LINES = 60
DEFAULT_TIMEOUT = 20.0
_MAX_REASON = 120

_ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[PX^_][^\x1b]*\x1b\\")
_DECISIVE = re.compile(r"\b(yes|no)\b", re.IGNORECASE)
_BOX_DRAWING = re.compile("[─-╿]")


def _is_chrome(line: str) -> bool:
    """Terminal UI chrome, not agent output.

    Small models otherwise read the live footer ("? for shortcuts") or the
    empty input box as a question and false-positive on every idle pane.  The
    footer markers are the same ones the manifest engine treats as a live
    idle/working footer.
    """
    low = line.lower()
    if any(marker in low for marker in _FOOTER_MARKERS):
        return True
    return _BOX_DRAWING.sub("", line).strip() in ("", ">")


_PROMPT = """\
You are monitoring an AI coding agent's terminal. Read the most recent output \
(newest last) and decide ONE thing: did the agent ASK THE HUMAN A QUESTION that \
it is now waiting to have answered?

Answer YES only if the newest output contains an actual question or an explicit \
request for the human to choose, decide, confirm, or clarify — and the agent \
cannot continue until the human replies.

Answer NO in every other case, including: the agent finished a task and is idle, \
it reported results or a summary without asking anything, it is still working, or \
the screen just shows an empty input prompt waiting for the next command. A \
completion or status message ("Done", "finished", "all tests pass", "I committed \
the changes", a summary of work) is NOT a question — answer NO even if an empty \
input box follows it. When in doubt, answer NO.

Respond with exactly one line, nothing else:
  YES: <reason in 8 words or fewer>
  NO

Terminal output:
---
{terminal}
---"""


@dataclass(frozen=True)
class Verdict:
    waiting: bool
    reason: str = ""


def _clean_tail(pane_text: str, max_lines: int = TAIL_LINES) -> str:
    lines = [_ANSI.sub("", line).rstrip() for line in pane_text.split("\n")]
    lines = [line for line in lines if not _is_chrome(line)]
    return "\n".join(lines[-max_lines:])


def build_prompt(pane_text: str) -> str:
    return _PROMPT.format(terminal=_clean_tail(pane_text))


def parse_verdict(raw: str) -> Verdict:
    """Parse an LLM answer conservatively; default to *not waiting*.

    The first decisive ``yes``/``no`` token wins, so ``NO`` embedded in a longer
    sentence still parses.  Anything without a decisive token is treated as NO.
    """
    match = _DECISIVE.search(raw or "")
    if not match or match.group(1).lower() != "yes":
        return Verdict(False)
    reason = raw[match.end() :].lstrip(" :,-").strip().splitlines()[0:1]
    return Verdict(True, (reason[0] if reason else "")[:_MAX_REASON])


async def detect(pane_text: str, provider, timeout: float = DEFAULT_TIMEOUT) -> Verdict:
    """Ask ``provider`` whether the agent is waiting on the human.

    Returns ``Verdict(False, "")`` on any timeout or provider error.
    """
    tail = _clean_tail(pane_text)
    if not tail.strip():
        return Verdict(False)
    try:
        raw = await asyncio.wait_for(provider.complete(_PROMPT.format(terminal=tail)), timeout)
    except Exception:
        return Verdict(False)
    return parse_verdict(raw)
