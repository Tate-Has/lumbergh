# lb⇄fleet Convergence — Phase 2: Unified Spawn — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend Lumbergh's single spawn primitive so `lb spawn … --into <session> [--run <id>]` places a worktree-isolated worker in a **window** of a session (auto-creating the session if absent) instead of always creating a new session — making a fleet-style batch of window workers first-class, fully observable *and* reap-safe.

**Architecture:** One backend spawn primitive keeps its shape (`worktrees.create` → make container → deliver brief). Only the "make the container" step branches: no `--into` → new session (today's `create_tmux_session`, target = bare name); `--into S` → `create_tmux_window(S, …)` (auto-creates `S` or adds a window), target = `S:window`. The registry records `target` + `run` (fields Phase 1 already added). Two Phase-1 carry-overs are prerequisites and land here: reap/teardown must kill the *window* (not the session) for a `session:window` target, and a window worker's transcript/outcome must resolve from the worktree registry (its cwd) plus its `LUMBERGH_SESSION=session:window` identity — with **no colon-keyed pollution of the session store**.

**Tech Stack:** Python 3.11+, FastAPI, raw `tmux` subprocesses, TinyDB, pytest. `lb` CLI is a thin HTTP client (`backend/lumbergh/agent_cli/`).

## Global Constraints

- Python 3.11+; run backend tests with `uv run pytest` from `backend/`.
- Run `./lint.sh` before done (backend ruff must be clean; the frontend lint step has a pre-existing env failure unrelated to this backend-only phase — do not chase it, and touch no frontend files).
- Red-green: write the failing test first, verify it fails, then implement.
- Bare-target behavior (standalone/ship/scout/bill spawns and their reap) MUST be unchanged. Only the `--into` path is new.
- A window target is `session:window` (one colon, no slash) — a valid tmux `-t` and FastAPI path param.
- `--into <session>` **auto-creates** the session when it isn't live, then adds the worker's window; when it is live, it adds a window.
- Do NOT write colon-keyed entries into the session store (`get_stored_sessions`); window-worker metadata resolves from the worktree registry instead.
- Prefer expressiveness over comments; no Arrange/Act/Assert narration; test names carry the contract.
- No commit trailers ("Co-Authored-By" / "Generated with Claude").

## File Structure

- **Modify** `backend/lumbergh/tmux_pty.py` — add `create_tmux_window(session, window, workdir, launch_command)` (auto-create session or add window; sets `LUMBERGH_SESSION=session:window`) and `kill_tmux_window(target)`.
- **Modify** `backend/lumbergh/routers/sessions.py` — factor the post-create send-keys (LUMBERGH_SESSION export, venv activation, launch) so `create_tmux_window` reuses it rather than duplicating (see Task 1).
- **Modify** `backend/lumbergh/worktrees.py` — thread `target` + `run` through `create(...)` to `record_worktree(...)`.
- **Modify** `backend/lumbergh/activity/resolve.py` — `session_meta` falls back to the worktree registry for a target absent from the session store.
- **Modify** `backend/lumbergh/routers/worktrees.py` — `reap` kills the window for a `session:window` target, the session for a bare target.
- **Modify** `backend/lumbergh/routers/bill.py` — `SpawnBody` gains `into` + `run`; `spawn()` branches container creation, threads target/run, skips the session-store write for window workers, and unwinds the right thing.
- **Modify** `backend/lumbergh/agent_cli/spawn.py` + `backend/lumbergh/agent_cli/main.py` — `lb spawn --into/--run` flags + help.
- **Tests:** `test_tmux_window_helpers.py` (new), `test_worktrees.py`, `test_adapter_resolve.py`, `test_worktree_router.py`, `test_bill_router.py`, `test_lb_spawn_cli.py`, `test_spawn_into_integration.py` (new).

---

### Task 1: tmux window helpers — `create_tmux_window` + `kill_tmux_window`

**Files:**
- Modify: `backend/lumbergh/routers/sessions.py:176-229` (`create_tmux_session` — extract the post-create steps)
- Modify: `backend/lumbergh/tmux_pty.py` (add the two helpers)
- Test: `backend/lumbergh/tests/test_tmux_window_helpers.py` (create)

**Interfaces:**
- Consumes: `list_tmux_sessions()` (tmux_pty, existing), `find_venv_activate` (sessions.py, existing).
- Produces:
  - `sessions._start_agent_in_target(target, workdir, launch_command)` — the three send-keys currently inlined in `create_tmux_session` (export `LUMBERGH_SESSION=<target>`, optional venv `source`, launch), factored to accept an explicit target and identity value. `create_tmux_session` calls it with `target=name`.
  - `tmux_pty.create_tmux_window(session, window, workdir, launch_command) -> str` — if `session` is not among `list_tmux_sessions()`, create it via `new-session -d -s session -n window -c workdir`; otherwise `new-window -t session -n window -c workdir`. Then run the agent-start steps with identity `session:window`. Returns the target `session:window`. Raises `RuntimeError` on the tmux create/new-window failure.
  - `tmux_pty.kill_tmux_window(target) -> bool` — `tmux kill-window -t <target>`; returns True on rc 0, False on failure (mirrors `kill_tmux_session`).

Note on the identity export: `create_tmux_session` sets `LUMBERGH_SESSION={name}`; the window equivalent MUST set `LUMBERGH_SESSION={session}:{window}` so the SessionStart hook and `session_identity` key the worker under its full target. To avoid a circular import (`tmux_pty` importing from `routers.sessions`), put `create_tmux_window` where it can call the agent-start helper — implement `create_tmux_window` in `routers/sessions.py` alongside `create_tmux_session` (which already owns venv/launch logic) and re-export it, OR keep the raw tmux calls in `tmux_pty` and the agent-start send-keys in `sessions`. Choose the placement that avoids a new circular import; state your choice in the report.

- [ ] **Step 1: Write the failing tests**

```python
# backend/lumbergh/tests/test_tmux_window_helpers.py
import subprocess

from lumbergh.constants import TMUX_CMD


def _run(*args):
    subprocess.run([TMUX_CMD, *args], check=True, capture_output=True)


def _windows(session):
    out = subprocess.run(
        [TMUX_CMD, "list-windows", "-t", session, "-F", "#{window_name}"],
        capture_output=True, encoding="utf-8",
    )
    return out.stdout.split()


import shutil

import pytest

pytestmark = pytest.mark.skipif(shutil.which(TMUX_CMD) is None, reason="tmux not installed")


@pytest.fixture
def cleanup_sessions():
    made = []
    yield made
    for s in made:
        subprocess.run([TMUX_CMD, "kill-session", "-t", s], capture_output=True)


def test_create_tmux_window_auto_creates_missing_session(tmp_path, cleanup_sessions):
    from lumbergh.tmux_pty import create_tmux_window

    made = cleanup_sessions
    made.append("lbtest-into")
    target = create_tmux_window("lbtest-into", "w1", tmp_path, "true")
    assert target == "lbtest-into:w1"
    assert "w1" in _windows("lbtest-into")


def test_create_tmux_window_adds_to_existing_session(tmp_path, cleanup_sessions):
    from lumbergh.tmux_pty import create_tmux_window

    made = cleanup_sessions
    made.append("lbtest-into2")
    _run("new-session", "-d", "-s", "lbtest-into2", "-n", "first")
    create_tmux_window("lbtest-into2", "w2", tmp_path, "true")
    assert set(_windows("lbtest-into2")) >= {"first", "w2"}


def test_kill_tmux_window_removes_only_that_window(tmp_path, cleanup_sessions):
    from lumbergh.tmux_pty import create_tmux_window, kill_tmux_window

    made = cleanup_sessions
    made.append("lbtest-into3")
    create_tmux_window("lbtest-into3", "keep", tmp_path, "true")
    create_tmux_window("lbtest-into3", "drop", tmp_path, "true")
    assert kill_tmux_window("lbtest-into3:drop") is True
    remaining = _windows("lbtest-into3")
    assert "keep" in remaining and "drop" not in remaining
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_tmux_window_helpers.py -v`
Expected: FAIL — `create_tmux_window` / `kill_tmux_window` don't exist yet.

- [ ] **Step 3: Implement**

Extract the agent-start steps from `create_tmux_session` into a helper that takes an explicit identity target, then add the two functions. Example (adjust placement per the circular-import note):

```python
# routers/sessions.py — factor out of create_tmux_session
def _start_agent_in_target(target: str, workdir: Path, launch_command: str) -> None:
    subprocess.run(
        [TMUX_CMD, "send-keys", "-t", target,
         f"export LUMBERGH_SESSION={shlex.quote(target)}", "Enter"],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    venv_activate = find_venv_activate(workdir)
    if venv_activate:
        subprocess.run(
            [TMUX_CMD, "send-keys", "-t", target, f"source {venv_activate}", "Enter"],
            capture_output=True, encoding="utf-8", errors="replace",
        )
    subprocess.run(
        [TMUX_CMD, "send-keys", "-t", target, launch_command, "Enter"],
        capture_output=True, encoding="utf-8", errors="replace",
    )


def create_tmux_window(session: str, window: str, workdir: Path,
                       launch_command: str = "claude --continue || claude") -> str:
    from lumbergh.tmux_pty import list_tmux_sessions
    live = {s["name"] for s in list_tmux_sessions()}
    if session not in live:
        r = subprocess.run(
            [TMUX_CMD, "new-session", "-d", "-s", session, "-n", window, "-c", str(workdir)],
            capture_output=True, encoding="utf-8", errors="replace",
        )
    else:
        r = subprocess.run(
            [TMUX_CMD, "new-window", "-t", session, "-n", window, "-c", str(workdir)],
            capture_output=True, encoding="utf-8", errors="replace",
        )
    if r.returncode != 0:
        raise RuntimeError(f"Failed to create window {session}:{window}: {r.stderr}")
    target = f"{session}:{window}"
    _start_agent_in_target(target, workdir, launch_command)
    return target
```

`create_tmux_session` keeps its behavior by calling `_start_agent_in_target(name, workdir, launch_command)` in place of the three inlined blocks (verify the resulting behavior is byte-for-byte the same: same env export, same venv step, same launch). Add `kill_tmux_window` to `tmux_pty.py` next to `kill_tmux_session`:

```python
def kill_tmux_window(target: str) -> bool:
    """Kill a single window (session:window), leaving sibling windows alive."""
    try:
        r = subprocess.run(
            [TMUX_CMD, "kill-window", "-t", target],
            capture_output=True, encoding="utf-8", errors="replace", timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False
```

If `create_tmux_window` lives in `sessions.py`, re-export it from `tmux_pty` (or import it in the test from `sessions`) — keep the test's import path matching where it lands; the test above imports from `lumbergh.tmux_pty`, so re-export there if you implement it in `sessions.py`.

- [ ] **Step 4: Run the tests + the existing session-creation regression**

Run: `cd backend && uv run pytest lumbergh/tests/test_tmux_window_helpers.py lumbergh/tests/test_windows_kill.py -v`
Expected: PASS. Also run any test that exercises `create_tmux_session` to confirm the refactor is behavior-preserving.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/tmux_pty.py backend/lumbergh/routers/sessions.py backend/lumbergh/tests/test_tmux_window_helpers.py
git commit -m "feat(tmux): create_tmux_window (auto-create or add) + kill_tmux_window"
```

---

### Task 2: Thread `target` + `run` through `worktrees.create`

**Files:**
- Modify: `backend/lumbergh/worktrees.py` (`create(...)` — add params, pass to `record_worktree`)
- Test: `backend/lumbergh/tests/test_worktrees.py`

**Interfaces:**
- Consumes: `record_worktree(..., target=, run=, session=)` (Phase 1).
- Produces: `worktrees.create(..., target: str | None = None, run: str | None = None)` — passes both to `record_worktree`. When `target` is None it falls back to `session` (same rule `record_worktree` already uses), so existing callers are unaffected.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/lumbergh/tests/test_worktrees.py  (uses the existing registry/tmp fixtures)
def test_create_threads_target_and_run(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMBERGH_DATA_DIR", str(tmp_path / "cfg"))
    repo = _init_git_repo(tmp_path / "repo")  # reuse this file's existing repo-init helper
    created = worktrees.create(
        repo, "feat/z", created_at="2026-07-30T00:00:00Z",
        create_branch=True, target="port:fleet-644", run="batch-9",
    )
    entry = worktrees.get_entry(Path(created["path"]))
    assert entry["target"] == "port:fleet-644"
    assert entry["run"] == "batch-9"
```

> Use whatever git-repo-init helper `test_worktrees.py` already defines (e.g. an existing fixture/function that creates a git repo under tmp_path); match the file's conventions rather than adding a new one.

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktrees.py -k "threads_target_and_run" -v`
Expected: FAIL — `create()` has no `target`/`run` params.

- [ ] **Step 3: Implement**

Add `target: str | None = None` and `run: str | None = None` to `create(...)`'s keyword-only params, and in its `record_worktree(...)` call pass `target=target, run=run` alongside the existing `session=session`.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktrees.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/worktrees.py backend/lumbergh/tests/test_worktrees.py
git commit -m "feat(worktrees): thread target + run through create()"
```

---

### Task 3: Reap/teardown kills the window for a window target

**Files:**
- Modify: `backend/lumbergh/routers/worktrees.py:74-83` (`reap`)
- Test: `backend/lumbergh/tests/test_worktree_router.py`

**Interfaces:**
- Consumes: `targets.parse_target` (Phase 1), `tmux_pty.kill_tmux_window` (Task 1), `tmux_pty.kill_tmux_session` (existing).
- Produces: `reap` resolves the worker as `entry.get("target") or entry.get("associated_session")`; if `parse_target(worker)[1]` is not None (a window part exists) it calls `kill_tmux_window(worker)`, else `kill_tmux_session(worker)` — only on a `status == "removed"` result, unchanged otherwise.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/lumbergh/tests/test_worktree_router.py
def test_reap_of_window_target_kills_window_not_session(monkeypatch, tmp_path):
    killed = {}
    monkeypatch.setattr(
        "lumbergh.routers.worktrees.worktrees.get_entry",
        lambda p: {"target": "port:fleet-644", "associated_session": "port:fleet-644"},
    )
    monkeypatch.setattr(
        "lumbergh.routers.worktrees.worktrees.reap",
        lambda p, force, rm_branch: {"status": "removed"},
    )
    monkeypatch.setattr(
        "lumbergh.routers.worktrees.kill_tmux_window",
        lambda t: killed.setdefault("window", t) or True,
    )
    monkeypatch.setattr(
        "lumbergh.routers.worktrees.kill_tmux_session",
        lambda t: killed.setdefault("session", t) or True,
    )
    from lumbergh.routers.worktrees import reap, ReapBody
    reap(ReapBody(path=str(tmp_path / "wt")))
    assert killed == {"window": "port:fleet-644"}  # session kill NOT called


def test_reap_of_bare_target_still_kills_session(monkeypatch, tmp_path):
    killed = {}
    monkeypatch.setattr(
        "lumbergh.routers.worktrees.worktrees.get_entry",
        lambda p: {"target": "scout-1", "associated_session": "scout-1"},
    )
    monkeypatch.setattr(
        "lumbergh.routers.worktrees.worktrees.reap",
        lambda p, force, rm_branch: {"status": "removed"},
    )
    monkeypatch.setattr(
        "lumbergh.routers.worktrees.kill_tmux_window",
        lambda t: killed.setdefault("window", t) or True,
    )
    monkeypatch.setattr(
        "lumbergh.routers.worktrees.kill_tmux_session",
        lambda t: killed.setdefault("session", t) or True,
    )
    from lumbergh.routers.worktrees import reap, ReapBody
    reap(ReapBody(path=str(tmp_path / "wt")))
    assert killed == {"session": "scout-1"}
```

> Confirm `ReapBody` is importable from `lumbergh.routers.worktrees`; if the module constructs it differently, call the endpoint the way the file's existing tests do.

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktree_router.py -k "reap_of_window or reap_of_bare" -v`
Expected: FAIL — reap currently always calls `kill_tmux_session(entry.get("associated_session"))`, so the window test sees `session` killed with a colon name.

- [ ] **Step 3: Implement**

Add `from lumbergh.tmux_pty import kill_tmux_window` and `from lumbergh.targets import parse_target` to `routers/worktrees.py`, and change `reap`:

```python
    entry = worktrees.get_entry(path) or {}
    worker = entry.get("target") or entry.get("associated_session")
    result = worktrees.reap(path, force=body.force, rm_branch=body.rm_branch)
    if result.get("status") == "removed" and worker:
        if parse_target(worker)[1] is not None:
            kill_tmux_window(worker)
        else:
            kill_tmux_session(worker)
    return result
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktree_router.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/routers/worktrees.py backend/lumbergh/tests/test_worktree_router.py
git commit -m "feat(worktrees): reap kills the window for a session:window target"
```

---

### Task 4: `session_meta` resolves a window target from the registry

**Files:**
- Modify: `backend/lumbergh/activity/resolve.py:10-18` (`session_meta`)
- Test: `backend/lumbergh/tests/test_adapter_resolve.py`

**Interfaces:**
- Consumes: `worktrees.all_entries()` (existing).
- Produces: `session_meta(name)` returns the session-store entry when present (unchanged); otherwise, if a worktree registry row has `target == name`, returns `{"workdir": <row path>, "agent_provider": None}`; else `{}`. This makes `resolve_adapter(target, cwd, provider)` and `_outcome_of(target)` work for window workers (which are intentionally NOT in the session store).

- [ ] **Step 1: Write the failing test**

```python
# add to backend/lumbergh/tests/test_adapter_resolve.py
def test_session_meta_falls_back_to_worktree_registry_for_window_target(monkeypatch):
    from lumbergh.activity.resolve import session_meta

    monkeypatch.setattr("lumbergh.routers.sessions.get_stored_sessions", lambda: {})
    monkeypatch.setattr(
        "lumbergh.worktrees.all_entries",
        lambda: [{"target": "port:fleet-644", "path": "/wt/644"}],
    )
    meta = session_meta("port:fleet-644")
    assert meta["workdir"] == "/wt/644"


def test_session_meta_prefers_session_store_when_present(monkeypatch):
    from lumbergh.activity.resolve import session_meta

    monkeypatch.setattr(
        "lumbergh.routers.sessions.get_stored_sessions",
        lambda: {"scout-1": {"workdir": "/live/scout", "agent_provider": "pi"}},
    )
    meta = session_meta("scout-1")
    assert meta["workdir"] == "/live/scout" and meta["agent_provider"] == "pi"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_adapter_resolve.py -k "session_meta" -v`
Expected: FAIL — the first test gets `{}` (no registry fallback yet).

- [ ] **Step 3: Implement**

```python
def session_meta(name: str) -> dict:
    from lumbergh.routers.sessions import get_stored_sessions

    stored = get_stored_sessions().get(name, {})
    if stored:
        return stored
    from lumbergh import worktrees

    for row in worktrees.all_entries():
        if row.get("target") == name and row.get("path"):
            return {"workdir": row["path"], "agent_provider": None}
    return {}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest lumbergh/tests/test_adapter_resolve.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/activity/resolve.py backend/lumbergh/tests/test_adapter_resolve.py
git commit -m "feat(resolve): session_meta falls back to worktree registry for window targets"
```

---

### Task 5: Spawn endpoint accepts `--into` / `--run`

**Files:**
- Modify: `backend/lumbergh/routers/bill.py` — `SpawnBody` (360-369), `_checked_request` (498-536), `spawn` (539+), `_unwind`/`_unwind_and_fail` (417-459)
- Test: `backend/lumbergh/tests/test_bill_router.py`

**Interfaces:**
- Consumes: `create_tmux_window` (Task 1), `worktrees.create(target=, run=)` (Task 2), `deliver_when_ready` (existing — targets any pane by its target string), `targets.format_target` (Phase 1), `tmux_pty.list_session_windows` (Phase 1).
- Produces: `SpawnBody` gains `into: str | None = None` and `run: str | None = None`. `spawn()` returns the same shape but with `session` set to the **target** (`S:window` for window workers). The response's `session` field is the addressable target the caller drives with `lb read/prompt --session <that>`.

**Behavior branches (bare vs into):**
- **name/collision:** if `into` is set, the worker's window name is `body.name or _derive_name(body.branch, set(list_session_windows(into)))`, and the collision check is against that session's windows — the session already existing is NOT a conflict (auto-create). If `into` is None, keep today's behavior (derive against live sessions; a live same-name session is a conflict).
- **container:** `into` → `target = create_tmux_window(into, window_name, workdir, launch)`; else `create_tmux_session(name, workdir, launch)` and `target = name`.
- **session store:** call `_store_session(...)` only for bare spawns. Window workers are intentionally absent from the store (they resolve via the registry, Task 4) and are visible via discovery + the fleet board.
- **unwind:** on a failure after the container exists, kill the window for a window target (`kill_tmux_window(target)`) and the session for a bare target. Thread the target into `_unwind`.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/lumbergh/tests/test_bill_router.py
def test_spawn_into_creates_window_worker(monkeypatch, tmp_path):
    from lumbergh.routers import bill

    (tmp_path / "repo" / ".git").mkdir(parents=True)
    brief = tmp_path / "brief.md"; brief.write_text("do the thing")

    monkeypatch.setattr(bill, "_resolve_brief", lambda p: brief)
    monkeypatch.setattr(
        "lumbergh.routers.bill.get_live_sessions"
        if hasattr(bill, "get_live_sessions") else "lumbergh.routers.sessions.get_live_sessions",
        lambda: {}, raising=False,
    )
    monkeypatch.setattr("lumbergh.routers.bill.list_session_windows", lambda s: [], raising=False)
    monkeypatch.setattr(
        "lumbergh.routers.bill.worktrees.create",
        lambda *a, **k: {"path": str(tmp_path / "wt")} | ({"target": k.get("target"), "run": k.get("run")}),
    )
    captured = {}
    def fake_window(session, window, workdir, launch_command="x"):
        captured["target"] = f"{session}:{window}"
        return f"{session}:{window}"
    monkeypatch.setattr("lumbergh.routers.bill.create_tmux_window", fake_window, raising=False)
    monkeypatch.setattr("lumbergh.routers.bill._deliver_brief", lambda *a, **k: type("D", (), {"ok": True})())
    stored = {}
    monkeypatch.setattr("lumbergh.routers.bill._store_session", lambda **k: stored.update(k))

    body = bill.SpawnBody(
        repo=str(tmp_path / "repo"), branch="kb-644", kind="ship",
        brief_path=str(brief), name="fleet-644", into="port", run="batch-9",
    )
    resp = bill.spawn(body)
    assert resp["session"] == "port:fleet-644"
    assert captured["target"] == "port:fleet-644"
    assert stored == {}  # window workers are NOT written to the session store
```

> The exact monkeypatch target paths depend on how `bill.py` imports these names (module-level `from … import create_tmux_window` vs qualified). READ `bill.py`'s imports first and set the patch paths to match; the `raising=False` guards above are a hint, not a license to patch a non-existent attribute — fix the path instead. Keep the assertions (target shape, no store write) intact.

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_bill_router.py -k "spawn_into" -v`
Expected: FAIL — `SpawnBody` has no `into`/`run`; `spawn` always creates a session and always stores.

- [ ] **Step 3: Implement**

1. Add `into: str | None = None` and `run: str | None = None` to `SpawnBody`.
2. Import `create_tmux_window` and `list_session_windows` at the top of `bill.py` (matching the style of the existing `create_tmux_session` import).
3. In `_checked_request`, branch the name/collision logic on `body.into` as described (window-name collision within the session for `into`; live-session collision for bare). Return the resolved worker name (window name or session name) plus brief/repo.
4. In `spawn()`:
   - call `worktrees.create(..., target=<computed target>, run=body.run, session=<name-or-None>)`. Compute `target` as `format_target(body.into, window_name)` when `into` else `name`.
   - branch container creation (`create_tmux_window` vs `create_tmux_session`), capturing `target`.
   - call `_store_session(...)` only when `body.into` is None.
   - deliver the brief to `target` (pass `target` where `name` was passed to `_deliver_brief`/`deliver_when_ready`).
   - on failure paths, thread `target` into `_unwind` and have `_unwind` kill window vs session via `parse_target`.
   - return `{"session": target, "kind": ..., "branch": ..., "path": ...}`.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest lumbergh/tests/test_bill_router.py -v`
Expected: PASS (new test + all existing bill-router tests, including the bare-spawn path, still green).

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/routers/bill.py backend/lumbergh/tests/test_bill_router.py
git commit -m "feat(bill): spawn --into places a worktree worker in a session window"
```

---

### Task 6: `lb spawn --into / --run` CLI flags

**Files:**
- Modify: `backend/lumbergh/agent_cli/spawn.py`
- Modify: `backend/lumbergh/agent_cli/main.py` (the `spawn` entry in `_COMMAND_HELP`)
- Test: `backend/lumbergh/tests/test_lb_spawn_cli.py`

**Interfaces:**
- Consumes: the `/api/bill/spawn` body shape (Task 5).
- Produces: `lb spawn … [--into <session>] [--run <id>]` sends `into` and `run` in the POST body; help text documents them. When `--into` is used, the printed result's `session` is the `session:window` target.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/lumbergh/tests/test_lb_spawn_cli.py
def test_spawn_cli_sends_into_and_run(monkeypatch):
    from lumbergh.agent_cli import spawn

    sent = {}
    def fake_request(method, path, json=None, **k):
        sent["json"] = json
        class R:
            status_code = 200
            def json(self):
                return {"session": "port:fleet-644", "kind": "ship",
                        "branch": "kb-644", "path": "/wt/644"}
        return R()
    monkeypatch.setattr(spawn, "_request", fake_request)

    rc = spawn.run({
        "--repo": "/repo/port", "--branch": "kb-644", "--kind": "ship",
        "--brief": "briefs/x.md", "--into": "port", "--run": "batch-9",
    })
    assert rc == 0
    assert sent["json"]["into"] == "port"
    assert sent["json"]["run"] == "batch-9"
```

> Match how `test_lb_spawn_cli.py` already stubs `_request` (import path / class shape); mirror the existing test's pattern rather than the sketch above if they differ.

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_lb_spawn_cli.py -k "into_and_run" -v`
Expected: FAIL — `spawn.run` doesn't put `into`/`run` in the body.

- [ ] **Step 3: Implement**

In `spawn.py`'s `run`, add to the POST `body`:

```python
        "into": flags.get("--into"),
        "run": flags.get("--run"),
```

Update the `spawn` help string in `main.py`'s `_COMMAND_HELP` to include `[--into <session>] [--run <id>]` and a one-line note that `--into` places the worker in a window of `<session>` (auto-creating it if needed), tagging it with `--run`.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest lumbergh/tests/test_lb_spawn_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/agent_cli/spawn.py backend/lumbergh/agent_cli/main.py backend/lumbergh/tests/test_lb_spawn_cli.py
git commit -m "feat(lb): spawn --into / --run flags"
```

---

### Task 7: End-to-end — two window workers, reap-safe

Real-tmux reproduction that a batch of window workers is spawnable, individually visible, and reap-isolated — the Phase 2 regression guard. Uses the backend spawn endpoint (or `create_tmux_window` + `worktrees.create` directly if driving the full HTTP spawn in-test is impractical — prefer the endpoint if a test harness for it already exists in `test_bill_router.py`, else compose the primitives).

**Files:**
- Create: `backend/lumbergh/tests/test_spawn_into_integration.py`

**Interfaces:**
- Consumes: real `tmux`, `create_tmux_window` (Task 1), `discover_live_targets` (Phase 1), `kill_tmux_window` (Task 1).

- [ ] **Step 1: Write the test**

```python
# backend/lumbergh/tests/test_spawn_into_integration.py
import shutil
import subprocess

import pytest

from lumbergh.constants import TMUX_CMD

pytestmark = pytest.mark.skipif(shutil.which(TMUX_CMD) is None, reason="tmux not installed")

_MARKER = "╭─ Claude Code ─╮"


@pytest.fixture
def session_name():
    name = "lbtest-batch"
    subprocess.run([TMUX_CMD, "kill-session", "-t", name], capture_output=True)
    yield name
    subprocess.run([TMUX_CMD, "kill-session", "-t", name], capture_output=True)


def test_two_window_workers_visible_and_reap_isolated(tmp_path, session_name):
    from lumbergh.idle_monitor import discover_live_targets
    from lumbergh.tmux_pty import create_tmux_window, kill_tmux_window

    launch = f"printf %s '{_MARKER}'; sleep 300"
    create_tmux_window(session_name, "fleet-643", tmp_path, launch)
    create_tmux_window(session_name, "fleet-644", tmp_path, launch)

    targets = discover_live_targets()
    assert f"{session_name}:fleet-643" in targets
    assert f"{session_name}:fleet-644" in targets

    assert kill_tmux_window(f"{session_name}:fleet-644") is True
    remaining = discover_live_targets()
    assert f"{session_name}:fleet-643" in remaining          # sibling survives
    assert f"{session_name}:fleet-644" not in remaining      # only the reaped one is gone
```

- [ ] **Step 2: Run — must pass on Tasks 1 + Phase 1**

Run: `cd backend && uv run pytest lumbergh/tests/test_spawn_into_integration.py -v`
Expected: PASS. If the marker doesn't survive into the captured pane (agent detection), inspect `capture_pane_text(target)` and adjust the launch command so the marker is visible — do NOT weaken the assertions.

- [ ] **Step 3: Commit**

```bash
git add backend/lumbergh/tests/test_spawn_into_integration.py
git commit -m "test(e2e): batch window workers are visible and reap-isolated"
```

---

### Task 8: Lint, full suite, wrap-up

**Files:** none (verification).

- [ ] **Step 1: Full backend suite** — `cd backend && uv run pytest -q` → all pass.
- [ ] **Step 2: Backend lint** — from the worktree root run `./lint.sh`; if it insists on the failing frontend step, run `cd backend && uv run ruff check . && uv run ruff format --check .` → clean. Fix only backend lint errors in files this phase touched (rename unused lambda/fixture args to `_name` or use `@pytest.mark.usefixtures`; never delete a side-effect fixture param — see the Phase 1 postmortem).
- [ ] **Step 3: Manual smoke (recommended)** — with the backend running: `lb spawn --repo <p> --branch b1 --kind scout --brief <f> --into demo --run r1`, then again with `--branch b2 --into demo --run r1`; confirm `lb` shows `demo:<w1>` and `demo:<w2>` as distinct rows, both `lb read`-able, then `lb worktree reap` one and confirm the other survives. Confirm a plain `lb spawn` (no `--into`) still makes its own session.
- [ ] **Step 4: Commit any lint fixups** — `chore: lint fixups for unified spawn`.

---

## Self-Review

**Spec coverage (Phase 2 = "Unified spawn — `--into`/`--run`, one spawn primitive"):**
- One spawn primitive, destination branch (new session vs window) → Tasks 1, 5. ✓
- `--into` auto-creates the session then adds a window → Task 1 (`create_tmux_window`), Task 5 (collision/auto-create logic). ✓
- Registry records `target` + `run` → Task 2 (thread through `create`), Task 5 (spawn passes them). ✓
- Both paths deliver the brief the same way → Task 5 (deliver to `target`). ✓
- `lb spawn` gains `--into/--run` → Task 6. ✓
- **Carry-over (prerequisite): reap kills the window not the session** → Task 3. ✓
- **Carry-over (prerequisite): per-window transcript/outcome resolution** → Task 4 (registry fallback) + Task 1 (`LUMBERGH_SESSION=session:window` identity). ✓
- Regression guard (real tmux, reap-isolated) → Task 7. ✓
- Out of scope (later phases): `batch`/`land`/`teardown` verbs (Phase 3); Redis removal + fleet retirement (Phase 4); dropping the legacy `associated_session` mirror (Phase 4 cleanup).

**Placeholder scan:** No TBD/TODO. The "read the imports/fixtures first and match the patch path" notes (Tasks 5, 6, 3, 2) are verification instructions — the change itself is fully specified; only the monkeypatch string must match the module's actual import style.

**Type consistency:** `create_tmux_window(session, window, workdir, launch_command) -> str` returns the `session:window` target used identically by Task 5 and Task 7. `kill_tmux_window(target) -> bool` matches Task 3 and Task 7. `worktrees.create(..., target=, run=)` (Task 2) matches Task 5's call. `session_meta(name) -> dict` keeps its signature (Task 4). `SpawnBody.into/run` (Task 5) matches the CLI body keys (Task 6). The spawn response's `session` field carries the target string throughout.

**Known follow-on (Phase 3/4):** `lb batch --into S --run r` becomes a thin loop over this spawn; `lb teardown --run r` reuses Task 3's window-aware kill across a run group. Note the `associated_session` mirror removal when writing the Phase 4 plan.
