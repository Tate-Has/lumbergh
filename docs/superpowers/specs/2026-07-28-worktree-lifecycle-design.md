# Worktree Lifecycle — Design

**Date:** 2026-07-28
**Status:** Approved (brainstorm), pending implementation plan
**Scope:** Sub-project A of two. Sub-project B ("Bill," the first-mate orchestrator) is a
separate spec that sits on top of this one.

## Motivation

Lumbergh already creates worktree-backed sessions (`mode="worktree"`): it makes a worktree at
`{repo}-worktrees/{branch}`, records `worktree_parent_repo` + `worktree_branch` on the session,
and can remove the worktree on session delete. Three things are missing:

1. **Env linking** — a fresh worktree has none of the parent's git-ignored env dirs (`.venv`,
   `node_modules`, `.env`), so it isn't immediately runnable without a reinstall.
2. **A first-class lifecycle** independent of a single session — worktrees that predate/outlive a
   session, hand-made worktrees, orphans, and worktrees handed between sessions can't be
   represented today.
3. **A CLI surface** — the orchestrator ("Bill") is just another Lumbergh session and acts by
   running shell commands, so worktree operations must exist as CLI subcommands, not only as
   backend functions or HTTP endpoints.

## Key decisions (from brainstorm)

- **Home base:** one core module in the backend, exposed BOTH as backend/REST (for the web UI) and
  as `lb worktree` subcommands (for Bill and humans). One implementation, no drift.
- **Tracking model:** reconciled registry — `git worktree list` is the source of truth for what
  exists; we keep a thin metadata overlay and join the two on read.
- **Env linking:** symlink by default, auto-detected set, overridable by a project dotfile.
- **Dotfile scope:** `.lumbergh.toml` `[worktree]` with an authoritative `links` list (per-path
  symlink/copy mode) plus optional `post_create` command hooks.
- **Reap policy:** explicit and guarded only. Orphans are surfaced, never auto-killed. Disposability
  (auto-reap after a green PR) is deferred to Bill, who will call `reap` himself.
