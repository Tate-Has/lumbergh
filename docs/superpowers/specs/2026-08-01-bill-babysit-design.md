# Bill "babysit": server-owned keep-alive loops for overseers

**Status:** design
**Date:** 2026-08-01
**Related:** [[project_worktree_lifecycle_and_bill]], [[project_lb_fleet_convergence]], `2026-07-31-overseer-centric-fleet-design.md`

## Problem

Bill can route a one-shot request to an overseer and then wait for exceptions, but he
cannot *keep an overseer cycling*. When the user asked him to "watch port — keep it moving
through the backlog: when it's done, run `/fleet-handoff`, then `/clear`, then `/fleet-start`,
and repeat," Bill did the only thing his rulebook has a shape for: he sent one `lb prompt`
containing all three commands as prose, then went to `lb fleet --wait`. That fails three ways:

1. **Slash commands aren't a relayable to-do list.** `/fleet-handoff`, `/clear`, `/fleet-start`
   are keystrokes injected into the session at specific moments, not instructions handed to it
   in a sentence. `/clear` wipes the session's context — so "run `/clear` then `/fleet-start`"
   destroys the very instruction to run `/fleet-start`. The sequence *must* be driven from
   outside, step by step, gated on the session going idle between steps.
2. **Bill has no "driver" shape — only "router + exception-waiter."** His vocabulary is
   one-shot delegate, then passively surface blocked/error/idle-unseen. "Keep this session
   cycling indefinitely" is a standing routine, and he has no primitive for it, so he flattened
   a stateful loop into one fire-and-forget message.
3. **The cadence is deterministic, and he was asked to improvise it.** "When the session is
   idle, send these commands in order, gated on idle between each, repeat" has zero judgment in
   it. Per the project's own convergence principle (deterministic steps live in `lb`; judgment
   lives in the agent), a small local model hand-driving a stateful `/clear` loop is precisely
   the chatty anti-pattern that principle exists to prevent — and it does not scale to the
   several sessions the user will eventually want babysat at once.

## Goal

The user opts a session into a continuous loop ("Bill, keep port looping"). The loop keeps that
overseer cycling through its backlog with periodic context refreshes, runs **server-side** so
neither Bill nor the session has to remember to keep going, and surfaces to the user — through
Bill — only when something genuinely needs a human decision. Bill *owns* it from the user's
chair (he starts it, reports on it, cancels it) without nursing each keystroke. Multiple
sessions can be babysat concurrently.

## Non-goals

- A general-purpose routine/automation engine. This is one shape — keep an overseer cycling —
  scoped tight. No cron, no arbitrary user scripts.
- Teaching Bill to hand-drive the cadence turn-by-turn. That is the failure being designed out.
- Changing how workers (ship/scout) are supervised. Babysit operates at the overseer level.

## Design

### The judgment / mechanism split

The refresh ritual divides cleanly, and the division is the heart of the design:

- **The session owns *when*.** A capable overseer (a Claude Code session) can watch its own
  context bar and decide it is time to refresh. It runs `/fleet-handoff` **itself** and ends
  that command by printing a sentinel line.
- **The routine owns what the session structurally cannot do for itself.** A session cannot
  restart itself after `/clear` — the clear wipes the context that would remember to. So the
  routine's irreducible job is exactly the two steps on the far side of a clear: send `/clear`,
  then send `/fleet-start`. It does nothing the session could have done alone.

This split is why the loop is reliable: the routine never has to *judge* when to refresh
(the session signals it) and never has to parse a context bar. It watches for one explicit
marker and reacts mechanically.

### `lb babysit` — the standing loop

Bill (or the user) starts a loop with:

```
lb babysit --session <name>          # start babysitting an overseer
lb babysit --stop --session <name>   # cancel it
lb babysit --list                    # active loops (also surfaced in lb fleet)
```

Starting registers an entry in a small persisted registry
(`~/.config/lumbergh/babysits.json`, reconciled like the worktree registry) so loops survive a
backend restart. The backend runs one independent watch loop per registered session,
concurrently. `lb fleet` marks a babysat overseer's row so the whole span of what Bill manages
is visible at a glance.

### The watch loop (per session)

The backend already runs `idle_monitor`, which knows every session's live state and can read a
session's transcript. The babysit loop subscribes to its babysat session's state and reacts:

1. **Session idle, last agent message contains the refresh sentinel** (`⟳ REFRESH-READY` by
   default) → the session has written its handoff and is asking to be cycled. Send `/clear`,
   then `/fleet-start`. The session picks up fresh from its handoff doc and continues. Loop.
2. **Session idle, last message contains the empty sentinel** (`⟳ BACKLOG-EMPTY`) →
   `/fleet-start` found nothing to do. Stop the loop and escalate: Bill reports "port's backlog
   is clear."
3. **Session blocked or error** → it is asking a question or has failed. Pause the loop and
   escalate to Bill (via the existing `bill_nudge` path). Bill answers from `preferences.md` if
   he can, else asks the user. When resolved, the loop resumes.
