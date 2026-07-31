"""
Tests for quiescence-based idle detection in IdleMonitor.

Core idea: Claude Code (and similar agents) animate spinners, timers, and
token counters continuously while working.  If the pane content stops
changing for long enough, the session is idle.  Pattern matching is used
only for ERROR detection and for labeling specific idle sub-states.

These tests exercise the pure classification logic without a live tmux.
"""

import json

import pytest

import lumbergh.idle_monitor as im
from lumbergh.idle_detector import SessionState
from lumbergh.idle_monitor import IdleMonitor

# Real Claude Code "working" state (from live wrangled-dashboard session).
# The spinner char and elapsed-time counter change every second or so, so
# two captures ~150ms apart normally catch different frames.  Below are
# two plausible frames that differ only in the spinner line.
BUSY_FRAME_1 = """\
● Spec committed (c01ebd6). Now invoking the writing-plans skill to produce the
  implementation plan.

● Skill(superpowers:writing-plans)
  \u23ba  Successfully loaded skill

● I'm using the writing-plans skill to create the implementation plan.

· Invoking writing-plans\u2026 (1m 18s \u00b7 \u2193 47 tokens \u00b7 thinking with medium effort)

\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
\u276f\u00a0
\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
  \u23f5\u23f5 accept edits on (shift+tab to cycle) \u00b7 esc to interrupt \u00b7 ctrl+t to hide tasks
"""

BUSY_FRAME_2 = """\
● Spec committed (c01ebd6). Now invoking the writing-plans skill to produce the
  implementation plan.

● Skill(superpowers:writing-plans)
  \u23ba  Successfully loaded skill

● I'm using the writing-plans skill to create the implementation plan.

\u2022 Invoking writing-plans\u2026 (1m 19s \u00b7 \u2193 52 tokens \u00b7 thinking with medium effort)

\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
\u276f\u00a0
\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
  \u23f5\u23f5 accept edits on (shift+tab to cycle) \u00b7 esc to interrupt \u00b7 ctrl+t to hide tasks
"""

# Real Claude Code "idle" state: empty prompt, status line WITHOUT
# "esc to interrupt", pane is fully static.
IDLE_CAPTURE = """\
● Spec committed (c01ebd6). Now invoking the writing-plans skill to produce the
  implementation plan.

● Brewed for 1m 12s \u00b7 10 cache read \u00b7 2.3k output

\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
\u276f\u00a0
\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
  \u23f5\u23f5 accept edits on (shift+tab to cycle)
"""


def test_changing_captures_within_burst_returns_working():
    """Spinner animating across a 3-frame burst -> WORKING."""
    mon = IdleMonitor()
    # Seed baseline
    mon._classify_burst("s1", [BUSY_FRAME_1, BUSY_FRAME_1, BUSY_FRAME_1], now=100.0)
    # Next poll catches animation
    state = mon._classify_burst("s1", [BUSY_FRAME_2, BUSY_FRAME_1, BUSY_FRAME_2], now=102.0)
    assert state == SessionState.WORKING


def test_changing_captures_across_polls_returns_working():
    """Content differs between polls (spinner ticked) -> WORKING."""
    mon = IdleMonitor()
    mon._classify_burst("s1", [BUSY_FRAME_1, BUSY_FRAME_1, BUSY_FRAME_1], now=100.0)
    state = mon._classify_burst("s1", [BUSY_FRAME_2, BUSY_FRAME_2, BUSY_FRAME_2], now=102.0)
    assert state == SessionState.WORKING


def test_stable_captures_eventually_return_idle():
    """Identical captures for longer than quiet threshold -> IDLE."""
    mon = IdleMonitor()
    mon._classify_burst("s1", [IDLE_CAPTURE, IDLE_CAPTURE, IDLE_CAPTURE], now=100.0)
    # Well past quiet threshold
    state = mon._classify_burst("s1", [IDLE_CAPTURE, IDLE_CAPTURE, IDLE_CAPTURE], now=100.0 + 30.0)
    assert state == SessionState.IDLE


def test_stable_captures_within_grace_period_still_working():
    """Stable but not yet past quiet threshold -> still WORKING (conservative)."""
    mon = IdleMonitor()
    mon._classify_burst("s1", [IDLE_CAPTURE, IDLE_CAPTURE, IDLE_CAPTURE], now=100.0)
    state = mon._classify_burst("s1", [IDLE_CAPTURE, IDLE_CAPTURE, IDLE_CAPTURE], now=101.0)
    assert state == SessionState.WORKING