- **Location:** sibling to the repo by default (`{repo}-worktrees/{branch}`, today's behavior),
  overridable to a central base dir globally and per-project.

## Architecture & surfaces

One core module, two front doors:

```
backend/lumbergh/worktrees.py         # core lifecycle: create · link · track · reconcile · reap
backend/lumbergh/routers/worktrees.py # REST for the web UI
lb worktree <subcommand>              # CLI front door (Bill + humans)
```

The core module is a lifecycle layer on top of the existing `git_utils` primitives
(`create_worktree`, `remove_worktree`, `list_worktrees`, `validate_branch_for_worktree`), not a
rewrite of them.

Integration with existing code:

- `_resolve_worktree_workdir` in `routers/sessions.py` is rerouted through this module, so
  worktrees created via session creation also get linking, `post_create` hooks, and a registry
  entry.
- Session-delete-with-cleanup (`delete_session(cleanup_worktree=True)`) calls the module's guarded
  `reap` instead of `remove_worktree` directly (session delete may pass `force=True`).

## The registry

A global TinyDB store at `~/.config/lumbergh/worktrees.json`, keyed by absolute worktree path.
Global (not per-project) so reconciliation across repos is a single read.

Per-entry fields:

```
path                # absolute worktree path (key)
parent_repo         # absolute path to the parent git repo
branch              # branch checked out in the worktree
created_at          # ISO timestamp (set by the backend, never inside a workflow script)
associated_session  # session name, or null
associated_agent    # derived from the session's agent_provider; null if no session
links_applied       # list of {path, mode} actually applied on create
task_intent         # optional freeform string ("fix flaky login test")
```

`associated_agent` is derived, not stored authoritatively — a session *is* an agent, so the agent
is whatever the owning session's `agent_provider` is at read time.

### Reconciliation (`lb worktree ls`)

Run `git worktree list --porcelain` for the target repo(s) and join against the store. Computed
state per worktree:

- **active** — present in git AND its `associated_session` is alive.
- **orphan** — present in git but no live owning session (surfaced in `ls`, never auto-reaped).
- **stale** — present in the store but gone from git (e.g. someone ran `git worktree remove` by
  hand) → the metadata entry is pruned on read.

Session liveness is checked via the existing session manager / tmux state.

## Worktree location

Where a worktree's directory is created, resolved in this order:

1. `.lumbergh.toml` `[worktree] base_dir` (per-project) — highest priority.
2. Global setting `worktree.base_dir` in `~/.config/lumbergh/global.json` — a central root for all
   repos.
3. Default: sibling container `{repo}-worktrees/` next to the parent repo (today's
   `get_worktree_container_path` behavior).

When a `base_dir` is set, a worktree lands at `<base_dir>/<repo-name>/<branch>`; the default sibling
layout is `<repo>-worktrees/<branch>`. Branch names are sanitized for the path as they are today.

**Filesystem caveat:** reflink `copy` mode only works when the worktree and the parent repo live on
the same filesystem. The default sibling location guarantees this; a central `base_dir` on a
different mount silently degrades `copy` to a full copy. This is a placement trade-off, not a
correctness bug — noted so users choosing a central dir understand the cost.

## Env linking

On create, link the parent's git-ignored env dirs into the worktree so it is immediately runnable.

Resolution order:

1. If `.lumbergh.toml` `[worktree]` exists in the parent repo, its `links` list is **authoritative**
   and auto-detection is skipped entirely.
2. Otherwise, auto-detect this default set: `.venv`, `node_modules`, `.env`, `.env.local`,
   `.direnv`.

Safety rules applied to every candidate (dotfile or auto-detected):

- Link only if the path **exists in the parent**.
- Link only if the path is **git-ignored in the worktree** — never shadow a git-tracked file.
- Skip if the path **already exists** in the worktree.

Each link is applied in one of two modes:

- `symlink` (default) — `worktree/<path>` → parent's real path. Zero disk, instantly runnable.
  Shares the parent's env, so a reinstall inside the worktree mutates the parent's too.
- `copy` — a real copy (CoW reflink where the filesystem supports it, plain copy otherwise). Fully
  isolated; safe for diverging deps; costs disk + time.

After links, run any `post_create` command hooks in the worktree.

### Known caveat: editable self-installs vs symlinked `.venv`

A Python project that installs itself editable (`pip install -e .` / `uv sync`) records the
**parent** repo path in the venv's `.pth`/editable finder. A symlinked `.venv` therefore imports the
parent's source, not the worktree's. Deps-only venvs are unaffected. The escape hatch is per-project
config: `{ path = ".venv", mode = "copy" }` plus a `post_create = ["uv sync"]` hook so the worktree
gets its own correctly-rooted install.

### Dotfile format

`.lumbergh.toml` at the repo root, namespaced so Lumbergh can grow other project config later:

```toml
[worktree]
base_dir = "~/.local/share/lumbergh/worktrees"  # optional; omit for sibling default
links = [
  { path = ".venv", mode = "copy" },   # editable-safe
  "node_modules",                       # bare string = symlink
  ".env",
]
post_create = ["uv sync"]
```

`post_create` executes shell commands from a repo-root file on worktree create. This runs with the
user's trust; acceptable because these are the user's own repos, but the trust boundary is stated
explicitly here and should be surfaced in docs.

## `lb worktree` command set

```
lb worktree create --repo <path> --branch <name> [--new] [--base <b>] [--session <name>] [--intent "..."]
lb worktree ls [--repo <path>] [--json]
lb worktree reap <path> [--force] [--rm-branch]
lb worktree adopt <path> [--session <name>]
lb worktree link|unlink <path>
```

- `create` — validate, create the worktree, apply links, run `post_create` hooks, write the registry
  entry, optionally bind to an existing session.
- `ls` — the reconciled table (`PATH · REPO · SESSION · AGENT · STATE`). `--json` is the
  machine-readable form Bill consumes.
- `reap` — the only destructive op. **Guarded:** refuses if the worktree has uncommitted changes OR
  unpushed commits, unless `--force`. `--rm-branch` also deletes the branch.
- `adopt` — attach a registry entry (and optionally a session) to a hand-made or orphaned worktree.
- `link <path>` — re-apply the configured/auto-detected links to an existing worktree (e.g. after
  editing the dotfile).
- `unlink <path>` — replace a symlinked entry with its own real copy, so the worktree stops sharing
  that dir with the parent (the "diverge only when needed" case).

## Web UI (v1, minimal)

- Creation already flows through `CreateSessionModal`'s worktree mode; it silently gains linking,
  hooks, and a registry entry via the rerouted backend path. No new creation UI.
- One new surface: a worktree panel on the Dashboard rendering the reconciled `ls` output, badging
  **orphans**, with a guarded **reap** button (surfacing the uncommitted/unpushed refusal).

## Testing

- **Unit:** reconciliation states (active / orphan / stale-prune); link application
  (symlink / copy / skip-tracked / skip-existing / skip-missing-in-parent); reap guard (refuse on
  dirty or unpushed); dotfile parse + auto-detect fallback.
- **E2E:** full `lb worktree create → ls → reap` roundtrip against a scratch repo.

## Out of scope (YAGNI)

- Auto-reap on session end, TTL/orphan auto-cleanup — deferred to Bill; this module offers only safe
  primitives.
- Cross-machine registry sync.
- Any orchestration logic — Bill (Sub-project B) is a separate spec.