4. **Session idle, no sentinel** → the session finished a chunk without asking to refresh (still
   has context budget) and without printing a sentinel. Default: leave it; the session drives
   its own within-context progress and only signals at a boundary. (A `--nudge-idle` option can
   send a bare `/fleet-start` here for sessions that don't self-continue, but the default assumes
   the session keeps itself moving until a refresh boundary.)
5. **User takeover detected** (input activity in the session the routine didn't send) → pause
   the loop immediately so it can never fight the user's keystrokes with a `/clear`, and flag it
   for Bill to confirm cancellation. Explicit `lb babysit --stop` remains the primary cancel
   path; this is the safety net.

Everything the loop can handle mechanically (case 1) it does silently. Everything needing a
human decision (2, 3, and 5) it hands up. That is the "only bug me when it's genuinely mine"
behavior.

### The session-side contract

The only cooperation required from the babysat project is a sentinel. The session's
`/fleet-handoff` command ends by printing `⟳ REFRESH-READY`; its `/fleet-start` prints
`⟳ BACKLOG-EMPTY` when there is nothing to pick up. That is the entire contract — printed
markers, no shell coupling, no new dependency on `lb` from the session's side.

The sentinel strings and the refresh commands are configured, not hardcoded, so babysit is not
welded to `port`'s particular command names:

```toml
# .lumbergh.toml
[babysit]
refresh_ready = "⟳ REFRESH-READY"     # session asks to be cycled
backlog_empty = "⟳ BACKLOG-EMPTY"     # nothing left to do
on_refresh = ["/clear", "/fleet-start"]  # what the routine sends after the sentinel
```

Defaults match the values above, so a repo that adopts the `port` convention needs no config.

### Bill's fourth shape: babysit

Bill's AGENTS.md today has three shapes — ship, scout, hand-off. This adds **babysit**:

> When the user asks you to keep a session moving / looping / cycling / babysat, your job is
> `lb babysit --session <name>` — start the loop, confirm it to the user, and go back to
> `lb fleet --wait`. You do **not** hand-drive the handoff/clear/start cadence yourself, and you
> never send those commands as prose in a single `lb prompt` — the loop owns the keystrokes and
> their timing. When the user says they are taking a session over, cancel its babysit with
> `lb babysit --stop --session <name>`.

The AGENTS.md entry includes the `port` incident as the worked example of the wrong move
(cramming the three commands into one prompt), because that is the specific failure the shape
exists to prevent.

Bill's supervision does not get harder as the number of babysat sessions grows: he still arms a
single `lb fleet --wait`, which already covers all his overseers. Whichever loop escalates, that
session's named row is what wakes him. Ten babysits, one supervision loop.

## Components to build

- `backend/lumbergh/babysit.py` — the per-session watch loop and the registry
  (`~/.config/lumbergh/babysits.json`). Reuses `idle_monitor` state + transcript reads,
  `tmux_pty.send_text` for the refresh commands, and `bill_nudge` for escalation. No new
  low-level primitives.
- `POST /api/bill/babysit` (start), `DELETE /api/bill/babysit` (stop), and inclusion of
  babysit state in the fleet snapshot / `GET /api/bill/fleet`.
- `backend/lumbergh/agent_cli/babysit.py` + registration in `agent_cli/main.py`
  (`lb babysit --session|--stop|--list`).
- `worktrees.read_babysit_config` (or a small `config` reader) for `.lumbergh.toml [babysit]`.
- `fleet.snapshot` marks babysat overseer rows.
- AGENTS.md template: the `babysit` shape + the `port` worked example.
- **Session-side (outside Lumbergh, in the babysat repo):** the `/fleet-handoff` command prints
  `⟳ REFRESH-READY`; `/fleet-start` prints `⟳ BACKLOG-EMPTY` on an empty backlog. Documented as
  the babysit contract; `lb init` can scaffold the `[babysit]` table.

## Testing

- Unit: the watch-loop state machine — sentinel-in-transcript → sends `[/clear, /fleet-start]`;
  blocked/error → escalates and pauses; backlog-empty → stops and escalates; idle-no-sentinel →
  no-op; user-takeover → pauses. Fake the state/transcript/send hooks the way the existing fleet
  and bill_nudge tests do.
- Registry: multiple concurrent babysits register/stop independently and survive a reconcile.
- End-to-end (against a live session, per the project's bug-repro rule): a real Claude Code
  session that prints the sentinel is cycled through one full handoff→clear→start by the loop,
  and a `--stop` releases it mid-loop without a dangling `/clear`.

## Open questions

- **Resume after escalation.** When a blocked session is answered and returns to work, the loop
  should resume automatically. Confirm the state transition (blocked→working→idle) is
  unambiguous enough to distinguish "resumed the same chunk" from "finished and awaiting
  refresh." Likely fine (only a sentinel triggers a refresh), but worth an explicit test.
- **Backlog-empty vs. a slow start.** `/fleet-start` may idle briefly before it begins working.
  The loop must not read that transient idle as `BACKLOG-EMPTY`; the empty case is gated on the
  explicit sentinel, not on idle alone — verify the session prints it reliably.
