# Bill — First-Mate Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Bill — a global, code-free orchestrator session that dispatches worker sessions into isolated worktrees, supervises them by long-polling the server, and reports outcomes to the user.

**Architecture:** Bill is an ordinary Lumbergh session whose workdir is a materialized instruction bundle at `~/.config/lumbergh/bill/`. Task state lives in the existing worktree registry (extended with `kind` and `origin`), never in Bill's home — so a weak local model has no bookkeeping to forget. Bill's entire vocabulary is three `lb` commands: `lb spawn`, `lb fleet [--wait]`, and the existing `lb worktree reap`. Every command fails closed with an actionable message.

**Tech Stack:** Python 3.11+, FastAPI, TinyDB, pytest (backend); React + TypeScript + Tailwind (frontend); libtmux/tmux for sessions.

**Spec:** `docs/superpowers/specs/2026-07-28-bill-orchestrator-design.md`

## Global Constraints

- Line length 100, target `py311`. Run `./lint.sh` before finishing any task; fix all errors.
- Backend tests: `cd backend && uv run pytest`. Never use bare `pip`/`pipx`.
- Comments: prefer expressive naming/structure over commentary. No `# Arrange/# Act/# Assert`, no comments restating a good name. A comment is justified only for a non-obvious external-schema fact or deliberate cleverness.
- Red-green-refactor: write the failing test, run it, verify it fails, then implement.
- Conventional-commit messages. No `Co-Authored-By` or AI-attribution lines.
- Personality affects only user-facing chat text — never briefs, commits, or PR text.
- Bill never writes project code, never merges, never invents an answer, never reaps unlanded work.
- Registry field values are exactly `kind` ∈ {`"ship"`, `"scout"`, `None`} and `origin` ∈ {`"bill"`, `None`}.
- Settings key is exactly `bill.personality` ∈ {`"professional"`, `"lumbergh"`}, default `"professional"`.
- Bill's session name is exactly `bill`; his workdir is exactly `~/.config/lumbergh/bill/` (respecting `LUMBERGH_DATA_DIR` via `constants.CONFIG_DIR`).
- Task identity **is** the session name. Brief = `briefs/<session>.md`, report = `reports/<session>.md`.

## File Structure

**Create:**
- `backend/lumbergh/bill/__init__.py` — bundle materialization: render `AGENTS.md`, create-if-missing `preferences.md`/`briefs/`/`reports/`.
- `backend/lumbergh/bill/AGENTS.md.template` — the bundle body with a `{{PERSONALITY}}` placeholder.
- `backend/lumbergh/bill/personality_professional.md` — default preamble.
- `backend/lumbergh/bill/personality_lumbergh.md` — opt-in flair preamble.
- `backend/lumbergh/bill/preferences_seed.md` — initial `preferences.md` content (written once).
- `backend/lumbergh/fleet.py` — cross-repo fleet reconciliation, wake-condition predicate, outcome-line parsing.
- `backend/lumbergh/routers/bill.py` — `POST /api/bill/summon`, `GET /api/bill/fleet`, `GET /api/bill/fleet/wait`, `POST /api/bill/spawn`.
- `backend/lumbergh/agent_cli/fleet.py` — `lb fleet` CLI.
- `backend/lumbergh/agent_cli/spawn.py` — `lb spawn` CLI.
- `backend/lumbergh/tests/test_bill_bundle.py`
- `backend/lumbergh/tests/test_fleet.py`
- `backend/lumbergh/tests/test_bill_router.py`
- `backend/lumbergh/tests/test_lb_fleet_cli.py`
- `backend/lumbergh/tests/test_lb_spawn_cli.py`
- `test/e2e/test_bill_e2e.py`

**Modify:**
- `backend/lumbergh/worktrees.py` — add `kind`/`origin` to `record_worktree`; add `set_task_fields`.
- `backend/lumbergh/main.py:174` — register the bill router.
- `backend/lumbergh/agent_cli/main.py` — register `fleet` and `spawn` commands + flags.
- `backend/lumbergh/skill/SKILL.md` — document the new commands.
- `backend/lumbergh/idle_monitor.py` — idle-Bill nudge backstop.
- `frontend/src/pages/Dashboard.tsx` — Summon Bill button.

Why this split: `fleet.py` is pure reconciliation logic (no HTTP, no CLI) so it is unit-testable without a server; `routers/bill.py` is the only place that blocks on asyncio; the CLI modules mirror the existing `agent_cli/worktree.py` pattern exactly.

---

### Task 1: Registry gains `kind` and `origin`

**Files:**
- Modify: `backend/lumbergh/worktrees.py:143-163` (`record_worktree`)
- Test: `backend/lumbergh/tests/test_worktrees.py` (append; create the file if absent)

**Interfaces:**
- Consumes: existing `worktrees.record_worktree`, `worktrees.get_entry`, `worktrees.all_entries`.
- Produces:
  - `record_worktree(path, parent_repo, branch, created_at, session=None, links_applied=None, task_intent=None, kind=None, origin=None) -> dict` — row now also carries `"kind"` and `"origin"`.
  - `set_task_fields(path: Path, *, kind: str | None = None, origin: str | None = None) -> dict | None` — patches an existing row, returns the updated row or `None` when the path is unknown.

- [ ] **Step 1: Write the failing tests**

Create or append to `backend/lumbergh/tests/test_worktrees.py`:

```python
from pathlib import Path

import pytest

from lumbergh import worktrees


@pytest.fixture
def registry(tmp_path, monkeypatch):
    from tinydb import TinyDB

    db = TinyDB(tmp_path / "worktrees.json")
    monkeypatch.setattr(worktrees, "get_worktrees_db", lambda: db)
    yield db
    db.close()


def test_record_worktree_persists_kind_and_origin(registry, tmp_path):
    row = worktrees.record_worktree(
        tmp_path / "wt",
        tmp_path / "repo",
        "feat/x",
        "2026-07-28T00:00:00+00:00",
        kind="scout",
        origin="bill",
    )
    assert row["kind"] == "scout"
    assert row["origin"] == "bill"
    assert worktrees.get_entry(tmp_path / "wt")["kind"] == "scout"


def test_record_worktree_defaults_kind_and_origin_to_none(registry, tmp_path):
    row = worktrees.record_worktree(
        tmp_path / "wt", tmp_path / "repo", "feat/x", "2026-07-28T00:00:00+00:00"
    )
    assert row["kind"] is None
    assert row["origin"] is None


def test_set_task_fields_patches_existing_row(registry, tmp_path):
    worktrees.record_worktree(
        tmp_path / "wt", tmp_path / "repo", "feat/x", "2026-07-28T00:00:00+00:00"
    )
    updated = worktrees.set_task_fields(tmp_path / "wt", kind="ship", origin="bill")
    assert updated["kind"] == "ship"
    assert worktrees.get_entry(tmp_path / "wt")["origin"] == "bill"


def test_set_task_fields_returns_none_for_unknown_path(registry, tmp_path):
    assert worktrees.set_task_fields(tmp_path / "nope", kind="ship") is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktrees.py -v`
Expected: FAIL — `record_worktree() got an unexpected keyword argument 'kind'` and `AttributeError: module 'lumbergh.worktrees' has no attribute 'set_task_fields'`.

- [ ] **Step 3: Implement**

In `backend/lumbergh/worktrees.py`, extend `record_worktree`'s signature and row, then add `set_task_fields` directly after `get_entry`:

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
) -> dict:
    row = {
        "path": _key(path),
        "parent_repo": str(Path(parent_repo).resolve()),
        "branch": branch,
        "created_at": created_at,
        "associated_session": session,
        "links_applied": links_applied or [],
        "task_intent": task_intent,
        "kind": kind,
        "origin": origin,
    }
    db = get_worktrees_db()
    db.upsert(row, Query().path == row["path"])
    return row


def set_task_fields(path: Path, *, kind: str | None = None, origin: str | None = None) -> dict | None:
    entry = get_entry(path)
    if entry is None:
        return None
    patch = {k: v for k, v in (("kind", kind), ("origin", origin)) if v is not None}
    if patch:
        get_worktrees_db().update(patch, Query().path == _key(path))
    return get_entry(path)
```

Also thread the two new arguments through `worktrees.create()` (it calls `record_worktree` near its end) by adding `kind: str | None = None, origin: str | None = None` to `create`'s keyword-only parameters and passing them into the `record_worktree` call.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktrees.py -v`
Expected: PASS (4 tests).

Also confirm nothing regressed: `cd backend && uv run pytest lumbergh/tests/test_lb_worktree_cli.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/worktrees.py backend/lumbergh/tests/test_worktrees.py
git commit -m "feat(bill): registry records task kind and origin"
```

---

### Task 2: Cross-repo fleet reconciliation

**Files:**
- Create: `backend/lumbergh/fleet.py`
- Test: `backend/lumbergh/tests/test_fleet.py`

**Interfaces:**
- Consumes: `worktrees.reconcile_all(live_sessions)` (already exists, `worktrees.py:232` — walks the distinct `parent_repo` values in the registry and returns the flattened per-repo rows, each with `path`/`repo`/`branch`/`session`/`agent`/`state` where state ∈ {`active`, `orphan`}), `worktrees.get_entry(path)`.

**Corrected during execution:** an earlier draft of this task had `snapshot()` build its own `_repos()` helper and loop over `worktrees.reconcile(repo, ...)`. That duplicated `reconcile_all`, which sub-project A already shipped. Use `reconcile_all` directly.
- Produces:
  - `snapshot(live_sessions: dict[str, dict], state_of, since_of, unseen_of, origin: str | None = None) -> list[dict]` — one row per worktree across every repo in the registry. Row keys: `task`, `repo`, `branch`, `session`, `kind`, `state`, `since`, `unseen`, `path`.
  - `needs_attention(row: dict) -> bool` — True when `state` ∈ {`blocked`, `error`, `dead`} or (`state == "idle"` and `unseen`).
  - `any_needs_attention(rows: list[dict]) -> bool`
  - `parse_outcome(text: str) -> str | None` — pulls the worker's final `DELIVERED: ...` / `FAILED: ...` line out of a transcript blob, so Bill reads an outcome instead of inferring one from prose. Returns the last such line, or `None`.

`state_of`, `since_of`, `unseen_of` are injected callables taking a session name — this is what makes the module testable without a live monitor.

- [ ] **Step 1: Write the failing tests**

Create `backend/lumbergh/tests/test_fleet.py`:

