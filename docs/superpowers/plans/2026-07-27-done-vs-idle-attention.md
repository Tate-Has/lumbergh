# `done` vs `idle` Seen/Unseen Attention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flag sessions that entered an attention state (idle/blocked/error) while unviewed as "unseen", clear on genuine viewer focus, and surface a "while you were away" count + labels.

**Architecture:** A new in-memory `session_attention` module is the runtime source of truth (mutated only on the asyncio loop, no locks). The idle monitor marks/clears attention on state transitions; the session manager marks "seen" via existing viewer presence (`active_clients`). Best-effort persistence is a single offloaded JSON file. The session-list API carries `unseen`/`attentionState`; the frontend overlays labels, a count badge, and urgency sorting.

**Tech Stack:** Python 3.11+ (stdlib), FastAPI, pytest; React/TypeScript, Vitest.

## Global Constraints

- Python **3.11+**; no new dependencies.
- `session_attention` must **never block the event loop** with I/O and **never raise** into the monitor/socket paths. In-memory mutations are synchronous; persistence is offloaded via `run_in_executor` and best-effort (log + swallow failures).
- Attention set = `IDLE`, `BLOCKED`, `ERROR`. `WORKING`/`STALLED`/`UNKNOWN` clear unseen.
- "Seen" = a session currently has viewers (`active_clients`); it is set on client register and cleared when the last client for the session disconnects. CLI/REST reads never change it.
- Persistence file: `CONFIG_DIR / "session_attention.json"`, shape `{name: attentionState}` for unseen sessions only. Viewers are never persisted.
- Run `./lint.sh` clean before completion.
- Commit messages: no AI attribution / Co-Authored-By lines.

---

### Task 1: `session_attention` module

**Files:**
- Modify: `backend/lumbergh/constants.py` (add `SESSION_ATTENTION_FILE`)
- Create: `backend/lumbergh/session_attention.py`
- Test: `backend/lumbergh/tests/test_session_attention.py`

**Interfaces:**
- Produces:
  - `SESSION_ATTENTION_FILE: Path` in constants (`CONFIG_DIR / "session_attention.json"`).
  - `set_viewing(name: str, viewing: bool) -> None` — `True`: mark viewing + clear unseen; `False`: drop viewing.
  - `mark_attention(name: str, state: str) -> None` — record unseen+state only if `name` has no viewers.
  - `clear_unseen(name: str) -> None`.
  - `is_unseen(name: str) -> bool`, `get(name: str) -> str | None` (attentionState or None), `unseen_count() -> int`, `snapshot() -> dict[str, dict]`.
  - `load(path: Path | None = None) -> None` (sync, best-effort), `_write(path: Path | None = None) -> None` (sync), `async persist() -> None` (offloads `_write`).
  - `reset() -> None` (test helper: clears in-memory maps).

- [ ] **Step 1: Add the constant**

In `backend/lumbergh/constants.py`, after `SESSION_IDENTITY_DIR`:

```python
SESSION_ATTENTION_FILE = CONFIG_DIR / "session_attention.json"
```

- [ ] **Step 2: Write the failing tests**

```python
# backend/lumbergh/tests/test_session_attention.py
import lumbergh.session_attention as sa


def setup_function():
    sa.reset()


def test_transition_without_viewer_marks_unseen():
    sa.mark_attention("s", "idle")
    assert sa.is_unseen("s") is True
    assert sa.get("s") == "idle"
    assert sa.unseen_count() == 1


def test_transition_with_viewer_does_not_mark():
    sa.set_viewing("s", True)
    sa.mark_attention("s", "idle")
    assert sa.is_unseen("s") is False
    assert sa.unseen_count() == 0


def test_viewing_clears_existing_unseen():
    sa.mark_attention("s", "blocked")
    assert sa.is_unseen("s") is True
    sa.set_viewing("s", True)
    assert sa.is_unseen("s") is False


def test_leaving_attention_state_clears():
    sa.mark_attention("s", "idle")
    sa.clear_unseen("s")
    assert sa.is_unseen("s") is False


def test_stop_viewing_does_not_reflag():
    # Watched it finish (seen), then closed the tab: still not unseen.
    sa.set_viewing("s", True)
    sa.mark_attention("s", "idle")
    sa.set_viewing("s", False)
    assert sa.is_unseen("s") is False


def test_snapshot_shape():
    sa.mark_attention("a", "error")
    snap = sa.snapshot()
    assert snap["a"] == {"unseen": True, "attentionState": "error"}


def test_persist_and_load_round_trip(tmp_path):
    path = tmp_path / "attn.json"
    sa.mark_attention("a", "idle")
    sa.mark_attention("b", "blocked")
    sa._write(path)
    sa.reset()
    assert sa.unseen_count() == 0
    sa.load(path)
    assert sa.get("a") == "idle"
    assert sa.get("b") == "blocked"


def test_load_missing_file_is_noop(tmp_path):
    sa.load(tmp_path / "nope.json")
    assert sa.unseen_count() == 0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_session_attention.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lumbergh.session_attention'`

