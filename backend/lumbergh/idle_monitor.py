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

Pattern-based overrides from :mod:`idle_detector` catch the one case
quiescence alone cannot: a pane parked on an approval/question/login
prompt (BLOCKED). "The agent exited/died" is not scraped from pane text —
it is derived from the process signal here (see :meth:`_mark_exited`).
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
from lumbergh.targets import parse_target
from lumbergh.tmux_pty import (
    IS_WINDOWS,
    capture_pane_content,
    capture_pane_text,
    capture_pane_title,
)

logger = logging.getLogger(__name__)

_ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[PX^_][^\x1b]*\x1b\\")


def _live_session_names() -> list[str]:
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


def discover_live_targets() -> list[str]:
    from lumbergh.targets import discover_targets
    from lumbergh.tmux_pty import build_pane_commands_lookup, list_session_windows

    return discover_targets(
        _live_session_names(),
        list_windows=list_session_windows,
        pane_commands=build_pane_commands_lookup(),
    )


class IdleMonitor:
    """Background service that monitors tmux sessions via quiescence detection."""

    POLL_INTERVAL_SECONDS = 2.0
    BURST_CAPTURES = 3
    BURST_GAP_SECONDS = 0.15
    QUIET_THRESHOLD_SECONDS = 5.0
    FINGERPRINT_LINE_COUNT = 20
    # How long a session must sit continuously IDLE before we spend a cheap-LLM
    # call asking whether it is actually waiting on a human answer.
    QUESTION_CHECK_DELAY_SECONDS = 10.0
    # How often to sweep the fleet for a stalled Bill. This sweep shells out to git
    # per repo, so it runs on its own throttle rather than every 2s poll; fifteen
    # seconds is still well within "human-scale noticeable" for a stalled orchestrator.
    BILL_NUDGE_CHECK_INTERVAL_SECONDS = 15.0

    def __init__(self):
        self._fingerprints: dict[str, str] = {}
        self._last_change: dict[str, float] = {}
        self._states: dict[str, SessionState] = {}
        self._state_since: dict[str, float] = {}
        # Soft "the agent asked something and is waiting" overlay (name -> reason),
        # inferred by a cheap LLM once per idle episode; see question_detector.
        self._needs_answer: dict[str, str] = {}
        self._question_checked: set[str] = set()
        self._question_inflight: set[str] = set()
        self._question_tasks: set[asyncio.Task] = set()
        self._task: asyncio.Task | None = None
        self._running = False
        self._bill_nudged = False
        self._bill_nudge_checked_at = 0.0
        self._live_targets: list[str] = []
        # Targets whose agent process went missing but whose terminal is still
        # open — held one poll before being declared exited, so a transient
        # discovery miss can't fire a false "the worker died" wake.
        self._exit_pending: set[str] = set()

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

    def live_targets(self) -> list[str]:
        return list(self._live_targets)

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
            targets = await loop.run_in_executor(None, discover_live_targets)
        except Exception as e:
            logger.warning(f"Failed to get live sessions: {e}")
            return

        self._live_targets = list(targets)

        live_session_names = set(await loop.run_in_executor(None, _live_session_names))
        await self._reap_dead_targets(set(targets), live_session_names)

        # Identity files are keyed by the full session:window target (that's what
        # each pane's LUMBERGH_SESSION is set to), so prune with full targets —
        # reducing to bare session names would delete every window worker's
        # identity each poll and force outcome reads onto the cwd-guess fallback.
        session_identity.prune(set(targets))

        await asyncio.gather(
            *(self._check_session(target) for target in targets),
            return_exceptions=True,
        )

        try:
            await self._maybe_nudge_bill(loop)
        except Exception:
            logger.debug("bill nudge skipped", exc_info=True)

    def _forget_target(self, target: str) -> None:
        self._fingerprints.pop(target, None)
        self._last_change.pop(target, None)
        self._states.pop(target, None)
        self._state_since.pop(target, None)
        self._needs_answer.pop(target, None)
        self._question_checked.discard(target)
        self._question_inflight.discard(target)
        self._exit_pending.discard(target)

    async def _reap_dead_targets(self, targets: set[str], live_sessions: set[str]) -> None:
        """Retire targets we were tracking that are no longer discovered.

        A target drops out for one of two reasons, told apart by the process
        signal (not pane text): if its tmux session is still alive, the agent
        process itself exited/died while the terminal stayed open — a real
        "the worker stopped" event worth surfacing as ERROR. If the whole
        session is gone, it was just killed — retire it silently.
        """
        dead_targets = set(self._fingerprints.keys()) - targets
        self._exit_pending &= dead_targets  # an agent that came back is no longer exiting

        for target in dead_targets:
            terminal_alive = parse_target(target)[0] in live_sessions
            was_tracked = self._states.get(target) not in (None, SessionState.ERROR)
            exiting = terminal_alive and was_tracked

            if exiting and target not in self._exit_pending:
                # First poll the agent is missing: hold one cycle (keep tracking
                # state so it re-enters here next poll) to absorb a transient miss.
                self._exit_pending.add(target)
                continue

            confirmed_exit = exiting and target in self._exit_pending
            self._forget_target(target)
            if confirmed_exit:
                await self._mark_exited(target)

    async def _mark_exited(self, session_name: str) -> None:
        """Surface an agent that exited/died from a still-open terminal.

        Ground truth from the process signal, so unlike the old pane-text guess
        it fires only when the agent is genuinely gone. Wakes the overseer once,
        then stops tracking (the persisted state carries the UI until relaunch).
        """
        logger.info(f"Session {session_name} agent exited (process gone, terminal alive) -> error")
        await self._persist_state(session_name, SessionState.ERROR)
        session_attention.mark_attention(session_name, SessionState.ERROR.value)
        await session_attention.persist()

    async def _maybe_nudge_bill(self, loop: asyncio.AbstractEventLoop) -> None:
        """Wake Bill if he's idle with live work, off the event loop and throttled.

        ``_fleet_rows`` shells out to tmux and git per repo, so it never runs on the
        loop directly, and it only runs on ``BILL_NUDGE_CHECK_INTERVAL_SECONDS`` — not
        every ~2s poll — since a stalled Bill is a human-scale problem, not one that
        needs sub-second detection.
        """
        from lumbergh import bill_nudge

        state = self.get_state(bill_nudge.BILL_SESSION).value
        if state != "idle":
            self._bill_nudged = False
            return
        if self._bill_nudged:
            return

        now = time.time()
        if now - self._bill_nudge_checked_at < self.BILL_NUDGE_CHECK_INTERVAL_SECONDS:
            return
        self._bill_nudge_checked_at = now

        from lumbergh.routers.bill import BILL_ORIGIN, _fleet_rows

        # BILL_ORIGIN, not BILL_SESSION: this argument is the registry `origin` filter,
        # and the two only happen to share a value today. Passing the session name here
        # would turn the whole backstop into a silent no-op the day Bill is renamed.
        rows = await loop.run_in_executor(None, _fleet_rows, BILL_ORIGIN)
        if not bill_nudge.should_nudge(state, rows):
            return

        # Latch from the send's own result. Setting it unconditionally meant a failed
        # tmux send disarmed the backstop permanently: nothing retries, and Bill never
        # leaves `idle` because he was never actually woken. `nudge` shells out to tmux
        # twice, so it goes to the executor like the sweep above.
        self._bill_nudged = await loop.run_in_executor(None, bill_nudge.nudge)

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
            if state == SessionState.IDLE:
                await self._maybe_drive_babysit(session_name)

        self._update_question_detection(session_name, state)

    async def _maybe_drive_babysit(self, session_name: str) -> None:
        """Let a babysit loop cycle a session that just went idle.

        Fires only on the transition into idle, so a babysat overseer that printed its
        refresh sentinel is sent the ``/clear`` + restart it can't run for itself before
        Bill is ever nudged. A blocked/error/plain idle is left alone and flows to Bill's
        normal supervision. Best-effort: a babysit failure must never stall the monitor.
        """
        from lumbergh import babysit

        try:
            await babysit.on_idle(session_name)
        except Exception:
            logger.warning("babysit drive failed for %s", session_name, exc_info=True)

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