```python
from pathlib import Path

import pytest

from lumbergh import fleet, worktrees


@pytest.fixture
def registry(tmp_path, monkeypatch):
    from tinydb import TinyDB

    db = TinyDB(tmp_path / "worktrees.json")
    monkeypatch.setattr(worktrees, "get_worktrees_db", lambda: db)
    yield db
    db.close()


def _fake_reconcile(rows_by_repo):
    def reconcile(repo, live_sessions):  # noqa: ARG001
        return rows_by_repo.get(str(repo), [])

    return reconcile


def test_snapshot_spans_every_repo_in_the_registry(registry, tmp_path, monkeypatch):
    worktrees.record_worktree(
        tmp_path / "a-wt", tmp_path / "a", "feat/a", "t", session="w-a", kind="ship", origin="bill"
    )
    worktrees.record_worktree(
        tmp_path / "b-wt", tmp_path / "b", "feat/b", "t", session="w-b", kind="scout", origin="bill"
    )
    monkeypatch.setattr(
        worktrees,
        "reconcile",
        _fake_reconcile(
            {
                str((tmp_path / "a").resolve()): [
                    {
                        "path": str((tmp_path / "a-wt").resolve()),
                        "repo": "a",
                        "branch": "feat/a",
                        "session": "w-a",
                        "agent": "claude-code",
                        "state": "active",
                    }
                ],
                str((tmp_path / "b").resolve()): [
                    {
                        "path": str((tmp_path / "b-wt").resolve()),
                        "repo": "b",
                        "branch": "feat/b",
                        "session": "w-b",
                        "agent": "claude-code",
                        "state": "active",
                    }
                ],
            }
        ),
    )
    rows = fleet.snapshot(
        {"w-a": {}, "w-b": {}},
        state_of=lambda n: "working",  # noqa: ARG005
        since_of=lambda n: 12.0,  # noqa: ARG005
        unseen_of=lambda n: False,  # noqa: ARG005
    )
    assert {r["task"] for r in rows} == {"w-a", "w-b"}
    assert {r["kind"] for r in rows} == {"ship", "scout"}


def test_snapshot_marks_a_registry_row_with_a_dead_session(registry, tmp_path, monkeypatch):
    worktrees.record_worktree(
        tmp_path / "a-wt", tmp_path / "a", "feat/a", "t", session="w-a", kind="ship", origin="bill"
    )
    monkeypatch.setattr(
        worktrees,
        "reconcile",
        _fake_reconcile(
            {
                str((tmp_path / "a").resolve()): [
                    {
                        "path": str((tmp_path / "a-wt").resolve()),
                        "repo": "a",
                        "branch": "feat/a",
                        "session": None,
                        "agent": None,
                        "state": "orphan",
                    }
                ]
            }
        ),
    )
    rows = fleet.snapshot(
        {},
        state_of=lambda n: "idle",  # noqa: ARG005
        since_of=lambda n: 0.0,  # noqa: ARG005
        unseen_of=lambda n: False,  # noqa: ARG005
    )
    assert rows[0]["state"] == "dead"
    assert rows[0]["task"] == "w-a"


def test_snapshot_uses_live_state_for_an_active_session(registry, tmp_path, monkeypatch):
    worktrees.record_worktree(
        tmp_path / "a-wt", tmp_path / "a", "feat/a", "t", session="w-a", kind="ship", origin="bill"
    )
    monkeypatch.setattr(
        worktrees,
        "reconcile",
        _fake_reconcile(
            {
                str((tmp_path / "a").resolve()): [
                    {
                        "path": str((tmp_path / "a-wt").resolve()),
                        "repo": "a",
                        "branch": "feat/a",
                        "session": "w-a",
                        "agent": "pi",
                        "state": "active",
                    }
                ]
            }
        ),
    )
    rows = fleet.snapshot(
        {"w-a": {}},
        state_of=lambda n: "blocked",  # noqa: ARG005
        since_of=lambda n: 41.6,  # noqa: ARG005
        unseen_of=lambda n: True,  # noqa: ARG005
    )
    assert rows[0]["state"] == "blocked"
    assert rows[0]["since"] == 42
    assert rows[0]["unseen"] is True


def test_snapshot_filters_by_origin(registry, tmp_path, monkeypatch):
    worktrees.record_worktree(
        tmp_path / "a-wt", tmp_path / "a", "feat/a", "t", session="w-a", origin="bill"
    )
    worktrees.record_worktree(tmp_path / "h-wt", tmp_path / "a", "feat/h", "t", session="w-h")
    monkeypatch.setattr(
        worktrees,
        "reconcile",
        _fake_reconcile(
            {
                str((tmp_path / "a").resolve()): [
                    {
                        "path": str((tmp_path / "a-wt").resolve()),
                        "repo": "a",
                        "branch": "feat/a",
                        "session": "w-a",
                        "agent": "pi",
                        "state": "active",
                    },
                    {
                        "path": str((tmp_path / "h-wt").resolve()),
                        "repo": "a",
                        "branch": "feat/h",
                        "session": "w-h",
                        "agent": "pi",
                        "state": "active",
                    },
                ]
            }
        ),
    )
    rows = fleet.snapshot(
        {"w-a": {}, "w-h": {}},
        state_of=lambda n: "working",  # noqa: ARG005
        since_of=lambda n: 1.0,  # noqa: ARG005
        unseen_of=lambda n: False,  # noqa: ARG005
        origin="bill",
    )
    assert [r["task"] for r in rows] == ["w-a"]


@pytest.mark.parametrize(
    ("state", "unseen", "expected"),
    [
        ("blocked", False, True),
        ("error", False, True),
        ("dead", False, True),
        ("idle", True, True),
        ("idle", False, False),
        ("working", False, False),
        ("working", True, False),
    ],
)
def test_needs_attention(state, unseen, expected):
    assert fleet.needs_attention({"state": state, "unseen": unseen}) is expected


def test_any_needs_attention():
    calm = [{"state": "working", "unseen": False}]
    assert fleet.any_needs_attention(calm) is False
    assert fleet.any_needs_attention([*calm, {"state": "blocked", "unseen": False}]) is True


def test_parse_outcome_finds_a_delivered_line():
    text = "ran the tests\nall green\nDELIVERED: https://github.com/o/r/pull/42"
    assert fleet.parse_outcome(text) == "DELIVERED: https://github.com/o/r/pull/42"


def test_parse_outcome_finds_a_failed_line():
    assert fleet.parse_outcome("tried it\nFAILED: the migration needs a decision") == (
        "FAILED: the migration needs a decision"
    )


def test_parse_outcome_takes_the_last_line_when_a_worker_repeats_itself():
    text = "DELIVERED: branch-one\nactually, one more fix\nDELIVERED: branch-two"
    assert fleet.parse_outcome(text) == "DELIVERED: branch-two"


def test_parse_outcome_ignores_a_mention_inside_prose():
    assert fleet.parse_outcome("I will end with DELIVERED: <url> when I finish") is None


def test_parse_outcome_returns_none_without_an_outcome_line():
    assert fleet.parse_outcome("still working on it") is None
    assert fleet.parse_outcome("") is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_fleet.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lumbergh.fleet'`.

- [ ] **Step 3: Implement**

Create `backend/lumbergh/fleet.py`:

```python
"""Cross-repo fleet view: every tracked worktree as one task row.

``worktrees.reconcile`` answers per-repo; a global orchestrator needs the whole
fleet, so this walks the distinct parent repos in the registry and reuses that
per-repo logic rather than reimplementing it.
"""

from collections.abc import Callable
from pathlib import Path

from lumbergh import worktrees

ATTENTION_STATES = {"blocked", "error", "dead"}


def snapshot(
    live_sessions: dict[str, dict],
    state_of: Callable[[str], str],
    since_of: Callable[[str], float | None],
    unseen_of: Callable[[str], bool],
    origin: str | None = None,
) -> list[dict]:
    rows: list[dict] = []
    for row in worktrees.reconcile_all(live_sessions):
        entry = worktrees.get_entry(Path(row["path"])) or {}
        if origin is not None and entry.get("origin") != origin:
            continue
        session = row.get("session") or entry.get("associated_session")
        if row["session"]:
            state = state_of(row["session"])
            since = since_of(row["session"])
            unseen = unseen_of(row["session"])
        else:
            state = "dead" if entry.get("associated_session") else "orphan"
            since = None
            unseen = False
        rows.append(
            {
                "task": session,
                "repo": row["repo"],
                "branch": row["branch"],
                "session": row["session"],
                "kind": entry.get("kind"),
                "state": state,
                "since": round(since) if since is not None else None,
                "unseen": unseen,
                "path": row["path"],
            }
        )
    return rows


def needs_attention(row: dict) -> bool:
    if row["state"] in ATTENTION_STATES:
        return True
    return row["state"] == "idle" and bool(row.get("unseen"))


def any_needs_attention(rows: list[dict]) -> bool:
    return any(needs_attention(r) for r in rows)


_OUTCOME = re.compile(r"^(DELIVERED|FAILED):\s*(.+)$")


def parse_outcome(text: str) -> str | None:
    """The worker's contracted final line, so an outcome is read rather than inferred."""
    for line in reversed((text or "").splitlines()):
        m = _OUTCOME.match(line.strip())
        if m:
            return f"{m.group(1)}: {m.group(2).strip()}"
    return None
```

Add `import re` to the module's imports.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_fleet.py -v`
Expected: PASS (17 tests, counting the parametrized cases).

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/fleet.py backend/lumbergh/tests/test_fleet.py
git commit -m "feat(bill): cross-repo fleet snapshot with attention predicate"
```

---

### Task 3: Fleet REST endpoints, including the long poll

**Files:**
- Create: `backend/lumbergh/routers/bill.py`
- Modify: `backend/lumbergh/main.py:174` (register router)
- Test: `backend/lumbergh/tests/test_bill_router.py`

**Interfaces:**
- Consumes: `fleet.snapshot`, `fleet.any_needs_attention`, `fleet.parse_outcome`, `idle_monitor.get_state(name).value`, `idle_monitor.state_since_seconds(name)`, `session_attention.is_unseen(name)`, `routers.worktrees._live_sessions()`, `activity.resolve.resolve_adapter`.
- Produces:
  - `GET /api/bill/fleet?origin=bill` → `{"total": int, "tasks": [row, ...]}`, rows carrying `outcome`.
  - `GET /api/bill/fleet/wait?timeout=300&origin=bill` → `{"woke": bool, "waited": float, "total": int, "tasks": [...]}`
  - Module helper `_fleet_rows(origin: str | None, with_outcome: bool = False) -> list[dict]` reused by both.

**Why `with_outcome` is a flag, not always-on:** reading a transcript costs real I/O, and the long poll calls `_fleet_rows` every 0.25s. Only the one-shot `/fleet` view enriches; the wait loop needs just `needs_attention`, which does not look at `outcome`.

**Corrected during execution** (three defects in this task's draft, all fixed in fix round 1):

1. The `_session_meta` helper below duplicates `agent.py`'s `_meta` byte-for-byte. Extract one shared helper instead of writing a second copy.
2. The `test_fleet_wait_returns_immediately_when_attention_is_already_needed` test below cannot distinguish check-before-sleep from sleep-then-check — it patches the row source to report `blocked` on every call and asserts only `woke is True`. Bound `waited` below `_POLL_INTERVAL` (or count calls) so the ordering guarantee is actually enforced by the suite.
3. `_outcome_of` needs a per-row guard. `/fleet` aggregates every worker and is Bill's only window on the fleet, so one corrupt transcript must yield `outcome: None` for that row rather than 500 the whole response and blind him to all workers.

- [ ] **Step 1: Write the failing tests**

Create `backend/lumbergh/tests/test_bill_router.py`:

```python
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lumbergh.routers import bill


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(bill.router)
    return TestClient(app)


