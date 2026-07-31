# Overseer-centric `lb fleet` — design

**Date:** 2026-07-31
**Status:** approved, pre-implementation
**Scope:** visibility only (enumeration). Attention/escalation rewiring is explicitly deferred.

## Problem

Bill (the middle-manager orchestrator) cannot see the top-level sessions he is
meant to manage. Running `lb fleet` shows only spawned worktree workers — and
when none are live, `0 tasks` — because `fleet.snapshot()` iterates *only*
tracked worktrees (`worktrees.reconcile_all`). A direct session like `port`
(the overseer running on the main checkout) is never a tracked worktree, so it
can never appear, regardless of the `origin` filter.

The intended management chain:

```
you
└─ bill            middle manager — talks to overseers, escalates real issues up
   ├─ port         overseer — manages the workers doing the work
   │  ├─ 668-ship  worker
   │  └─ 673-e2e   worker
   ├─ aio          overseer
   └─ lumbergh     overseer
```

Bill's fleet is **overseer-centric**: overseers are his direct reports; workers
nest under them for context.

## Roles

- **Bill** — the viewer/root. Never a row in his own fleet.
- **Overseer** — any live agent session that is not itself a spawned worker
  (`port`, `aio`, `lumbergh`, …). An overseer with no workers is a valid leaf.
- **Worker** — a tracked worktree (today's fleet row), nested under the overseer
  whose `workdir` equals the worker's `parent_repo`.

"Live agent session" = a discovered agent session from `idle_monitor.live_targets()`
/ `worktrees._live_sessions()`, reduced to its bare session name.

**A session is an overseer only if it is none of:** `bill`; a worker itself; or a
**run/batch container** — a session that merely holds worker windows. A batch run
creates a container session (e.g. `port-661-673`) whose windows are worker targets
(`port-661-673:661-reporting`). Exclude any session name that appears as the
`session` part (`parse_target(target)[0]`) of a worker target, so containers are
never mistaken for overseers. Concretely, overseer candidates come from stored
*direct*-type sessions (`port`, `aio`, `lumbergh`) minus `bill`; worker and
container sessions are excluded by the rule above.

## Approach (chosen)

Extend `fleet.snapshot()` — the single source of truth already shared by the
`lb fleet` CLI and the dashboard — rather than adding a parallel view or doing
the join in the CLI. One enumeration, both consumers benefit.

Alternatives considered and rejected:
- *New `/bill/overview` endpoint composing sessions + fleet* — duplicates
  enumeration; the user asked about `lb fleet` specifically.
- *Join `/sessions` + `/fleet` client-side in the CLI* — pushes the tree logic
  into the CLI and forces the dashboard to reimplement it.

## Data model / enumeration changes

`fleet.snapshot(...)` gains overseer rows and a parent link:

1. **Worker rows** — unchanged in substance. Additionally set:
   - `role = "worker"` (the existing `kind` stays the spawn kind: ship/scout)
   - `parent` = the owning overseer's session name, resolved by matching the
     worker's `parent_repo` to a live overseer session whose `workdir` resolves
     to the same path. If no live overseer matches, `parent = None` (orphan →
     rendered at top level so nothing hides).
2. **Overseer rows** — for each live agent session that is *not* backing a
   tracked worktree and is not `bill`, emit a row:
   - `role = "overseer"` (`kind` empty)
   - `session` = the session name; `state`/`since`/`unseen` from the existing
     `state_of` / `since_of` / `unseen_of` lookups.
   - `path` = the session's `workdir`; worktree-only columns (`branch`, `run`,
     `outcome`) are empty/`None`.
3. **Ordering** — each overseer immediately followed by its workers; orphan
   workers last. The payload stays a **flat list of rows**; the tree is derived
   from `kind` + `parent`. No structural nesting in the API.

`bill` is excluded by name (`BILL_SESSION`/`BILL_ORIGIN` constant already exists).

## `--origin` and `--wait`

- Plain `lb fleet` returns the full tree: all overseers + all their workers.
- `--origin <name>` continues to narrow **workers** by their stamped origin;
  overseers are sessions (not origin-stamped) and always show.
- `lb fleet --wait` behavior is **unchanged** in this step: it still defaults to
  `origin=bill` and wakes on worker attention. Making `--wait` wake Bill on
  *overseer* state (idle/blocked = "needs direction") is the next step toward the
  escalation goal and is **out of scope here**.

## CLI rendering (`lb fleet`)

Render overseers with their workers indented beneath. The `kind` column already
exists; add a `parent` column. Existing columns and the two load-bearing path
columns are preserved.

## Testing

Unit tests on `fleet.snapshot`:
- an overseer session with no worktrees appears as `kind="overseer"`;
- `bill` is excluded;
- a worker nests under the overseer whose `workdir == parent_repo` (`parent` set);
- a worker whose overseer session is not live surfaces at top level (`parent=None`);
- a batch **container** session (holds worker windows) is *not* emitted as an overseer;
- `--origin` still narrows workers while overseers remain visible.

## Deferred (next step, not this change)

- Escalation/attention: `lb fleet --wait` and the Bill nudge waking on overseer
  state so Bill surfaces only what needs the human, reducing prodding.
- Per-overseer ownership stamped at spawn time (today every spawn is
  `origin="bill"`; nesting currently relies on the `parent_repo → workdir` match,
  which is sufficient for one overseer per repo).
