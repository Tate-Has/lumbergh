# Worktree Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make git worktrees a first-class, tracked, self-linking resource in Lumbergh, driven from both the web UI and a new `lb worktree` CLI.

**Architecture:** A single core module `backend/lumbergh/worktrees.py` holds all lifecycle logic (config, location, linking, registry, reconcile, reap) on top of the existing `git_utils` primitives. A REST router exposes it; the web UI and the `lb worktree` CLI both consume that router (the CLI is a thin HTTP client, exactly like the existing `lb` commands). Git's `worktree list` is the source of truth for existence; a global TinyDB store (`~/.config/lumbergh/worktrees.json`) is a metadata overlay reconciled on read.

**Tech Stack:** Python 3.11+, FastAPI, TinyDB, GitPython (via existing `git_utils`), `tomllib` (stdlib), pytest; React + TypeScript + TanStack Query for the panel.

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-07-28-worktree-lifecycle-design.md` — this plan implements it verbatim.
- Registry store path: `~/.config/lumbergh/worktrees.json` (via `CONFIG_DIR`, respecting `LUMBERGH_DATA_DIR`).
- Dotfile: `.lumbergh.toml` at repo root, `[worktree]` table. When present, its `links` list is authoritative and auto-detection is skipped for that repo.
- Auto-detect default link set (no dotfile): `.venv`, `node_modules`, `.env`, `.env.local`, `.direnv`.
- Link safety rules (always): link only if the path exists in the parent, is git-ignored in the worktree, and does not already exist in the worktree.
- Link modes: `symlink` (default) or `copy` (reflink via `cp --reflink=auto` where available, else plain copy).
- Location resolution order: dotfile `base_dir` → global setting `worktree.base_dir` → sibling default `{repo}-worktrees/{branch}`. With a `base_dir`, path is `<base_dir>/<repo-name>/<branch>`.
- Reap is explicit and guarded: refuse if the worktree has uncommitted changes OR unpushed commits, unless `force=True`. Never auto-reap.
- `created_at` is stamped by the backend at record time (never inside any workflow/subagent script).
- Reuse existing helpers; do not reimplement git plumbing. Follow the AXI/TOON output conventions already used in `agent_cli/main.py`.
- Run `./lint.sh` before considering any task done.

---

### Task 1: Config parsing + location resolution

**Files:**
- Create: `backend/lumbergh/worktrees.py`
- Modify: `backend/lumbergh/routers/settings.py` (add `worktree.base_dir` default near `_get_defaults`)
- Test: `backend/lumbergh/tests/test_worktrees.py`

**Interfaces:**
- Consumes: `git_utils.get_worktree_container_path(repo: Path) -> Path`, `git_utils.sanitize_branch_for_path(branch: str) -> str`.
- Produces:
  - `@dataclass LinkSpec: path: str; mode: Literal["symlink","copy"]`
  - `@dataclass WorktreeProjectConfig: links: list[LinkSpec] | None; post_create: list[str]; base_dir: str | None` (`links is None` means "no dotfile links table → auto-detect")
  - `parse_worktree_config(repo: Path) -> WorktreeProjectConfig`
  - `resolve_worktree_dir(repo: Path, branch: str, cfg: WorktreeProjectConfig, global_base_dir: str | None) -> Path`

- [ ] **Step 1: Write the failing test**

```python
# backend/lumbergh/tests/test_worktrees.py
from pathlib import Path

from lumbergh import worktrees


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_parse_config_absent_dotfile_yields_autodetect(tmp_path):
    cfg = worktrees.parse_worktree_config(tmp_path)
    assert cfg.links is None
    assert cfg.post_create == []
    assert cfg.base_dir is None


def test_parse_config_reads_links_modes_hooks_and_basedir(tmp_path):
    _write(
        tmp_path / ".lumbergh.toml",
        '[worktree]\n'
        'base_dir = "~/wt"\n'
        'links = [{ path = ".venv", mode = "copy" }, "node_modules"]\n'
        'post_create = ["uv sync"]\n',
    )
    cfg = worktrees.parse_worktree_config(tmp_path)
    assert cfg.base_dir == "~/wt"
    assert cfg.post_create == ["uv sync"]
    assert cfg.links == [
        worktrees.LinkSpec(path=".venv", mode="copy"),
        worktrees.LinkSpec(path="node_modules", mode="symlink"),
    ]


def test_resolve_dir_sibling_default(tmp_path):
    repo = tmp_path / "app"
    repo.mkdir()
    cfg = worktrees.parse_worktree_config(repo)
    out = worktrees.resolve_worktree_dir(repo, "feat/x", cfg, global_base_dir=None)
    assert out == tmp_path / "app-worktrees" / "feat-x"


def test_resolve_dir_global_base_dir(tmp_path):
    repo = tmp_path / "app"
    repo.mkdir()
    cfg = worktrees.parse_worktree_config(repo)
    out = worktrees.resolve_worktree_dir(repo, "feat/x", cfg, global_base_dir=str(tmp_path / "central"))
    assert out == tmp_path / "central" / "app" / "feat-x"


def test_resolve_dir_dotfile_base_dir_wins_over_global(tmp_path):
    repo = tmp_path / "app"
    repo.mkdir()
    _write(repo / ".lumbergh.toml", f'[worktree]\nbase_dir = "{tmp_path / "proj"}"\n')
    cfg = worktrees.parse_worktree_config(repo)
    out = worktrees.resolve_worktree_dir(repo, "feat/x", cfg, global_base_dir=str(tmp_path / "central"))
    assert out == tmp_path / "proj" / "app" / "feat-x"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktrees.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lumbergh.worktrees'` (or `AttributeError`).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/lumbergh/worktrees.py