def test_fleet_returns_rows(client, monkeypatch):
    monkeypatch.setattr(
        bill,
        "_fleet_rows",
        lambda origin, with_outcome=False: [  # noqa: ARG005
            {
                "task": "w-a",
                "repo": "app",
                "branch": "feat/a",
                "session": "w-a",
                "kind": "ship",
                "state": "working",
                "since": 5,
                "unseen": False,
                "path": "/w/app-worktrees/feat-a",
            }
        ],
    )
    body = client.get("/api/bill/fleet").json()
    assert body["total"] == 1
    assert body["tasks"][0]["task"] == "w-a"


def test_fleet_wait_returns_immediately_when_attention_is_already_needed(client, monkeypatch):
    monkeypatch.setattr(
        bill,
        "_fleet_rows",
        lambda origin, with_outcome=False: [  # noqa: ARG005
            {"state": "blocked", "unseen": False, "task": "w-a"}
        ],
    )
    body = client.get("/api/bill/fleet/wait", params={"timeout": 5}).json()
    assert body["woke"] is True
    assert body["tasks"][0]["task"] == "w-a"


def test_fleet_wait_times_out_on_a_calm_fleet(client, monkeypatch):
    monkeypatch.setattr(
        bill,
        "_fleet_rows",
        lambda origin, with_outcome=False: [  # noqa: ARG005
            {"state": "working", "unseen": False, "task": "w-a"}
        ],
    )
    body = client.get("/api/bill/fleet/wait", params={"timeout": 0.5}).json()
    assert body["woke"] is False
    assert body["total"] == 1


def test_fleet_wait_wakes_when_a_worker_becomes_blocked(client, monkeypatch):
    calls = {"n": 0}

    def rows(origin, with_outcome=False):  # noqa: ARG001
        calls["n"] += 1
        state = "blocked" if calls["n"] > 2 else "working"
        return [{"state": state, "unseen": False, "task": "w-a"}]

    monkeypatch.setattr(bill, "_fleet_rows", rows)
    body = client.get("/api/bill/fleet/wait", params={"timeout": 10}).json()
    assert body["woke"] is True
    assert body["tasks"][0]["state"] == "blocked"


def test_outcome_of_reads_the_workers_final_line(monkeypatch):
    class _Event:
        def __init__(self, text):
            self.text = text
            self.tool_summary = ""

    class _Adapter:
        def read_new(self):
            return [_Event("ran the tests"), _Event("DELIVERED: https://example.test/pull/7")]

    monkeypatch.setattr(bill, "resolve_adapter", lambda *a, **kw: _Adapter())  # noqa: ARG005
    monkeypatch.setattr(bill, "_session_meta", lambda name: {"workdir": "/w"})  # noqa: ARG005
    assert bill._outcome_of("w-a") == "DELIVERED: https://example.test/pull/7"


def test_outcome_of_is_none_without_a_transcript(monkeypatch):
    monkeypatch.setattr(bill, "resolve_adapter", lambda *a, **kw: None)  # noqa: ARG005
    monkeypatch.setattr(bill, "_session_meta", lambda name: {})  # noqa: ARG005
    assert bill._outcome_of("w-a") is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_bill_router.py -v`
Expected: FAIL — `ImportError: cannot import name 'bill' from 'lumbergh.routers'`.

- [ ] **Step 3: Implement**

Create `backend/lumbergh/routers/bill.py`:

```python
"""Bill's control surface: the fleet view, its long poll, spawn, and summon."""

import asyncio
import time
from pathlib import Path

from fastapi import APIRouter

from lumbergh import fleet, session_attention
from lumbergh.activity.resolve import resolve_adapter
from lumbergh.idle_monitor import idle_monitor

router = APIRouter(prefix="/api/bill", tags=["bill"])

_POLL_INTERVAL = 0.25
_OUTCOME_TAIL_EVENTS = 15


def _session_meta(name: str) -> dict:
    from lumbergh.routers.sessions import get_stored_sessions

    return get_stored_sessions().get(name, {})


def _outcome_of(session: str) -> str | None:
    """The worker's contracted final line, read from its transcript.

    ``resolve_adapter`` builds a fresh adapter each call, so ``read_new`` starts at
    offset 0 and returns full history — this never steals events from ``lb read``.
    """
    meta = _session_meta(session)
    cwd = Path(meta["workdir"]) if meta.get("workdir") else None
    adapter = resolve_adapter(session, cwd, meta.get("agent_provider"))
    if adapter is None:
        return None
    events = adapter.read_new()[-_OUTCOME_TAIL_EVENTS:]
    return fleet.parse_outcome("\n".join((e.text or "") for e in events))


def _fleet_rows(origin: str | None, with_outcome: bool = False) -> list[dict]:
    from lumbergh.routers.worktrees import _live_sessions

    rows = fleet.snapshot(
        _live_sessions(),
        state_of=lambda n: idle_monitor.get_state(n).value,
        since_of=idle_monitor.state_since_seconds,
        unseen_of=session_attention.is_unseen,
        origin=origin,
    )
    if with_outcome:
        for row in rows:
            row["outcome"] = _outcome_of(row["session"]) if row.get("session") else None
    return rows


@router.get("/fleet")
def get_fleet(origin: str | None = None):
    rows = _fleet_rows(origin, with_outcome=True)
    return {"total": len(rows), "tasks": rows}


@router.get("/fleet/wait")
async def wait_fleet(timeout: float = 300.0, origin: str | None = None):
    """Block until any task needs Bill, so supervision costs no tokens while idle.

    The current snapshot is checked before the first sleep, so a worker that went
    blocked before the call arrived still wakes it — no lost wakeup.
    """
    deadline = time.monotonic() + timeout
    start = time.monotonic()
    while True:
        rows = _fleet_rows(origin)
        woke = fleet.any_needs_attention(rows)
        if woke or time.monotonic() >= deadline:
            return {
                "woke": woke,
                "waited": round(time.monotonic() - start, 1),
                "total": len(rows),
                "tasks": rows,
            }
        await asyncio.sleep(_POLL_INTERVAL)
```

Then register it in `backend/lumbergh/main.py` next to the existing worktrees registration (line ~174):

```python
app.include_router(bill_router.router)
```

with the import alongside the other router imports:

```python
from lumbergh.routers import bill as bill_router
```

Match the existing import style in that file — if the neighbouring routers use `from lumbergh.routers import worktrees as worktrees_router`, follow exactly that form.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_bill_router.py -v`
Expected: PASS (6 tests).

Confirm the app still boots: `cd backend && uv run python -c "from lumbergh.main import app; print(len(app.routes))"` → prints a number, no traceback.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/routers/bill.py backend/lumbergh/main.py backend/lumbergh/tests/test_bill_router.py
git commit -m "feat(bill): fleet endpoint with long-poll wait"
```

---

### Task 4: `lb fleet` CLI

**Files:**
- Create: `backend/lumbergh/agent_cli/fleet.py`
- Modify: `backend/lumbergh/agent_cli/main.py` (FLAGS, `_BOOL_FLAGS`, dispatch)
- Test: `backend/lumbergh/tests/test_lb_fleet_cli.py`

**Interfaces:**
- Consumes: `agent_cli.main._emit`, `_err`, `_request`; `agent_cli.toon.render_collection`, `render_object`; endpoints from Task 3.
- Produces: `fleet.run(flags: dict) -> int` — exit 0 on success, 2 on usage error, 1 on server error.

Columns rendered: `task`, `repo`, `branch`, `kind`, `state`, `since`, `unseen`, `outcome`. Showing `outcome` here means a woken Bill sees "idle, unseen, `DELIVERED: <url>`" in one command and can report without a second call.

- [ ] **Step 1: Write the failing tests**

Create `backend/lumbergh/tests/test_lb_fleet_cli.py`:

```python
import json

from lumbergh.agent_cli import fleet as fleet_cli


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


_ROW = {
    "task": "w-a",
    "repo": "app",
    "branch": "feat/a",
    "session": "w-a",
    "kind": "ship",
    "state": "blocked",
    "since": 42,
    "unseen": False,
    "outcome": None,
    "path": "/w/app-worktrees/feat-a",
}


def test_fleet_renders_table(monkeypatch, capsys):
    monkeypatch.setattr(
        fleet_cli, "_request", lambda m, p, **kw: _Resp({"total": 1, "tasks": [_ROW]})  # noqa: ARG005
    )
    rc = fleet_cli.run({})
    out = capsys.readouterr().out
    assert rc == 0
    assert "blocked" in out
    assert "w-a" in out


def test_fleet_json_emits_raw_rows(monkeypatch, capsys):
    monkeypatch.setattr(
        fleet_cli, "_request", lambda m, p, **kw: _Resp({"total": 1, "tasks": [_ROW]})  # noqa: ARG005
    )
    rc = fleet_cli.run({"--json": True})
    assert rc == 0
    assert json.loads(capsys.readouterr().out)[0]["task"] == "w-a"


def test_fleet_shows_a_finished_workers_outcome(monkeypatch, capsys):
    finished = dict(_ROW, state="idle", unseen=True, outcome="DELIVERED: https://x.test/pull/7")
    monkeypatch.setattr(
        fleet_cli,
        "_request",
        lambda m, p, **kw: _Resp({"total": 1, "tasks": [finished]}),  # noqa: ARG005
    )
    rc = fleet_cli.run({})
    out = capsys.readouterr().out
    assert rc == 0
    assert "DELIVERED" in out


