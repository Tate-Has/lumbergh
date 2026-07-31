# Worktrees in the Git Graph — Live Fleet Map

**Date:** 2026-07-30
**Status:** Design — awaiting implementation plan

## Problem

Lumbergh's per-session commit DAG (`GitGraph.tsx`, backend `get_graph_log`) runs
`git log --all`, so it already *draws* the commits on worktree branches — but it
never labels them. There is no way, from the graph, to see which branches are
checked out in a worktree or which agent session is actively working in one.

Meanwhile Lumbergh already has first-class worktree infrastructure (`worktrees.py`,
`/api/worktrees`, `WorktreePanel`, the `lb` fleet spawning each worker into its own
worktree). The data exists; it is simply not joined into the graph.

**Goal:** Turn the DAG into a live fleet map — each worktree's HEAD commit is badged
with its branch and a status dot colored by the owning agent session's live state
(working / idle / blocked / unseen).

## Scope

- **Surface:** the commit DAG graph only (`GitGraph.tsx`). Not the WorktreePanel,
  not a new standalone view.
- **Coverage:** all sibling worktrees of the parent repo, shown from any session's
  graph in that repo. The worktree the user is currently viewing is still shown, but
  marked "you are here."
- **Detail:** branch name + live agent state per worktree (the richest option).

Out of scope: changing the WorktreePanel, new REST endpoints, schema migrations, a
second data store, or altering worktree lifecycle/reap behavior.

## Key constraint: cache safety

The graph is served from `diff_cache`, which caches on a **git fingerprint**
(file mtimes + `git status --porcelain`). Agent *activity* state (working → idle)
does not change git status, so baking live state into the cached graph payload would
produce **stale badges**. The design therefore splits the two concerns:

| Concern | Owner | Changes when | Cache-safe in graph payload? |
|---|---|---|---|
| Structural: which commit is a worktree HEAD, its branch/path/owning session | Backend `get_graph_log` | worktrees or commits change (tracked by the git fingerprint) | Yes |
| Live: working / idle / blocked / unseen | Frontend overlay | agent activity changes (fast poll) | No — must not be cached |

## Design

### Backend — `get_graph_log` payload gains a `worktrees` array

In `git_utils.py::get_graph_log(cwd, limit)`, after building commits, call the
existing `list_worktrees(cwd)` (which returns **all** sibling worktrees of the repo
via the shared git common dir, regardless of which worktree `cwd` is). For each
worktree, resolve the owning session name by matching the worktree path against the
session store's `workdir` — the same join `worktrees.reconcile` / `_live_session_for`
already perform. Append to the payload:

```jsonc
"worktrees": [
  {
    "branch": "feature/foo",
    "headHash": "abc123…",      // full or short hash matching the commit nodes' hash field
    "path": "/…/repo-worktrees/feature-foo",
    "sessionName": "foo-worker" | null,
    "isMain": false,            // the primary working copy
    "isCurrent": true | false   // this worktree == the session being viewed (by workdir)
  }
]
```

Structural only — **no `idleState` here.** `isCurrent` is computed against the
requesting session's `workdir` (already available to the endpoint via
`get_session_workdir(name)`), passed into the graph computation.

`diff_cache._compute_all` already computes the graph off-thread per active session
and caches by fingerprint; this new field rides along unchanged, and because it is
structural it stays correct under the existing fingerprint.

### Frontend — `GitGraph.tsx` renders worktree badges on HEAD nodes

1. Consume `graph.worktrees` (add to `GraphData` in `diff/types.ts`).
2. Build a `headHash → worktree` map. For each rendered commit node whose hash is a
   worktree HEAD, attach a badge: **branch name** + a **status dot**.
3. The dot's color/state comes from the **live session-list query** (the same data
   the Dashboard already polls: `idleState`, `attentionState`, `unseen`, `workdir`),
   joined by `sessionName`. `GitGraph` obtains the session list via the existing
   sessions query hook; if it isn't already in scope there, it subscribes to the same
   TanStack query key (cheap — deduped/cached, no new endpoint).
4. The current worktree's badge gets a subtle "you are here" marker (`isCurrent`).
5. A worktree with `sessionName: null` (orphan — no live session) renders a muted
   "no agent" dot, consistent with the WorktreePanel's orphan treatment.

### Off-screen worktrees

`git log --all` with `max_count = limit` (default 100, topo order) includes worktree
branch tips as long as they fall within the limit. If a worktree's `headHash` is not
among the rendered nodes (its tip is older than the limit), it must not silently
vanish: collect these into a compact **"off-screen worktrees" strip** rendered beside
the graph, each row showing branch + agent state + a click that raises the graph limit
(reusing the existing limit-bump control) to bring the node into view.

## State → color mapping

Reuse the existing dashboard convention so the graph reads the same as the session
cards (exact palette to be lifted from the current `SessionCard`/badge components,
not reinvented):

- **working** — active/spinner color
- **idle** — waiting-for-input color
- **blocked** / needs-answer — attention color
- **unseen** — the existing unseen indicator
- **no agent (orphan)** — muted/grey

## Components touched

- `backend/lumbergh/git_utils.py` — `get_graph_log` (+ worktree join; reuse
  `list_worktrees` and the session-store path match).
- `backend/lumbergh/diff_cache.py` — thread the current session's `workdir` through
  for `isCurrent` if not already available; otherwise unchanged.
- `backend/lumbergh/routers/sessions.py` — `GET /git/graph` passes the viewing
  session's workdir into the graph computation.
- `frontend/src/components/diff/types.ts` — extend `GraphData` with `worktrees`.
- `frontend/src/components/graph/GitGraph.tsx` — badge rendering + session-state join
  + off-screen strip.
- (`graphLayout.ts` — only if badge placement needs a layout hook; prefer rendering
  badges as an overlay keyed off existing node positions, no layout change.)

## Testing

- **Backend unit:** `get_graph_log` on a repo with 2+ worktrees returns a `worktrees`
  array with correct `headHash`/`branch`/`isMain`/`isCurrent`, and `sessionName`
  populated when a session's `workdir` matches (and `null` when none does). A repo
  with no worktrees returns `worktrees: []` and is otherwise unchanged.
- **Backend unit:** `isCurrent` is true only for the worktree whose path equals the
  requesting session's workdir.
- **Cache safety:** flipping a session's idle state does *not* change the graph
  payload (structural field only) — asserts the split holds.
- **Frontend:** given a graph payload with worktrees and a session list, `GitGraph`
  renders a badge on the matching HEAD node with the state-derived dot; an orphan
  worktree renders muted; a worktree whose head is off-graph appears in the strip.
- **UI E2E (optional, per project testing convention):** only if this proves to need
  a Gherkin flow — a graph with a live worktree shows the agent badge. Follow the
  project's "feature-first red-green vs skip for UX polish" rule.

## Non-goals / deferred

- Live-updating the badge without the session-list poll (e.g. websocket push) —
  the existing poll cadence is sufficient.
- Showing per-worktree uncommitted/unpushed counts on the graph badge — that lives in
  the WorktreePanel; revisit only if the HEAD-node badge feels thin.
- Any change to how worktrees are created, reaped, or reconciled.