def test_regression_busy_pane_with_empty_prompt_not_marked_idle():
    """
    Regression: in recent Claude Code, the \u276f prompt character renders even
    while working.  The old pattern-based detector flipped to IDLE the moment
    it saw \u276f on a recent line.  Quiescence must not make that mistake as
    long as the pane is still animating.
    """
    mon = IdleMonitor()
    # Several consecutive polls, each catching animation differences
    mon._classify_burst("wrangled", [BUSY_FRAME_1, BUSY_FRAME_1, BUSY_FRAME_1], now=100.0)
    for offset in (2.0, 4.0, 6.0, 8.0, 10.0, 12.0):
        # Alternate frames so every poll shows change
        frames = [BUSY_FRAME_2 if i % 2 else BUSY_FRAME_1 for i in range(3)]
        state = mon._classify_burst("wrangled", frames, now=100.0 + offset)
    assert state == SessionState.WORKING


def test_error_like_text_does_not_flip_to_error():
    """Error/rate-limit *words* in the pane must not be read as a real error.

    They are almost always displayed content — a diff, a log line, code being
    edited — not the agent actually stopping. Real "the agent died" is derived
    from the process signal (see the exited-agent path), never from pane text.
    """
    error_content = IDLE_CAPTURE + "\nrate limit exceeded (429) — APIError, Connection error\n"
    mon = IdleMonitor()
    mon._classify_burst("s1", [error_content, error_content, error_content], now=100.0)
    state = mon._classify_burst("s1", [error_content, error_content, error_content], now=200.0)
    assert state != SessionState.ERROR
    assert state == SessionState.IDLE


async def test_long_running_working_session_never_stalls(monkeypatch):
    """A session busy for a long time stays WORKING — there is no time-based stall.

    Elapsed working-time is not a reliable "stuck" signal: a healthy long command
    (a spinner ticking over a 30-min ingest) looks identical to a real hang, so we
    don't promote to a red 'stalled' state on duration alone.
    """
    mon = IdleMonitor()

    async def _cap(_n):
        return ["frame"]

    async def _persist(_n, _s):
        return None

    async def _persist_attn():
        return None

    monkeypatch.setattr(mon, "_burst_capture", _cap)
    monkeypatch.setattr(mon, "_classify_burst", lambda *_a, **_k: SessionState.WORKING)
    monkeypatch.setattr(mon, "_persist_state", _persist)
    monkeypatch.setattr(im, "capture_pane_title", lambda _n: "")
    monkeypatch.setattr(im.session_attention, "persist", _persist_attn)
    monkeypatch.setattr(im.session_attention, "mark_attention", lambda *_a: None)
    monkeypatch.setattr(im.session_attention, "clear_unseen", lambda *_a: None)

    clock = {"t": 1000.0}
    monkeypatch.setattr(im.time, "time", lambda: clock["t"])

    await mon._check_session("w")
    assert mon.get_state("w") == SessionState.WORKING

    clock["t"] += 3600  # an hour of continuous work later
    await mon._check_session("w")
    assert mon.get_state("w") == SessionState.WORKING


def _seed_tracked_agent(mon, name="worker", state=SessionState.WORKING):
    mon._fingerprints[name] = "fp"
    mon._states[name] = state


def _capture_exit_effects(mon, monkeypatch):
    persisted, marked = [], {}

    async def _persist(name, state):
        persisted.append((name, state))

    async def _noop():
        return None

    monkeypatch.setattr(mon, "_persist_state", _persist)
    monkeypatch.setattr(im.session_attention, "mark_attention", lambda n, s: marked.update({n: s}))
    monkeypatch.setattr(im.session_attention, "persist", _noop)
    return persisted, marked


async def test_agent_exit_from_live_terminal_surfaces_error_after_confirm(monkeypatch):
    """Agent process gone but its terminal still open -> ERROR, after a one-poll hold."""
    mon = IdleMonitor()
    persisted, marked = _capture_exit_effects(mon, monkeypatch)
    _seed_tracked_agent(mon)

    await mon._reap_dead_targets(targets=set(), live_sessions={"worker"})
    assert marked == {}  # held, not yet fired
    assert "worker" in mon._exit_pending

    await mon._reap_dead_targets(targets=set(), live_sessions={"worker"})
    assert marked == {"worker": "error"}
    assert persisted == [("worker", SessionState.ERROR)]
    assert "worker" not in mon._fingerprints  # stopped tracking after firing