def test_fleet_reports_an_empty_fleet(monkeypatch, capsys):
    monkeypatch.setattr(
        fleet_cli, "_request", lambda m, p, **kw: _Resp({"total": 0, "tasks": []})  # noqa: ARG005
    )
    rc = fleet_cli.run({})
    assert rc == 0
    assert "0" in capsys.readouterr().out


def test_wait_hits_the_wait_endpoint_and_reports_the_wake(monkeypatch, capsys):
    captured = {}

    def fake_request(method, path, **kw):
        captured["path"] = path
        captured["params"] = kw.get("params")
        return _Resp({"woke": True, "waited": 12.5, "total": 1, "tasks": [_ROW]})

    monkeypatch.setattr(fleet_cli, "_request", fake_request)
    rc = fleet_cli.run({"--wait": True, "--timeout": "600"})
    out = capsys.readouterr().out
    assert rc == 0
    assert captured["path"] == "/api/bill/fleet/wait"
    assert captured["params"]["timeout"] == "600"
    assert "blocked" in out


def test_wait_timeout_is_not_an_error(monkeypatch, capsys):
    monkeypatch.setattr(
        fleet_cli,
        "_request",
        lambda m, p, **kw: _Resp(  # noqa: ARG005
            {"woke": False, "waited": 300.0, "total": 1, "tasks": [dict(_ROW, state="working")]}
        ),
    )
    rc = fleet_cli.run({"--wait": True})
    out = capsys.readouterr().out
    assert rc == 0
    assert "no task needs you" in out.lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_lb_fleet_cli.py -v`
Expected: FAIL — `ImportError: cannot import name 'fleet' from 'lumbergh.agent_cli'`.

- [ ] **Step 3: Implement**

Create `backend/lumbergh/agent_cli/fleet.py`:

```python
"""`lb fleet` — the whole crew in one table, with a token-free long poll."""

import json

from lumbergh.agent_cli.main import _emit, _err, _request
from lumbergh.agent_cli.toon import render_collection, render_object

_COLS = ["task", "repo", "branch", "kind", "state", "since", "unseen", "outcome"]
_HELP = "lb fleet [--wait] [--timeout <s>] [--origin bill] [--json]"


def run(flags: dict) -> int:
    waiting = "--wait" in flags
    params = {}
    if flags.get("--origin"):
        params["origin"] = flags["--origin"]
    if waiting:
        params["timeout"] = flags.get("--timeout", "300")
        path = "/api/bill/fleet/wait"
    else:
        path = "/api/bill/fleet"

    resp = _request("GET", path, params=params, timeout=_client_timeout(params))
    if resp.status_code >= 400:
        return _err(f"fleet request failed ({resp.status_code})", _HELP, 1)
    d = resp.json()
    rows = d.get("tasks", [])

    if "--json" in flags:
        _emit(json.dumps(rows))
        return 0

    if not rows:
        _emit("fleet: 0 tasks")
        return 0

    if waiting:
        woke = d.get("woke")
        _emit(
            render_object(
                [
                    ("woke", "true" if woke else "false"),
                    ("waited", f"{d.get('waited', 0)}s"),
                    ("note", "" if woke else "no task needs you yet — re-run to keep waiting"),
                ]
            )
        )
    _emit(render_collection("fleet", [_display(r) for r in rows], _COLS))
    return 0


def _display(row: dict) -> dict:
    shown = {c: row.get(c) for c in _COLS}
    shown["since"] = f"{row['since']}s" if row.get("since") is not None else "-"
    shown["kind"] = row.get("kind") or "-"
    shown["unseen"] = "yes" if row.get("unseen") else ""
    shown["outcome"] = row.get("outcome") or "-"
    return shown


def _client_timeout(params: dict) -> float:
    """Outlive the server's own long poll so the client never times out first."""
    return float(params.get("timeout", 300)) + 20
```

In `backend/lumbergh/agent_cli/main.py`:

1. Add to `FLAGS`:

```python
    "fleet": {"--wait", "--timeout", "--origin", "--json"},
```

2. `--wait` and `--json` are already in `_BOOL_FLAGS`; no change needed there.

3. Add to `dispatch`:

```python
        "fleet": lambda: _cmd_fleet(flags),
```

4. Add the handler next to `_cmd_worktree`:

```python
def _cmd_fleet(flags) -> int:
    from lumbergh.agent_cli import fleet as fleet_cli

    return fleet_cli.run(flags)
```

5. Add a line to `_cmd_home`'s help block so `lb` advertises the new verb:

```python
                "Run `lb fleet --wait` to block until a task needs you",
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_lb_fleet_cli.py lumbergh/tests/test_lb_cli.py -v`
Expected: PASS (6 new tests, existing CLI tests still green).

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/agent_cli/fleet.py backend/lumbergh/agent_cli/main.py backend/lumbergh/tests/test_lb_fleet_cli.py
git commit -m "feat(bill): lb fleet with long-poll wait"
```

---

### Task 5: Spawn endpoint with unwind

**Files:**
- Modify: `backend/lumbergh/routers/bill.py` (add spawn)
- Test: `backend/lumbergh/tests/test_bill_router.py` (append)

**Interfaces:**
- Consumes: `worktrees.create(repo, branch, created_at=..., create_branch=..., base_branch=..., session=..., task_intent=..., kind=..., origin=..., global_base_dir=...)` (Task 1), `worktrees.reap(path, force=..., rm_branch=...)`, `worktrees.remove_entry(path)`, `tmux_pty.create_tmux_session(name, workdir, launch_command=...)`, `providers.get_launch_command`, `routers.sessions.get_live_sessions`, `routers.sessions.sessions_table`, `routers.sessions.SESSION_NAME_PATTERN`, `tmux_pty.send_text`.
- Produces:
  - `POST /api/bill/spawn` body `{repo, branch, kind, brief_path, name?, create_branch?, base_branch?, agent_provider?, task_intent?}` → `200 {"session", "path", "branch", "kind", "brief_path"}` or `400 {"detail": {"error": str, "stage": str}}`.
  - `_derive_name(branch: str, live: set[str]) -> str` — sanitized, uniquified session name.

- [ ] **Step 1: Write the failing tests**

Append to `backend/lumbergh/tests/test_bill_router.py`:

```python
def test_derive_name_sanitizes_and_uniquifies():
    assert bill._derive_name("feat/flaky-login", set()) == "feat-flaky-login"
    assert bill._derive_name("feat/flaky-login", {"feat-flaky-login"}) == "feat-flaky-login-2"
    assert (
        bill._derive_name("feat/flaky-login", {"feat-flaky-login", "feat-flaky-login-2"})
        == "feat-flaky-login-3"
    )


def test_spawn_rejects_a_missing_brief(client, tmp_path):
    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(tmp_path),
            "branch": "feat/x",
            "kind": "ship",
            "brief_path": str(tmp_path / "nope.md"),
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"]["stage"] == "brief"


def test_spawn_rejects_an_unknown_kind(client, tmp_path):
    brief = tmp_path / "b.md"
    brief.write_text("do the thing")
    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(tmp_path),
            "branch": "feat/x",
            "kind": "wander",
            "brief_path": str(brief),
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"]["stage"] == "kind"


def test_spawn_surfaces_a_worktree_failure(client, tmp_path, monkeypatch):
    brief = tmp_path / "b.md"
    brief.write_text("do the thing")
    monkeypatch.setattr(bill, "_live_names", lambda: set())
    monkeypatch.setattr(
        bill.worktrees, "create", lambda *a, **kw: {"error": "branch already checked out"}  # noqa: ARG005
    )
    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(tmp_path),
            "branch": "feat/x",
            "kind": "ship",
            "brief_path": str(brief),
        },
    )
    assert r.status_code == 400
    body = r.json()["detail"]
    assert body["stage"] == "worktree"
    assert "already checked out" in body["error"]


def test_spawn_unwinds_the_worktree_when_the_session_fails(client, tmp_path, monkeypatch):
    brief = tmp_path / "b.md"
    brief.write_text("do the thing")
    reaped = {}

    monkeypatch.setattr(bill, "_live_names", lambda: set())
    monkeypatch.setattr(
        bill.worktrees,
        "create",
        lambda *a, **kw: {"path": str(tmp_path / "wt"), "links_applied": []},  # noqa: ARG005
    )

    def boom(*a, **kw):  # noqa: ARG001
        raise RuntimeError("tmux is not installed")

    monkeypatch.setattr(bill, "create_tmux_session", boom)
    def record_reap(path, **kw):  # noqa: ARG001
        reaped["path"] = str(path)
        return {"status": "removed"}

    monkeypatch.setattr(bill.worktrees, "reap", record_reap)
    monkeypatch.setattr(bill.worktrees, "remove_entry", lambda path: None)  # noqa: ARG005

    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(tmp_path),
            "branch": "feat/x",
            "kind": "ship",
            "brief_path": str(brief),
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"]["stage"] == "session"
    assert reaped["path"] == str(tmp_path / "wt")


def test_spawn_happy_path_records_the_task_and_delivers_the_brief(client, tmp_path, monkeypatch):
    brief = tmp_path / "b.md"
    brief.write_text("do the thing")
    sent = {}
    stored = {}

    monkeypatch.setattr(bill, "_live_names", lambda: set())
    monkeypatch.setattr(
        bill.worktrees,
        "create",
        lambda *a, **kw: {"path": str(tmp_path / "wt"), "links_applied": []},  # noqa: ARG005
    )
    monkeypatch.setattr(bill, "create_tmux_session", lambda *a, **kw: None)  # noqa: ARG005
    monkeypatch.setattr(bill, "_store_session", lambda **kw: stored.update(kw))
    monkeypatch.setattr(bill, "send_text", lambda name, text: sent.update(name=name, text=text))

    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": str(tmp_path),
            "branch": "feat/x",
            "kind": "scout",
            "brief_path": str(brief),
            "task_intent": "figure out the flaky login test",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["session"] == "feat-x"
    assert body["kind"] == "scout"
    assert stored["name"] == "feat-x"
    assert str(brief) in sent["text"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_bill_router.py -v`
Expected: FAIL — `AttributeError: module 'lumbergh.routers.bill' has no attribute '_derive_name'` and 404s on `/api/bill/spawn`.

- [ ] **Step 3: Implement**

Add to `backend/lumbergh/routers/bill.py` (imports at top, code below the fleet endpoints):

