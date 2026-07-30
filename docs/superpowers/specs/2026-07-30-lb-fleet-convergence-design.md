# Design: Converging `lb` and `sherpa fleet`

**Date:** 2026-07-30
**Status:** Approved — ready for implementation planning
**Origin:** `~/.config/lumbergh/shared/lb-fleet-convergence.md` (surfaced 2026-07-30 while running a fleet batch alongside an `lb`-spawned scout; the scout was visible in `lb`, the fleet workers weren't).

## Problem

`lb` (Lumbergh's agent CLI) and `sherpa fleet` are two overlapping worker-orchestration tools with a seam between them.

- **`lb`** is the observe/drive substrate. It talks to the Lumbergh backend over HTTP and tracks at **session** granularity: a state classifier, transcript reader, `prompt`/`wait`, plus its own worktree-isolated `spawn` (ship/scout) and a task board (`lb fleet` → `/api/bill/fleet`).
- **`sherpa fleet`** is a standalone Redis-based orchestrator. It spawns workers as **tmux windows inside one session**, each in its own git worktree, and owns the issue→batch→`land`→teardown workflow. It deliberately requires no server — just tmux + git + Redis.

**The blind spot:** a fleet run stuffs N agents into windows of a single session (e.g. `port`), so `lb` sees only the parent session — one state, one transcript — blind to the workers inside it. A standalone `lb`-spawned session (a scout) shows up fine; fleet workers don't.

## Guiding principle: context-efficient control

The north star for the converged tool is **`lb` as context-efficient control**. The dividing line between "built into `lb` as a subcommand" and "left to a skill/agent" is **inference**:

- A step that is **deterministic** (no judgment — enumerate windows, assemble a batch, land, teardown) belongs *inside* `lb` so an agent gets the final state in **one call** instead of several turns of glue.
- A step that needs **judgment** stays in the skill/agent layer.

This reframes the "god command" concern: the enemy is not a large command surface, it is a *chatty* one. The surface may grow, as long as every command collapses many turns into one deterministic result.

## Decisions (settled during brainstorming)

1. **End-state:** shared substrate; deterministic workflows become built-in `lb` verbs; judgment-requiring flows stay as skills. `sherpa fleet` is absorbed rather than kept as a peer.
2. **Backend dependency:** the converged `lb` **requires the Lumbergh backend** (that's acceptable). Fleet's orchestration moves behind the backend; `lb` stays a thin client.
3. **Architecture:** **Approach A** — a flat `target` string identifier + `run`-grouping over the existing worktree/task registry. (Rejected: a hierarchical Worker-under-Session entity model — more code/concepts, fights the current flat keying; and a "keep Redis" variant — leaves two coordination stores.)
4. **Redis:** dropped entirely. A `run` of `session:window` targets is fully observable via the existing pane classifier, so no worker self-reporting is needed.
5. **Scope:** full convergence in **one** spec, structured as phased increments so it remains buildable in passes.

## Architecture: the `target` model (Approach A)

One concept replaces "session" everywhere it means "a thing I observe/drive": a **target**, a string that is either:

- `session` — the whole session's active window (today's behavior, unchanged), or
- `session:window` — a specific window.

Because tmux `-t` already parses `session:window[.pane]` syntax, the pane-capture functions (`capture_pane_content` / `capture_pane_text` / `capture_pane_title` in `tmux_pty.py`) need **no logic change** — their parameter is renamed and re-typed from `session_name` to `target`, and callers that assume "bare session" stop assuming it.

Every trackable agent — standalone session, ship, scout, or a fleet-batch window — is addressed by one `target` string. A `run` (group id) on the task record turns a set of targets into a batch. `origin` (already present, groups Bill's crew) is orthogonal and unchanged.

## Components & changes

### 1. Window-aware substrate

- **Discovery:** a new backend step enumerates windows per session (`tmux list-windows`) and, for each window, decides "is a claude running here?" using the idle_detector's existing pattern matching applied per-pane. Every window running a claude becomes a first-class target. A session with a single claude in its active window collapses to the bare-`session` target, so standalone/ship/scout sessions are unaffected.
- **State & transcript per target:** `idle_monitor` classifies one state per target (not per bare session), reading from that target's pane. Transcript reading keys on the target's pane/cwd. A fleet run's `port:fleet-644` window gets its own `state`, `transcript`, and `unseen` flag.
- **Registry:** in `worktrees.py`, `associated_session` generalizes to `target`; each task record gains an optional `run` group id. Standalone tasks have no `run`; a batch's workers share one.

**Value alone:** a single pane of glass — `lb` and the dashboard list every agent (fleet-batch windows and standalone sessions), each individually addressable via `lb read/state/prompt/wait --session port:fleet-644`.

### 2. Unified spawn

One backend spawn primitive with an optional destination:

- `lb spawn …` (no destination) → new **session**, as today (standalone ship/scout).
- `lb spawn … --into <session> [--run <id>]` → new **window** in that session, tagged with `run`.

Both paths produce a `target`, a worktree, a registry record, and deliver the brief the same way (`spawn_delivery.py`). The shared worktree lifecycle (`record_worktree`, links, reconcile, reap) is inherited by both shapes.

### 3. Deterministic workflow verbs (built-in)

Each collapses a multi-turn dance into one call:

- **`lb batch --repo <p> --run <id> --briefs <dir|list>`** — stand up N workers as windows in one session, each worktree-isolated. (Absorbs `fleet spawn` ×N.)
- **`lb land --run <id> [--onto <branch>] [--push]`** — assemble the run's branches, run the project smoke gate, single-push the batch. (Absorbs `fleet land`.)
- **`lb teardown --run <id>`** — kill the run's windows + reap its worktrees + branches, refusing where `worktree reap` would lose work (uncommitted/unpushed). (Absorbs `fleet kill`/`clear`.)

### 4. Redis removal

Every fleet-over-Redis capability maps to what the always-present backend already does:

| fleet (Redis) | converged `lb` |
|---|---|
| `status` | task registry + per-target state (§1) |
| `watch` (events stream) | `lb fleet --wait` long-poll (exists) |
| `report` / `stop-hook` (worker self-report) | **gone** — state inferred from the pane |
| `ask` / `inbox` (needs-decision uplink) | worker's pane → `blocked` state → `lb wait --until blocked` + `lb prompt` |

The `ask`/`inbox` replacement is the one semantic shift: instead of a worker XADD-ing a question and blocking on Redis, it asks in its pane and stalls; the classifier reports `blocked`, and the overseer answers with `lb prompt`. Consequently **workers no longer need fleet installed or a `FLEET_*` env** — a real simplification.

## The `lb` command surface (after convergence)

Sorted by the inference test:

- **Observe/drive (unchanged, now target-aware):** `read`, `state`, `wait`, `wait-output`, `prompt`, `fleet`, `worktree*` — these simply accept `session:window` targets now.
- **Spawn (extended):** `spawn … [--into <session> --run <id>]`.
- **New built-ins (deterministic → in-binary):** `batch`, `land`, `teardown`.

Three new verbs. The surface grows only with verbs that finish a whole deterministic job — never chatty primitives — which is the god-command-vs-context-efficiency line.

## `sherpa fleet` deprecation path

`sherpa fleet` is not rewritten in place. Its behavior is re-homed into `lb`/backend, then `sherpa fleet` becomes a **thin shim** that shells out to the new `lb` verbs (so muscle memory and existing scripts keep working) with a deprecation notice. It is deleted once nothing calls it. No flag-day cutover.

## Phasing

Each phase ships value and is independently landable.

1. **Window-aware substrate** — target model, discovery, per-target state/transcript, registry `target`+`run`. *(Ships the single pane of glass alone.)*
2. **Unified spawn** — `--into`/`--run`, one spawn primitive.
3. **Workflow verbs** — `batch`, `land`, `teardown`.
4. **Redis removal + fleet shim** — cut the worker-side uplink over to `blocked`+`prompt`, re-home `sherpa fleet` onto `lb`, deprecate.

## Testing

- **Backend unit tests:** target parsing (`session` vs `session:window`), window discovery / claude-detection per pane, `run`-grouping in the registry.
- **Red-green for the core gap:** per the repo's red-green rule, Phase 1 opens with a failing test that reproduces "a fleet worker in `port:fleet-644` is invisible/undriveable via `lb`," which passes once discovery + per-target state land.
- **E2E (the convergence regression guard):** spawn a 2-worker batch (`lb batch`), drive one worker to `blocked`, answer it with `lb prompt`, then `lb land` and `lb teardown` the run — exercising discovery, per-target state, the needs-decision replacement, and the workflow verbs end-to-end.

## Non-goals

- Headless (no-backend) operation — explicitly dropped; the backend is required.
- A hierarchical Worker/Session entity model — flat `target` + `run` is the model.
- Preserving any worker-side Redis uplink.