async def test_killed_session_is_retired_silently(monkeypatch):
    """Whole tmux session gone (killed) -> no error, no wake."""
    mon = IdleMonitor()
    persisted, marked = _capture_exit_effects(mon, monkeypatch)
    _seed_tracked_agent(mon)

    await mon._reap_dead_targets(targets=set(), live_sessions=set())

    assert marked == {}
    assert persisted == []
    assert "worker" not in mon._fingerprints
    assert mon._exit_pending == set()


async def test_transient_discovery_miss_does_not_fire_exit(monkeypatch):
    """A single missed poll while the agent lives must not fire a false exit."""
    mon = IdleMonitor()
    _persisted, marked = _capture_exit_effects(mon, monkeypatch)
    _seed_tracked_agent(mon)

    await mon._reap_dead_targets(targets=set(), live_sessions={"worker"})
    assert "worker" in mon._exit_pending

    await mon._reap_dead_targets(targets={"worker"}, live_sessions={"worker"})
    assert marked == {}
    assert mon._exit_pending == set()


def test_sessions_tracked_independently():
    """Two sessions with independent state -> independent classification."""
    mon = IdleMonitor()
    # s1: idle (stable captures)
    mon._classify_burst("s1", [IDLE_CAPTURE] * 3, now=100.0)
    # s2: busy
    mon._classify_burst("s2", [BUSY_FRAME_1] * 3, now=100.0)

    s1_state = mon._classify_burst("s1", [IDLE_CAPTURE] * 3, now=130.0)
    s2_state = mon._classify_burst("s2", [BUSY_FRAME_2, BUSY_FRAME_1, BUSY_FRAME_2], now=130.0)
    assert s1_state == SessionState.IDLE
    assert s2_state == SessionState.WORKING


def test_recover_session_data_db_trims_trailing_garbage(tmp_path, monkeypatch):
    """Trailing-garbage corruption from interleaved writes must be recoverable."""
    # Point SESSIONS_DATA_DIR at an empty tmp_path
    from lumbergh import constants, db_utils

    monkeypatch.setattr(constants, "SESSIONS_DATA_DIR", tmp_path)
    monkeypatch.setattr(db_utils, "SESSIONS_DATA_DIR", tmp_path)

    valid = {"_default": {"1": {"state": "idle"}}, "extra": {"1": {"hello": "world"}}}
    path = tmp_path / "s-garbage.json"
    path.write_text(json.dumps(valid) + '}}}stray garbage from prior write")"}}}')

    assert db_utils.recover_session_data_db("s-garbage") is True

    # File is now valid JSON with all previously valid tables intact
    recovered = json.loads(path.read_text())
    assert recovered == valid


def test_recover_session_data_db_resets_unrecoverable_file(tmp_path, monkeypatch):
    """Totally corrupt files are backed up and replaced with an empty DB."""
    from lumbergh import constants, db_utils

    monkeypatch.setattr(constants, "SESSIONS_DATA_DIR", tmp_path)
    monkeypatch.setattr(db_utils, "SESSIONS_DATA_DIR", tmp_path)

    path = tmp_path / "s-broken.json"
    path.write_text("definitely not json at all {{{")

    assert db_utils.recover_session_data_db("s-broken") is True

    # Main file is empty, backup exists beside it
    assert json.loads(path.read_text()) == {}
    backups = list(tmp_path.glob("s-broken.json.corrupt-*"))
    assert len(backups) == 1
    assert "not json" in backups[0].read_text()


@pytest.mark.asyncio
async def test_persist_state_self_heals_corrupt_db(tmp_path, monkeypatch):
    """A corrupt DB file should not block future idle-state persistence."""
    from lumbergh import constants, db_utils

    monkeypatch.setattr(constants, "SESSIONS_DATA_DIR", tmp_path)
    monkeypatch.setattr(db_utils, "SESSIONS_DATA_DIR", tmp_path)

    path = tmp_path / "s-corrupt.json"
    path.write_text('{"todos": {"1": {"items": []}}}trailing junk}}}')

    mon = IdleMonitor()
    await mon._persist_state("s-corrupt", SessionState.IDLE)

    data = json.loads(path.read_text())
    assert "idle_state" in data
    idle_rows = list(data["idle_state"].values())
    assert any(row.get("state") == "idle" for row in idle_rows)
    # Pre-existing todos table survived the recovery
    assert data.get("todos") == {"1": {"items": []}}