- [ ] **Step 4: Implement `session_attention.py`**

```python
# backend/lumbergh/session_attention.py
"""Runtime 'seen/unseen' attention overlay for sessions.

A session becomes *unseen* when it enters an attention state (idle/blocked/error)
while nobody is viewing it, and *seen* again when a viewer opens it. This powers
the "finished while you were away" distinction (pattern adapted in spirit from
herdr; no code copied — see ~/.config/lumbergh/shared/herdr-steal-list.md).

The maps are mutated only on the asyncio event loop with no await between
read-modify-write, so no locking is needed. Persistence is a single small JSON
file, written offloaded and best-effort; viewers are never persisted.
"""

import json
import logging
import os
import tempfile
from pathlib import Path

from lumbergh.constants import SESSION_ATTENTION_FILE

logger = logging.getLogger(__name__)

_viewing: set[str] = set()
_unseen: dict[str, str] = {}  # name -> attentionState


def reset() -> None:
    _viewing.clear()
    _unseen.clear()


def set_viewing(name: str, viewing: bool) -> None:
    if viewing:
        _viewing.add(name)
        _unseen.pop(name, None)
    else:
        _viewing.discard(name)


def mark_attention(name: str, state: str) -> None:
    if name in _viewing:
        return
    _unseen[name] = state


def clear_unseen(name: str) -> None:
    _unseen.pop(name, None)


def is_unseen(name: str) -> bool:
    return name in _unseen


def get(name: str) -> str | None:
    return _unseen.get(name)


def unseen_count() -> int:
    return len(_unseen)


def snapshot() -> dict[str, dict]:
    return {name: {"unseen": True, "attentionState": state} for name, state in _unseen.items()}


def _write(path: Path | None = None) -> None:
    target = path or SESSION_ATTENTION_FILE
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(_unseen, f)
        os.replace(tmp, target)
    except OSError as exc:
        logger.warning("Could not persist session attention: %s", exc)


def load(path: Path | None = None) -> None:
    target = path or SESSION_ATTENTION_FILE
    try:
        data = json.loads(target.read_text())
        if isinstance(data, dict):
            _unseen.clear()
            _unseen.update({str(k): str(v) for k, v in data.items()})
    except (OSError, ValueError):
        return


async def persist() -> None:
    import asyncio

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _write)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_session_attention.py -q`
Expected: PASS (8 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/lumbergh/constants.py backend/lumbergh/session_attention.py backend/lumbergh/tests/test_session_attention.py
git commit -m "feat(attention): in-memory seen/unseen attention store"
```

---

### Task 2: Mark/clear attention on monitor transitions

**Files:**
- Modify: `backend/lumbergh/idle_monitor.py` (`_check_session` transition block)
- Test: `backend/lumbergh/tests/test_idle_monitor_attention.py`

**Interfaces:**
- Consumes: `session_attention.mark_attention`, `clear_unseen`, `persist` (Task 1).
- Produces: on a recorded state change, attention is marked (idle/blocked/error) or cleared, then persisted (offloaded).

**Notes:** The transition block is `idle_monitor.py:224` (`if state != old_state:`). Add the module import `from lumbergh import session_attention` at the top (alongside `session_identity`).

- [ ] **Step 1: Write the failing test**

```python
# backend/lumbergh/tests/test_idle_monitor_attention.py
import lumbergh.idle_monitor as im
from lumbergh.idle_detector import SessionState


async def _run_transition(monitor, name, captures_state, monkeypatch):
    # Drive _check_session with a stubbed classification and no real tmux.
    monkeypatch.setattr(monitor, "_burst_capture", _stub_capture)
    monkeypatch.setattr(monitor, "_classify_burst", lambda *a, **k: captures_state)
    monkeypatch.setattr(im, "capture_pane_title", lambda name: "")
    await monitor._check_session(name)


async def _stub_capture(name):
    return ["frame"]


async def test_transition_to_idle_marks_attention(monkeypatch):
    monitor = im.IdleMonitor()
    marked = {}
    monkeypatch.setattr(im.session_attention, "mark_attention", lambda n, s: marked.update({n: s}))
    monkeypatch.setattr(im.session_attention, "clear_unseen", lambda n: None)

    async def _noop_persist():
        return None

    monkeypatch.setattr(im.session_attention, "persist", _noop_persist)
    await _run_transition(monitor, "s", SessionState.IDLE, monkeypatch)
    assert marked == {"s": "idle"}


async def test_transition_to_working_clears_attention(monkeypatch):
    monitor = im.IdleMonitor()
    cleared = []
    monkeypatch.setattr(im.session_attention, "mark_attention", lambda n, s: None)
    monkeypatch.setattr(im.session_attention, "clear_unseen", lambda n: cleared.append(n))

    async def _noop_persist():
        return None

    monkeypatch.setattr(im.session_attention, "persist", _noop_persist)
    await _run_transition(monitor, "s", SessionState.WORKING, monkeypatch)
    assert cleared == ["s"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_idle_monitor_attention.py -q`
Expected: FAIL — `AttributeError: module 'lumbergh.idle_monitor' has no attribute 'session_attention'`.

- [ ] **Step 3: Import and hook the transition block**

Add near the existing import (`from lumbergh import session_identity`):

```python
from lumbergh import session_attention, session_identity
```

(Replace the existing `from lumbergh import session_identity` line with the combined import.)

Then in `_check_session`, extend the transition block (currently ends at `await self._persist_state(session_name, state)`):

```python
        old_state = self._states.get(session_name, SessionState.UNKNOWN)
        if state != old_state:
            logger.info(f"Session {session_name} state: {old_state.value} -> {state.value}")
            self._states[session_name] = state
            await self._persist_state(session_name, state)
            if state in (SessionState.IDLE, SessionState.BLOCKED, SessionState.ERROR):
                session_attention.mark_attention(session_name, state.value)
            else:
                session_attention.clear_unseen(session_name)
            await session_attention.persist()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_idle_monitor_attention.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/idle_monitor.py backend/lumbergh/tests/test_idle_monitor_attention.py
git commit -m "feat(attention): mark/clear attention on monitor transitions"
```

---

### Task 3: Mark "seen" via viewer presence

**Files:**
- Modify: `backend/lumbergh/session_manager.py` (`register_client`, `unregister_client`)
- Test: `backend/lumbergh/tests/test_session_manager_attention.py`

**Interfaces:**
- Consumes: `session_attention.set_viewing`, `persist` (Task 1).
- Produces: `register_client` sets viewing True; the last `unregister_client` sets viewing False; both persist (offloaded).

**Notes:** In `register_client`, `managed.clients.add(websocket)` is at `session_manager.py:241` (inside `async with self._lock`). In `unregister_client`, the last-client branch is `if not managed.clients:` at `session_manager.py:310`. Add the import `from lumbergh import session_attention` at the top of the file.

- [ ] **Step 1: Write the failing test**

```python
# backend/lumbergh/tests/test_session_manager_attention.py
import lumbergh.session_manager as sm


async def test_register_marks_seen(monkeypatch):
    calls = []
    monkeypatch.setattr(sm.session_attention, "set_viewing", lambda n, v: calls.append((n, v)))

    async def _noop_persist():
        return None

    monkeypatch.setattr(sm.session_attention, "persist", _noop_persist)
    manager = sm.SessionManager()

    class _WS:
        async def send_json(self, *a, **k):
            return None

    monkeypatch.setattr(manager, "_send_initial_repaint", lambda *a, **k: _acoro())
    # Force the "reuse existing PTY" path so no real tmux/PTY is created.
    from types import SimpleNamespace

    managed = SimpleNamespace(
        clients=set(), active_clients=set(), client_sizes={}, activity_seq={}, pane_state=None
    )
    manager._sessions["s"] = managed
    await manager.register_client("s", _WS())
    assert ("s", True) in calls


async def _acoro():
    return None
```

(If constructing `ManagedSession` via `SimpleNamespace` proves brittle against the real dataclass, build a real `ManagedSession` instead — the assertion is only that `set_viewing("s", True)` was called on register.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_session_manager_attention.py -q`
Expected: FAIL — `AttributeError: module 'lumbergh.session_manager' has no attribute 'session_attention'`.

- [ ] **Step 3: Import and hook register/unregister**

Add at the top of `session_manager.py` (with the other `from lumbergh import ...`):

```python
from lumbergh import session_attention
```

In `register_client`, immediately after `managed.clients.add(websocket)` (still inside the `async with self._lock`):

```python
            managed.clients.add(websocket)
            session_attention.set_viewing(session_name, True)
```

At the end of `register_client`, just before `return managed`, offload persistence:

```python
        await session_attention.persist()
        return managed
```

In `unregister_client`, inside the `if not managed.clients:` branch, add:

```python
            if not managed.clients:
                session_attention.set_viewing(session_name, False)
```

and after the `async with self._lock` block in `unregister_client` (best-effort), add:

```python
        await session_attention.persist()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest lumbergh/tests/test_session_manager_attention.py -q`
Expected: PASS (1 passed). If the `SimpleNamespace` stub is rejected by real code paths, switch to a real `ManagedSession` as noted.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/session_manager.py backend/lumbergh/tests/test_session_manager_attention.py
git commit -m "feat(attention): mark sessions seen on viewer presence"
```

---

### Task 4: Load on startup + expose in the API

**Files:**
- Modify: `backend/lumbergh/main.py` (`lifespan` loads persisted attention)
- Modify: `backend/lumbergh/routers/sessions.py` (`get_session_status` adds fields)
- Test: `backend/lumbergh/tests/test_session_status_attention.py`

**Interfaces:**
- Consumes: `session_attention.load`, `snapshot`/`get`/`is_unseen` (Task 1).
- Produces: `get_session_status(name)` result dict includes `unseen: bool` and `attentionState: str | None`.

**Notes:** `get_session_status(name) -> dict` is at `sessions.py:325`; it builds `result` and reads the `idle_state` table (~line 344). Add the fields there.

- [ ] **Step 1: Write the failing test**

```python
# backend/lumbergh/tests/test_session_status_attention.py
import lumbergh.session_attention as sa
from lumbergh.routers.sessions import get_session_status


def setup_function():
    sa.reset()


def test_status_includes_unseen_fields(monkeypatch):
    sa.mark_attention("s", "idle")
    result = get_session_status("s")
    assert result["unseen"] is True
    assert result["attentionState"] == "idle"


def test_status_defaults_when_seen():
    result = get_session_status("never-flagged")
    assert result["unseen"] is False
    assert result["attentionState"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_session_status_attention.py -q`
Expected: FAIL — `KeyError: 'unseen'`.

- [ ] **Step 3: Add fields in `get_session_status`**

At the top of `sessions.py`, add with the other imports:

```python
from lumbergh import session_attention
```

Inside `get_session_status`, where `result` is assembled (after the idle_state block, still inside the function), add:

```python
    result["unseen"] = session_attention.is_unseen(name)
    result["attentionState"] = session_attention.get(name)
```

(Place this outside the `try/except` that guards the optional DB reads, so the fields are always present.)

- [ ] **Step 4: Load persisted attention on startup**

In `main.py` `lifespan`, next to `install_session_hook()` / before `idle_monitor.start()`:

```python
    from lumbergh import session_attention

    session_attention.load()
```

- [ ] **Step 5: Run tests + import sanity**

Run: `cd backend && uv run pytest lumbergh/tests/test_session_status_attention.py -q && uv run python -c "import lumbergh.main"`
Expected: PASS (2 passed), import exits 0.

- [ ] **Step 6: Commit**

```bash
git add backend/lumbergh/main.py backend/lumbergh/routers/sessions.py backend/lumbergh/tests/test_session_status_attention.py
git commit -m "feat(attention): load on startup and expose unseen in session status"
```

---

### Task 5: Frontend status logic (labels + urgency)

**Files:**
- Modify: `frontend/src/utils/sessionStatus.ts`
- Test: `frontend/src/utils/sessionStatus.test.ts`

**Interfaces:**
- Produces: `SessionBase` gains `unseen?: boolean` and `attentionState?: 'idle' | 'blocked' | 'error' | ... | null`. `getSessionStatus` returns "while you were away" labels when `unseen`. `sessionUrgencyRank` boosts unseen sessions.

**Notes:** Mirror the existing test style in `sessionStatus.test.ts`.

- [ ] **Step 1: Write the failing tests**

```typescript
// append to frontend/src/utils/sessionStatus.test.ts
describe('unseen "while you were away" overlay', () => {
  it('labels an unseen idle session as done-while-away', () => {
    const status = getSessionStatus({
      name: 's', alive: true, idleState: 'idle', unseen: true, displayName: null,
    })
    expect(status.label).toBe('Done — while you were away')
    expect(status.pulse).toBe(true)
  })

  it('labels an unseen blocked session distinctly from a seen one', () => {
    const away = getSessionStatus({
      name: 's', alive: true, idleState: 'blocked', unseen: true, displayName: null,
    })
    expect(away.label).toBe('Blocked — while you were away')
    const seen = getSessionStatus({
      name: 's', alive: true, idleState: 'blocked', unseen: false, displayName: null,
    })
    expect(seen.label).toBe('Blocked — waiting on you')
  })

  it('labels an unseen error session as failed-while-away', () => {
    const status = getSessionStatus({
      name: 's', alive: true, idleState: 'error', unseen: true, displayName: null,
    })
    expect(status.label).toBe('Failed — while you were away')
  })

  it('ranks unseen sessions above ordinary ones but below the pinned favorite', () => {
    expect(sessionUrgencyRank({ theOne: false, idleState: 'idle', unseen: true })).toBeLessThan(
      sessionUrgencyRank({ theOne: false, idleState: 'idle', unseen: false })
    )
    expect(sessionUrgencyRank({ theOne: true, idleState: 'idle', unseen: true })).toBe(0)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/utils/sessionStatus.test.ts`
Expected: FAIL — labels don't match / `unseen` not a known field.

- [ ] **Step 3: Implement the overlay**

In `frontend/src/utils/sessionStatus.ts`, extend `SessionBase`:

```typescript
export interface SessionBase {
  name: string
  alive: boolean
  idleState?: 'unknown' | 'idle' | 'working' | 'blocked' | 'error' | 'stalled' | null
  unseen?: boolean
  attentionState?: 'idle' | 'blocked' | 'error' | null
  paused?: boolean
  displayName: string | null
  theOne?: boolean
}
```

In `getSessionStatus`, after the `if (!session.alive)` guard, add an unseen overlay before the normal switch:

```typescript
  if (session.unseen) {
    switch (session.idleState) {
      case 'blocked':
        return { color: 'purple', pulse: true, label: 'Blocked — while you were away' }
      case 'error':
        return { color: 'red', pulse: true, label: 'Failed — while you were away' }
      default:
        return { color: 'yellow', pulse: true, label: 'Done — while you were away' }
    }
  }
```

Update `sessionUrgencyRank` to accept and rank `unseen`:

```typescript
export function sessionUrgencyRank(
  session: Pick<SessionBase, 'theOne' | 'idleState' | 'unseen'>
): number {
  if (session.theOne) return 0
  if (session.idleState === 'blocked') return 1
  if (session.unseen) return 2
  return 3
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/utils/sessionStatus.test.ts`
Expected: PASS (existing + new cases).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/sessionStatus.ts frontend/src/utils/sessionStatus.test.ts
git commit -m "feat(attention): while-you-were-away labels and urgency ranking"
```

---

### Task 6: Frontend surfaces — card chip + dashboard count

**Files:**
- Modify: `frontend/src/components/SessionCard.tsx` (thread `unseen`/`attentionState`; render a "while away" chip)
- Modify: `frontend/src/pages/Dashboard.tsx` (thread fields; render a count badge)

**Interfaces:**
- Consumes: `unseen`/`attentionState` from the session-list API (Task 4).

**Notes:** This is UX surfacing (visual polish); no Gherkin/UI-e2e per project testing convention — the behavioral logic is already unit-tested in Task 5. Verify via build + lint.

- [ ] **Step 1: Add the fields to both local session types**

In `SessionCard.tsx` (near `idleStateUpdatedAt?: string | null`, line ~29) and `Dashboard.tsx` (near line ~34), add to the session interface:

```typescript
  unseen?: boolean
  attentionState?: 'idle' | 'blocked' | 'error' | null
```

- [ ] **Step 2: Render a "while away" chip on the card**

In `SessionCard.tsx`, where the status is shown (the block around line ~267 gated on `session.alive && session.idleState`), add a small chip when `session.unseen` is true, using the label from `getSessionStatus(session)` (which already yields the "while you were away" text). Keep it consistent with the existing status pill styling; reuse `statusColorClasses` for the color.

- [ ] **Step 3: Render a count badge on the dashboard**

In `Dashboard.tsx`, compute `const unseenCount = sessions.filter((s) => s.unseen).length` from the already-fetched list, and render a small badge (e.g. near the header/title) reading `${unseenCount} while you were away` when `unseenCount > 0`. No new fetch — it derives from the polled list.

- [ ] **Step 4: Type-check, build, and eyeball**

Run: `cd frontend && npx tsc --noEmit && npx vitest run src/utils/sessionStatus.test.ts`
Expected: tsc exits 0; tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/SessionCard.tsx frontend/src/pages/Dashboard.tsx
git commit -m "feat(attention): dashboard count badge and card while-away chip"
```

---

### Task 7: Full verification

- [ ] **Step 1: Full backend suite**

Run: `cd backend && uv run pytest -q`
Expected: all PASS (prior suites + the new attention tests).

- [ ] **Step 2: Lint**

Run: `./lint.sh`
Expected: exits 0 (auto-fixes applied; fix any remaining errors and re-run). The pre-existing `CsvViewer.tsx` eslint warning is unrelated.

- [ ] **Step 3: Commit any lint fixups**

```bash
git add -A
git commit -m "chore(attention): lint cleanups"
```

(Skip if nothing changed. Do not sweep unrelated files such as `frontend/package-lock.json` into the commit.)

---

## Self-Review

**Spec coverage:**
- In-memory attention truth, no locks, offloaded best-effort persistence → Task 1. ✓
- Mark on transition into idle/blocked/error, clear otherwise → Task 2. ✓
- Seen = viewer presence via register/unregister_client → Task 3. ✓
- Load on startup; `unseen`/`attentionState` in session-list response → Task 4. ✓
- Frontend labels ("Done/Blocked/Failed — while you were away"), BLOCKED relabel by seen/unseen, urgency sort → Task 5; count badge + card chip → Task 6. ✓
- Count folded into existing polled list (no new endpoint) → Tasks 4 & 6. ✓
- "Watched it finish then left" does not reflag → Task 1 `test_stop_viewing_does_not_reflag`. ✓
- Persistence is a single JSON file, offloaded (deviation from spec's per-session table, chosen to avoid sync-TinyDB event-loop lag) → Task 1. ✓ (flagged)

**Placeholder scan:** No TBD/TODO; each backend step has complete code; Task 6's visual steps describe exact fields/derivations with the label source (Task 5's `getSessionStatus`) — acceptable for UX surfacing where the behavioral logic is unit-tested in Task 5.

**Type consistency:** `mark_attention(name, state.value)` (Task 2) passes the `SessionState.value` string that `get()`/`snapshot()` return (Task 1) and that `attentionState` carries through the API (Task 4) into the frontend union (Tasks 5-6). `set_viewing(name, bool)` signature matches Tasks 1/3. `sessionUrgencyRank` gains `unseen` in its `Pick<...>` (Task 5) consistent with `SessionBase`. ✓
