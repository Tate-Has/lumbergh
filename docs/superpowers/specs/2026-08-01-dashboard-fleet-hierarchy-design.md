# Dashboard fleet hierarchy: grouped sub-sessions, first-class Bill, orphan-only worktrees

**Date:** 2026-08-01
**Status:** Approved (design)

## Problem

The backend now models a fleet hierarchy — Bill → overseers → workers (see
`fleet.snapshot`) — but the dashboard still renders every tmux session as a flat,
equal card. Three consequences:

1. **Workers and their overseers sit side by side** with no grouping. A batch of
   spawned workers floods the board with full-detail cards that duplicate their
   parent's context.
2. **Every worktree shows in the top panel**, including ones backing a live
   session. Those don't need a reap affordance — their session card already
   represents them — so the panel is cluttered with rows the user can't (and
   shouldn't) act on.
3. **Bill is just another card.** He's the manager of the whole fleet but has no
   more prominence than a scratch session, and in the individual-session view
   there's no persistent way to get back to him.

## Goals

- Group worker sub-sessions under their parent overseer on the dashboard, with a
  compact, low-detail presentation.
- Make Bill a first-class citizen: a distinct hero on the dashboard and pinned to
  the left of the session switcher in the detail view.
- Reduce the worktree panel to only the worktrees that actually need reaping
  (orphans with no live session).

## Non-goals

- **No `DELIVERED`/`FAILED` outcome on dashboard worker rows.** Parsing an
  outcome means reading each worker's transcript; `fleet` does this only on the
  way out of its long poll precisely because doing it per-poll stalls the event
  loop. The dashboard polls `/sessions` every 10s, so it must stay
  transcript-free. Worker state is conveyed by fields already in the payload.
- **No new dashboard dependency on `/api/bill/fleet`.** That endpoint has
  seen/unseen side effects (`_mark_seen`) and is Bill-scoped; polling it from the
  dashboard would clear the user's "while you were away" overlay. Everything the
  dashboard needs is derivable from an enriched `/sessions`.
- No change to `lb`, the `/worktrees` endpoint payload, or `fleet.snapshot`.

## Design

### 1. Backend — enrich `/sessions` with `role` and `parent`

`list_sessions` (`backend/lumbergh/routers/sessions.py`) gains two fields per
session row, both computed in-memory over the list already being built — no
subprocess, no transcript, no fleet call:

- `role`: `"bill"` when `name == BILL_SESSION` (`"bill"`); `"worker"` when
  `type == "worktree"`; otherwise `"session"`.
- `parent`: for a worker row, the `name` of the session whose resolved `workdir`
  equals the worker's resolved `worktree_parent_repo`; `null` otherwise (and
  `null` for every non-worker row).