```python
import re
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel

from lumbergh import worktrees
from lumbergh.tmux_pty import create_tmux_session, send_text

KINDS = {"ship", "scout"}


class SpawnBody(BaseModel):
    repo: str
    branch: str
    kind: str
    brief_path: str
    name: str | None = None
    create_branch: bool = False
    base_branch: str | None = None
    agent_provider: str | None = None
    task_intent: str | None = None


def _fail(stage: str, error: str, help_text: str) -> HTTPException:
    return HTTPException(status_code=400, detail={"stage": stage, "error": error, "help": help_text})


def _live_names() -> set[str]:
    from lumbergh.routers.sessions import get_live_sessions

    return set(get_live_sessions().keys())


def _derive_name(branch: str, live: set[str]) -> str:
    base = re.sub(r"[^a-zA-Z0-9_-]", "-", branch).strip("-") or "task"
    if base not in live:
        return base
    n = 2
    while f"{base}-{n}" in live:
        n += 1
    return f"{base}-{n}"


def _store_session(**fields) -> None:
    from tinydb import Query

    from lumbergh.routers.sessions import sessions_table

    sessions_table.upsert(fields, Query().name == fields["name"])


@router.post("/spawn")
def spawn(body: SpawnBody):
    """Create worktree + session + deliver the brief, unwinding any partial work."""
    if body.kind not in KINDS:
        raise _fail("kind", f"unknown kind `{body.kind}`", "kind must be ship or scout")

    brief = Path(body.brief_path).expanduser()
    if not brief.is_file():
        raise _fail("brief", f"no brief file at {brief}", "write the brief before spawning")

    repo = Path(body.repo).expanduser()
    if not (repo / ".git").exists():
        raise _fail("repo", f"{repo} is not a git repository", "pass the repo's root path")

    live = _live_names()
    name = body.name or _derive_name(body.branch, live)
    if name in live:
        raise _fail("name", f"session `{name}` is already live", "pass a different --name")

    from lumbergh.routers.settings import get_settings

    created = worktrees.create(
        repo,
        body.branch,
        created_at=datetime.now(UTC).isoformat(),
        create_branch=body.create_branch,
        base_branch=body.base_branch,
        session=name,
        task_intent=body.task_intent,
        kind=body.kind,
        origin="bill",
        global_base_dir=get_settings().get("worktree", {}).get("base_dir") or None,
    )
    if created.get("error"):
        raise _fail("worktree", created["error"], "fix the branch or repo and retry")

    workdir = Path(created["path"])
    from lumbergh.providers import get_launch_command

    launch = get_launch_command(body.agent_provider, get_settings().get("defaultAgent"))
    try:
        create_tmux_session(name, workdir, launch_command=launch)
    except (RuntimeError, OSError) as e:
        _unwind(workdir)
        raise _fail("session", f"could not start the worker: {e}", "check tmux, then retry")

    _store_session(
        name=name,
        workdir=str(workdir),
        description=body.task_intent or "",
        type="worktree",
        agent_provider=body.agent_provider,
        worktree_parent_repo=str(repo.resolve()),
        worktree_branch=body.branch,
    )
    send_text(name, _brief_delivery(brief, body.kind, name))
    return {
        "session": name,
        "path": str(workdir),
        "branch": body.branch,
        "kind": body.kind,
        "brief_path": str(brief),
    }


def _unwind(workdir: Path) -> None:
    """A half-created task must not survive; the worktree is fresh, so the guard passes."""
    worktrees.reap(workdir, force=True)
    worktrees.remove_entry(workdir)


def _brief_delivery(brief: Path, kind: str, name: str) -> str:
    report = f"Write your report to {brief.parent.parent / 'reports' / f'{name}.md'}. "
    return (
        f"Read your brief at {brief} and follow it. "
        + (report if kind == "scout" else "")
        + "Finish your final message with exactly one line: "
        "`DELIVERED: <pr-url-or-branch>` or `FAILED: <reason>`."
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_bill_router.py -v`
Expected: PASS (10 tests total in the file).

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/routers/bill.py backend/lumbergh/tests/test_bill_router.py
git commit -m "feat(bill): spawn endpoint that unwinds partial tasks"
```

---

### Task 6: `lb spawn` CLI

**Files:**
- Create: `backend/lumbergh/agent_cli/spawn.py`
- Modify: `backend/lumbergh/agent_cli/main.py` (FLAGS, dispatch)
- Test: `backend/lumbergh/tests/test_lb_spawn_cli.py`

**Interfaces:**
- Consumes: `POST /api/bill/spawn` from Task 5; `agent_cli.main._emit/_err/_request`.
- Produces: `spawn.run(flags: dict) -> int`.

- [ ] **Step 1: Write the failing tests**

Create `backend/lumbergh/tests/test_lb_spawn_cli.py`:

```python
from lumbergh.agent_cli import spawn as spawn_cli


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


def test_spawn_requires_repo_branch_kind_and_brief(capsys):
    rc = spawn_cli.run({"--repo": "/w/app"})
    out = capsys.readouterr().out
    assert rc == 2
    assert "--brief" in out


def test_spawn_rejects_a_bad_kind_before_calling_the_server(capsys):
    rc = spawn_cli.run(
        {"--repo": "/w/app", "--branch": "feat/x", "--kind": "wander", "--brief": "/w/b.md"}
    )
    assert rc == 2
    assert "ship" in capsys.readouterr().out


