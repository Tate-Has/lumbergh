"""
Background monitor for session idle state detection.

Periodically polls all live tmux sessions and updates their state,
independent of whether any WebSocket clients are connected.

State classification is based on pane-content quiescence: Claude Code
(and other agent CLIs) animate spinners, timers, and token counters
continuously while working, so a frozen pane means the session is idle.
Each poll takes a short burst of captures (to avoid aliasing with the
animation period) and compares the tail fingerprint across bursts and
across polls.

Pattern-based overrides from :mod:`idle_detector` catch cases that
quiescence alone cannot (rate limit errors, shell prompts).
"""

import asyncio
import hashlib
import json
import logging
import re
import time
from datetime import UTC, datetime

import libtmux

from lumbergh import question_detector, session_attention, session_identity
from lumbergh.constants import TMUX_CMD
from lumbergh.db_utils import (
    get_session_data_db,
    recover_session_data_db,
    session_data_lock,
)
from lumbergh.idle_detector import SessionState, classify_overrides
from lumbergh.tmux_pty import (
    IS_WINDOWS,
    capture_pane_content,
    capture_pane_text,
    capture_pane_title,
)

logger = logging.getLogger(__name__)

_ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[PX^_][^\x1b]*\x1b\\")


class IdleMonitor:
    """Background service that monitors tmux sessions via quiescence detection."""

    POLL_INTERVAL_SECONDS = 2.0
    BURST_CAPTURES = 3
    BURST_GAP_SECONDS = 0.15
    QUIET_THRESHOLD_SECONDS = 5.0
    STALL_THRESHOLD_SECONDS = 600
    FINGERPRINT_LINE_COUNT = 20
    # How long a session must sit continuously IDLE before we spend a cheap-LLM
    # call asking whether it is actually waiting on a human answer.
    QUESTION_CHECK_DELAY_SECONDS = 10.0

    def __init__(self):
        self._fingerprints: dict[str, str] = {}
        self._last_change: dict[str, float] = {}
        self._states: dict[str, SessionState] = {}
        self._working_since: dict[str, float] = {}
        self._state_since: dict[str, float] = {}
        # Soft "the agent asked something and is waiting" overlay (name -> reason),
        # inferred by a cheap LLM once per idle episode; see question_detector.
        self._needs_answer: dict[str, str] = {}
        self._question_checked: set[str] = set()
        self._question_inflight: set[str] = set()
        self._question_tasks: set[asyncio.Task] = set()
        self._task: asyncio.Task | None = None
        self._running = False

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._running = True
            self._task = asyncio.create_task(self._monitor_loop())
            logger.info("Idle monitor started")

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
            logger.info("Idle monitor stopped")

    def get_state(self, session_name: str) -> SessionState:
        return self._states.get(session_name, SessionState.UNKNOWN)

    def _record_state_change(self, session_name: str, state: SessionState) -> None:
        self._states[session_name] = state
        self._state_since[session_name] = time.time()

    def state_since_seconds(self, session_name: str) -> float | None:
        started = self._state_since.get(session_name)
        return None if started is None else time.time() - started

    def needs_answer(self, session_name: str) -> bool:
        return session_name in self._needs_answer

    def needs_answer_reason(self, session_name: str) -> str | None:
        return self._needs_answer.get(session_name)

    @classmethod
    def _fingerprint(cls, content: str) -> str:
        """Hash the tail of pane content (ANSI stripped, whitespace trimmed)."""
        lines = [_ANSI_PATTERN.sub("", line).rstrip() for line in content.split("\n")]
        while lines and not lines[-1]:
            lines.pop()
        tail = lines[-cls.FINGERPRINT_LINE_COUNT :]
        return hashlib.sha1("\n".join(tail).encode("utf-8")).hexdigest()

    def _classify_burst(
        self, session_name: str, captures: list[str], now: float, osc_title: str = ""
    ) -> SessionState:
        """
        Classify a session's state from a burst of captures.

        Returns WORKING if the pane changed within the burst or since the
        last poll.  Returns IDLE once the pane has been stable for at least
        ``QUIET_THRESHOLD_SECONDS``.  Manifest overrides (ERROR, BLOCKED,
        shell prompts) take precedence.
        """
        if not captures:
            return SessionState.UNKNOWN

        override = classify_overrides(captures[-1], osc_title)
        if override is not None:
            return override

        fingerprints = [self._fingerprint(c) for c in captures]
        last_fp = fingerprints[-1]
        prev_fp = self._fingerprints.get(session_name)

        burst_stable = len(set(fingerprints)) == 1
        changed_since_prev_poll = prev_fp is not None and prev_fp != last_fp

        if not burst_stable or changed_since_prev_poll:
            self._last_change[session_name] = now
            self._fingerprints[session_name] = last_fp
            return SessionState.WORKING

        # Fully stable within burst and across polls
        self._fingerprints[session_name] = last_fp
        if session_name not in self._last_change:
            # First sighting: bias toward working until quiet threshold elapses
            self._last_change[session_name] = now
            return SessionState.WORKING

        quiet_for = now - self._last_change[session_name]
        if quiet_for >= self.QUIET_THRESHOLD_SECONDS:
            return SessionState.IDLE
        return SessionState.WORKING

    async def _monitor_loop(self) -> None:
        while self._running:
            try:
                await self._check_all_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Idle monitor error: {e}")
            await asyncio.sleep(self.POLL_INTERVAL_SECONDS)

    async def _check_all_sessions(self) -> None:
        loop = asyncio.get_event_loop()
        try:
            sessions = await loop.run_in_executor(None, self._get_live_session_names)
        except Exception as e:
            logger.warning(f"Failed to get live sessions: {e}")
            return

        dead_sessions = set(self._fingerprints.keys()) - set(sessions)
        for name in dead_sessions:
            self._fingerprints.pop(name, None)
            self._last_change.pop(name, None)
            self._states.pop(name, None)
            self._working_since.pop(name, None)
            self._state_since.pop(name, None)
            self._needs_answer.pop(name, None)
            self._question_checked.discard(name)
            self._question_inflight.discard(name)

        session_identity.prune(set(sessions))

        await asyncio.gather(
            *(self._check_session(name) for name in sessions),
            return_exceptions=True,
        )

    def _get_live_session_names(self) -> list[str]:
        try:
            server = libtmux.Server(tmux_bin=TMUX_CMD)
            names = [s.name for s in server.sessions if s.name is not None]
            if names or not IS_WINDOWS:
                return names
        except Exception:
            if not IS_WINDOWS:
                return []

        # Windows fallback: psmux's `-F` format flags don't always work
        # under libtmux, so parse the default `list-sessions` output.
        try:
            import subprocess

            result = subprocess.run(
                [TMUX_CMD, "list-sessions"],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            if result.returncode != 0:
                return []
            names = []
            pattern = re.compile(r"^([^:]+):")
            for line in result.stdout.splitlines():
                match = pattern.match(line)
                if match:
                    names.append(match.group(1))
            return names
        except Exception:
            return []

    async def _burst_capture(self, session_name: str) -> list[str]:
        """Take BURST_CAPTURES snapshots with short async gaps between them."""
        loop = asyncio.get_event_loop()
        captures: list[str] = []
        for i in range(self.BURST_CAPTURES):
            if i > 0:
                await asyncio.sleep(self.BURST_GAP_SECONDS)
            content = await loop.run_in_executor(None, capture_pane_content, session_name)
            captures.append(content or "")
        return captures

    async def _check_session(self, session_name: str) -> None:
        captures = await self._burst_capture(session_name)
        if not any(captures):
            return

        loop = asyncio.get_event_loop()
        osc_title = await loop.run_in_executor(None, capture_pane_title, session_name)

        state = self._classify_burst(session_name, captures, time.time(), osc_title)

        if state == SessionState.WORKING:
            if session_name not in self._working_since:
                self._working_since[session_name] = time.time()
            elif time.time() - self._working_since[session_name] > self.STALL_THRESHOLD_SECONDS:
                state = SessionState.STALLED
        else:
            self._working_since.pop(session_name, None)

        old_state = self._states.get(session_name, SessionState.UNKNOWN)
        if state != old_state:
            logger.info(f"Session {session_name} state: {old_state.value} -> {state.value}")
            self._record_state_change(session_name, state)
            await self._persist_state(session_name, state)
            if state in (SessionState.IDLE, SessionState.BLOCKED, SessionState.ERROR):
                session_attention.mark_attention(session_name, state.value)
            else:
                session_attention.clear_unseen(session_name)
            await session_attention.persist()

        self._update_question_detection(session_name, state)

    def _update_question_detection(self, session_name: str, state: SessionState) -> None:
        """Schedule a cheap-LLM question check for a sustained-idle session.

        Runs every poll (not just on transitions).  Fires at most once per idle
        episode, after the session has been continuously IDLE for
        ``QUESTION_CHECK_DELAY_SECONDS``.  Any non-idle state resets the episode
        and drops a stale ``needs_answer`` flag.
        """
        if state != SessionState.IDLE:
            self._needs_answer.pop(session_name, None)
            self._question_checked.discard(session_name)
            return
        if session_name in self._question_checked or session_name in self._question_inflight:
            return
        since = self.state_since_seconds(session_name)
        if since is None or since < self.QUESTION_CHECK_DELAY_SECONDS:
            return
        # Mark checked before the (settings-reading) enable gate so a disabled
        # detector reads settings at most once per idle episode.
        self._question_checked.add(session_name)
        if not self._question_detection_enabled():
            return
        self._question_inflight.add(session_name)
        task = asyncio.create_task(self._run_question_detection(session_name))
        self._question_tasks.add(task)
        task.add_done_callback(self._question_tasks.discard)

    def _question_detection_enabled(self) -> bool:
        from lumbergh.routers.settings import get_settings

        return bool(get_settings().get("questionDetectionEnabled"))

    def _question_provider(self):
        from lumbergh.ai.providers import get_provider
        from lumbergh.routers.settings import get_settings

        settings = get_settings()
        if not settings.get("questionDetectionEnabled"):
            return None
        try:
            return get_provider(settings.get("ai", {}), settings)
        except Exception:
            return None

    async def _run_question_detection(self, session_name: str) -> None:
        try:
            if self._states.get(session_name) != SessionState.IDLE:
                return
            provider = self._question_provider()
            if provider is None:
                return
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, capture_pane_text, session_name)
            if not text or not text.strip():
                return
            verdict = await question_detector.detect(text, provider)
            if verdict.waiting and self._states.get(session_name) == SessionState.IDLE:
                self._needs_answer[session_name] = verdict.reason
                logger.info(
                    f"Session {session_name} appears to be waiting on a human: {verdict.reason}"
                )
        except Exception as e:
            logger.warning(f"Question detection failed for {session_name}: {e}")
        finally:
            self._question_inflight.discard(session_name)

    async def _persist_state(self, session_name: str, state: SessionState) -> None:
        loop = asyncio.get_event_loop()

        def _save():
            with session_data_lock(session_name):
                try:
                    _write_idle_state(session_name, state)
                except (ValueError, json.JSONDecodeError) as e:
                    logger.warning(f"Corrupt DB for {session_name}; attempting recovery: {e}")
                    if recover_session_data_db(session_name):
                        _write_idle_state(session_name, state)
                    else:
                        raise

        try:
            await loop.run_in_executor(None, _save)
        except Exception as e:
            logger.error(f"Failed to persist state for {session_name}: {e}")


def _write_idle_state(session_name: str, state: SessionState) -> None:
    """Write the idle_state row.  Caller must hold session_data_lock(name)."""
    session_db = get_session_data_db(session_name)
    state_table = session_db.table("idle_state")
    state_table.truncate()
    state_table.insert(
        {
            "state": state.value,
            "updatedAt": datetime.now(tz=UTC).isoformat(),
        }
    )


# Global singleton instance
idle_monitor = IdleMonitor()