Parent resolution mirrors `fleet._resolved` / `fleet.snapshot`: build a map of
`{resolved(workdir): name}` over the non-worker rows, then look up each worker's
resolved `worktree_parent_repo`. Path resolution is best-effort — an
unresolvable path falls back to the raw string, and a worker with no matching
live overseer gets `parent: null` (it renders as a top-level card, an "orphan
worker").

`BILL_SESSION` lives in `bill_nudge` / `bill` router today; the sessions router
will reference the same constant (import it, don't re-hardcode `"bill"`).

**"Overseer" is not a stored role.** A session is presented as an overseer purely
because it *has* worker children. That is a frontend-derived fact, so no backend
flag is needed and a plain solo session never sprouts an expander.

Edge cases:
- Two live sessions sharing a resolved workdir: last-writer wins in the map
  (same non-determinism `fleet` already tolerates; acceptable — sharing a repo
  root across two live overseers is degenerate).
- Bill's own `workdir` is his home, not a repo root, so no worker resolves to
  him; he is never a `parent`.

### 2. Frontend — Dashboard grouping + Bill hero

**Pure grouping helper.** A new `groupSessions(sessions)` (e.g.
`frontend/src/utils/sessionGroups.ts`) partitions the alive/non-paused list into:

```
{
  bill: Session | null,                       // role === 'bill'
  groups: { parent: Session, workers: Session[] }[],  // parent has >=1 worker child
  solos: Session[]                            // everything else, incl. orphan workers
}
```

A worker attaches to a group when its `parent` names a session present and live
in the list; otherwise it falls into `solos`. Ordering: top-level items (group
parents + solos) keep the existing `sessionUrgencyRank` → `lastUsedAt` sort;
workers within a group sort by `sessionUrgencyRank`. Bill is removed from groups
and solos (he's the hero).

**Bill hero (`BillHeroCard`).** Rendered above "Active Sessions" only when
`bill` is non-null (live). Full-width, visually distinct (heavier border/tint),
`UserRoundCog` icon to match the existing summon button. Content:
- Bill's live status (from his `idleState`, via the shared `getSessionStatus`).
- A rollup line: *"watching N sessions · M need you"*, where N = number of
  `groups` (sessions with children) and M = count of direct reports needing
  attention. "Needs attention" reuses the existing signal: `idleState` is
  `blocked`/`error`, or (`idleState === 'idle'` and `unseen`), or `needsAnswer`.
- Click navigates to Bill's session. When Bill isn't live, no hero renders and
  the header's existing Summon Bill button remains the entry point.

**Overseer card.** For each `group`, the parent renders as (approximately) the
current `SessionCard` plus a footer control: worker count, an attention rollup
badge (e.g. `1 ✋ needs you`), and an expand/collapse toggle (collapsed by
default; expansion state is local component state). Expanded, it reveals the
group's worker rows nested beneath it.

**Worker row (`WorkerRow`).** Compact, low-detail: status dot + state icon,
`displayName || name`, state label, an attention marker (✓ finished =
idle+unseen, ✋ blocked, ⚠ error), and click-to-open (navigate to the worker
session). A small delete/reap control stays available (worktree cleanup path,
same as `SessionCard`'s delete). Explicitly dropped vs. a full card: cloud
toggle, star, window count, description, agent-provider badge, pause/edit/reset.

**Solo sessions** render as the existing `SessionCard`, unchanged.

**Inactive Sessions** section is unchanged — dead/paused sessions (including dead
workers) stay in a flat grid. Grouping the dead adds cost without value.

### 3. Frontend — Bill pinned left in the session switcher

`SessionNavigatorDots` (used by both desktop `TerminalHeader` and the mobile tab
bar) pulls the session named `bill` out of the alphabetical list and renders it
**first**, ahead of the starred group, with:
- the `UserRoundCog` icon instead of two-letter initials, and
- a distinct ring/tint so Bill reads as the manager, not a peer.

Applies to both the `compact` and non-compact variants, so "Bill always on the
left" holds on desktop and mobile from one change.

### 4. Frontend — Worktree panel: orphans only

`WorktreePanel` filters its rows to `state === 'orphan'` before rendering. Active
worktrees (those backing a live session) are now represented by their grouped
session cards and leave the top of the board. The panel already returns `null`
when it has no rows, so an all-active machine shows no panel. The reap flow and
the backend `/worktrees` payload are unchanged (the filter is frontend-only, so
`lb` and other consumers still see every worktree).

## Testing

Per project testing conventions (feature-first red-green for user stories; skip
Gherkin for UX polish):

- **Backend unit** (`backend/lumbergh/tests/`): `list_sessions` sets `role` and
  `parent` correctly — a worktree session resolves to its parent overseer by
  repo path; Bill gets `role: "bill"`; a worker whose parent repo has no live
  session gets `parent: null`; a plain session gets `role: "session"`,
  `parent: null`.
- **Frontend unit**: `groupSessions()` — a worker nests under its live parent;
  an orphan worker lands in `solos`; Bill is extracted to `bill`; ordering
  follows `sessionUrgencyRank`.
- **UI E2E (Gherkin, Playwright/pytest-bdd)** — one scenario for the user story:
  with a live overseer and a spawned worker, the worker is not a top-level card,
  the overseer shows a worker count, expanding reveals the worker row, and Bill's
  hero is present. Styling specifics and the worktree-panel filter are polish —
  covered by unit tests / manual check, no Gherkin.

## Rollout / touch list

- `backend/lumbergh/routers/sessions.py` — `role`/`parent` enrichment in
  `list_sessions`; import `BILL_SESSION`.
- `frontend/src/utils/sessionGroups.ts` — new `groupSessions` helper (+ unit test).
- `frontend/src/pages/Dashboard.tsx` — consume the helper; render hero + groups.
- `frontend/src/components/BillHeroCard.tsx` — new.
- `frontend/src/components/OverseerCard.tsx` + `WorkerRow.tsx` — new (or fold
  the overseer affordance into `SessionCard` with a `workers` prop; decided at
  plan time).
- `frontend/src/components/SessionNavigatorDots.tsx` — pin Bill first.
- `frontend/src/components/WorktreePanel.tsx` — orphan-only filter.
- Tests as above.
