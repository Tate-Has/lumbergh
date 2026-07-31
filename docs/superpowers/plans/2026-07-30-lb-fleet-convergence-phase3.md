# lb⇄fleet Convergence — Phase 3: Workflow Verbs (batch / land / teardown) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the three deterministic workflow verbs that absorb `sherpa fleet`'s issue→batch→land→teardown flow into `lb`, all operating on a **run group** (registry rows sharing a `run` id): `lb batch` stands up N window workers in one call; `lb land` cherry-picks the run's commits onto a base, smoke-tests, and single-pushes; `lb teardown` kills the run's windows and reaps its worktrees.

**Architecture:** Each verb is a backend endpoint under `/api/bill/` with a thin `lb` CLI wrapper. `batch` is a loop over Phase 2's `spawn --into <session> --run <id>` (one worker per brief file; branch+window name = the brief's filename stem; session defaults to the run id). `land` assembles in an **ephemeral git worktree** (never the user's checkout): `git worktree add` a `batch-<run>` branch off fresh `origin/<base>`, cherry-pick each member's commits in registry order (conflict → abort + STOP), run the smoke command from `.lumbergh.toml [land].smoke` (or `--smoke`), then without `--push` STOP-and-report, with `--push` do one `push batch:base`. `teardown` iterates run members: kill the window (Phase 2 `kill_tmux_window`) and reap the worktree (Phase 2 `reap`, which already refuses dirty/unpushed), best-effort, reporting refusals.

**Tech Stack:** Python 3.11+, FastAPI, raw `git`/`tmux` subprocesses, TinyDB, pytest. `lb` CLI in `backend/lumbergh/agent_cli/`.

## Global Constraints

- Python 3.11+; backend tests via `uv run pytest` from `backend/`.
- Run `./lint.sh` before done — backend ruff must be clean; the frontend eslint/tsc step has a pre-existing env failure unrelated to this backend-only phase (do not chase it; touch no frontend files).
- Red-green: failing test first, verify it fails, then implement.
- **Pushing is explicit and observable.** `lb land` without `--push` MUST NOT push — it assembles + smokes + reports only. The single push happens ONLY when the request carries `push=true`. This honors the project rule against pushing (which triggers CI) without explicit intent.
- `land` MUST NOT mutate the user's main checkout (no `checkout -B` in the repo root) — assemble in an ephemeral worktree and remove it.
- A run group is identified by registry rows where `run == <id>` (populated by Phase 2 `spawn --into … --run`). All three verbs derive their members from there.
- `teardown` reaps via the Phase 2 `worktree reap`, which refuses dirty/unpushed worktrees — teardown is best-effort and reports refusals rather than forcing (unless `--force` is passed through).
- Prefer expressiveness over comments; no Arrange/Act/Assert narration; test names carry the contract. No commit trailers.

## File Structure

- **Create** `backend/lumbergh/runs.py` — `run_members(run_id) -> list[dict]`: registry rows with matching `run`, in a deterministic order. One responsibility: the run-group query.
- **Create** `backend/lumbergh/land.py` — the git assembly engine: `assemble(repo, run_id, base, members) -> AssembleResult`, `run_smoke(worktree, cmd) -> bool`, `push_batch(worktree, batch_branch, base) -> PushResult`, `cleanup_assembly(worktree)`. Pure-ish over `git` subprocesses; no FastAPI.
- **Modify** `backend/lumbergh/worktrees.py` — add `read_land_smoke(repo) -> str | None` reading `[land].smoke` from `.lumbergh.toml` (next to the existing `parse_worktree_config`).
- **Create** `backend/lumbergh/briefs.py` — `enumerate_briefs(paths: list[str]) -> list[tuple[Path, str]]`: expand a directory (its `*.md`) or a file list into `(brief_path, stem)` pairs, validating stems are legal branch/window names and unique.
- **Modify** `backend/lumbergh/routers/bill.py` — add `/api/bill/batch`, `/api/bill/land`, `/api/bill/teardown` endpoints (+ their Pydantic bodies). `batch` reuses the existing spawn internals per brief.
- **Create** `backend/lumbergh/agent_cli/batch.py`, `land.py`, `teardown.py` — thin CLI wrappers.
- **Modify** `backend/lumbergh/agent_cli/main.py` — dispatch + `_COMMAND_HELP` for the three verbs.
- **Tests:** `test_runs.py`, `test_land.py`, `test_briefs.py`, `test_land_config.py` (new); `test_bill_router.py`; `test_lb_batch_cli.py`, `test_lb_land_cli.py`, `test_lb_teardown_cli.py` (new); `test_run_workflow_integration.py` (new e2e).

---

### Task 1: `run_members` — the run-group query

**Files:**
- Create: `backend/lumbergh/runs.py`
- Test: `backend/lumbergh/tests/test_runs.py`

**Interfaces:**
- Consumes: `worktrees.all_entries()` (existing).
- Produces: `run_members(run_id: str) -> list[dict]` — every registry row whose `run == run_id`, sorted by `target` (deterministic cherry-pick/teardown order). Empty list if none.

- [ ] **Step 1: Write the failing test**

```python
# backend/lumbergh/tests/test_runs.py
from lumbergh.runs import run_members


def test_run_members_filters_by_run_id_sorted_by_target(monkeypatch):
    monkeypatch.setattr(
        "lumbergh.worktrees.all_entries",
        lambda: [
            {"target": "s:b", "run": "r1", "branch": "b"},
            {"target": "s:a", "run": "r1", "branch": "a"},
            {"target": "solo", "run": None, "branch": "x"},
            {"target": "s:c", "run": "r2", "branch": "c"},
        ],
    )
    members = run_members("r1")
    assert [m["target"] for m in members] == ["s:a", "s:b"]


def test_run_members_empty_for_unknown_run(monkeypatch):
    monkeypatch.setattr("lumbergh.worktrees.all_entries", lambda: [])
    assert run_members("nope") == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_runs.py -v`
Expected: FAIL — `lumbergh.runs` doesn't exist.

- [ ] **Step 3: Implement**

```python
# backend/lumbergh/runs.py
"""Query the registry for the members of a run group."""

from lumbergh import worktrees


def run_members(run_id: str) -> list[dict]:
    rows = [r for r in worktrees.all_entries() if r.get("run") == run_id]
    return sorted(rows, key=lambda r: r.get("target") or "")
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest lumbergh/tests/test_runs.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/runs.py backend/lumbergh/tests/test_runs.py
git commit -m "feat(runs): run_members registry query for a run group"
```

---

### Task 2: `.lumbergh.toml [land].smoke` reader

**Files:**
- Modify: `backend/lumbergh/worktrees.py` (add `read_land_smoke`)
- Test: `backend/lumbergh/tests/test_land_config.py` (create)

**Interfaces:**
- Produces: `worktrees.read_land_smoke(repo: Path) -> str | None` — the `[land].smoke` string from `<repo>/.lumbergh.toml`, or None if the file/section/key is absent.

- [ ] **Step 1: Write the failing test**

```python
# backend/lumbergh/tests/test_land_config.py
from lumbergh.worktrees import read_land_smoke


def test_reads_land_smoke(tmp_path):
    (tmp_path / ".lumbergh.toml").write_text('[land]\nsmoke = "uv run pytest -q"\n')
    assert read_land_smoke(tmp_path) == "uv run pytest -q"


def test_none_when_absent(tmp_path):
    (tmp_path / ".lumbergh.toml").write_text('[worktree]\nlinks = []\n')
    assert read_land_smoke(tmp_path) is None


def test_none_when_no_dotfile(tmp_path):
    assert read_land_smoke(tmp_path) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest lumbergh/tests/test_land_config.py -v` → FAIL (`read_land_smoke` undefined).

- [ ] **Step 3: Implement**

Add to `worktrees.py` (it already imports `tomllib` and reads `.lumbergh.toml` in `parse_worktree_config`):

```python
def read_land_smoke(repo: Path) -> str | None:
    dotfile = repo / ".lumbergh.toml"
    if not dotfile.is_file():
        return None
    data = tomllib.loads(dotfile.read_text())
    smoke = data.get("land", {}).get("smoke")
    return smoke if isinstance(smoke, str) and smoke else None
```

- [ ] **Step 4: Run to verify it passes** → `cd backend && uv run pytest lumbergh/tests/test_land_config.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/worktrees.py backend/lumbergh/tests/test_land_config.py
git commit -m "feat(worktrees): read [land].smoke from .lumbergh.toml"
```

---

### Task 3: Brief enumeration for `batch`

**Files:**
- Create: `backend/lumbergh/briefs.py`
- Test: `backend/lumbergh/tests/test_briefs.py`

**Interfaces:**
- Consumes: `routers.sessions.SESSION_NAME_PATTERN` (existing name validator) — a stem must be a legal window/branch name.
- Produces: `enumerate_briefs(paths: list[str]) -> list[tuple[Path, str]]` — if `paths` is a single directory, its sorted `*.md` files; else the given files. Each yields `(resolved_path, stem)` where `stem = path.stem`. Raises `ValueError` with a clear message if: a path doesn't exist, a stem isn't a legal name, or two briefs share a stem.

- [ ] **Step 1: Write the failing tests**

```python
# backend/lumbergh/tests/test_briefs.py
import pytest

from lumbergh.briefs import enumerate_briefs


def test_directory_globs_md_files_sorted(tmp_path):
    (tmp_path / "b.md").write_text("b")
    (tmp_path / "a.md").write_text("a")
    (tmp_path / "note.txt").write_text("x")
    result = enumerate_briefs([str(tmp_path)])
    assert [stem for _, stem in result] == ["a", "b"]


def test_explicit_file_list(tmp_path):
    p1 = tmp_path / "kb-1.md"; p1.write_text("1")
    p2 = tmp_path / "kb-2.md"; p2.write_text("2")
    result = enumerate_briefs([str(p1), str(p2)])
    assert [stem for _, stem in result] == ["kb-1", "kb-2"]


def test_missing_path_raises(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        enumerate_briefs([str(tmp_path / "nope.md")])


def test_duplicate_stems_raise(tmp_path):
    d1 = tmp_path / "a"; d1.mkdir(); (d1 / "x.md").write_text("1")
    d2 = tmp_path / "b"; d2.mkdir(); (d2 / "x.md").write_text("2")
    with pytest.raises(ValueError, match="duplicate"):
        enumerate_briefs([str(d1 / "x.md"), str(d2 / "x.md")])


def test_illegal_stem_raises(tmp_path):
    bad = tmp_path / "has space.md"; bad.write_text("x")
    with pytest.raises(ValueError, match="name"):
        enumerate_briefs([str(bad)])
```

- [ ] **Step 2: Run to verify it fails** → `cd backend && uv run pytest lumbergh/tests/test_briefs.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# backend/lumbergh/briefs.py
"""Expand `lb batch --briefs` (a directory or a file list) into (brief, stem) pairs."""

from pathlib import Path

from lumbergh.routers.sessions import SESSION_NAME_PATTERN


def enumerate_briefs(paths: list[str]) -> list[tuple[Path, str]]:
    resolved = [Path(p).expanduser() for p in paths]
    if len(resolved) == 1 and resolved[0].is_dir():
        files = sorted(resolved[0].glob("*.md"))
    else:
        files = resolved

    out: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for f in files:
        if not f.is_file():
            raise ValueError(f"brief path does not exist: {f}")
        stem = f.stem
        if not SESSION_NAME_PATTERN.match(stem):
            raise ValueError(
                f"brief filename `{f.name}` yields an illegal worker name `{stem}` "
                "(letters, numbers, underscores, hyphens only)"
            )
        if stem in seen:
            raise ValueError(f"duplicate worker name `{stem}` from {f.name}")
        seen.add(stem)
        out.append((f.resolve(), stem))
    return out
```

- [ ] **Step 4: Run to verify it passes** → `cd backend && uv run pytest lumbergh/tests/test_briefs.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/briefs.py backend/lumbergh/tests/test_briefs.py
git commit -m "feat(briefs): enumerate_briefs (dir or file list) -> (brief, stem)"
```

---

### Task 4: `/api/bill/batch` endpoint + `lb batch` CLI

**Files:**
- Modify: `backend/lumbergh/routers/bill.py` (add `BatchBody` + `batch` endpoint)
- Create: `backend/lumbergh/agent_cli/batch.py`
- Modify: `backend/lumbergh/agent_cli/main.py` (dispatch + help)
- Test: `backend/lumbergh/tests/test_bill_router.py`, `backend/lumbergh/tests/test_lb_batch_cli.py` (create)

**Interfaces:**
- Consumes: `briefs.enumerate_briefs` (Task 3); the existing spawn internals (`SpawnBody`, `spawn`) from Phase 2 — each brief becomes a `spawn(SpawnBody(..., into=<session>, run=<run>, name=<stem>, branch=<stem>, kind=<kind>, brief_path=<path>, create_branch=True, base_branch=<base>))`.
- Produces: `POST /api/bill/batch` with body `{repo, run, briefs: list[str], kind, base?, session?}`. Session defaults to `run`. Returns `{"run": run, "session": session, "workers": [<spawn result per brief>], "failed": [{"brief": name, "error": ...}]}`. Continues past a single brief's spawn failure (records it in `failed`) so one bad brief doesn't abort the batch; `lb batch` surfaces the counts.

- [ ] **Step 1: Write the failing test** (endpoint-level, spawn internals stubbed)

```python
# add to backend/lumbergh/tests/test_bill_router.py
def test_batch_spawns_one_worker_per_brief(monkeypatch, tmp_path):
    from lumbergh.routers import bill

    d = tmp_path / "briefs"; d.mkdir()
    (d / "kb-1.md").write_text("one"); (d / "kb-2.md").write_text("two")

    calls = []
    def fake_spawn(body):
        calls.append((body.into, body.run, body.name, body.branch))
        return {"session": f"{body.into}:{body.name}", "kind": body.kind,
                "branch": body.branch, "path": f"/wt/{body.name}"}
    monkeypatch.setattr(bill, "spawn", fake_spawn)

    resp = bill.batch(bill.BatchBody(
        repo=str(tmp_path / "repo"), run="sprint", briefs=[str(d)], kind="ship",
    ))
    assert resp["session"] == "sprint"
    assert {c[2] for c in calls} == {"kb-1", "kb-2"}
    assert all(c[0] == "sprint" and c[1] == "sprint" for c in calls)  # into+run default to run id
    assert len(resp["workers"]) == 2 and resp["failed"] == []
```

- [ ] **Step 2: Run to verify it fails** → FAIL (`BatchBody`/`batch` undefined).

- [ ] **Step 3: Implement**

Add `BatchBody(BaseModel)` with `repo: str`, `run: str`, `briefs: list[str]`, `kind: str`, `base: str | None = None`, `session: str | None = None`. Add the endpoint:

```python
@router.post("/batch")
def batch(body: BatchBody):
    from lumbergh.briefs import enumerate_briefs

    session = body.session or body.run
    try:
        pairs = enumerate_briefs(body.briefs)
    except ValueError as e:
        raise _fail("briefs", str(e), "check --briefs paths and filenames")
    if not pairs:
        raise _fail("briefs", "no briefs found", "pass a directory of .md files or a file list")

    workers, failed = [], []
    for brief_path, stem in pairs:
        try:
            result = spawn(SpawnBody(
                repo=body.repo, branch=stem, kind=body.kind,
                brief_path=str(brief_path), name=stem, create_branch=True,
                base_branch=body.base, into=session, run=body.run,
            ))
            workers.append(result)
        except HTTPException as e:
            failed.append({"brief": stem, "error": e.detail})
    return {"run": body.run, "session": session, "workers": workers, "failed": failed}
```

> `spawn` raises `HTTPException` on failure; catching it per-brief keeps one bad brief from aborting the batch. If you prefer, factor the spawn body-build into a helper — but reusing `spawn(SpawnBody(...))` directly is fine and keeps unwind/registry behavior identical to a single spawn.

Create `agent_cli/batch.py` mirroring `spawn.py`'s shape: required `--repo`, `--run`, `--briefs` (accepts one or more values), `--kind`; optional `--base`, `--session`. POST to `/api/bill/batch`; render the returned worker count + any `failed`. Add `batch` to `main.py`'s dispatch and `_COMMAND_HELP` (usage-line style, matching the other entries):
`lb batch --repo <path> --run <id> --briefs <dir|file...> --kind ship|scout [--base <b>] [--session <n>]`

- [ ] **Step 4: Run tests** → `cd backend && uv run pytest lumbergh/tests/test_bill_router.py lumbergh/tests/test_lb_batch_cli.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/routers/bill.py backend/lumbergh/agent_cli/batch.py backend/lumbergh/agent_cli/main.py backend/lumbergh/tests/test_bill_router.py backend/lumbergh/tests/test_lb_batch_cli.py
git commit -m "feat(lb): batch — stand up N window workers from briefs in one call"
```

---

### Task 5: `land.py` — git assembly engine (ephemeral worktree, cherry-pick, smoke, push)

**Files:**
- Create: `backend/lumbergh/land.py`
- Test: `backend/lumbergh/tests/test_land.py`

**Interfaces:**
- Produces (all over raw `git` subprocess; `repo` is the parent repo path):
  - `assemble(repo: Path, run_id: str, base: str, member_branches: list[str]) -> dict` — `git fetch origin <base>`; create an ephemeral worktree at a temp path on a fresh branch `batch-<run_id>` off `origin/<base>` (`git worktree add <tmp> -b batch-<run_id> origin/<base>`); for each member branch, cherry-pick its commits ahead of `origin/<base>` (`git rev-list --reverse origin/<base>..<branch>`), in order; on a cherry-pick failure run `git cherry-pick --abort` and return `{"ok": False, "stage": "cherry-pick", "branch": <branch>, "error": ...}`. On success return `{"ok": True, "worktree": <tmp>, "batch": "batch-<run_id>", "picked": {<branch>: [<sha>...]}}`. NEVER touches the user's main checkout HEAD.
  - `run_smoke(worktree: Path, cmd: str) -> dict` — run `cmd` (shell) in `worktree`; `{"ok": rc == 0, "returncode": rc}`.
  - `push_batch(worktree: Path, batch_branch: str, base: str) -> dict` — `git push origin <batch_branch>:<base>` from `worktree`; `{"ok": rc == 0, "error": ...}`.
  - `cleanup_assembly(repo: Path, worktree: Path, batch_branch: str) -> None` — `git worktree remove --force <worktree>` then `git branch -D <batch_branch>` (best-effort).

- [ ] **Step 1: Write the failing tests** (real temp git repo — this is git plumbing, mocks would prove nothing)

```python
# backend/lumbergh/tests/test_land.py
import subprocess

import pytest

from lumbergh import land


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo_with_two_branches(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t"); _git(repo, "config", "user.name", "t")
    (repo / "base.txt").write_text("base"); _git(repo, "add", "."); _git(repo, "commit", "-qm", "base")
    # simulate origin as a bare clone so origin/<base> exists
    origin = tmp_path / "origin.git"
    _git(repo, "clone", "--bare", "-q", str(repo), str(origin))
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "fetch", "-q", "origin")
    _git(repo, "branch", "--set-upstream-to=origin/master", "master")  # base = master here
    for name in ("feat-a", "feat-b"):
        _git(repo, "checkout", "-q", "-b", name, "master")
        (repo / f"{name}.txt").write_text(name); _git(repo, "add", "."); _git(repo, "commit", "-qm", name)
    _git(repo, "checkout", "-q", "master")
    return repo


def test_assemble_cherry_picks_both_branches(repo_with_two_branches):
    repo = repo_with_two_branches
    result = land.assemble(repo, "r1", "master", ["feat-a", "feat-b"])
    assert result["ok"] is True
    wt = result["worktree"]
    assert (wt / "feat-a.txt").exists() and (wt / "feat-b.txt").exists()
    # master (the user's checkout) is untouched — no batch files leaked into repo root
    assert not (repo / "feat-a.txt").exists()
    land.cleanup_assembly(repo, wt, result["batch"])


def test_assemble_reports_conflict_and_aborts(tmp_path):
    # two branches that edit the same line → cherry-pick conflict
    repo = tmp_path / "repo"; repo.mkdir()
    _git(repo, "init", "-q"); _git(repo, "config", "user.email", "t@t"); _git(repo, "config", "user.name", "t")
    (repo / "f.txt").write_text("0\n"); _git(repo, "add", "."); _git(repo, "commit", "-qm", "base")
    origin = tmp_path / "o.git"; _git(repo, "clone", "--bare", "-q", str(repo), str(origin))
    _git(repo, "remote", "add", "origin", str(origin)); _git(repo, "fetch", "-q", "origin")
    for name, val in (("x", "1\n"), ("y", "2\n")):
        _git(repo, "checkout", "-q", "-b", name, "master")
        (repo / "f.txt").write_text(val); _git(repo, "add", "."); _git(repo, "commit", "-qm", name)
    _git(repo, "checkout", "-q", "master")
    result = land.assemble(repo, "r2", "master", ["x", "y"])
    assert result["ok"] is False and result["stage"] == "cherry-pick"
```

- [ ] **Step 2: Run to verify it fails** → `cd backend && uv run pytest lumbergh/tests/test_land.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement** `land.py` per the Interfaces. Use a temp dir under the system temp (or `<repo>/.git/lb-batch-<run>`) for the ephemeral worktree; resolve `origin/<base>` for the cherry-pick range; run `git` via `subprocess.run([...], cwd=..., capture_output=True, text=True)`. Cherry-pick order = the order of `member_branches` as passed. On any conflict, `git cherry-pick --abort` in the worktree before returning the error dict. Keep each function single-purpose.

- [ ] **Step 4: Run to verify it passes** → `cd backend && uv run pytest lumbergh/tests/test_land.py -v` → PASS (both the happy path and the conflict path).

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/land.py backend/lumbergh/tests/test_land.py
git commit -m "feat(land): git assembly engine — ephemeral worktree, cherry-pick, smoke, push"
```

---

### Task 6: `/api/bill/land` endpoint + `lb land` CLI

**Files:**
- Modify: `backend/lumbergh/routers/bill.py` (`LandBody` + `land` endpoint)
- Create: `backend/lumbergh/agent_cli/land.py`
- Modify: `backend/lumbergh/agent_cli/main.py` (dispatch + help)
- Test: `backend/lumbergh/tests/test_bill_router.py`, `backend/lumbergh/tests/test_lb_land_cli.py` (create)

**Interfaces:**
- Consumes: `runs.run_members` (Task 1), `land.assemble/run_smoke/push_batch/cleanup_assembly` (Task 5), `worktrees.read_land_smoke` (Task 2).
- Produces: `POST /api/bill/land` body `{run, onto?, push: bool = False, smoke?: str | None, skip_smoke: bool = False}`. Derives `repo` from the run members' shared `parent_repo` (error if members span repos or the run is empty). Order = `run_members` order; member branch = each row's `branch`. Flow: `assemble` → (unless `skip_smoke`) `run_smoke` with `smoke or read_land_smoke(repo)` (if neither, error telling the caller to configure `[land].smoke` or pass `--smoke`/`--skip-smoke`) → if not `push`: return `{"ok": True, "pushed": False, "batch": ..., "picked": ..., "smoke": "passed|skipped", "next": "re-run with push=true"}` and **cleanup the assembly worktree** (leave it only on smoke failure for inspection, per fleet) → if `push`: `push_batch` then `cleanup_assembly`, return `{"pushed": True, ...}`. On assemble conflict or smoke failure, return the failure dict (HTTP 400 via `_fail`) and leave the assembly worktree in place for inspection.

- [ ] **Step 1: Write the failing test** (endpoint with `land.*` + `run_members` stubbed — the git engine itself is covered by Task 5)

```python
# add to backend/lumbergh/tests/test_bill_router.py
def test_land_without_push_assembles_smokes_and_stops(monkeypatch):
    from lumbergh.routers import bill

    monkeypatch.setattr(
        "lumbergh.routers.bill.run_members",
        lambda r: [{"parent_repo": "/repo/port", "branch": "feat-a", "target": "sprint:feat-a"},
                   {"parent_repo": "/repo/port", "branch": "feat-b", "target": "sprint:feat-b"}],
    )
    monkeypatch.setattr("lumbergh.routers.bill.land.assemble",
        lambda repo, run, base, branches: {"ok": True, "worktree": "/tmp/b", "batch": f"batch-{run}", "picked": {}})
    smoked = {}
    monkeypatch.setattr("lumbergh.routers.bill.land.run_smoke",
        lambda wt, cmd: smoked.setdefault("cmd", cmd) or {"ok": True, "returncode": 0})
    monkeypatch.setattr("lumbergh.routers.bill.worktrees.read_land_smoke", lambda repo: "make test")
    pushed = {}
    monkeypatch.setattr("lumbergh.routers.bill.land.push_batch", lambda *a: pushed.setdefault("did", True))
    monkeypatch.setattr("lumbergh.routers.bill.land.cleanup_assembly", lambda *a: None)

    resp = bill.land(bill.LandBody(run="sprint", onto="master", push=False))
    assert resp["pushed"] is False
    assert smoked["cmd"] == "make test"
    assert "did" not in pushed  # NOT pushed without push=true
```

- [ ] **Step 2: Run to verify it fails** → FAIL (`LandBody`/`land` undefined).

- [ ] **Step 3: Implement** the `LandBody` + `land` endpoint per Interfaces. Guard: empty run → `_fail("run", ...)`; members spanning repos → `_fail("run", "run spans multiple repos", ...)`. Resolve base default (`onto or "dev"` — but read the project's default branch if simple; otherwise default `"main"` and document it). Resolve smoke command precedence: `body.smoke` → `read_land_smoke(repo)` → if both None and not `skip_smoke`, `_fail("smoke", "no smoke command", "configure [land].smoke or pass --smoke/--skip-smoke")`.

Create `agent_cli/land.py`: `--run` (required), `--onto`, `--push` (flag), `--smoke`, `--skip-smoke`. POST to `/api/bill/land`; render the batch/picked/smoke/pushed summary. Add `land` to dispatch + `_COMMAND_HELP`:
`lb land --run <id> [--onto <base>] [--push] [--smoke "<cmd>"] [--skip-smoke]`

- [ ] **Step 4: Run tests** → `cd backend && uv run pytest lumbergh/tests/test_bill_router.py lumbergh/tests/test_lb_land_cli.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/routers/bill.py backend/lumbergh/agent_cli/land.py backend/lumbergh/agent_cli/main.py backend/lumbergh/tests/test_bill_router.py backend/lumbergh/tests/test_lb_land_cli.py
git commit -m "feat(lb): land — assemble + smoke + explicit single-push a run"
```

---

### Task 7: `/api/bill/teardown` endpoint + `lb teardown` CLI

**Files:**
- Modify: `backend/lumbergh/routers/bill.py` (`TeardownBody` + `teardown` endpoint)
- Create: `backend/lumbergh/agent_cli/teardown.py`
- Modify: `backend/lumbergh/agent_cli/main.py`
- Test: `backend/lumbergh/tests/test_bill_router.py`, `backend/lumbergh/tests/test_lb_teardown_cli.py` (create)

**Interfaces:**
- Consumes: `runs.run_members` (Task 1); `worktrees.reap` (existing — refuses dirty/unpushed unless `force`); `tmux_pty.kill_tmux_window` + `targets.parse_target` (Phase 2).
- Produces: `POST /api/bill/teardown` body `{run, force: bool = False}`. For each member (in `run_members` order): if the target has a window part, `kill_tmux_window(target)`; then `worktrees.reap(Path(member["path"]), force=force, rm_branch=True)`. Collect per-member `{target, killed: bool, reaped: <status>}`. Best-effort: a reap refusal (dirty/unpushed) is recorded, not raised. Returns `{"run": run, "results": [...], "refused": [<targets reap refused>]}`.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/lumbergh/tests/test_bill_router.py
def test_teardown_kills_windows_and_reaps_members(monkeypatch):
    from lumbergh.routers import bill

    monkeypatch.setattr(
        "lumbergh.routers.bill.run_members",
        lambda r: [{"target": "sprint:a", "path": "/wt/a"}, {"target": "sprint:b", "path": "/wt/b"}],
    )
    killed = []
    monkeypatch.setattr("lumbergh.routers.bill.kill_tmux_window", lambda t: killed.append(t) or True)
    reaped = []
    def fake_reap(path, force, rm_branch):
        reaped.append(str(path))
        return {"status": "removed"} if "a" in str(path) else {"status": "refused", "reason": "dirty"}
    monkeypatch.setattr("lumbergh.routers.bill.worktrees.reap", fake_reap)

    resp = bill.teardown(bill.TeardownBody(run="sprint"))
    assert set(killed) == {"sprint:a", "sprint:b"}
    assert set(reaped) == {"/wt/a", "/wt/b"}
    assert resp["refused"] == ["sprint:b"]
```

- [ ] **Step 2: Run to verify it fails** → FAIL (`TeardownBody`/`teardown` undefined).

- [ ] **Step 3: Implement** the endpoint per Interfaces (import `kill_tmux_window`, `parse_target` if not already in bill.py). Create `agent_cli/teardown.py`: `--run` (required), `--force` (flag). POST to `/api/bill/teardown`; render results + a clear note listing any `refused` targets and that they were left running with unlanded/dirty work. Add to dispatch + `_COMMAND_HELP`:
`lb teardown --run <id> [--force]`

- [ ] **Step 4: Run tests** → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/lumbergh/routers/bill.py backend/lumbergh/agent_cli/teardown.py backend/lumbergh/agent_cli/main.py backend/lumbergh/tests/test_bill_router.py backend/lumbergh/tests/test_lb_teardown_cli.py
git commit -m "feat(lb): teardown — kill windows + reap a run, refusing dirty work"
```

---

### Task 8: End-to-end — batch → land (dry) → teardown

Real git + tmux, exercising the whole run lifecycle as an agent would drive it. This is the Phase 3 regression guard.

**Files:**
- Create: `backend/lumbergh/tests/test_run_workflow_integration.py`

**Interfaces:**
- Consumes: `land.assemble/run_smoke/cleanup_assembly` (Task 5), `runs.run_members` (Task 1), real `git`. (tmux optional — this test can exercise the git+registry lifecycle without a live tmux by driving `land`/`run_members` directly over a seeded registry; if it also spawns real windows, skip when tmux is absent.)

- [ ] **Step 1: Write the test**

Build a real git repo with an `origin` bare remote and two feature branches (as in Task 5's fixture). Seed the worktree registry with two rows sharing `run="itest"` (targets `s:feat-a`, `s:feat-b`, matching branches, `parent_repo` = the repo). Then:
- `members = run_members("itest")` → assert 2, sorted.
- `assemble(repo, "itest", "master", [m["branch"] for m in members])` → `ok True`; assert both feature files present in the assembly worktree and ABSENT from the repo root (non-disruptive); then `cleanup_assembly` and assert the batch branch/worktree are gone.
- (If exercising teardown over real worktrees: create two real `git worktree`s, register them, run the teardown endpoint logic, assert they're reaped.)
Do NOT weaken assertions; keep the non-disruptive check (repo root untouched) — it's the guard for the ephemeral-worktree requirement.

- [ ] **Step 2: Run — passes on Tasks 1–7** → `cd backend && uv run pytest lumbergh/tests/test_run_workflow_integration.py -v` → PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/lumbergh/tests/test_run_workflow_integration.py
git commit -m "test(e2e): run lifecycle — batch group, land assembly non-disruptive, teardown"
```

---

### Task 9: Lint, full suite, wrap-up

**Files:** none (verification).

- [ ] **Step 1:** `cd backend && uv run pytest -q` → all pass.
- [ ] **Step 2:** backend lint — `cd backend && uv run ruff check . && uv run ruff format --check .` → clean (fix only backend files this phase touched; for unused-arg lint rename to `_name` or use `@pytest.mark.usefixtures`, NEVER delete a side-effect fixture param — see the Phase 1 postmortem). `git diff main -- frontend/` MUST be empty.
- [ ] **Step 3: Manual smoke (recommended)** — with the backend running: write two brief files, `lb batch --repo <p> --run demo --briefs <dir> --kind scout`; confirm `lb` shows `demo:<stem1>`/`demo:<stem2>`; make a commit in each worktree; `lb land --run demo --onto <base> --skip-smoke` (no `--push`) and confirm it reports an assembled batch WITHOUT pushing and without touching your current branch; then `lb teardown --run demo` and confirm both windows/worktrees are gone.
- [ ] **Step 4: Commit any lint fixups** — `chore: lint fixups for workflow verbs`.

---

## Self-Review

**Spec coverage (Phase 3 = "Workflow verbs — batch / land / teardown"):**
- `lb batch` stands up N window workers from briefs, one call → Tasks 3, 4. ✓
- `lb land` assembles the run's branches, smokes, single-pushes on explicit go → Tasks 1, 2, 5, 6. ✓ (cherry-pick + single push per the design decision; ephemeral worktree so the user's checkout is never mutated.)
- `lb teardown` kills the run's windows + reaps worktrees, refusing dirty work → Tasks 1, 7. ✓
- Run group = registry rows sharing `run` → Task 1, used by land + teardown. ✓
- Smoke command from `.lumbergh.toml [land].smoke` + `--smoke` override → Task 2, used by land. ✓
- Push is explicit/observable (no push without `push=true`) → Task 6 + Global Constraints. ✓
- e2e over the whole lifecycle → Task 8. ✓
- Out of scope (Phase 4): Redis removal, `sherpa fleet` retirement, dropping the `associated_session` mirror.

**Placeholder scan:** No TBD/TODO; every code step carries real code or an exact command sequence. The "match the module's import paths" / "read the fixture" notes are verification instructions, not deferred work.

**Type consistency:** `run_members(run_id) -> list[dict]` (Task 1) consumed identically by Tasks 6, 7, 8. `enumerate_briefs(paths) -> list[tuple[Path, str]]` (Task 3) consumed by Task 4. `land.assemble/run_smoke/push_batch/cleanup_assembly` signatures (Task 5) match Task 6's calls and Task 8's e2e. `read_land_smoke(repo) -> str | None` (Task 2) matches Task 6's precedence use. `batch` spawns via Phase 2's `spawn(SpawnBody(..., into=, run=))`. `teardown` reaps via Phase 2 `worktrees.reap(path, force, rm_branch)` and kills via `kill_tmux_window(target)`.

**Known follow-on (Phase 4):** land's default base branch (`dev` vs `main`) is project-specific — Task 6 defaults it and allows `--onto`; revisit if a per-project default belongs in `.lumbergh.toml [land].base`. Note the `associated_session` mirror removal when writing the Phase 4 plan.