"""First-class worktree lifecycle: config, location, linking, registry, reconcile, reap.

Git's `worktree list` is the source of truth for existence; this module keeps a
thin metadata overlay (see registry helpers) reconciled on read.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from lumbergh.git_utils import get_worktree_container_path, sanitize_branch_for_path

LinkMode = Literal["symlink", "copy"]
DEFAULT_LINKS = [".venv", "node_modules", ".env", ".env.local", ".direnv"]


@dataclass(frozen=True)
class LinkSpec:
    path: str
    mode: LinkMode = "symlink"


@dataclass
class WorktreeProjectConfig:
    links: list[LinkSpec] | None = None  # None => auto-detect
    post_create: list[str] = field(default_factory=list)
    base_dir: str | None = None


def _coerce_link(entry: object) -> LinkSpec:
    if isinstance(entry, str):
        return LinkSpec(path=entry, mode="symlink")
    if isinstance(entry, dict) and "path" in entry:
        mode = entry.get("mode", "symlink")
        if mode not in ("symlink", "copy"):
            raise ValueError(f"invalid link mode: {mode!r}")
        return LinkSpec(path=str(entry["path"]), mode=mode)
    raise ValueError(f"invalid link entry: {entry!r}")


def parse_worktree_config(repo: Path) -> WorktreeProjectConfig:
    dotfile = repo / ".lumbergh.toml"
    if not dotfile.is_file():
        return WorktreeProjectConfig()
    data = tomllib.loads(dotfile.read_text())
    wt = data.get("worktree", {})
    raw_links = wt.get("links")
    links = [_coerce_link(e) for e in raw_links] if raw_links is not None else None
    return WorktreeProjectConfig(
        links=links,
        post_create=list(wt.get("post_create", [])),
        base_dir=wt.get("base_dir"),
    )


def resolve_worktree_dir(
    repo: Path, branch: str, cfg: WorktreeProjectConfig, global_base_dir: str | None
) -> Path:
    leaf = sanitize_branch_for_path(branch)
    base = cfg.base_dir or global_base_dir
    if base:
        return Path(base).expanduser() / repo.name / leaf
    return get_worktree_container_path(repo) / leaf
```

Also add the setting default in `settings.py`'s defaults builder (the dict returned by `_get_defaults`), so `get_settings()["worktree"]["base_dir"]` exists:

```python
# inside the defaults dict in backend/lumbergh/routers/settings.py
"worktree": {"base_dir": ""},
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktrees.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/worktrees.py backend/lumbergh/tests/test_worktrees.py backend/lumbergh/routers/settings.py
git commit -m "feat(worktree): dotfile config parsing + location resolution"
```

---

### Task 2: Link planning + application

**Files:**
- Modify: `backend/lumbergh/worktrees.py`
- Test: `backend/lumbergh/tests/test_worktrees.py`

**Interfaces:**
- Consumes: `LinkSpec`, `WorktreeProjectConfig`, `DEFAULT_LINKS` from Task 1; `git_utils.get_repo`.
- Produces:
  - `plan_links(repo: Path, worktree: Path, cfg: WorktreeProjectConfig) -> list[LinkSpec]` — resolves auto-detect vs dotfile and applies safety filters, returning only the specs that WILL be linked.
  - `apply_links(repo: Path, worktree: Path, specs: list[LinkSpec]) -> list[dict]` — performs the links, returns records `[{"path","mode"}]` actually applied.
  - `_is_git_ignored(repo: Path, rel: str) -> bool` (internal)

- [ ] **Step 1: Write the failing test**

```python
# append to backend/lumbergh/tests/test_worktrees.py
import subprocess


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@t.t")
    _git(path, "config", "user.name", "t")
    (path / ".gitignore").write_text(".venv/\nnode_modules/\n.env\n")
    (path / "README").write_text("x")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "init")
    return path


def test_plan_links_autodetect_only_existing_and_ignored(tmp_path):
    repo = _init_repo(tmp_path / "app")
    (repo / ".venv").mkdir()
    (repo / ".env").write_text("SECRET=1")
    # node_modules absent -> skipped; README tracked -> never a candidate anyway
    cfg = worktrees.parse_worktree_config(repo)
    wt = tmp_path / "wt"
    wt.mkdir()
    planned = {s.path for s in worktrees.plan_links(repo, wt, cfg)}
    assert planned == {".venv", ".env"}


def test_plan_links_skips_when_already_present_in_worktree(tmp_path):
    repo = _init_repo(tmp_path / "app")
    (repo / ".venv").mkdir()
    cfg = worktrees.parse_worktree_config(repo)
    wt = tmp_path / "wt"
    (wt / ".venv").mkdir(parents=True)  # already there
    assert worktrees.plan_links(repo, wt, cfg) == []


def test_apply_links_symlink_and_copy(tmp_path):
    repo = _init_repo(tmp_path / "app")
    (repo / ".venv").mkdir()
    (repo / ".venv" / "marker").write_text("v")
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "pkg").write_text("n")
    _write(
        repo / ".lumbergh.toml",
        '[worktree]\nlinks = [{ path = ".venv", mode = "copy" }, "node_modules"]\n',
    )
    cfg = worktrees.parse_worktree_config(repo)
    wt = tmp_path / "wt"
    wt.mkdir()
    applied = worktrees.apply_links(repo, wt, worktrees.plan_links(repo, wt, cfg))
    assert {r["path"]: r["mode"] for r in applied} == {".venv": "copy", "node_modules": "symlink"}
    assert (wt / "node_modules").is_symlink()
    assert not (wt / ".venv").is_symlink()
    assert (wt / ".venv" / "marker").read_text() == "v"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktrees.py -k "plan_links or apply_links" -v`
Expected: FAIL with `AttributeError: module 'lumbergh.worktrees' has no attribute 'plan_links'`.

- [ ] **Step 3: Write minimal implementation**

```python
# append to backend/lumbergh/worktrees.py
import shutil
import subprocess

from lumbergh.git_utils import get_repo  # add to existing imports at top


def _is_git_ignored(repo: Path, rel: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "check-ignore", "-q", rel],
        capture_output=True,
    )
    return result.returncode == 0


def plan_links(repo: Path, worktree: Path, cfg: WorktreeProjectConfig) -> list[LinkSpec]:
    specs = cfg.links if cfg.links is not None else [LinkSpec(p) for p in DEFAULT_LINKS]
    planned: list[LinkSpec] = []
    for spec in specs:
        src = repo / spec.path
        dst = worktree / spec.path
        if not src.exists():
            continue
        if dst.exists() or dst.is_symlink():
            continue
        if not _is_git_ignored(repo, spec.path):
            continue
        planned.append(spec)
    return planned


def _reflink_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["cp", "-a", "--reflink=auto", str(src), str(dst)], capture_output=True
    )
    if result.returncode != 0:
        if src.is_dir():
            shutil.copytree(src, dst, symlinks=True)
        else:
            shutil.copy2(src, dst)


def apply_links(repo: Path, worktree: Path, specs: list[LinkSpec]) -> list[dict]:
    applied: list[dict] = []
    for spec in specs:
        src = (repo / spec.path).resolve()
        dst = worktree / spec.path
        dst.parent.mkdir(parents=True, exist_ok=True)
        if spec.mode == "symlink":
            dst.symlink_to(src)
        else:
            _reflink_copy(src, dst)
        applied.append({"path": spec.path, "mode": spec.mode})
    return applied
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktrees.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/worktrees.py backend/lumbergh/tests/test_worktrees.py
git commit -m "feat(worktree): link planning + symlink/copy application with safety rules"
```

---

### Task 3: Registry store (metadata overlay)

**Files:**
- Modify: `backend/lumbergh/db_utils.py` (add `get_worktrees_db`)
- Modify: `backend/lumbergh/worktrees.py`
- Test: `backend/lumbergh/tests/test_worktrees.py`

**Interfaces:**
- Consumes: `db_utils.get_worktrees_db() -> TinyDB` (new), `db_utils.CONFIG_DIR`.
- Produces:
  - `record_worktree(path, parent_repo, branch, created_at, session=None, links_applied=None, task_intent=None) -> dict`
  - `get_entry(path: Path) -> dict | None`
  - `remove_entry(path: Path) -> None`
  - `all_entries() -> list[dict]`
  Registry rows are keyed by the absolute worktree path string (`str(Path(path).resolve())`).

- [ ] **Step 1: Write the failing test**

```python
# append to backend/lumbergh/tests/test_worktrees.py
def test_registry_record_get_remove(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMBERGH_DATA_DIR", str(tmp_path / "cfg"))
    from lumbergh import db_utils
    import importlib

    importlib.reload(db_utils)
    importlib.reload(worktrees)

    wt = tmp_path / "app-worktrees" / "feat-x"
    worktrees.record_worktree(
        wt, parent_repo=tmp_path / "app", branch="feat/x",
        created_at="2026-07-28T00:00:00Z", session="kb-1", links_applied=[{"path": ".venv", "mode": "copy"}],
    )
    row = worktrees.get_entry(wt)
    assert row["branch"] == "feat/x"
    assert row["associated_session"] == "kb-1"
    assert row["created_at"] == "2026-07-28T00:00:00Z"
    assert [r["path"] for r in worktrees.all_entries()] == [str(wt.resolve())]
    worktrees.remove_entry(wt)
    assert worktrees.get_entry(wt) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktrees.py -k registry -v`
Expected: FAIL — `get_worktrees_db` / `record_worktree` undefined.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/lumbergh/db_utils.py — add beside get_global_db
def get_worktrees_db() -> TinyDB:
    """TinyDB instance for the worktree metadata overlay (reconciled with git)."""
    return _get_cached_db(CONFIG_DIR / "worktrees.json")
```

```python
# append to backend/lumbergh/worktrees.py
from tinydb import Query

from lumbergh.db_utils import get_worktrees_db


def _key(path: Path) -> str:
    return str(Path(path).resolve())


def record_worktree(
    path: Path,
    parent_repo: Path,
    branch: str,
    created_at: str,
    session: str | None = None,
    links_applied: list[dict] | None = None,
    task_intent: str | None = None,
) -> dict:
    row = {
        "path": _key(path),
        "parent_repo": str(Path(parent_repo).resolve()),
        "branch": branch,
        "created_at": created_at,
        "associated_session": session,
        "links_applied": links_applied or [],
        "task_intent": task_intent,
    }
    db = get_worktrees_db()
    db.upsert(row, Query().path == row["path"])
    return row


def get_entry(path: Path) -> dict | None:
    return get_worktrees_db().get(Query().path == _key(path))


def remove_entry(path: Path) -> None:
    get_worktrees_db().remove(Query().path == _key(path))


def all_entries() -> list[dict]:
    return get_worktrees_db().all()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktrees.py -k registry -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/db_utils.py backend/lumbergh/worktrees.py backend/lumbergh/tests/test_worktrees.py
git commit -m "feat(worktree): registry metadata store (global worktrees.json)"
```

---

### Task 4: Reconciliation (git ∪ registry ∪ session state)

**Files:**
- Modify: `backend/lumbergh/worktrees.py`
- Test: `backend/lumbergh/tests/test_worktrees.py`

**Interfaces:**
- Consumes: `git_utils.list_worktrees(repo) -> list[WorktreeInfo]` (has `.path: Path`, `.branch: str`); registry helpers from Task 3.
- Produces:
  - `reconcile(repo: Path, live_sessions: dict[str, dict]) -> list[dict]` where `live_sessions` maps session-name → meta (`{"workdir","agent_provider"}`). Returns rows `{path, repo, branch, session, agent, state}` with `state ∈ {"active","orphan"}`. Rows in the registry but absent from git are pruned (removed) and omitted.
  - `_live_session_for(worktree: Path, live_sessions) -> tuple[str|None, str|None]` (name, agent) — a session owns a worktree when its `workdir` resolves to the worktree path.

The router (Task 6) supplies `live_sessions` from `get_stored_sessions()` filtered by `list_tmux_sessions()`; the core stays free of tmux/HTTP for testability.

- [ ] **Step 1: Write the failing test**

```python
# append to backend/lumbergh/tests/test_worktrees.py
def test_reconcile_active_orphan_and_stale_prune(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMBERGH_DATA_DIR", str(tmp_path / "cfg"))
    from lumbergh import db_utils
    import importlib

    importlib.reload(db_utils)
    importlib.reload(worktrees)

    repo = _init_repo(tmp_path / "app")
    active = tmp_path / "app-worktrees" / "active"
    orphan = tmp_path / "app-worktrees" / "orphan"
    _git(repo, "worktree", "add", "-q", "-b", "active", str(active))
    _git(repo, "worktree", "add", "-q", "-b", "orphan", str(orphan))

    now = "2026-07-28T00:00:00Z"
    worktrees.record_worktree(active, repo, "active", now, session="kb-1")
    worktrees.record_worktree(orphan, repo, "orphan", now, session="kb-gone")
    worktrees.record_worktree(tmp_path / "ghost", repo, "ghost", now)  # not in git -> stale

    live = {"kb-1": {"workdir": str(active), "agent_provider": "claude"}}
    rows = worktrees.reconcile(repo, live)

    by_branch = {r["branch"]: r for r in rows}
    assert by_branch["active"]["state"] == "active"
    assert by_branch["active"]["session"] == "kb-1"
    assert by_branch["active"]["agent"] == "claude"
    assert by_branch["orphan"]["state"] == "orphan"
    assert by_branch["orphan"]["session"] is None
    assert "ghost" not in by_branch
    assert worktrees.get_entry(tmp_path / "ghost") is None  # pruned
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktrees.py -k reconcile -v`
Expected: FAIL — `reconcile` undefined.

- [ ] **Step 3: Write minimal implementation**

```python
# append to backend/lumbergh/worktrees.py
from lumbergh.git_utils import list_worktrees


def _live_session_for(worktree: Path, live_sessions: dict[str, dict]) -> tuple[str | None, str | None]:
    target = _key(worktree)
    for name, meta in live_sessions.items():
        wd = meta.get("workdir")
        if wd and str(Path(wd).resolve()) == target:
            return name, meta.get("agent_provider")
    return None, None


def reconcile(repo: Path, live_sessions: dict[str, dict]) -> list[dict]:
    git_worktrees = {_key(wt.path): wt for wt in list_worktrees(repo)}

    # Prune stale registry rows (recorded here but gone from git).
    for row in all_entries():
        if row["parent_repo"] == _key(repo) and row["path"] not in git_worktrees:
            remove_entry(Path(row["path"]))

    rows: list[dict] = []
    for key, wt in git_worktrees.items():
        if _key(repo) == key:
            continue  # the main working tree itself
        entry = get_entry(wt.path) or {}
        session, agent = _live_session_for(wt.path, live_sessions)
        rows.append(
            {
                "path": key,
                "repo": repo.name,
                "branch": wt.branch or entry.get("branch"),
                "session": session,
                "agent": agent,
                "state": "active" if session else "orphan",
            }
        )
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktrees.py -k reconcile -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/worktrees.py backend/lumbergh/tests/test_worktrees.py
git commit -m "feat(worktree): reconcile git worktrees with registry + session state"
```

---

### Task 5: Guarded reap + create orchestration

**Files:**
- Modify: `backend/lumbergh/git_utils.py` (add `count_unpushed_commits`)
- Modify: `backend/lumbergh/worktrees.py`
- Test: `backend/lumbergh/tests/test_worktrees.py`

**Interfaces:**
- Consumes: `git_utils.create_worktree`, `git_utils.remove_worktree`, `git_utils.get_porcelain_status(cwd) -> list[dict]`, and new `git_utils.count_unpushed_commits(cwd) -> int`.
- Produces:
  - `create(repo, branch, *, created_at, create_branch=False, base_branch=None, session=None, task_intent=None, global_base_dir=None) -> dict` — full orchestration: resolve dir, git-create, apply links, run `post_create`, record registry. Returns `{"path": str, "links_applied": [...]}` or `{"error": str}`.
  - `reap(worktree: Path, *, force=False, rm_branch=False) -> dict` — guard on dirty/unpushed, then `remove_worktree`, `remove_entry`, optional branch delete. Returns `{"status":"removed"}` or `{"error": str, "reason": "dirty"|"unpushed"|...}`.

- [ ] **Step 1: Write the failing test**

```python
# append to backend/lumbergh/tests/test_worktrees.py
def test_reap_refuses_dirty_then_force_removes(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMBERGH_DATA_DIR", str(tmp_path / "cfg"))
    from lumbergh import db_utils
    import importlib

    importlib.reload(db_utils)
    importlib.reload(worktrees)

    repo = _init_repo(tmp_path / "app")
    now = "2026-07-28T00:00:00Z"
    created = worktrees.create(repo, "feat/x", created_at=now, create_branch=True)
    wt = Path(created["path"])
    (wt / "dirty.txt").write_text("uncommitted")

    refused = worktrees.reap(wt, force=False)
    assert refused["error"]
    assert refused["reason"] == "dirty"
    assert wt.exists()

    forced = worktrees.reap(wt, force=True)
    assert forced["status"] == "removed"
    assert not wt.exists()
    assert worktrees.get_entry(wt) is None


def test_create_applies_links_and_records(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMBERGH_DATA_DIR", str(tmp_path / "cfg"))
    from lumbergh import db_utils
    import importlib

    importlib.reload(db_utils)
    importlib.reload(worktrees)

    repo = _init_repo(tmp_path / "app")
    (repo / ".venv").mkdir()
    (repo / ".venv" / "m").write_text("v")
    now = "2026-07-28T00:00:00Z"
    created = worktrees.create(repo, "feat/y", created_at=now, create_branch=True, session="kb-9")
    wt = Path(created["path"])
    assert (wt / ".venv").is_symlink()
    entry = worktrees.get_entry(wt)
    assert entry["associated_session"] == "kb-9"
    assert entry["created_at"] == now
    assert {r["path"] for r in entry["links_applied"]} == {".venv"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktrees.py -k "reap or create_applies" -v`
Expected: FAIL — `create` / `reap` / `count_unpushed_commits` undefined.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/lumbergh/git_utils.py — add near the worktree helpers
def count_unpushed_commits(cwd: Path) -> int:
    """Count commits reachable from any local branch but no remote branch.

    This is the reap guard's "unpushed work" check. With no remotes at all,
    every local commit counts as unpushed, so a never-pushed worktree is
    correctly protected from silent loss. Falls back to 0 on git error.
    """
    try:
        repo = get_repo(cwd)
    except InvalidGitRepositoryError:
        return 0
    try:
        out = repo.git.rev_list("--count", "--branches", "--not", "--remotes")
        return int(out.strip() or "0")
    except GitCommandError:
        return 0
```

```python
# append to backend/lumbergh/worktrees.py
from lumbergh.git_utils import (
    count_unpushed_commits,
    create_worktree as _git_create_worktree,
    get_porcelain_status,
    remove_worktree as _git_remove_worktree,
)

# NOTE: do not import get_settings here. The core stays free of the settings/router
# layer; the caller passes `global_base_dir` in (the router reads the setting).


def create(
    repo: Path,
    branch: str,
    *,
    created_at: str,
    create_branch: bool = False,
    base_branch: str | None = None,
    session: str | None = None,
    task_intent: str | None = None,
    global_base_dir: str | None = None,
) -> dict:
    cfg = parse_worktree_config(repo)
    dest = resolve_worktree_dir(repo, branch, cfg, global_base_dir)
    result = _git_create_worktree(
        repo, branch, worktree_path=dest, create_branch=create_branch, base_branch=base_branch
    )
    if "error" in result:
        return result
    wt = Path(result["path"])
    applied = apply_links(repo, wt, plan_links(repo, wt, cfg))
    for cmd in cfg.post_create:
        subprocess.run(cmd, shell=True, cwd=wt, check=False)
    record_worktree(
        wt, repo, branch, created_at,
        session=session, links_applied=applied, task_intent=task_intent,
    )
    return {"path": str(wt), "links_applied": applied}


def reap(worktree: Path, *, force: bool = False, rm_branch: bool = False) -> dict:
    if not force:
        if get_porcelain_status(worktree):
            return {"error": "worktree has uncommitted changes", "reason": "dirty"}
        if count_unpushed_commits(worktree) > 0:
            return {"error": "worktree has unpushed commits", "reason": "unpushed"}
    entry = get_entry(worktree)
    parent = Path(entry["parent_repo"]) if entry else worktree
    branch = entry.get("branch") if entry else None
    result = _git_remove_worktree(parent, worktree, force=force)
    if "error" in result:
        return result
    remove_entry(worktree)
    if rm_branch and branch:
        try:
            get_repo(parent).git.branch("-D", branch)
        except GitCommandError:
            pass
    return {"status": "removed", "path": str(worktree)}
```

Note: if importing `get_settings` at module top causes a circular import, move that import inside the router (Task 6) and pass `global_base_dir` in from there — the core `create()` already accepts it as a parameter, so the core module need not import settings at all. Prefer that: **do not** import `get_settings` in `worktrees.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktrees.py -v`
Expected: PASS (all worktrees tests).

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/git_utils.py backend/lumbergh/worktrees.py backend/lumbergh/tests/test_worktrees.py
git commit -m "feat(worktree): guarded reap + create orchestration (links + hooks + registry)"
```

---

### Task 6: REST router + adopt/link/unlink

**Files:**
- Create: `backend/lumbergh/routers/worktrees.py`
- Modify: `backend/lumbergh/main.py` (register router)
- Modify: `backend/lumbergh/worktrees.py` (add `adopt`, `unlink_path`)
- Test: `backend/lumbergh/tests/test_worktree_router.py`

**Interfaces:**
- Consumes: core functions from Tasks 1–5; `tmux_pty.list_tmux_sessions()`, `routers.sessions.get_stored_sessions()`, `routers.settings.get_settings()`.
- Produces REST endpoints (all under `/api/worktrees`):
  - `POST /api/worktrees` body `{repo, branch, create_branch?, base_branch?, session?, task_intent?}` → `create`
  - `GET  /api/worktrees?repo=<path>` → `{"worktrees": reconcile(...)}`
  - `POST /api/worktrees/reap` body `{path, force?, rm_branch?}` → `reap`
  - `POST /api/worktrees/adopt` body `{path, session?}` → `adopt`
  - `POST /api/worktrees/link` body `{path}` → re-apply links; `POST /api/worktrees/unlink` body `{path}` → promote symlink→copy
- Core additions:
  - `adopt(worktree: Path, created_at: str, session: str | None) -> dict` — derive parent_repo via `git rev-parse --git-common-dir`, record entry.
  - `unlink_path(worktree: Path, rel: str) -> dict` — replace a symlink with a real copy of its target.

- [ ] **Step 1: Write the failing test**

```python
# backend/lumbergh/tests/test_worktree_router.py
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMBERGH_DATA_DIR", str(tmp_path / "cfg"))
    import importlib
    from lumbergh import db_utils, worktrees
    from lumbergh.routers import worktrees as wt_router

    importlib.reload(db_utils)
    importlib.reload(worktrees)
    importlib.reload(wt_router)
    monkeypatch.setattr(wt_router, "get_stored_sessions", lambda: {})
    monkeypatch.setattr(wt_router, "list_tmux_sessions", lambda: [])
    from lumbergh.main import app

    return TestClient(app)


def test_create_list_reap_roundtrip(client, tmp_path):
    from lumbergh.tests.test_worktrees import _init_repo

    repo = _init_repo(tmp_path / "app")
    r = client.post("/api/worktrees", json={"repo": str(repo), "branch": "feat/x", "create_branch": True})
    assert r.status_code == 200, r.text
    wt_path = r.json()["path"]

    listed = client.get("/api/worktrees", params={"repo": str(repo)}).json()["worktrees"]
    assert any(w["path"] == str(Path(wt_path).resolve()) for w in listed)
    assert listed[0]["state"] == "orphan"  # no live session in this test

    reaped = client.post("/api/worktrees/reap", json={"path": wt_path, "force": True})
    assert reaped.status_code == 200
    assert reaped.json()["status"] == "removed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktree_router.py -v`
Expected: FAIL — router module missing / route 404.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/lumbergh/routers/worktrees.py
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from lumbergh import worktrees
from lumbergh.routers.sessions import get_stored_sessions
from lumbergh.routers.settings import get_settings
from lumbergh.tmux_pty import list_tmux_sessions

router = APIRouter(prefix="/api/worktrees", tags=["worktrees"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _live_sessions() -> dict[str, dict]:
    alive = {s["name"] for s in list_tmux_sessions()}
    return {n: m for n, m in get_stored_sessions().items() if n in alive}


def _global_base_dir() -> str | None:
    return get_settings().get("worktree", {}).get("base_dir") or None


class CreateBody(BaseModel):
    repo: str
    branch: str
    create_branch: bool = False
    base_branch: str | None = None
    session: str | None = None
    task_intent: str | None = None


class ReapBody(BaseModel):
    path: str
    force: bool = False
    rm_branch: bool = False


class AdoptBody(BaseModel):
    path: str
    session: str | None = None


class PathBody(BaseModel):
    path: str


@router.post("")
def create(body: CreateBody):
    return worktrees.create(
        Path(body.repo).expanduser(), body.branch, created_at=_now(),
        create_branch=body.create_branch, base_branch=body.base_branch,
        session=body.session, task_intent=body.task_intent,
        global_base_dir=_global_base_dir(),
    )


@router.get("")
def ls(repo: str):
    return {"worktrees": worktrees.reconcile(Path(repo).expanduser(), _live_sessions())}


@router.post("/reap")
def reap(body: ReapBody):
    return worktrees.reap(Path(body.path).expanduser(), force=body.force, rm_branch=body.rm_branch)


@router.post("/adopt")
def adopt(body: AdoptBody):
    return worktrees.adopt(Path(body.path).expanduser(), _now(), body.session)


@router.post("/link")
def link(body: PathBody):
    wt = Path(body.path).expanduser()
    repo = worktrees.parent_repo_of(wt)
    cfg = worktrees.parse_worktree_config(repo)
    return {"linked": worktrees.apply_links(repo, wt, worktrees.plan_links(repo, wt, cfg))}


@router.post("/unlink")
def unlink(body: PathBody):
    wt = Path(body.path).expanduser()
    # Promote every currently-symlinked recorded link to a real copy.
    entry = worktrees.get_entry(wt) or {}
    results = [worktrees.unlink_path(wt, r["path"]) for r in entry.get("links_applied", [])]
    return {"unlinked": results}
```

Add the core helpers referenced above to `worktrees.py`:

```python
# append to backend/lumbergh/worktrees.py
def parent_repo_of(worktree: Path) -> Path:
    common = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "--git-common-dir"],
        capture_output=True, text=True,
    ).stdout.strip()
    git_dir = Path(common)
    if not git_dir.is_absolute():
        git_dir = (worktree / git_dir).resolve()
    return git_dir.parent


def adopt(worktree: Path, created_at: str, session: str | None) -> dict:
    repo = parent_repo_of(worktree)
    branch = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()
    row = record_worktree(worktree, repo, branch, created_at, session=session)
    return {"status": "adopted", **row}


def unlink_path(worktree: Path, rel: str) -> dict:
    target = worktree / rel
    if not target.is_symlink():
        return {"path": rel, "status": "skipped", "reason": "not a symlink"}
    real = target.resolve()
    target.unlink()
    _reflink_copy(real, target)
    return {"path": rel, "status": "copied"}
```

Register the router:

```python
# backend/lumbergh/main.py — beside the other include_router calls
from lumbergh.routers import worktrees as worktrees_router  # with the other router imports
app.include_router(worktrees_router.router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktree_router.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/routers/worktrees.py backend/lumbergh/main.py backend/lumbergh/worktrees.py backend/lumbergh/tests/test_worktree_router.py
git commit -m "feat(worktree): REST router (create/ls/reap/adopt/link/unlink)"
```

---

### Task 7: `lb worktree` CLI subcommand

**Files:**
- Create: `backend/lumbergh/agent_cli/worktree.py`
- Modify: `backend/lumbergh/agent_cli/main.py` (register `worktree` command + flags + dispatch)
- Test: `backend/lumbergh/tests/test_lb_worktree_cli.py`

**Interfaces:**
- Consumes: `agent_cli.main._request`, `agent_cli.toon.render_collection/render_object`, `_err`, `_emit`.
- Produces: `run(subcommand: str, flags: dict, positional: list) -> int`, dispatched from `main()` when `command == "worktree"`.
- CLI grammar:
  - `lb worktree ls [--repo <path>] [--json]`
  - `lb worktree create --repo <path> --branch <name> [--new] [--base <b>] [--session <name>] [--intent <text>]`
  - `lb worktree reap <path> [--force] [--rm-branch]`
  - `lb worktree adopt <path> [--session <name>]`
  - `lb worktree link <path>` / `lb worktree unlink <path>`

- [ ] **Step 1: Write the failing test**

```python
# backend/lumbergh/tests/test_lb_worktree_cli.py
from lumbergh.agent_cli import worktree as wt_cli


class _Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


def test_ls_renders_table(monkeypatch, capsys):
    monkeypatch.setattr(
        wt_cli, "_request",
        lambda method, path, **kw: _Resp(
            {"worktrees": [{"path": "/w/app-worktrees/x", "repo": "app",
                            "branch": "x", "session": None, "agent": None, "state": "orphan"}]}
        ),
    )
    rc = wt_cli.run("ls", {"--repo": "/w/app"}, [])
    out = capsys.readouterr().out
    assert rc == 0
    assert "orphan" in out
    assert "app-worktrees/x" in out


def test_reap_requires_path(monkeypatch, capsys):
    rc = wt_cli.run("reap", {}, [])
    assert rc == 2
    assert "path" in capsys.readouterr().out.lower()


def test_create_posts_expected_body(monkeypatch, capsys):
    captured = {}

    def fake_request(method, path, **kw):
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kw.get("json")
        return _Resp({"path": "/w/app-worktrees/feat", "links_applied": []})

    monkeypatch.setattr(wt_cli, "_request", fake_request)
    rc = wt_cli.run("create", {"--repo": "/w/app", "--branch": "feat", "--new": True}, [])
    assert rc == 0
    assert captured["method"] == "POST"
    assert captured["json"]["create_branch"] is True
    assert captured["json"]["branch"] == "feat"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_lb_worktree_cli.py -v`
Expected: FAIL — `agent_cli.worktree` missing.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/lumbergh/agent_cli/worktree.py
"""`lb worktree` — first-class worktree lifecycle over the REST surface."""

from lumbergh.agent_cli.main import _emit, _err, _request
from lumbergh.agent_cli.toon import render_collection, render_object

_COLS = ["path", "repo", "branch", "session", "agent", "state"]


def run(sub: str, flags: dict, positional: list) -> int:
    if sub in ("", "ls"):
        return _ls(flags)
    if sub == "create":
        return _create(flags)
    if sub == "reap":
        return _reap(flags, positional)
    if sub == "adopt":
        return _adopt(flags, positional)
    if sub in ("link", "unlink"):
        return _linkop(sub, positional)
    return _err(f"unknown worktree subcommand `{sub}`",
                "lb worktree ls|create|reap|adopt|link|unlink", 2)


def _ls(flags) -> int:
    repo = flags.get("--repo")
    if not repo:
        return _err("--repo is required", "lb worktree ls --repo <path> [--json]", 2)
    data = _request("GET", "/api/worktrees", params={"repo": repo}).json()
    rows = data["worktrees"]
    if "--json" in flags:
        import json
        _emit(json.dumps(rows))
        return 0
    _emit(render_collection("worktrees", rows, _COLS))
    return 0


def _create(flags) -> int:
    repo, branch = flags.get("--repo"), flags.get("--branch")
    if not repo or not branch:
        return _err("--repo and --branch are required",
                    "lb worktree create --repo <path> --branch <name> [--new] [--base <b>]", 2)
    body = {
        "repo": repo, "branch": branch,
        "create_branch": "--new" in flags,
        "base_branch": flags.get("--base"),
        "session": flags.get("--session"),
        "task_intent": flags.get("--intent"),
    }
    d = _request("POST", "/api/worktrees", json=body).json()
    if d.get("error"):
        return _err(d["error"], None, 1)
    _emit(render_object([("path", d["path"]),
                         ("linked", ", ".join(r["path"] for r in d.get("links_applied", [])) or "-")]))
    return 0


def _reap(flags, positional) -> int:
    if not positional:
        return _err("worktree path is required",
                    "lb worktree reap <path> [--force] [--rm-branch]", 2)
    body = {"path": positional[0], "force": "--force" in flags, "rm_branch": "--rm-branch" in flags}
    d = _request("POST", "/api/worktrees/reap", json=body).json()
    if d.get("error"):
        hint = "re-run with --force to override" if d.get("reason") in ("dirty", "unpushed") else None
        return _err(d["error"], hint, 1)
    _emit(render_object([("reaped", d["path"])]))
    return 0


def _adopt(flags, positional) -> int:
    if not positional:
        return _err("worktree path is required", "lb worktree adopt <path> [--session <name>]", 2)
    body = {"path": positional[0], "session": flags.get("--session")}
    d = _request("POST", "/api/worktrees/adopt", json=body).json()
    _emit(render_object([("adopted", d.get("path", positional[0])), ("branch", d.get("branch", "-"))]))
    return 0


def _linkop(sub, positional) -> int:
    if not positional:
        return _err("worktree path is required", f"lb worktree {sub} <path>", 2)
    d = _request("POST", f"/api/worktrees/{sub}", json={"path": positional[0]}).json()
    _emit(render_object([(sub, positional[0]), ("result", str(d))]))
    return 0
```

Wire it into `agent_cli/main.py`:

```python
# 1) add to FLAGS dict:
    "worktree": {"--repo", "--branch", "--base", "--session", "--intent",
                 "--new", "--force", "--rm-branch", "--json"},
# 2) add to _BOOL_FLAGS: "--new", "--force", "--rm-branch", "--json"
# 3) in main(), before the final unknown-command return:
        if command == "worktree":
            from lumbergh.agent_cli import worktree as wt
            sub = positional[0] if positional else ""
            rest = positional[1:] if positional else []
            return wt.run(sub, flags, rest)
```

Note: `worktree` subcommands are the first `positional[0]`, so pop it before passing `rest` to `wt.run`. The `create`/`ls` paths use flags only; `reap`/`adopt`/`link`/`unlink` take the path in `rest[0]`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest lumbergh/tests/test_lb_worktree_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/agent_cli/worktree.py backend/lumbergh/agent_cli/main.py backend/lumbergh/tests/test_lb_worktree_cli.py
git commit -m "feat(worktree): lb worktree CLI subcommand over REST"
```

---

### Task 8: Route session-created worktrees through the module

**Files:**
- Modify: `backend/lumbergh/routers/sessions.py` (`_resolve_worktree_workdir`, and delete cleanup path ~line 1106)
- Test: `backend/lumbergh/tests/test_worktrees.py` (integration-style)

**Interfaces:**
- Consumes: `worktrees.create`, `worktrees.reap`, `worktrees.parse_worktree_config`, settings `get_settings`.
- Produces: no new public API — behavior change so that worktree sessions gain linking/hooks/registry and delete-cleanup uses the guarded reap.

**Rationale:** today `_resolve_worktree_workdir` calls `git_utils.create_worktree` directly (sessions.py:588) and delete calls `remove_worktree` directly (sessions.py:1108). Rerouting keeps a single lifecycle path.

- [ ] **Step 1: Write the failing test**

```python
# append to backend/lumbergh/tests/test_worktrees.py
def test_session_created_worktree_is_registered(tmp_path, monkeypatch):
    """Creating a worktree session records a registry entry + links (integration seam)."""
    monkeypatch.setenv("LUMBERGH_DATA_DIR", str(tmp_path / "cfg"))
    import importlib
    from lumbergh import db_utils, worktrees as w
    from lumbergh.routers import sessions

    importlib.reload(db_utils)
    importlib.reload(w)
    importlib.reload(sessions)

    repo = _init_repo(tmp_path / "app")
    (repo / ".venv").mkdir()
    (repo / ".venv" / "m").write_text("v")

    from lumbergh.models import CreateSessionRequest, WorktreeConfig

    body = CreateSessionRequest(
        mode="worktree",
        worktree=WorktreeConfig(parent_repo=str(repo), branch="feat/z", create_branch=True),
    )
    workdir, parent, branch = sessions._resolve_worktree_workdir(body)
    assert (Path(workdir) / ".venv").is_symlink()
    assert w.get_entry(Path(workdir)) is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktrees.py -k session_created -v`
Expected: FAIL — no registry entry (current code calls `git_utils.create_worktree` directly, no linking/registry).

- [ ] **Step 3: Write minimal implementation**

Rewrite `_resolve_worktree_workdir` (sessions.py ~568) to delegate:

```python
# backend/lumbergh/routers/sessions.py
from datetime import datetime, timezone

from lumbergh import worktrees
from lumbergh.routers.settings import get_settings


def _resolve_worktree_workdir(body: CreateSessionRequest) -> tuple[Path, str, str]:
    if not body.worktree:
        raise HTTPException(status_code=400, detail="Worktree config required for worktree mode")
    parent_repo = Path(body.worktree.parent_repo).expanduser().resolve()
    if not parent_repo.exists():
        raise HTTPException(status_code=400, detail=f"Parent repository does not exist: {body.worktree.parent_repo}")
    if not (parent_repo / ".git").exists():
        raise HTTPException(status_code=400, detail=f"Not a git repository: {body.worktree.parent_repo}")

    base_dir = get_settings().get("worktree", {}).get("base_dir") or None
    result = worktrees.create(
        parent_repo, body.worktree.branch,
        created_at=datetime.now(timezone.utc).isoformat(),
        create_branch=body.worktree.create_branch,
        base_branch=body.worktree.base_branch,
        session=body.name or None,
        global_base_dir=base_dir,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return Path(result["path"]), str(parent_repo), body.worktree.branch
```

Reroute the delete cleanup (sessions.py ~1106) to the guarded reap (session delete may force):

```python
    if cleanup_worktree and session_type == "worktree" and worktree_parent_repo and workdir:
        wt_result = worktrees.reap(Path(workdir), force=True)
        worktree_removed = wt_result.get("status") == "removed"
```

Note: `body.name` may be empty at this point (it is auto-derived later). If empty, pass `session=None`; the reconcile step still associates the session by matching `workdir` at read time, so a missing name here is harmless. Keep the `reset_to` handling that currently follows worktree creation, if present, unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest lumbergh/tests/test_worktrees.py -k session_created -v && uv run pytest lumbergh/tests/ -k "session" -v`
Expected: PASS; existing session tests still green.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/routers/sessions.py backend/lumbergh/tests/test_worktrees.py
git commit -m "feat(worktree): route session worktrees through lifecycle module (links + registry + guarded reap)"
```

---

### Task 9: Web UI — worktree panel

**Files:**
- Create: `frontend/src/components/WorktreePanel.tsx`
- Modify: `frontend/src/pages/Dashboard.tsx` (mount the panel)
- Modify: `frontend/src/hooks/useApiClient.ts` (add worktree fetch/reap calls) — follow existing client patterns
- Test: `frontend/src/components/WorktreePanel.test.tsx` (if a component test setup exists; otherwise cover via the e2e in Task 10)

**Interfaces:**
- Consumes: `GET /api/worktrees?repo=`, `POST /api/worktrees/reap`.
- Produces: a panel listing worktrees with an **ORPHAN** badge and a guarded **Reap** button that surfaces the dirty/unpushed refusal message.

- [ ] **Step 1: Write the component**

```tsx
// frontend/src/components/WorktreePanel.tsx
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useApiClient } from "../hooks/useApiClient";

type Row = {
  path: string; repo: string; branch: string;
  session: string | null; agent: string | null; state: "active" | "orphan";
};

export function WorktreePanel({ repo }: { repo: string }) {
  const api = useApiClient();
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["worktrees", repo],
    queryFn: async () => (await api.get(`/api/worktrees?repo=${encodeURIComponent(repo)}`)).worktrees as Row[],
    enabled: !!repo,
  });
  const reap = useMutation({
    mutationFn: (path: string) => api.post("/api/worktrees/reap", { path }),
    onSuccess: (res: any) => {
      if (res?.error) alert(`${res.error}${res.reason ? ` — reap blocked (${res.reason}); commit/push or force` : ""}`);
      qc.invalidateQueries({ queryKey: ["worktrees", repo] });
    },
  });

  if (!data?.length) return null;
  return (
    <div className="rounded border border-neutral-800 p-3">
      <h3 className="mb-2 text-sm font-semibold">Worktrees</h3>
      <ul className="space-y-1">
        {data.map((w) => (
          <li key={w.path} className="flex items-center justify-between text-xs">
            <span className="truncate">
              {w.branch} {w.state === "orphan" && <span className="ml-1 rounded bg-amber-600/30 px-1 text-amber-300">orphan</span>}
            </span>
            <button className="text-red-400 hover:underline" onClick={() => reap.mutate(w.path)}>reap</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 2: Mount it on the Dashboard**

Add `<WorktreePanel repo={selectedRepoPath} />` where the Dashboard already knows the active repo/search dir. Follow the existing card layout; keep it collapsible if the Dashboard uses collapsible sections.

- [ ] **Step 3: Verify build + lint**

Run: `cd frontend && npm run build && cd .. && ./lint.sh`
Expected: build succeeds, lint clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/WorktreePanel.tsx frontend/src/pages/Dashboard.tsx frontend/src/hooks/useApiClient.ts
git commit -m "feat(worktree): dashboard panel listing worktrees with guarded reap"
```

---

### Task 10: End-to-end roundtrip

**Files:**
- Create: `test/e2e/test_worktrees_e2e.py`

**Interfaces:**
- Consumes: the running backend (E2E harness pattern already used in `test/e2e`).

- [ ] **Step 1: Write the E2E test**

```python
# test/e2e/test_worktrees_e2e.py
# Follows the existing test/e2e conventions (httpx client + fixtures).
# Create a scratch git repo, POST create, GET ls (expect the worktree),
# POST reap force, GET ls (expect it gone).
```

Fill in using the same client fixture the other `test/e2e` files use (inspect a sibling file first for the base URL + auth fixture). The assertions mirror `test_worktree_router.py::test_create_list_reap_roundtrip` but against the live server.

- [ ] **Step 2: Run the E2E suite**

Run: `./test/e2e-vm.sh` (or `cd test/e2e && pytest test_worktrees_e2e.py` against a running server)
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add test/e2e/test_worktrees_e2e.py
git commit -m "test(worktree): e2e create/ls/reap roundtrip"
```

---

## Self-Review

**Spec coverage:**
- Home base (module + REST + `lb worktree`) → Tasks 1–7. ✓
- Reconciled registry (git truth + overlay, orphan/stale) → Tasks 3–4. ✓
- Worktree location (sibling default, global + dotfile `base_dir`, reflink caveat) → Task 1 + reflink in Task 2. ✓
- Env linking (symlink default, auto-detect set, dotfile authoritative, safety rules, copy mode) → Tasks 1–2. ✓
- `.lumbergh.toml` scope (links + per-path mode + `post_create`) → Tasks 1, 5. ✓
- Guarded explicit reap (dirty/unpushed refusal, `--force`, `--rm-branch`) → Tasks 5, 7. ✓
- `lb worktree` command set (create/ls/reap/adopt/link/unlink) → Task 7. ✓
- Session integration (reroute create + delete cleanup) → Task 8. ✓
- Web UI (orphan badge + guarded reap, no new creation UI) → Task 9. ✓
- Testing (unit reconcile/link/reap-guard/dotfile + e2e roundtrip) → Tasks 1–7, 10. ✓
- Out of scope (auto-reap/TTL/sync) → not implemented, correct. ✓

**Placeholder scan:** Only Task 10's E2E body is described-not-shown, intentionally, because it must adopt the existing `test/e2e` fixture (base URL + auth) which the worker inspects from a sibling file; the assertion shape is pinned to `test_worktree_router.py`. All other steps carry real code.

**Type consistency:** `LinkSpec(path, mode)`, `WorktreeProjectConfig(links, post_create, base_dir)`, and `reconcile(...) -> [{path,repo,branch,session,agent,state}]` are used identically across core, router, and CLI. `create(...)` returns `{path, links_applied}`; `reap(...)` returns `{status,path}` or `{error,reason}` — matched by router and CLI. Registry rows use `associated_session`/`links_applied` consistently.

## Execution Handoff

Two execution options — see below.
