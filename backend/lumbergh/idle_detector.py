"""
Idle state detector for agent terminal sessions.

Analyzes terminal output to detect whether the agent is idle (waiting for input)
or actively working on a task.  Supports Claude Code, Cursor CLI, and other providers.
"""

import re
import time
from collections import deque
from enum import Enum


class SessionState(Enum):
    UNKNOWN = "unknown"
    IDLE = "idle"  # Waiting for user input
    WORKING = "working"
    ERROR = "error"  # Agent exited, crashed, or hit a rate limit
    STALLED = "stalled"  # Working for too long without progress


class IdleDetectionResult:
    """Result of idle detection analysis."""

    def __init__(self, state: SessionState, confidence: float, reason: str = ""):
        self.state = state
        self.confidence = confidence
        self.reason = reason


class IdleDetector:
    """
    Detects whether an agent session is idle or working.

    Maintains a rolling buffer of terminal lines and analyzes patterns
    to determine the current state.  Patterns cover Claude Code, Cursor CLI,
    and other supported providers.
    """

    # Spinner characters used by agent CLIs.
    # Braille dots cycle only during active work, so they're an unambiguous
    # WORKING signal on their own. Modern Claude Code (v2.x) cycles
    # ✻ ✶ ✳ ✺ ✦ ✧ ✢ ● during work BUT also leaves the static ✻ on the
    # post-work "Sautéed for 11m 6s" line — so those chars need a
    # corroborating active signal before counting as WORKING.
    _UNAMBIGUOUS_SPINNER_CHARS = set("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
    _AMBIGUOUS_SPINNER_CHARS = set("✻✽✶✳✺✦✧✢●")
    SPINNER_CHARS = _UNAMBIGUOUS_SPINNER_CHARS | _AMBIGUOUS_SPINNER_CHARS

    # Active-tense verbs Claude Code displays while working. Past-tense
    # variants ("Crunched for 1m 19s") indicate the work has *finished*
    # and the line lingers in the pane — they must NOT match here.
    _CLAUDE_WORKING_VERBS = (
        r"Cooking|Crunching|Cogitating|Pondering|Mulling|Marinating|"
        r"Churning|Forging|Smithing|Wrangling|Slithering|Channelling|"
        r"Thinking|Hatching|Ruminating|Brewing|Simmering|Stewing|"
        r"Noodling|Whittling|Chewing|Mustering|Plotting|Scheming|"
        r"Conjuring|Sautéing|Baking|Roasting|Frying|Whisking|Folding|"
        r"Kneading|Reducing|Boiling|Steeping|Sizzling|Working\b"
    )

    # Patterns indicating active work (thinking, running tools)
    WORKING_PATTERNS = [
        re.compile(rf"({_CLAUDE_WORKING_VERBS})", re.IGNORECASE),
        re.compile(r"Running…|Executing"),  # Tool execution
        re.compile(r"thought for \d+s"),  # "thought for Xs" indicator
        re.compile(r"esc to interrupt", re.IGNORECASE),  # Actively processing
        re.compile(r"Reading|Writing|Searching", re.IGNORECASE),  # Cursor agent tool usage
        re.compile(r"Working \(\d+s", re.IGNORECASE),  # Codex CLI working indicator
        re.compile(r"◼\s"),  # Claude Code subagent task in progress
        re.compile(r"Running \d+ agents?"),  # Claude Code parallel subagent header
        re.compile(r"\d+ tool uses?"),  # Subagent task widget tool counter
    ]

    # Past-tense "Verbed for Xs" line that Claude Code shows AFTER work
    # finishes. The static `\u273b` stays on this line, so detecting the
    # past tense is the only way to distinguish "still working" from
    # "just finished working" when the input box has scrolled off-screen.
    POST_WORK_PATTERN = re.compile(
        r"\b(Cook|Crunch|Cogitat|Ponder|Mull|Marinat|Churn|Forg|Smith|"
        r"Wrangl|Slither|Channell|Hatch|Ruminat|Brew|Simmer|Stew|"
        r"Noodl|Whittl|Chew|Work|Saut|Bak|Roast|Fri)(ed|\u00e9ed) for \d+",
    )

    # Claude Code's static auto-mode footer renders deterministically:
    #   working:  "\u23f5\u23f5 auto mode on (shift+tab to cycle) \u00b7 esc to interrupt"
    #   idle:     "\u23f5\u23f5 auto mode on (shift+tab to cycle) \u00b7 \u2190 for agents"
    # The suffix is the cleanest state signal we get \u2014 it's drawn by the
    # TUI itself, not buried in chat output.
    WORKING_FOOTER_PATTERN = re.compile(r"auto mode on.*esc to interrupt")
    IDLE_FOOTER_PATTERN = re.compile(r"auto mode on.*(\u2190 for agents|new task\?)")

    # Patterns indicating idle state (waiting for user input)
    IDLE_PATTERNS = [
        re.compile(r"\u276f"),  # Agent prompt character (U+276F)
        re.compile(r"Do you want to proceed\?"),
        re.compile(r"Esc to cancel"),
        re.compile(r"\? for shortcuts"),
        re.compile(r"Yes.*No", re.DOTALL),  # Yes/No choice
        re.compile(r"Shift\+Tab"),  # Cursor CLI mode switching hint
        re.compile(r"\(y/n\)"),  # Command approval prompt (Cursor)
        re.compile(r"Type your message"),  # Gemini CLI input prompt
        re.compile(r"Action Required"),  # Gemini CLI approval prompt
        re.compile(r"Apply this change\?"),  # Gemini CLI file write approval
        re.compile(r"Allow (once|execution|for this session)"),  # Gemini CLI permission
        re.compile(r"Would you like to make the following edits"),  # Codex CLI approval
        re.compile(r"Yes, proceed|Yes, and don't ask again"),  # Codex CLI approval choices
        re.compile(r"Press enter to confirm or esc to cancel"),  # Codex CLI confirmation
        re.compile(r"\d+% left · ~/"),  # Codex CLI status bar (idle)
    ]

    # Patterns indicating an error state (agent exited, rate limited, crashed).
    # These are checked only against the *very last* non-empty lines (see
    # _analyze_state) to avoid false reds when the strings appear in
    # scrollback (user prompts, code being discussed, subagent output).
    # Patterns are anchored to "feel like a fresh error message" rather
    # than an incidental mention.
    ERROR_PATTERNS = [
        re.compile(r"\b(rate[ _]limit(ed)?|429|too many requests)\b", re.IGNORECASE),
        re.compile(r"^\s*(API ?error|APIConnectionError|APIError)[: ]", re.IGNORECASE),
        re.compile(r"\b(server is )?overloaded\b", re.IGNORECASE),
        re.compile(r"^\s*(unexpected error|Connection error)[: ]", re.IGNORECASE),
    ]

    # Shell prompt patterns (agent exited, user is back at their shell)
    SHELL_PROMPT_PATTERNS = [
        re.compile(r"[\$%#]\s*$"),  # Ends with $ % or #
        re.compile(r"@.*[\$%#]\s*$"),  # user@host$
        re.compile(r"^\s*\w+@[\w.-]+[:\s]"),  # user@hostname:
    ]

    # Agent prompt pattern (idle state)
    PROMPT_PATTERN = re.compile(r"^[\u276f>]\s*$")

    # Hysteresis settings. Leaving the WORKING state requires more
    # evidence than entering it — Claude Code briefly shows no working
    # indicator between subagent tasks even though work is ongoing.
    STATE_CHANGE_DELAY_MS = 500
    LEAVE_WORKING_DELAY_MS = 2500

    def __init__(self, buffer_lines: int = 50):
        """
        Initialize the idle detector.

        Args:
            buffer_lines: Number of recent lines to keep for analysis
        """
        self._buffer: deque[str] = deque(maxlen=buffer_lines)
        self._current_state = SessionState.UNKNOWN
        self._pending_state: SessionState | None = None
        self._pending_state_time: float = 0
        self._last_output_time: float = 0

    def process_output(self, data: str) -> IdleDetectionResult:
        """
        Process terminal output and detect state changes.

        Args:
            data: Raw terminal output data

        Returns:
            IdleDetectionResult with current state and confidence
        """
        self._last_output_time = time.time()

        # Split into lines and add to buffer
        lines = data.split("\n")
        for line in lines:
            # Strip ANSI escape codes for analysis
            clean_line = self._strip_ansi(line)
            if clean_line:  # Only add non-empty lines
                self._buffer.append(clean_line)

        # Analyze current state
        detected_state, confidence, reason = self._analyze_state()

        # Handle hysteresis - only change state if stable
        now = time.time()

        if detected_state != self._current_state:
            if self._pending_state != detected_state:
                # New state detected, start waiting
                self._pending_state = detected_state
                self._pending_state_time = now
            else:
                delay_ms = (
                    self.LEAVE_WORKING_DELAY_MS
                    if self._current_state == SessionState.WORKING
                    else self.STATE_CHANGE_DELAY_MS
                )
                if (now - self._pending_state_time) * 1000 >= delay_ms:
                    self._current_state = detected_state
                    self._pending_state = None
        else:
            # State matches current, clear pending
            self._pending_state = None

        return IdleDetectionResult(self._current_state, confidence, reason)

    def analyze_snapshot(self, content: str) -> IdleDetectionResult:
        """
        Re-analyze the agent state from a complete pane snapshot.

        Unlike :meth:`process_output` (which appends streaming data) and
        :meth:`analyze_initial_content` (which sets state immediately), this
        replaces the buffer with the latest pane snapshot and then applies
        full hysteresis, so transient one-frame flickers (e.g. between
        subagent tasks) don't change the reported state.
        """
        self._last_output_time = time.time()
        self._buffer.clear()
        for line in content.split("\n"):
            clean_line = self._strip_ansi(line)
            if clean_line:
                self._buffer.append(clean_line)

        detected_state, confidence, reason = self._analyze_state()
        now = time.time()

        if detected_state != self._current_state:
            if self._pending_state != detected_state:
                self._pending_state = detected_state
                self._pending_state_time = now
            else:
                delay_ms = (
                    self.LEAVE_WORKING_DELAY_MS
                    if self._current_state == SessionState.WORKING
                    else self.STATE_CHANGE_DELAY_MS
                )
                if (now - self._pending_state_time) * 1000 >= delay_ms:
                    self._current_state = detected_state
                    self._pending_state = None
        else:
            self._pending_state = None

        return IdleDetectionResult(self._current_state, confidence, reason)

    def get_state(self) -> SessionState:
        """Get the current detected state."""
        return self._current_state

    def analyze_initial_content(self, content: str) -> IdleDetectionResult:
        """
        Analyze initial pane content to determine starting state.

        Args:
            content: Full pane content captured at connection time

        Returns:
            IdleDetectionResult with initial state
        """
        # Process content but skip hysteresis for initial state
        lines = content.split("\n")
        for line in lines:
            clean_line = self._strip_ansi(line)
            if clean_line:
                self._buffer.append(clean_line)

        detected_state, confidence, reason = self._analyze_state()

        # Set initial state immediately (no hysteresis)
        self._current_state = detected_state

        return IdleDetectionResult(self._current_state, confidence, reason)

    def _match_patterns(self, lines: list[str], patterns: list[re.Pattern]) -> re.Pattern | None:
        """Return the first matching pattern across lines, or None."""
        for line in lines:
            for pattern in patterns:
                if pattern.search(line):
                    return pattern
        return None

    # Characters drawn by the agent CLI's input box. If any appear in the
    # recent buffer, the agent is still running its TUI — not exited to
    # the shell. Used to suppress false shell-prompt ERROR detection when
    # bash tool output happens to end in a $ / % / # near the bottom.
    _AGENT_UI_CHARS = set("❯╭╰─│⏵◼◻✔⎿✻✶✳✺✦✧✢●")  # noqa: RUF001

    def _has_activity_indicators(self, lines: list[str]) -> bool:
        """Check if any lines contain spinner, working, idle, or agent-UI indicators."""
        for line in lines:
            if any(char in line for char in self.SPINNER_CHARS):
                return True
            if any(char in line for char in self._AGENT_UI_CHARS):
                return True
            if any(p.search(line) for p in self.WORKING_PATTERNS):
                return True
            if any(p.search(line) for p in self.IDLE_PATTERNS):
                return True
        return False

    @staticmethod
    def _recency_multiplier(distance_from_end: int) -> float:
        """Return scoring multiplier based on line recency."""
        if distance_from_end == 0:
            return 2.0
        if distance_from_end <= 2:
            return 1.5
        return 1.0

    # Scoring weights
    _BASE_WEIGHT = 3.0  # Per-pattern match
    _SPINNER_WEIGHT = 8.0  # Spinner + active signal on last line
    _PROMPT_WEIGHT = 8.0  # Agent prompt on last line (unambiguous)
    _POST_WORK_WEIGHT = 8.0  # "Verbed for Xs" line (work just ended)
    _FOOTER_WEIGHT = 10.0  # Auto-mode footer (deterministic state suffix)

    def _score_lines(  # noqa: C901
        self, recent_lines: list[str]
    ) -> tuple[dict[SessionState, float], dict[SessionState, list[str]]]:
        """Score recent lines against WORKING and IDLE patterns with recency bias."""
        scores: dict[SessionState, float] = {
            SessionState.WORKING: 0.0,
            SessionState.IDLE: 0.0,
        }
        reasons: dict[SessionState, list[str]] = {
            SessionState.WORKING: [],
            SessionState.IDLE: [],
        }
        last_line = recent_lines[-1] if recent_lines else ""

        # Special: post-work line ("✻ Sautéed for 11m 6s") is a strong
        # IDLE signal. Claude Code keeps the static `✻` char on this line
        # after work finishes, so a spinner-char alone is ambiguous —
        # but the past-tense verb is not.
        # Strongest signal: Claude Code's deterministic auto-mode footer.
        # When the agent is working it renders "· esc to interrupt"; when
        # idle it renders "· ← for agents". Normally at the very bottom,
        # but the subagent picker UI (toggled with `↓ to manage`) can push
        # the footer up by 2-3 lines — scan a wider tail to catch that.
        for footer_line in recent_lines[-5:]:
            if self.WORKING_FOOTER_PATTERN.search(footer_line):
                scores[SessionState.WORKING] += self._FOOTER_WEIGHT
                reasons[SessionState.WORKING].append("Working auto-mode footer")
                break
            if self.IDLE_FOOTER_PATTERN.search(footer_line):
                scores[SessionState.IDLE] += self._FOOTER_WEIGHT
                reasons[SessionState.IDLE].append("Idle auto-mode footer")
                break

        # Only check the last 3 lines: past-tense verbs deeper in the
        # buffer are just chat/scrollback discussing the agent.
        post_work_hit = self._match_patterns(recent_lines[-3:], [self.POST_WORK_PATTERN])
        if post_work_hit:
            scores[SessionState.IDLE] += self._POST_WORK_WEIGHT
            reasons[SessionState.IDLE].append("Post-work line")

        # Special: braille-style spinner on last line is unambiguous.
        if any(char in last_line for char in self._UNAMBIGUOUS_SPINNER_CHARS):
            scores[SessionState.WORKING] += self._SPINNER_WEIGHT
            reasons[SessionState.WORKING].append("Unambiguous spinner on last line")
        # Ambiguous Claude Code spinner chars (✻ ✽ etc.) also appear on
        # the static post-work line. The spinner line is rarely the last
        # line — the static footer is — so look for spinner+verb together
        # on any line within the scoring window. Same-line corroboration
        # keeps chat scrollback from triggering (no chat line has both a
        # spinner glyph AND a present-tense working verb).
        elif not post_work_hit:
            for line in recent_lines[-5:]:
                has_spinner = any(c in line for c in self._AMBIGUOUS_SPINNER_CHARS)
                has_active_verb = has_spinner and any(p.search(line) for p in self.WORKING_PATTERNS)
                if has_active_verb:
                    scores[SessionState.WORKING] += self._SPINNER_WEIGHT
                    reasons[SessionState.WORKING].append("Spinner + verb on same line")
                    break

        # Special: agent prompt on last line
        if self.PROMPT_PATTERN.search(last_line):
            scores[SessionState.IDLE] += self._PROMPT_WEIGHT
            reasons[SessionState.IDLE].append("Agent prompt on last line")

        # Score each line against all patterns — but only the last ~4
        # lines. Pattern strings ("esc to interrupt", "Cooking", "Yes/No",
        # `❯`) routinely appear in chat scrollback discussing the agent  # noqa: RUF003
        # or in prior tool output, and would otherwise dominate scoring.
        # The agent's *current* UI state is reflected only at the bottom
        # of the visible pane.
        scoring_window = recent_lines[-4:]
        window_len = len(scoring_window)
        for i, line in enumerate(scoring_window):
            dist = window_len - 1 - i
            mult = self._recency_multiplier(dist)

            for pattern in self.WORKING_PATTERNS:
                if pattern.search(line):
                    scores[SessionState.WORKING] += self._BASE_WEIGHT * mult
                    reasons[SessionState.WORKING].append(f"{pattern.pattern} (line -{dist})")

            for pattern in self.IDLE_PATTERNS:
                if pattern.search(line):
                    scores[SessionState.IDLE] += self._BASE_WEIGHT * mult
                    reasons[SessionState.IDLE].append(f"{pattern.pattern} (line -{dist})")

        return scores, reasons

    def _analyze_state(self) -> tuple[SessionState, float, str]:
        """
        Analyze buffer to determine current state using score-based detection.

        ERROR and shell prompt are short-circuited (unambiguous).
        WORKING vs IDLE is resolved by scoring: each pattern match adds a
        weighted score (with recency bias), and the highest total wins.
        """
        if not self._buffer:
            return SessionState.UNKNOWN, 0.0, "No data"

        recent_lines = list(self._buffer)[-10:]
        last_line = recent_lines[-1] if recent_lines else ""

        # 1. Error patterns — only check the most-recent non-empty lines.
        # Old behavior scanned all 10 recent lines, which falsely flagged red
        # when error-like strings appeared in user prompts, code, or
        # subagent output. Errors that matter happen at the *tail* of output.
        error_scan_lines = [line for line in recent_lines[-3:] if line.strip()]
        match = self._match_patterns(error_scan_lines, self.ERROR_PATTERNS)
        if match:
            return SessionState.ERROR, 0.9, f"Error pattern: {match.pattern}"

        # 2. Shell prompt (short-circuit — depends on absence of indicators)
        if not self._has_activity_indicators(recent_lines):
            match = self._match_patterns([last_line], self.SHELL_PROMPT_PATTERNS)
            if match:
                return SessionState.ERROR, 0.85, f"Shell prompt: {match.pattern}"

        # 3. Score-based WORKING vs IDLE detection
        scores, reasons = self._score_lines(recent_lines)
        w_score = scores[SessionState.WORKING]
        i_score = scores[SessionState.IDLE]

        if w_score == 0.0 and i_score == 0.0:
            return SessionState.UNKNOWN, 0.3, "No patterns matched"

        total = w_score + i_score
        if w_score >= i_score:
            top = "; ".join(reasons[SessionState.WORKING][:3])
            return SessionState.WORKING, min(0.95, w_score / total), f"Working: {top}"
        top = "; ".join(reasons[SessionState.IDLE][:3])
        return SessionState.IDLE, min(0.95, i_score / total), f"Idle: {top}"

    @staticmethod
    def _strip_ansi(text: str) -> str:
        """Remove ANSI escape codes from text."""
        ansi_pattern = re.compile(
            r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[PX^_][^\x1b]*\x1b\\"
        )
        return ansi_pattern.sub("", text)
