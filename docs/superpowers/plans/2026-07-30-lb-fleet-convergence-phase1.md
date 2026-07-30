# lb⇄fleet Convergence — Phase 1: Window-Aware Substrate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Lumbergh track agents at `session:window` granularity so a `sherpa fleet` worker running in a window (e.g. `port:fleet-644`) becomes a first-class, individually observable/driveable target in `lb` and the dashboard — closing the "fleet workers are invisible to lb" blind spot.

**Architecture:** Introduce a single `target` string identifier — either `session` (bare, today's behavior) or `session:window`. A pure target model + a tmux-backed discovery step become the one source of "what is trackable." The idle monitor, the agent control router (`/api/agent/...`), and the worktree/task registry all key on `target` instead of a bare session name. Because tmux `-t` already accepts `session:window` syntax, the pane-capture layer needs no logic change. Sessions with a single agent window collapse to the bare-`session` target, so all existing standalone/ship/scout behavior is preserved.

**Tech Stack:** Python 3.11+, FastAPI, libtmux + raw `tmux` subprocesses, TinyDB, pytest. Frontend untouched in Phase 1 (it consumes `/api/agent/sessions` and the fleet rows, which gain window entries automatically).

## Global Constraints

- Python 3.11+; use `uv run pytest` from `backend/` to run tests.
- Run `./lint.sh` before considering the phase done; fix all unfixable errors.
- Follow the repo's red-green rule: write the failing test first, verify it fails, then implement.
- A single-agent-window session MUST keep collapsing to its bare `session` name — no behavior change for standalone/ship/scout/bill sessions. Only sessions with 2+ agent windows expand into `session:window` targets.
- Prefer expressiveness over comments (per user global CLAUDE.md); no Arrange/Act/Assert narration; let test names document contracts.
- tmux target strings use `session:window` (a colon, never a slash) so they remain valid FastAPI path params.

## File Structure

- **Create** `backend/lumbergh/targets.py` — the target model: parse/format, the collapse rule (`select_targets`), the agent-window predicate (`window_runs_agent`), and the tmux-backed `discover_targets`. One responsibility: "what is a trackable target and how do we enumerate them."
- **Create** `backend/lumbergh/tests/test_targets.py` — unit tests for the pure functions in `targets.py`.
- **Modify** `backend/lumbergh/tmux_pty.py` — rename the `session_name` parameter to `target` on `capture_pane_content`, `capture_pane_text`, `capture_pane_title` (semantic only; value already passed to `-t`). Add `list_session_windows(session)`.
- **Modify** `backend/lumbergh/idle_monitor.py` — drive the poll loop off `discover_targets`; key all per-agent dicts on `target`.
- **Modify** `backend/lumbergh/routers/agent.py` — `_live_names()` returns discovered targets; endpoints accept `session:window`.
- **Create** `backend/lumbergh/tests/test_agent_router_targets.py` — router-level tests that two agent windows in one session both appear and are addressable.
- **Modify** `backend/lumbergh/worktrees.py` — `record_worktree` gains `target` (with `session=` back-compat alias) and `run`.
- **Modify** `backend/lumbergh/tests/test_worktrees.py` — cover `target`/`run`.
- **Modify** `backend/lumbergh/routers/bill.py` — `_fleet_rows` surfaces window targets and a `run` value.
- **Create** `backend/lumbergh/tests/test_window_discovery_integration.py` — the end-to-end reproduction against a real tmux session with two agent-marked windows.

---

### Task 1: Target model — parse, format, and the collapse rule

**Files:**
- Create: `backend/lumbergh/targets.py`
- Test: `backend/lumbergh/tests/test_targets.py`

**Interfaces:**
- Produces:
  - `parse_target(target: str) -> tuple[str, str | None]` — `"port"` → `("port", None)`; `"port:fleet-644"` → `("port", "fleet-644")`.
  - `format_target(session: str, window: str | None) -> str` — inverse of `parse_target`.
  - `select_targets(windows_by_session: dict[str, list[str]]) -> list[str]` — given each session's list of *agent* window names, return the target list applying the collapse rule: 0 agent windows → nothing; exactly 1 → bare `session`; 2+ → one `session:window` per agent window (sorted for determinism).

- [ ] **Step 1: Write the failing tests**

```python
# backend/lumbergh/tests/test_targets.py
from lumbergh.targets import format_target, parse_target, select_targets


def test_parse_bare_session_has_no_window():
    assert parse_target("port") == ("port", None)


def test_parse_session_window_splits_on_first_colon():
    assert parse_target("port:fleet-644") == ("port", "fleet-644")


def test_format_round_trips_parse():
    assert format_target("port", None) == "port"
    assert format_target("port", "fleet-644") == "port:fleet-644"


def test_single_agent_window_collapses_to_bare_session():
    assert select_targets({"port": ["claude"]}) == ["port"]


def test_multiple_agent_windows_expand_to_targets():
    assert select_targets({"port": ["fleet-644", "fleet-643"]}) == [
        "port:fleet-643",
        "port:fleet-644",
    ]


def test_session_with_no_agent_windows_yields_nothing():
    assert select_targets({"port": []}) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_targets.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lumbergh.targets'`.

- [ ] **Step 3: Implement the pure functions**

```python
# backend/lumbergh/targets.py
"""The `target` identifier: `session` (bare) or `session:window`.

A target is the unit Lumbergh observes and drives. A session with a single
agent window collapses to its bare name (preserving all prior single-session
behavior); a session with several agent windows — e.g. a fleet batch — expands
into one target per window.
"""


def parse_target(target: str) -> tuple[str, str | None]:
    session, sep, window = target.partition(":")
    return (session, window) if sep else (session, None)


def format_target(session: str, window: str | None) -> str:
    return f"{session}:{window}" if window else session


def select_targets(windows_by_session: dict[str, list[str]]) -> list[str]:
    targets: list[str] = []
    for session, windows in windows_by_session.items():
        if not windows:
            continue
        if len(windows) == 1:
            targets.append(session)
        else:
            targets.extend(format_target(session, w) for w in sorted(windows))
    return targets
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_targets.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/targets.py backend/lumbergh/tests/test_targets.py
git commit -m "feat(targets): session:window target model + collapse rule"
```

---

### Task 2: Agent-window predicate + tmux-backed discovery

**Files:**
- Modify: `backend/lumbergh/tmux_pty.py` (add `list_session_windows`)
- Modify: `backend/lumbergh/targets.py` (add `window_runs_agent`, `discover_targets`)
- Test: `backend/lumbergh/tests/test_targets.py`

**Interfaces:**
- Consumes: `select_targets`, `format_target` (Task 1); `capture_pane_text` (existing, `tmux_pty`).
- Produces:
  - `tmux_pty.list_session_windows(session: str) -> list[str]` — window names in a session, via `tmux list-windows -t <session> -F "#{window_name}"`; `[]` on any failure.
  - `targets.window_runs_agent(pane_text: str) -> bool` — True when a pane shows an agent UI. Initial heuristic: the pane contains a Claude Code UI marker. Kept as one named function so the heuristic can evolve without touching callers.
  - `targets.discover_targets(session_names: list[str], list_windows, capture) -> list[str]` — pure-ish composition: `list_windows(session)` per session, `capture(format_target(session, window))` per window, keep windows where `window_runs_agent(text)`, then `select_targets`. `list_windows`/`capture` are injected so tests need no tmux.

- [ ] **Step 1: Write the failing tests**

```python
# add to backend/lumbergh/tests/test_targets.py
from lumbergh.targets import discover_targets, window_runs_agent

CLAUDE_PANE = "\n╭─ Claude Code ─╮\n│ > \n╰──────────────╯\n"
SHELL_PANE = "user@host:~/src$ "


def test_window_runs_agent_detects_claude_ui():
    assert window_runs_agent(CLAUDE_PANE) is True


def test_window_runs_agent_rejects_plain_shell():
    assert window_runs_agent(SHELL_PANE) is False


def test_discover_collapses_single_agent_window():
    windows = {"port": ["win0"]}
    panes = {"port": CLAUDE_PANE}  # bare session capture
    result = discover_targets(
        ["port"],
        list_windows=lambda s: windows[s],
        capture=lambda t: panes.get(t, ""),
    )
    assert result == ["port"]


def test_discover_expands_two_agent_windows():
    panes = {"port:fleet-643": CLAUDE_PANE, "port:fleet-644": CLAUDE_PANE}
    result = discover_targets(
        ["port"],
        list_windows=lambda s: ["fleet-644", "fleet-643"],
        capture=lambda t: panes.get(t, ""),
    )
    assert result == ["port:fleet-643", "port:fleet-644"]


def test_discover_ignores_non_agent_windows():
    panes = {"port:fleet-644": CLAUDE_PANE, "port:logs": SHELL_PANE}
    result = discover_targets(
        ["port"],
        list_windows=lambda s: ["fleet-644", "logs"],
        capture=lambda t: panes.get(t, ""),
    )
    assert result == ["port"]  # only one agent window → collapses
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_targets.py -k "agent or discover" -v`
Expected: FAIL with `ImportError: cannot import name 'discover_targets'`.

- [ ] **Step 3: Implement discovery**

Add to `backend/lumbergh/targets.py`:

```python
from collections.abc import Callable

_AGENT_MARKERS = ("Claude Code", "╭─ Claude")  # box-drawn Claude Code prompt frame


def window_runs_agent(pane_text: str) -> bool:
    return any(marker in pane_text for marker in _AGENT_MARKERS)


def discover_targets(
    session_names: list[str],
    list_windows: Callable[[str], list[str]],
    capture: Callable[[str], str],
) -> list[str]:
    windows_by_session: dict[str, list[str]] = {}
    for session in session_names:
        windows = list_windows(session)
        agent_windows = [
            w for w in windows if window_runs_agent(capture(format_target(session, w)))
        ]
        windows_by_session[session] = agent_windows
    return select_targets(windows_by_session)
```

Add to `backend/lumbergh/tmux_pty.py` (near the other capture helpers):

```python
def list_session_windows(session: str) -> list[str]:
    """Window names in a session, or [] on any failure."""
    try:
        result = subprocess.run(
            [TMUX_CMD, "list-windows", "-t", session, "-F", "#{window_name}"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=2,
        )
        if result.returncode != 0:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception:
        return []
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_targets.py -v`
Expected: PASS (all target tests).

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/targets.py backend/lumbergh/tmux_pty.py backend/lumbergh/tests/test_targets.py
git commit -m "feat(targets): tmux-backed window discovery + agent-window predicate"
```

---

### Task 3: Idle monitor keys on targets

**Files:**
- Modify: `backend/lumbergh/idle_monitor.py:173-197` (`_check_all_sessions`) and `241-273` (`_get_live_session_names`)
- Modify: `backend/lumbergh/tmux_pty.py` (rename `session_name` → `target` on `capture_pane_content`/`_text`/`_title` — value already flows to `-t`, so this is a rename only)
- Test: `backend/lumbergh/tests/test_idle_monitor_targets.py` (create)

**Interfaces:**
- Consumes: `targets.discover_targets` (Task 2); `tmux_pty.list_session_windows`, `capture_pane_content/_text` (Tasks 2 + existing).
- Produces: `IdleMonitor` whose `_states`, `_state_since`, `_fingerprints`, `_working_since`, `_needs_answer`, etc. are keyed by `target`; `get_state(target)`, `state_since_seconds(target)`, `needs_answer(target)` accept target strings unchanged in signature.

- [ ] **Step 1: Write the failing test**

```python
# backend/lumbergh/tests/test_idle_monitor_targets.py
import asyncio

from lumbergh.idle_detector import SessionState
from lumbergh.idle_monitor import IdleMonitor


def test_two_agent_windows_get_independent_state(monkeypatch):
    monitor = IdleMonitor()
    discovered = ["port:fleet-643", "port:fleet-644"]

    monkeypatch.setattr(
        "lumbergh.idle_monitor.discover_live_targets", lambda: discovered
    )

    async def fake_check(target):
        monitor._record_state_change(
            target,
            SessionState.IDLE if target.endswith("644") else SessionState.WORKING,
        )

    monkeypatch.setattr(monitor, "_check_session", fake_check)

    asyncio.run(monitor._check_all_sessions())

    assert monitor.get_state("port:fleet-644") == SessionState.IDLE
    assert monitor.get_state("port:fleet-643") == SessionState.WORKING
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_idle_monitor_targets.py -v`
Expected: FAIL — `_check_all_sessions` currently enumerates bare session names via `_get_live_session_names`, so `discover_live_targets` doesn't exist / isn't used.

- [ ] **Step 3: Implement target-driven discovery in the monitor**

Add a module-level helper in `idle_monitor.py` and route the loop through it:

```python
def discover_live_targets() -> list[str]:
    from lumbergh.targets import discover_targets
    from lumbergh.tmux_pty import capture_pane_text, list_session_windows

    return discover_targets(
        _live_session_names(),
        list_windows=list_session_windows,
        capture=lambda t: capture_pane_text(t, lines=200),
    )
```

Rename the existing `IdleMonitor._get_live_session_names` to a module-level `_live_session_names()` (unchanged body — it still returns bare session names, which is the correct input to discovery). In `_check_all_sessions`, replace the `sessions = ... _get_live_session_names` call with:

```python
targets = await loop.run_in_executor(None, discover_live_targets)
```

and rename the local `sessions`/`name` variables to `targets`/`target` throughout the method (the dead-key cleanup set-difference and the `gather` over `_check_session` are otherwise unchanged — they already operate on whatever strings the list holds). Leave `session_identity.prune`/`_maybe_nudge_bill` keyed on bare session names: pass `{parse_target(t)[0] for t in targets}` to `prune`.

Rename `session_name` → `target` in the three `tmux_pty` capture function signatures and their internal `-t` uses.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_idle_monitor_targets.py lumbergh/tests/test_idle_monitor_state_since.py lumbergh/tests/test_idle_monitor_question.py lumbergh/tests/test_tmux_pty.py -v`
Expected: PASS (new test + existing monitor/tmux tests still green).

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/idle_monitor.py backend/lumbergh/tmux_pty.py backend/lumbergh/tests/test_idle_monitor_targets.py
git commit -m "feat(idle-monitor): classify state per session:window target"
```

---

### Task 4: Agent control router surfaces and addresses targets

**Files:**
- Modify: `backend/lumbergh/routers/agent.py:28-65` (`_live_names`, `_require`, `sessions`)
- Test: `backend/lumbergh/tests/test_agent_router_targets.py` (create)

**Interfaces:**
- Consumes: `idle_monitor.discover_live_targets` (Task 3).
- Produces: `/api/agent/sessions` lists one entry per discovered target (bare or `session:window`); `/sessions/{name}/state|read|wait` accept a `session:window` `name` (colon path param) and resolve it through `idle_monitor` and the activity adapters unchanged.

- [ ] **Step 1: Write the failing test**

```python
# backend/lumbergh/tests/test_agent_router_targets.py
from fastapi.testclient import TestClient

from lumbergh.idle_detector import SessionState
from lumbergh.main import app


def test_sessions_endpoint_lists_each_agent_window(monkeypatch):
    targets = ["port:fleet-643", "port:fleet-644"]
    monkeypatch.setattr("lumbergh.routers.agent.discover_live_targets", lambda: targets)
    monkeypatch.setattr(
        "lumbergh.routers.agent.idle_monitor.get_state",
        lambda t: SessionState.IDLE,
    )
    client = TestClient(app)
    resp = client.get("/api/agent/sessions", headers=_agent_auth())
    names = [s["name"] for s in resp.json()["sessions"]]
    assert names == ["port:fleet-643", "port:fleet-644"]


def test_state_endpoint_addresses_a_window(monkeypatch):
    monkeypatch.setattr(
        "lumbergh.routers.agent.discover_live_targets", lambda: ["port:fleet-644"]
    )
    monkeypatch.setattr(
        "lumbergh.routers.agent.idle_monitor.get_state",
        lambda t: SessionState.WORKING,
    )
    client = TestClient(app)
    resp = client.get("/api/agent/sessions/port:fleet-644/state", headers=_agent_auth())
    assert resp.status_code == 200
    assert resp.json()["session"] == "port:fleet-644"
    assert resp.json()["state"] == "working"
```

> `_agent_auth()` builds the agent-token header. Reuse the existing helper from `test_agent_router.py` / `test_agent_auth.py` (import it or copy its one-liner) rather than re-deriving the token.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_agent_router_targets.py -v`
Expected: FAIL — `_live_names()` still reads bare session names from `get_live_sessions()`, so the window targets are absent and `_require` 404s `port:fleet-644`.

- [ ] **Step 3: Point the router at discovery**

In `backend/lumbergh/routers/agent.py`, replace `_live_names` and import discovery:

```python
from lumbergh.idle_monitor import discover_live_targets


def _live_names() -> list[str]:
    return discover_live_targets()
```

`_require`, `state`, `read`, `wait`, `wait-output`, and `sessions` need no further change — they already key off the `name` string and call `idle_monitor`/adapters with it. Confirm the `{name}` path routes accept a colon (they do; FastAPI path params match everything except `/`).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_agent_router_targets.py lumbergh/tests/test_agent_router.py -v`
Expected: PASS (new target tests + existing agent-router tests green).

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/routers/agent.py backend/lumbergh/tests/test_agent_router_targets.py
git commit -m "feat(agent-router): list and address session:window targets"
```

---

### Task 5: Worktree/task registry gains `target` and `run`

**Files:**
- Modify: `backend/lumbergh/worktrees.py:144-168` (`record_worktree`)
- Modify: `backend/lumbergh/tests/test_worktrees.py`

**Interfaces:**
- Produces: `record_worktree(..., target: str | None = None, run: str | None = None, session: str | None = None)`. `target` is the new canonical field; `session=` remains accepted and is stored into `target` when `target` is not given (back-compat for existing callers). The stored row carries both `"target"` and, for one release, the legacy `"associated_session"` mirror so nothing downstream breaks mid-migration. Adds `"run"`.

- [ ] **Step 1: Write the failing tests**

```python
# add to backend/lumbergh/tests/test_worktrees.py
def test_record_worktree_stores_target_and_run(tmp_path, worktrees_db):
    row = worktrees.record_worktree(
        path=tmp_path / "wt",
        parent_repo=tmp_path / "repo",
        branch="feat/x",
        created_at="2026-07-30T00:00:00Z",
        target="port:fleet-644",
        run="batch-9",
    )
    assert row["target"] == "port:fleet-644"
    assert row["run"] == "batch-9"


def test_record_worktree_session_kwarg_back_compat(tmp_path, worktrees_db):
    row = worktrees.record_worktree(
        path=tmp_path / "wt2",
        parent_repo=tmp_path / "repo",
        branch="feat/y",
        created_at="2026-07-30T00:00:00Z",
        session="scout-1",
    )
    assert row["target"] == "scout-1"
    assert row["run"] is None
```

> Reuse the existing worktrees-db fixture in `test_worktrees.py` (or its setup pattern) for `worktrees_db`; do not invent a new persistence path.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktrees.py -k "target or back_compat" -v`
Expected: FAIL — `record_worktree` has no `target`/`run` parameters (`TypeError: unexpected keyword argument 'target'`).

- [ ] **Step 3: Implement the field additions**

```python
def record_worktree(
    path: Path,
    parent_repo: Path,
    branch: str,
    created_at: str,
    session: str | None = None,
    links_applied: list[dict] | None = None,
    task_intent: str | None = None,
    kind: str | None = None,
    origin: str | None = None,
    target: str | None = None,
    run: str | None = None,
) -> dict:
    resolved_target = target if target is not None else session
    row = {
        "path": _key(path),
        "parent_repo": str(Path(parent_repo).resolve()),
        "branch": branch,
        "created_at": created_at,
        "target": resolved_target,
        "associated_session": resolved_target,
        "links_applied": links_applied or [],
        "task_intent": task_intent,
        "kind": kind,
        "origin": origin,
        "run": run,
    }
    db = get_worktrees_db()
    db.upsert(row, Query().path == row["path"])
    return row
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktrees.py -v`
Expected: PASS (new tests + existing worktree tests green).

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/worktrees.py backend/lumbergh/tests/test_worktrees.py
git commit -m "feat(worktrees): record target + run on task registry (session= back-compat)"
```

---

### Task 6: Fleet rows surface window targets and their run

**Files:**
- Modify: `backend/lumbergh/routers/bill.py` (`_fleet_rows` and the row shape it emits)
- Modify: `backend/lumbergh/tests/test_bill_router.py`

**Interfaces:**
- Consumes: `idle_monitor.discover_live_targets` (Task 3); registry rows with `target`/`run` (Task 5).
- Produces: each fleet row carries `target` (superseding the bare-session assumption) and `run` (may be `null`). Existing columns (`repo`, `branch`, `kind`, `state`, `since`, `unseen`, `outcome`, `repo_path`, `path`) are unchanged; `state`/`unseen`/`outcome` are resolved per `target`.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/lumbergh/tests/test_bill_router.py
def test_fleet_rows_carry_target_and_run(monkeypatch):
    # A registry entry recorded for a fleet-batch window.
    monkeypatch.setattr(
        "lumbergh.routers.bill.worktrees.all_entries",
        lambda: [
            {
                "path": "/wt/644",
                "parent_repo": "/repo/port",
                "branch": "kb-644",
                "target": "port:fleet-644",
                "associated_session": "port:fleet-644",
                "run": "batch-9",
                "kind": "ship",
                "origin": "bill",
            }
        ],
    )
    monkeypatch.setattr(
        "lumbergh.routers.bill.idle_monitor.get_state",
        lambda t: __import__(
            "lumbergh.idle_detector", fromlist=["SessionState"]
        ).SessionState.WORKING,
    )
    rows = _fleet_rows("bill")
    assert rows[0]["target"] == "port:fleet-644"
    assert rows[0]["run"] == "batch-9"
```

> Import `_fleet_rows` from `lumbergh.routers.bill` at the top of the test. Match the exact monkeypatch targets to the names `_fleet_rows` actually calls (read the current function first and adjust the patch paths if they differ — e.g. if it iterates `worktrees.all_entries()` vs a reconcile helper).

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_bill_router.py -k "target_and_run" -v`
Expected: FAIL — rows key off `associated_session`/bare session and omit `target`/`run`.

- [ ] **Step 3: Implement per-target rows**

Read the current `_fleet_rows` body first. Change it to read `row.get("target") or row.get("associated_session")` as the tracked identifier, resolve `state`/`unseen`/`since`/`outcome` against that target, and include `"target"` and `"run": row.get("run")` in each emitted dict. (This is the minimal change; the `_COLS` display list in `agent_cli/fleet.py` gains `run` in a later task or now if trivial.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_bill_router.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/routers/bill.py backend/lumbergh/tests/test_bill_router.py
git commit -m "feat(bill): fleet rows carry per-window target + run"
```

---

### Task 7: End-to-end reproduction — a fleet worker in a window is visible to lb

This is the headline gap from the origin note, tested the way a user hits it: a real tmux session with two agent-marked windows, observed through the live `/api/agent/sessions` endpoint. Per the repo rule, it reproduces the bug end-to-end rather than leading with a unit test — and it stays green only because Tasks 1–4 landed.

**Files:**
- Create: `backend/lumbergh/tests/test_window_discovery_integration.py`

**Interfaces:**
- Consumes: real `tmux`, `discover_live_targets` (Task 3), `/api/agent/sessions` (Task 4).

- [ ] **Step 1: Write the reproduction test**

```python
# backend/lumbergh/tests/test_window_discovery_integration.py
import shutil
import subprocess

import pytest

from lumbergh.constants import TMUX_CMD
from lumbergh.idle_monitor import discover_live_targets

pytestmark = pytest.mark.skipif(shutil.which(TMUX_CMD) is None, reason="tmux not installed")

_MARKER = "╭─ Claude Code ─╮"  # what window_runs_agent looks for


def _tmux(*args):
    subprocess.run([TMUX_CMD, *args], check=True, capture_output=True)


@pytest.fixture
def two_window_session():
    name = "lbtest-fleet"
    subprocess.run([TMUX_CMD, "kill-session", "-t", name], capture_output=True)
    _tmux("new-session", "-d", "-s", name, "-n", "fleet-643")
    _tmux("new-window", "-t", name, "-n", "fleet-644")
    for window in ("fleet-643", "fleet-644"):
        _tmux("send-keys", "-t", f"{name}:{window}", f"printf %s '{_MARKER}'", "Enter")
    yield name
    subprocess.run([TMUX_CMD, "kill-session", "-t", name], capture_output=True)


def test_both_fleet_windows_are_discovered(two_window_session):
    targets = discover_live_targets()
    assert f"{two_window_session}:fleet-643" in targets
    assert f"{two_window_session}:fleet-644" in targets
```

- [ ] **Step 2: Run the test — it must pass on top of Tasks 1–4**

Run: `cd backend && uv run pytest lumbergh/tests/test_window_discovery_integration.py -v`
Expected: PASS. To prove it is a real regression guard, temporarily revert Task 3's `discover_live_targets` wiring (or point `_check_all_sessions` back at bare names) and confirm this test fails, then restore.

- [ ] **Step 3: Commit**

```bash
git add backend/lumbergh/tests/test_window_discovery_integration.py
git commit -m "test(e2e): fleet-batch windows are discovered as distinct targets"
```

---

### Task 8: Lint, full suite, and phase wrap-up

**Files:** none (verification task).

- [ ] **Step 1: Run the full backend suite**

Run: `cd backend && uv run pytest -q`
Expected: PASS (no regressions from the target rename).

- [ ] **Step 2: Lint**

Run: `./lint.sh`
Expected: exits 0 after auto-fixes; resolve any remaining errors.

- [ ] **Step 3: Manual smoke (optional but recommended)**

With the backend running and a real fleet/two-window session live, run `lb` and confirm both windows appear as rows, then `lb read --session <session>:<window>` and `lb state --session <session>:<window>` resolve. Confirm a normal single-window session still shows as its bare name (no regression).

- [ ] **Step 4: Commit any lint fixups**

```bash
git add -A && git commit -m "chore: lint fixups for window-aware substrate"
```

---

## Self-Review

**Spec coverage (Phase 1 scope only):**
- Target model (`session` / `session:window`) → Task 1. ✓
- Discovery + per-pane agent detection → Task 2. ✓
- Per-target state/transcript via idle_monitor + pane-layer rename → Task 3. ✓
- `lb`/dashboard list & address every agent window (the single pane of glass) → Tasks 4, 6, 7. ✓
- Registry `associated_session` → `target` + `run` group → Task 5. ✓
- Red-green for the core "fleet worker invisible to lb" gap, reproduced end-to-end → Task 7. ✓
- Out of Phase 1 (correctly deferred to later plans): unified spawn `--into/--run`, `batch`/`land`/`teardown`, Redis removal, fleet retirement.

**Placeholder scan:** No TBD/TODO; every code step carries real code. The two "read the current function first" notes (Tasks 6 & 4 path-param) are verification instructions, not deferred work — the change itself is specified.

**Type consistency:** `parse_target`/`format_target`/`select_targets` signatures match across Tasks 1–3; `discover_targets(session_names, list_windows, capture)` is used identically in Task 2's test, Task 3's `discover_live_targets`, and Task 7. `record_worktree(..., target=, run=, session=)` matches between Task 5's impl and its tests. `discover_live_targets()` (no args) is the single monitor-level entry point consumed by Tasks 4, 6, 7.

**Known follow-on for a later plan:** the legacy `associated_session` mirror stored in Task 5 should be dropped once all readers use `target`; note it when writing the Phase 2 plan.