def test_spawn_posts_the_expected_body(monkeypatch, capsys):
    captured = {}

    def fake_request(method, path, **kw):
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kw.get("json")
        return _Resp(
            {
                "session": "feat-x",
                "path": "/w/app-worktrees/feat-x",
                "branch": "feat/x",
                "kind": "ship",
                "brief_path": "/w/b.md",
            }
        )

    monkeypatch.setattr(spawn_cli, "_request", fake_request)
    rc = spawn_cli.run(
        {
            "--repo": "/w/app",
            "--branch": "feat/x",
            "--kind": "ship",
            "--brief": "/w/b.md",
            "--new": True,
            "--intent": "fix the flaky login test",
        }
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert captured["path"] == "/api/bill/spawn"
    assert captured["json"]["create_branch"] is True
    assert captured["json"]["kind"] == "ship"
    assert captured["json"]["task_intent"] == "fix the flaky login test"
    assert "feat-x" in out


def test_spawn_surfaces_the_server_stage_and_help(monkeypatch, capsys):
    monkeypatch.setattr(
        spawn_cli,
        "_request",
        lambda m, p, **kw: _Resp(  # noqa: ARG005
            {
                "detail": {
                    "stage": "worktree",
                    "error": "branch already checked out",
                    "help": "fix the branch or repo and retry",
                }
            },
            status=400,
        ),
    )
    rc = spawn_cli.run(
        {"--repo": "/w/app", "--branch": "feat/x", "--kind": "ship", "--brief": "/w/b.md"}
    )
    out = capsys.readouterr().out
    assert rc == 1
    assert "already checked out" in out
    assert "retry" in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_lb_spawn_cli.py -v`
Expected: FAIL — `ImportError: cannot import name 'spawn' from 'lumbergh.agent_cli'`.

- [ ] **Step 3: Implement**

Create `backend/lumbergh/agent_cli/spawn.py`:

```python
"""`lb spawn` — one call for worktree + worker + brief delivery."""

from lumbergh.agent_cli.main import _emit, _err, _request
from lumbergh.agent_cli.toon import render_object

_KINDS = ("ship", "scout")
_HELP = (
    "lb spawn --repo <path> --branch <b> --kind ship|scout --brief <file> "
    "[--new] [--base <b>] [--name <n>] [--agent <provider>] [--intent '...']"
)


def run(flags: dict) -> int:
    missing = [f for f in ("--repo", "--branch", "--kind", "--brief") if not flags.get(f)]
    if missing:
        return _err(f"{', '.join(missing)} required", _HELP, 2)
    if flags["--kind"] not in _KINDS:
        return _err(f"unknown kind `{flags['--kind']}`", "--kind must be ship or scout", 2)

    body = {
        "repo": flags["--repo"],
        "branch": flags["--branch"],
        "kind": flags["--kind"],
        "brief_path": flags["--brief"],
        "name": flags.get("--name"),
        "create_branch": "--new" in flags,
        "base_branch": flags.get("--base"),
        "agent_provider": flags.get("--agent"),
        "task_intent": flags.get("--intent"),
    }
    resp = _request("POST", "/api/bill/spawn", json=body)
    if resp.status_code >= 400:
        d = resp.json().get("detail", {})
        return _err(f"{d.get('stage', 'spawn')}: {d.get('error', 'spawn failed')}", d.get("help"), 1)
    d = resp.json()
    _emit(
        render_object(
            [
                ("session", d["session"]),
                ("kind", d["kind"]),
                ("branch", d["branch"]),
                ("path", d["path"]),
            ]
        )
    )
    return 0
```

In `backend/lumbergh/agent_cli/main.py`:

1. Add to `FLAGS`:

```python
    "spawn": {
        "--repo",
        "--branch",
        "--kind",
        "--brief",
        "--name",
        "--base",
        "--agent",
        "--intent",
        "--new",
    },
```

2. Add to `dispatch`:

```python
        "spawn": lambda: _cmd_spawn(flags),
```

3. Add the handler:

```python
def _cmd_spawn(flags) -> int:
    from lumbergh.agent_cli import spawn as spawn_cli

    return spawn_cli.run(flags)
```

(`--new` is already in `_BOOL_FLAGS`.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_lb_spawn_cli.py lumbergh/tests/test_lb_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/agent_cli/spawn.py backend/lumbergh/agent_cli/main.py backend/lumbergh/tests/test_lb_spawn_cli.py
git commit -m "feat(bill): lb spawn CLI"
```

---

### Task 7: Bill's instruction bundle and its materialization

**Files:**
- Create: `backend/lumbergh/bill/__init__.py`
- Create: `backend/lumbergh/bill/AGENTS.md.template`
- Create: `backend/lumbergh/bill/personality_professional.md`
- Create: `backend/lumbergh/bill/personality_lumbergh.md`
- Create: `backend/lumbergh/bill/preferences_seed.md`
- Test: `backend/lumbergh/tests/test_bill_bundle.py`

**Interfaces:**
- Consumes: `constants.CONFIG_DIR`.
- Produces:
  - `bill.home() -> Path` — `CONFIG_DIR / "bill"`.
  - `bill.render(personality: str) -> str` — the `AGENTS.md` body with the preamble substituted.
  - `bill.materialize(personality: str = "professional", home: Path | None = None) -> Path` — writes `AGENTS.md` (always), symlinks `CLAUDE.md`, creates `preferences.md` / `briefs/` / `reports/` only when absent. Returns the home.

- [ ] **Step 1: Write the failing tests**

Create `backend/lumbergh/tests/test_bill_bundle.py`:

```python
from lumbergh import bill


def test_render_substitutes_the_professional_preamble():
    body = bill.render("professional")
    assert "{{PERSONALITY}}" not in body
    assert "TPS" not in body


def test_render_substitutes_the_lumbergh_preamble():
    body = bill.render("lumbergh")
    assert "{{PERSONALITY}}" not in body
    assert body != bill.render("professional")


def test_render_falls_back_to_professional_for_an_unknown_personality():
    assert bill.render("pirate") == bill.render("professional")


def test_materialize_creates_the_full_home(tmp_path):
    home = bill.materialize(home=tmp_path / "bill")
    assert (home / "AGENTS.md").is_file()
    assert (home / "CLAUDE.md").resolve() == (home / "AGENTS.md").resolve()
    assert (home / "preferences.md").is_file()
    assert (home / "briefs").is_dir()
    assert (home / "reports").is_dir()


def test_materialize_refreshes_agents_md_but_never_preferences(tmp_path):
    home = bill.materialize(home=tmp_path / "bill")
    (home / "preferences.md").write_text("I hate mocks.\n")
    (home / "AGENTS.md").write_text("clobbered\n")
    (home / "briefs" / "w-a.md").write_text("do the thing\n")

    bill.materialize(personality="lumbergh", home=home)

    assert (home / "preferences.md").read_text() == "I hate mocks.\n"
    assert (home / "briefs" / "w-a.md").read_text() == "do the thing\n"
    assert "clobbered" not in (home / "AGENTS.md").read_text()
    assert (home / "AGENTS.md").read_text() == bill.render("lumbergh")


def test_materialize_is_idempotent(tmp_path):
    home = bill.materialize(home=tmp_path / "bill")
    first = (home / "AGENTS.md").read_text()
    bill.materialize(home=home)
    assert (home / "AGENTS.md").read_text() == first


def test_bundle_forbids_writing_code_and_merging():
    body = bill.render("professional")
    lowered = body.lower()
    assert "never write project code" in lowered
    assert "never merge" in lowered
    assert "lb fleet --wait" in body
    assert "lb spawn" in body


def test_personality_never_leaks_into_the_brief_template():
    professional = bill.render("professional")
    flair = bill.render("lumbergh")
    marker = "## Brief template"
    assert professional.split(marker)[1] == flair.split(marker)[1]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_bill_bundle.py -v`
Expected: FAIL — `ImportError: cannot import name 'bill' from 'lumbergh'`.

- [ ] **Step 3: Implement**

Create `backend/lumbergh/bill/personality_professional.md`:

```markdown
You are Bill, the user's engineering manager. You are direct, brief, and factual.
You lead with outcomes and you never pad a report.
```

Create `backend/lumbergh/bill/personality_lumbergh.md`:

```markdown
You are Bill Lumbergh, the user's manager. You are unfailingly pleasant, faintly
condescending, and fond of the phrase "if you could go ahead and". You care deeply about
TPS reports. Keep the bit to a light garnish on the first and last sentence — it never
obscures the technical content, and you drop it entirely when delivering bad news.
```

Create `backend/lumbergh/bill/preferences_seed.md`:

```markdown
# The user's standing preferences

Bill appends to this file whenever the user states a standing preference or corrects him.
The user edits it freely. Lumbergh never overwrites it.

Format: one dated bullet per preference, with the reason it exists.

<!-- e.g. - 2026-07-28: Prefer small PRs over one big one. Reason: easier to review on a phone. -->
```

Create `backend/lumbergh/bill/AGENTS.md.template`:

```markdown
{{PERSONALITY}}

# Your job

You manage the user's software work across every project. You do not do the work.
You break requests into tasks, dispatch a worker for each, supervise them, and report outcomes.

## Hard rules

1. **Never write project code.** Delegate implementation, investigation, planning, and diagnosis.
2. **Never merge or land anything.** Report; the user decides.
3. **Never invent an answer.** Answer a worker only from `preferences.md` or from what the user
   actually said. Anything else — scope, product, or design judgment — goes to the user. A worker
   left with a made-up answer ships the wrong thing.
4. **Never reap unlanded work.** A `reap` refusal is a stop-and-report, never something to force.
5. **Report outcomes faithfully.** If work failed, say so plainly with the evidence.

## Your tools

Run `lb <command> --help` when unsure; the binary is the authority on syntax.

- `lb fleet` — every task: `TASK · REPO · BRANCH · KIND · STATE · SINCE · UNSEEN · OUTCOME`.
  A finished worker's `OUTCOME` is its own final line, so you usually do not need `lb read`
  to know how a task ended.
- `lb fleet --wait [--timeout <s>]` — blocks until a task needs you (blocked, error, dead, or
  finished-unseen). This is how you supervise. It costs nothing while it waits.
- `lb spawn --repo <path> --branch <b> --kind ship|scout --brief <file> [--new] [--intent "..."]`
  — creates the worker's isolated copy, starts it, and hands it the brief.
- `lb read --session <name> [--last N]` — what a worker actually did.
- `lb prompt --session <name> "<text>"` — send a worker one short instruction.
- `lb worktree reap <path>` — clean up after the user has landed the work. It refuses if work
  would be lost; that refusal is information, not an obstacle.

## The loop

1. Read `preferences.md` at the start of every session. It is the user's standing opinion.
2. **Resolve the project.** Use what the user said, `preferences.md`, and the repos that already
   appear in `lb fleet`. Proceed on one confident match and name it. If several or none fit, ask
   one short question.
3. **Decide the shape.**
   - **ship** — you can describe the change and how to tell it worked. This is the default.
   - **scout** — you cannot. The worker's deliverable is a report, no code. Read it, tell the user
     what it found, then dispatch ship tasks from it. A report recommends; it never authorizes.
   You do not know these codebases. When you catch yourself guessing at file names or design,
   that is the signal to scout instead of ship.
4. **Write the brief** to `briefs/<session>.md`, then `lb spawn`.
5. **Supervise:** `lb fleet --wait`. On a wake:
   - `blocked` → `lb read` it. Answer from `preferences.md` if the answer is there; otherwise ask
     the user. Then `lb prompt` the worker.
   - `error` or `dead` → read it, then tell the user what happened. Do not silently retry.
   - finished → the `OUTCOME` column already holds `DELIVERED:` or `FAILED:`; read the task
     only if you need detail beyond it. Then report.
   Re-arm the wait immediately after handling a wake. Never sit idle while tasks are live.
6. **Report.** Give the user the outcome, not the machinery: what changed, the full
   `https://...` PR URL when there is one, and what needs their decision. No task ids, paths,
   states, or file names unless they need them to act.
7. After the user lands the work, `lb worktree reap` its copy and say what is still in flight.

## Delivery

Check whether the project has a GitHub remote — do not assume.

- **Remote present:** the worker runs the project's own validation gate, pushes, and opens a PR.
  Report the full URL and whether checks are green.
- **No remote:** the worker leaves a validated branch off `main`, ready to fast-forward.

You never run the validation gate and never judge the code. That is the worker's job.

## Preferences

When the user states a standing preference or corrects you, append one dated bullet to
`preferences.md` with the reason. Read it before you answer any worker's question.

## Brief template

Copy this into `briefs/<session>.md` and fill it in. Keep it specific — a vague brief is the
main reason a worker does the wrong thing well.

```
# Task: <one line>

## What to do
<the change or the question to answer, in the user's own terms>

## Done when
<how the worker knows it worked — the observable result, not the steps>

## Constraints
<anything the user cares about: files to avoid, approaches ruled out, preferences that apply>

## Delivery
Use this project's own validation gate. If the project has a GitHub remote, push and open a PR;
otherwise leave a validated branch off main.
You are in an isolated copy of the repo. Do not touch the user's main checkout.
If an instruction here looks wrong or unsupported, ask before coding — do not guess.
Finish your final message with exactly one line:
`DELIVERED: <pr-url-or-branch>` or `FAILED: <reason>`.
```
```

Create `backend/lumbergh/bill/__init__.py`:

```python
"""Bill's instruction bundle: tracked here, materialized into his session workdir.

``AGENTS.md`` is re-rendered on every summon so Bill improves when Lumbergh upgrades;
``preferences.md``, ``briefs/``, and ``reports/`` are the user's and are only ever created.
"""

from pathlib import Path

from lumbergh.constants import CONFIG_DIR

_SRC = Path(__file__).resolve().parent
DEFAULT_PERSONALITY = "professional"


def home() -> Path:
    return CONFIG_DIR / "bill"


def _personality_body(personality: str) -> str:
    path = _SRC / f"personality_{personality}.md"
    if not path.is_file():
        path = _SRC / f"personality_{DEFAULT_PERSONALITY}.md"
    return path.read_text().strip()


def render(personality: str = DEFAULT_PERSONALITY) -> str:
    template = (_SRC / "AGENTS.md.template").read_text()
    return template.replace("{{PERSONALITY}}", _personality_body(personality))


def materialize(personality: str = DEFAULT_PERSONALITY, home: Path | None = None) -> Path:
    target = home or globals()["home"]()
    target.mkdir(parents=True, exist_ok=True)
    (target / "briefs").mkdir(exist_ok=True)
    (target / "reports").mkdir(exist_ok=True)

    (target / "AGENTS.md").write_text(render(personality))

    claude = target / "CLAUDE.md"
    if not claude.exists():
        claude.symlink_to("AGENTS.md")

    prefs = target / "preferences.md"
    if not prefs.exists():
        prefs.write_text((_SRC / "preferences_seed.md").read_text())

    return target
```

Note the shadowing in `materialize`: the parameter is named `home`, so the module function is reached via `globals()`. If that reads badly to you, rename the parameter to `home_dir` and update the tests to match — but keep the public name `materialize(personality=..., home=...)` since Task 8 calls it that way.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_bill_bundle.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Verify the bundle ships in the wheel**

Run: `cd backend && uv run python -c "from lumbergh import bill; print(bill.render('lumbergh')[:60])"`
Expected: prints the flair preamble's first line. (Hatchling includes non-Python files under the package dir, same as `lumbergh/assets/tmux.conf`.)

- [ ] **Step 6: Commit**

```bash
git add backend/lumbergh/bill backend/lumbergh/tests/test_bill_bundle.py
git commit -m "feat(bill): instruction bundle with personality toggle"
```

---

### Task 8: Summon endpoint

**Files:**
- Modify: `backend/lumbergh/routers/bill.py` (add summon)
- Test: `backend/lumbergh/tests/test_bill_router.py` (append)

**Interfaces:**
- Consumes: `bill.materialize`, `bill.home`, `routers.settings.get_settings`, `create_tmux_session`, `_store_session`, `_live_names`.
- Produces: `POST /api/bill/summon` → `{"session": "bill", "workdir": str, "existing": bool}`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/lumbergh/tests/test_bill_router.py`:

```python
def test_summon_creates_bill_and_materializes_his_home(client, tmp_path, monkeypatch):
    spawned = {}
    monkeypatch.setattr(bill, "_live_names", lambda: set())
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")
    monkeypatch.setattr(
        bill, "create_tmux_session", lambda name, workdir, **kw: spawned.update(  # noqa: ARG005
            name=name, workdir=str(workdir)
        )
    )
    monkeypatch.setattr(bill, "_store_session", lambda **kw: None)  # noqa: ARG005

    body = client.post("/api/bill/summon").json()
    assert body == {
        "session": "bill",
        "workdir": str(tmp_path / "bill"),
        "existing": False,
    }
    assert (tmp_path / "bill" / "AGENTS.md").is_file()
    assert spawned["name"] == "bill"


def test_summon_returns_the_existing_session_without_respawning(client, tmp_path, monkeypatch):
    monkeypatch.setattr(bill, "_live_names", lambda: {"bill"})
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")

    def boom(*a, **kw):  # noqa: ARG001
        raise AssertionError("must not spawn a second Bill")

    monkeypatch.setattr(bill, "create_tmux_session", boom)
    body = client.post("/api/bill/summon").json()
    assert body["existing"] is True
    assert body["session"] == "bill"


def test_summon_renders_the_configured_personality(client, tmp_path, monkeypatch):
    monkeypatch.setattr(bill, "_live_names", lambda: set())
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")
    monkeypatch.setattr(bill, "create_tmux_session", lambda *a, **kw: None)  # noqa: ARG005
    monkeypatch.setattr(bill, "_store_session", lambda **kw: None)  # noqa: ARG005
    monkeypatch.setattr(bill, "_settings", lambda: {"bill": {"personality": "lumbergh"}})

    client.post("/api/bill/summon")
    assert (tmp_path / "bill" / "AGENTS.md").read_text() == bill.bill_bundle.render("lumbergh")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_bill_router.py -v`
Expected: FAIL — `AttributeError: module 'lumbergh.routers.bill' has no attribute 'bill_bundle'` / 404 on summon.

- [ ] **Step 3: Implement**

Add to `backend/lumbergh/routers/bill.py`:

```python
from lumbergh import bill as bill_bundle

BILL_SESSION = "bill"
BILL_PROVIDER = "pi"


def _settings() -> dict:
    from lumbergh.routers.settings import get_settings

    return get_settings()


def _personality() -> str:
    return _settings().get("bill", {}).get("personality") or bill_bundle.DEFAULT_PERSONALITY


@router.post("/summon")
def summon():
    workdir = bill_bundle.materialize(_personality(), home=bill_bundle.home())
    if BILL_SESSION in _live_names():
        return {"session": BILL_SESSION, "workdir": str(workdir), "existing": True}

    from lumbergh.providers import get_launch_command

    create_tmux_session(
        BILL_SESSION,
        workdir,
        launch_command=get_launch_command(BILL_PROVIDER, _settings().get("defaultAgent")),
    )
    _store_session(
        name=BILL_SESSION,
        workdir=str(workdir),
        description="Your engineering manager",
        type="direct",
        agent_provider=BILL_PROVIDER,
    )
    return {"session": BILL_SESSION, "workdir": str(workdir), "existing": False}
```

Also add the default to `_get_defaults()` in `backend/lumbergh/routers/settings.py`, next to `"defaultAgent"`:

```python
        "bill": {"personality": "professional"},
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_bill_router.py lumbergh/tests/test_settings*.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/routers/bill.py backend/lumbergh/routers/settings.py backend/lumbergh/tests/test_bill_router.py
git commit -m "feat(bill): summon endpoint materializing his home"
```

---

### Task 9: Idle-Bill nudge backstop

**Files:**
- Create: `backend/lumbergh/bill_nudge.py`
- Test: `backend/lumbergh/tests/test_bill_nudge.py`

**Interfaces:**
- Consumes: `fleet.snapshot` output rows, `tmux_pty.send_text`.
- Produces:
  - `should_nudge(bill_state: str, rows: list[dict]) -> bool` — True when Bill is `idle` and at least one of his tasks is live (`working`) or needs attention.
  - `nudge(send=send_text) -> bool` — sends one short wake line to the `bill` session; returns whether it sent.

Kept as a pure predicate plus a thin sender so it is testable without tmux or the monitor. Wiring it into the monitor's periodic pass is the last step.

- [ ] **Step 1: Write the failing tests**

Create `backend/lumbergh/tests/test_bill_nudge.py`:

```python
import pytest

from lumbergh import bill_nudge


@pytest.mark.parametrize(
    ("bill_state", "rows", "expected"),
    [
        ("idle", [{"state": "working", "unseen": False}], True),
        ("idle", [{"state": "blocked", "unseen": False}], True),
        ("idle", [{"state": "idle", "unseen": True}], True),
        ("idle", [], False),
        ("idle", [{"state": "idle", "unseen": False}], False),
        ("working", [{"state": "blocked", "unseen": False}], False),
        ("blocked", [{"state": "working", "unseen": False}], False),
    ],
)
def test_should_nudge(bill_state, rows, expected):
    assert bill_nudge.should_nudge(bill_state, rows) is expected


def test_nudge_sends_one_short_line():
    sent = {}
    assert bill_nudge.nudge(send=lambda name, text: sent.update(name=name, text=text) or True)
    assert sent["name"] == "bill"
    assert "lb fleet" in sent["text"]
    assert "\n" not in sent["text"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest lumbergh/tests/test_bill_nudge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lumbergh.bill_nudge'`.

- [ ] **Step 3: Implement**

Create `backend/lumbergh/bill_nudge.py`:

```python
"""Wake Bill when he goes quiet with live work.

A model that ends its turn without re-arming ``lb fleet --wait`` would stall the whole
crew silently. The server already knows both facts, so it can just tap him on the shoulder.
"""

from collections.abc import Callable

from lumbergh import fleet
from lumbergh.tmux_pty import send_text

BILL_SESSION = "bill"
_WAKE = "A task needs you — run `lb fleet` and handle it, then re-arm `lb fleet --wait`."


def should_nudge(bill_state: str, rows: list[dict]) -> bool:
    if bill_state != "idle":
        return False
    return any(r["state"] == "working" or fleet.needs_attention(r) for r in rows)


def nudge(send: Callable[[str, str], bool] = send_text) -> bool:
    return bool(send(BILL_SESSION, _WAKE))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest lumbergh/tests/test_bill_nudge.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Wire it into the monitor**

In `backend/lumbergh/idle_monitor.py`, add this method to `IdleMonitor` (the class at line 48):

```python
    def _maybe_nudge_bill(self) -> None:
        from lumbergh import bill_nudge
        from lumbergh.routers.bill import _fleet_rows

        state = self.get_state(bill_nudge.BILL_SESSION).value
        if state != "idle":
            self._bill_nudged = False
            return
        if self._bill_nudged:
            return
        if bill_nudge.should_nudge(state, _fleet_rows("bill")):
            bill_nudge.nudge()
            self._bill_nudged = True
```

The `_bill_nudged` flag stops it firing on every poll of one idle stretch; it resets as soon as Bill is doing anything.

Initialize it in `__init__` (line 61) alongside the other per-session dicts:

```python
        self._bill_nudged = False
```

Call it at the end of `_check_all_sessions` (line 167), immediately after the existing `await asyncio.gather(...)` block at line 188-191, wrapped so a nudge failure never breaks monitoring (`logger` is already defined at line 43):

```python
        try:
            self._maybe_nudge_bill()
        except Exception:
            logger.debug("bill nudge skipped", exc_info=True)
```

- [ ] **Step 6: Verify nothing regressed**

Run: `cd backend && uv run pytest lumbergh/tests/test_idle_monitor*.py lumbergh/tests/test_bill_nudge.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/lumbergh/bill_nudge.py backend/lumbergh/idle_monitor.py backend/lumbergh/tests/test_bill_nudge.py
git commit -m "feat(bill): nudge Bill awake when he idles with live work"
```

---

### Task 10: Summon Bill button

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx` (handler near `handleCreateScratch` at ~624; button in the header cluster at ~693)
- Test: manual (there is no Vitest suite for Dashboard; the UI E2E suite is Playwright/pytest-bdd and a new feature file is out of scope for v1)

**Interfaces:**
- Consumes: `POST /api/bill/summon` from Task 8, `getApiBase()`, `navigate` — all already in this file.

- [ ] **Step 1: Add the handler**

Directly after `handleCreateScratch` in `frontend/src/pages/Dashboard.tsx`:

```tsx
  const [summoningBill, setSummoningBill] = useState(false)

  const handleSummonBill = async () => {
    if (summoningBill) return
    setSummoningBill(true)
    try {
      const res = await fetch(`${getApiBase()}/bill/summon`, { method: 'POST' })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Failed to summon Bill')
      }
      const data = await res.json()
      navigate(`/session/${data.session}`)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to summon Bill')
    } finally {
      setSummoningBill(false)
    }
  }
```

Move the `useState` up with the other state declarations at the top of the component rather than leaving it mid-file — match the file's existing layout.

- [ ] **Step 2: Add the button**

In the header cluster, immediately before the `New Session` button (~line 704):

```tsx
          <Button
            onClick={handleSummonBill}
            disabled={summoningBill}
            title="Summon Bill, your manager"
            data-testid="summon-bill-btn"
            variant="secondary"
            size="sm"
          >
            <UserRoundCog size={16} />
          </Button>
```

Add `UserRoundCog` to the existing `lucide-react` import. (`secondary` is a real `Button` variant — see `frontend/src/components/ui/Button.tsx:3` — and it is the neutral one, which is what this button wants next to the primary `New Session`.)

- [ ] **Step 3: Verify it builds and lints**

Run: `./lint.sh`
Expected: exit 0.

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Manual check**

Start the backend and frontend (`./backend/start.sh`, `./frontend/start.sh`), open the dashboard, click the button. Expected: it navigates to the `bill` session, `~/.config/lumbergh/bill/AGENTS.md` exists, and the pane is running `pi`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat(bill): summon Bill from the dashboard"
```

---

### Task 11: Document the new commands in the lb skill

**Files:**
- Modify: `backend/lumbergh/skill/SKILL.md`
- Test: `backend/lumbergh/tests/test_lb_skill.py` (existing — `lb skill --check` pins the committed copy)

**Interfaces:**
- Consumes: nothing new. `agent_cli/skill.py` embeds `SKILL_MD`; `lb skill --check` compares the committed file to it.

**The source of truth is `SKILL_MD`, the module-level string in `backend/lumbergh/agent_cli/skill.py`.** `backend/lumbergh/skill/SKILL.md` is the committed copy, and `check()` compares them byte-for-byte (`skill.py:72-76`). So: edit `SKILL_MD`, then regenerate the committed copy.

- [ ] **Step 1: Add the two commands to `SKILL_MD`'s Commands list**

```markdown
- `lb fleet [--wait] [--timeout <s>] [--json]` — every task under way: task, repo, branch,
  kind, state, time in state, and whether it finished unseen. `--wait` blocks until a task
  needs you (blocked, errored, died, or finished unseen), so supervising costs nothing while
  you wait.
- `lb spawn --repo <path> --branch <b> --kind ship|scout --brief <file> [--new] [--base <b>]
  [--name <n>] [--agent <provider>] [--intent "..."]` — create an isolated worktree, start a
  worker in it, and hand it the brief. Unwinds itself if any step fails.
```

- [ ] **Step 2: Regenerate the committed copy**

```bash
cd backend && uv run lb skill > lumbergh/skill/SKILL.md
```

- [ ] **Step 3: Verify the pin**

Run: `cd backend && uv run lb skill --check`
Expected: `skill: committed SKILL.md is up to date`, exit 0.

Run: `cd backend && uv run pytest lumbergh/tests/test_lb_skill.py -v`
Expected: PASS.

If `--check` fails on a trailing newline (`lb skill` prints via `print()`, which appends one), fix it by writing the file from Python instead:

```bash
cd backend && uv run python -c "from lumbergh.agent_cli import skill; skill.committed_path().write_text(skill.SKILL_MD)"
```

- [ ] **Step 4: Commit**

```bash
git add backend/lumbergh/skill/SKILL.md backend/lumbergh/agent_cli/skill.py
git commit -m "docs(bill): document lb fleet and lb spawn in the lb skill"
```

---

### Task 12: E2E roundtrip

**Files:**
- Create: `test/e2e/test_bill_e2e.py`
- Test: itself

**Interfaces:**
- Consumes: the `client` and `test_repo_dir` fixtures from `test/e2e/conftest.py` (same as `test/e2e/test_worktrees_e2e.py`), and the endpoints from Tasks 3, 5, 8.

The worker's brief must live somewhere the *server* can read, since pytest may run on the host while the server runs in the VM. Summon first — that materializes `~/.config/lumbergh/bill/` server-side — then write the brief through a spawn call that points at a path under Bill's own `briefs/`, created by the server. To keep the test independent of host/VM filesystem sharing, it asserts spawn's fail-closed behavior for a brief the server cannot see, and drives the happy path with a brief the summon step created.

- [ ] **Step 1: Write the test**

Create `test/e2e/test_bill_e2e.py`:

```python
"""E2E for Bill's control surface: summon -> fleet -> spawn guard -> spawn -> reap.

The client only ever sends path strings; all filesystem work happens server-side, so this
works both against a local dev server and under ``test/e2e-vm.sh`` where the server lives
in the VM.
"""

import uuid


def test_summon_is_idempotent_and_materializes_bills_home(client):
    first = client.post("/api/bill/summon")
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["session"] == "bill"
    assert body["workdir"].endswith("/bill")

    second = client.post("/api/bill/summon")
    assert second.status_code == 200, second.text
    assert second.json()["existing"] is True


def test_fleet_reports_a_total_and_a_task_list(client):
    body = client.get("/api/bill/fleet").json()
    assert "total" in body
    assert isinstance(body["tasks"], list)


def test_fleet_wait_returns_on_timeout_without_erroring(client):
    body = client.get("/api/bill/fleet/wait", params={"timeout": 1, "origin": "bill"}).json()
    assert body["woke"] in (True, False)
    assert body["waited"] >= 0


def test_spawn_refuses_a_brief_the_server_cannot_read(client, test_repo_dir):
    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": test_repo_dir,
            "branch": f"e2e/bill-{uuid.uuid4().hex[:8]}",
            "kind": "ship",
            "brief_path": "/nonexistent/brief.md",
            "create_branch": True,
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"]["stage"] == "brief"


def test_spawn_refuses_an_unknown_kind(client, test_repo_dir):
    r = client.post(
        "/api/bill/spawn",
        json={
            "repo": test_repo_dir,
            "branch": f"e2e/bill-{uuid.uuid4().hex[:8]}",
            "kind": "wander",
            "brief_path": "/nonexistent/brief.md",
            "create_branch": True,
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"]["stage"] == "kind"


def test_spawn_then_fleet_then_reap_roundtrip(client, test_repo_dir):
    summon = client.post("/api/bill/summon").json()
    branch = f"e2e/bill-{uuid.uuid4().hex[:8]}"
    name = f"e2e-bill-{uuid.uuid4().hex[:6]}"
    brief_path = f"{summon['workdir']}/briefs/{name}.md"
    created_path = None

    client.post(
        "/api/bill/brief",
        json={"path": brief_path, "body": "# Task: e2e smoke\n\nDo nothing.\n"},
    )

    try:
        r = client.post(
            "/api/bill/spawn",
            json={
                "repo": test_repo_dir,
                "branch": branch,
                "kind": "scout",
                "brief_path": brief_path,
                "name": name,
                "create_branch": True,
            },
        )
        assert r.status_code == 200, r.text
        created_path = r.json()["path"]
        assert r.json()["session"] == name

        tasks = client.get("/api/bill/fleet", params={"origin": "bill"}).json()["tasks"]
        row = next((t for t in tasks if t["task"] == name), None)
        assert row is not None, f"spawned task missing from fleet: {tasks}"
        assert row["kind"] == "scout"
    finally:
        client.delete(f"/api/sessions/{name}")
        if created_path:
            client.post(
                "/api/worktrees/reap",
                json={"path": created_path, "force": True, "rm_branch": True},
            )
```

- [ ] **Step 2: Add the brief-write endpoint the test needs**

The roundtrip needs the server to create a brief file inside Bill's home. Bill himself writes briefs with his own file tools, but the E2E client cannot, so add a small endpoint to `backend/lumbergh/routers/bill.py` — it is genuinely useful (it is how a future UI would show a brief) and it keeps the write inside Bill's home:

```python
class BriefBody(BaseModel):
    path: str
    body: str


@router.post("/brief")
def write_brief(body: BriefBody):
    """Write a brief, refusing any path outside Bill's home."""
    target = Path(body.path).expanduser().resolve()
    home_dir = bill_bundle.home().resolve()
    if not target.is_relative_to(home_dir / "briefs"):
        raise _fail("path", f"{target} is outside {home_dir / 'briefs'}", "write under briefs/")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body.body)
    return {"path": str(target)}
```

And a unit test in `backend/lumbergh/tests/test_bill_router.py`:

```python
def test_write_brief_refuses_a_path_outside_bills_home(client, tmp_path, monkeypatch):
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")
    r = client.post("/api/bill/brief", json={"path": str(tmp_path / "escape.md"), "body": "x"})
    assert r.status_code == 400
    assert r.json()["detail"]["stage"] == "path"


def test_write_brief_accepts_a_path_inside_briefs(client, tmp_path, monkeypatch):
    monkeypatch.setattr(bill.bill_bundle, "home", lambda: tmp_path / "bill")
    (tmp_path / "bill" / "briefs").mkdir(parents=True)
    r = client.post(
        "/api/bill/brief", json={"path": str(tmp_path / "bill" / "briefs" / "w.md"), "body": "hi"}
    )
    assert r.status_code == 200
    assert (tmp_path / "bill" / "briefs" / "w.md").read_text() == "hi"
```

- [ ] **Step 3: Run the unit tests**

Run: `cd backend && uv run pytest lumbergh/tests/test_bill_router.py -v`
Expected: PASS.

- [ ] **Step 4: Run the E2E suite**

Run: `./test/e2e-vm.sh`
Expected: all E2E tests pass, including `test_bill_e2e.py`.

If the roundtrip fails because the spawned `pi`/agent binary is absent in the VM, pass `"agent_provider": "claude-code"` in the spawn body — the test only needs *a* session to exist, not a working agent. If no agent binary exists in the VM at all, keep the guard tests and mark the roundtrip with `pytest.mark.skipif` on a documented condition rather than deleting it; do not leave it silently failing.

- [ ] **Step 5: Commit**

```bash
git add test/e2e/test_bill_e2e.py backend/lumbergh/routers/bill.py backend/lumbergh/tests/test_bill_router.py
git commit -m "test(bill): e2e summon/fleet/spawn/reap roundtrip"
```

---

### Task 13: Full verification and the manual smoke

**Files:** none (verification only)

- [ ] **Step 1: Full backend suite**

Run: `cd backend && uv run pytest`
Expected: all PASS. Fix any regression before continuing.

- [ ] **Step 2: Lint**

Run: `./lint.sh`
Expected: exit 0.

- [ ] **Step 3: Full E2E**

Run: `./test/e2e-vm.sh`
Expected: all PASS.

- [ ] **Step 4: Manual smoke with a real Bill**

This is the part tests cannot cover: whether a small local model actually follows the bundle. Do it and write down what happened.

1. Set the personality: `PATCH /api/settings` with `{"bill": {"personality": "professional"}}` (or leave the default).
2. Click **Summon Bill** on the dashboard.
3. Give him one real request in his terminal, e.g. "the flaky login test in <repo> keeps failing — deal with it."
4. Observe and record: Did he resolve the repo? Did he choose scout vs ship sensibly? Did he write a brief and call `lb spawn` without hallucinating flags? Did he re-arm `lb fleet --wait`? Did he report an outcome rather than mechanics?
5. Flip `bill.personality` to `lumbergh`, re-summon, and confirm the flair appears in his chat and **not** in the brief he writes.

- [ ] **Step 5: Record the findings**

Append what you observed to the spec under a new `## Smoke results` heading — especially any instruction the model ignored, since that is the input to the next iteration of the bundle.

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/specs/2026-07-28-bill-orchestrator-design.md
git commit -m "docs(bill): record first smoke run against a local model"
```
