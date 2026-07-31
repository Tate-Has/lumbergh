# Worktrees in the Git Graph — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Badge each worktree's HEAD commit in the DAG with its branch + a live agent-state dot, turning the git graph into a fleet map.

**Architecture:** Backend `get_graph_log` gains a structural `worktrees` array (branch, short headHash, path, isMain, isCurrent, sessionName), resolved from a caller-supplied `session_paths` map — `git_utils` stays pure. The volatile agent activity state is NOT baked in; the frontend overlays live `idleState`/`attentionState` by polling `/sessions` and joining on `sessionName`.

**Tech Stack:** Python/GitPython/FastAPI backend; React/TS frontend.

## Global Constraints

- `list_worktrees(cwd).commit` is a **7-char short hash** → match against a commit node's `shortHash`, never `hash`.
- No new REST endpoints, no schema migration, no second store.
- Live agent state must not enter the cached graph payload (fingerprint doesn't track it).
- Reuse existing state→color: `getSessionStatus()` + `statusColorClasses` from `utils/sessionStatus.ts`.

---

### Task 1: Backend — structural `worktrees` in the graph payload

**Files:**
- Modify: `backend/lumbergh/git_utils.py` — `get_graph_log`
- Modify: `backend/lumbergh/routers/sessions.py` — add `get_session_path_map()`, pass it into graph calls
- Modify: `backend/lumbergh/diff_cache.py` — pass `session_paths` in `_compute_all`
- Test: `backend/tests/test_graph_worktrees.py`

**Interfaces:**
- Produces: `get_graph_log(cwd, limit=100, session_paths: dict[str,str] | None = None)` → payload now includes `"worktrees": [{"branch","headHash","path","isMain","isCurrent","sessionName"}]`
- Produces: `get_session_path_map() -> dict[str, str]` (resolved workdir path → session name)

- [ ] **Step 1: Failing test** — `test_graph_worktrees.py`: create a repo, commit, add a worktree on a new branch, call `get_graph_log(main_repo)`. Assert payload has a `worktrees` entry for the sibling with `branch` == new branch, `headHash` matching a commit node's `shortHash`, `isMain` False, `isCurrent` False; and the main entry `isMain` True / `isCurrent` True. With `session_paths={resolved_wt_path: "wt-sess"}`, that entry's `sessionName == "wt-sess"`. A repo with no extra worktrees → the single main entry.
- [ ] **Step 2:** Run `cd backend && uv run pytest tests/test_graph_worktrees.py -v` → FAIL (no `worktrees` key).
- [ ] **Step 3:** Implement in `get_graph_log`: after building `commits`/`branches`, call `list_worktrees(cwd)`; build entries (resolve paths; `isCurrent = resolved(wt.path)==resolved(cwd)`; `sessionName=(session_paths or {}).get(resolved(wt.path))`). Add `"worktrees": [...]` to the return dict AND `"worktrees": []` to both early-return dicts. Add the `session_paths` param.
- [ ] **Step 4:** Add `get_session_path_map()` to `sessions.py` (iterate `sessions_table.all()`, map `resolve(workdir)->name`). Wire `session_git_graph` inline path to `_run_git(get_graph_log, workdir, limit, get_session_path_map())`. In `diff_cache._compute_all`, build the map once per loop (import `get_session_path_map`) and pass it.
- [ ] **Step 5:** Run pytest → PASS. Run `./lint.sh`.
- [ ] **Step 6:** Commit `feat(git): expose worktrees in the commit-graph payload`.

---

### Task 2: Frontend — worktree badges + live state overlay

**Files:**
- Modify: `frontend/src/components/diff/types.ts` — extend `GraphData`
- Modify: `frontend/src/components/graph/GitGraph.tsx` — poll `/sessions`, render badges, off-screen strip

**Interfaces:**
- Consumes: `GraphData.worktrees` from Task 1; `getSessionStatus`/`statusColorClasses` from `utils/sessionStatus.ts`.

- [ ] **Step 1:** Add to `GraphData`:
  ```ts
  worktrees?: {
    branch: string; headHash: string; path: string
    isMain: boolean; isCurrent: boolean; sessionName: string | null
  }[]
  ```
- [ ] **Step 2:** In `GitGraph`, add a lightweight sessions poll: `useState<SessionBase[]>` + `useEffect` fetching `${getApiBase()}/sessions` every 5s (mirrors the existing `/settings` fetch pattern). Build `sessionsByName: Map<string, SessionBase>`.
- [ ] **Step 3:** Build `worktreeByShortHash: Map<string, Worktree>` from `graphData.worktrees`. For each rendered node whose `commit.shortHash` is a key, render a badge next to the node (mirror the existing ref-label rendering path around the node rows): branch name + a status dot. Dot classes from `statusColorClasses[getSessionStatus(session).color].dot` when `sessionName` resolves to a live session; muted (`bg-text-tertiary`) when `sessionName` is null/offline. Mark `isCurrent` with a subtle "• here" suffix or ring.
- [ ] **Step 4:** Off-screen strip: any `worktrees` entry whose `headHash` is not among `nodes[].commit.shortHash` → render a compact list beside the graph (branch + dot); clicking bumps `commitLimit` (reuse existing limit control) to pull it in.
- [ ] **Step 5:** Run `./lint.sh`; run the app / typecheck (`cd frontend && npx tsc --noEmit`). Verify a repo with a worktree shows a badge.
- [ ] **Step 6:** Commit `feat(git): worktree fleet badges on the commit graph`.

---

## Self-Review

- **Spec coverage:** structural backend field ✓ (T1), frontend badge + live overlay ✓ (T2), all-siblings scope ✓ (`list_worktrees` returns all), you-are-here ✓ (isCurrent), orphan muted ✓, off-screen strip ✓, cache safety ✓ (no idleState in payload). 
- **Placeholder scan:** none.
- **Type consistency:** `headHash` (short) ↔ `shortHash` match rule stated in Global Constraints and both tasks; `session_paths`/`get_session_path_map` names consistent across T1 steps.
