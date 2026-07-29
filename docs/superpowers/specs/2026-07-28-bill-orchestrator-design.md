# Bill — the First-Mate Orchestrator — Design

**Date:** 2026-07-28
**Status:** Approved (brainstorm), pending implementation plan
**Scope:** Sub-project B of two. Sub-project A (worktree lifecycle,
`docs/superpowers/specs/2026-07-28-worktree-lifecycle-design.md`) shipped first and is the
foundation this design stands on.

## Motivation

Lumbergh supervises many agent sessions, but the human is the only orchestrator. Every
decomposition, dispatch, check-in, and hand-off is manual. Firstmate
(github.com/kunchenguid/firstmate) demonstrates the alternative: talk to one agent, and it runs
a crew of workers in isolated worktrees, supervises them, and hands back finished work.

Bill is that role for Lumbergh — a **middle manager**. He knows the user's opinions, not the
code. He breaks work up, delegates it, moves it along, absorbs the small stuff, and reports
outcomes. He does not write code; he expects workers to write it and explain it, and he explains
the user's intent to them.

Firstmate solves this with a large instruction distro (502-line `AGENTS.md`, ~80 `bin/` scripts,
its own state tree). Lumbergh has something firstmate does not: a **running server** that already
tracks every session's state, detects blocked/idle/error, reads transcripts, and — since
sub-project A — owns a worktree registry. Bill is therefore much smaller than firstmate: most of
what firstmate implements in shell, Lumbergh already knows.

## Locked decisions

These were settled with the user before design and are not revisited here.

1. **Bill is not server infrastructure. Bill is just another Lumbergh session** whose working
   directory is a firstmate-style instruction bundle. His only superpower is driving peer sessions
   through the `lb` CLI. No new daemon.
2. **Bill is global, not per-repo.** One manager across all projects, holding the user's
   preferences — the one piece of state no single repo can own.
3. **Bill never writes project code.** He delegates implementation and investigation alike.
4. **Bill runs on a cheap local model** (Qwen-class) under the `pi` harness. Both are already
   supported: `pi` is a registered provider (`backend/lumbergh/providers.py`) with a dedicated
   transcript adapter (`backend/lumbergh/activity/pi.py`), so Lumbergh can read Bill's state and
   transcript like any other session.
5. **Personality toggle**, default off. `professional` by default; an opt-in `lumbergh` personality
   adds Office-Space flair. Swappable preamble, nothing more.
6. **Landing stays with the user.** Bill never merges.

### Two consequences of "cheap model, no code context"

These shape nearly every decision below, so they are stated once here:

- **Bill delegates his thinking, not just his coding.** When he cannot write a sharp brief, he
  dispatches a *scout* whose deliverable is a plan, then dispatches *ship* tasks from that plan. A
  vague brief is the primary cause of a worker confidently doing the wrong thing, and Bill lacks
  the code knowledge to avoid one unaided. Scouting reduces his job to relay, track, and sequence.
- **The protocol lives in CLI commands, not in a long prompt.** Small local models drop rules from
  long documents. Every step Bill takes is one `lb` subcommand that fails closed with an actionable
  error. His instruction bundle stays short. This is deliberately the inverse of firstmate's
  large-instruction-surface approach.

## Architecture

```
~/.config/lumbergh/bill/          Bill's session workdir — DOCUMENTS ONLY
  AGENTS.md                       rendered from the repo bundle + personality; refreshed on upgrade
  CLAUDE.md                       symlink to AGENTS.md (harness compatibility)
  preferences.md                  the user's opinions; Bill appends, user edits; NEVER overwritten
  briefs/<session>.md             per-task brief Bill writes before dispatch
  reports/<session>.md            scout deliverable, written by the worker

backend/lumbergh/bill/            tracked bundle source + materialization (new)
backend/lumbergh/worktrees.py     task state (extended: kind, origin, cross-repo reconcile)
lb spawn | lb fleet               Bill's new verbs (new)
POST /api/bill/summon             dashboard summon (new)
```

### State ownership: the server owns state, Bill owns documents

A Bill task *is* a `(session, worktree)` pair, which is exactly what sub-project A's registry row
already records (`path`, `parent_repo`, `branch`, `associated_session`, `task_intent`). Rather than
give Bill his own state tree, the registry is extended with two fields:

```
kind    "ship" | "scout" | null     what the task delivers
origin  "bill" | null               who dispatched it
```

Bill therefore **writes no state files**. He reads `lb fleet`. This is what makes a weak model
viable: there is no bookkeeping for him to forget, his conversation memory is never authoritative,
a restart is a non-event, and the dashboard sees his tasks for free.

Rejected alternatives: Bill owning state in his home (firstmate-style) duplicates a store just
built, and one missed status append loses a task; splitting state between server and Bill creates
two sources of truth for one question.

### Workers need no reporting protocol

Lumbergh already detects `blocked` (including question detection), `idle`, `error`, and
done-vs-idle attention. A worker that stops to ask something *is observed* as blocked. Firstmate's
entire `state/<id>.status` append contract therefore disappears.

The brief asks a worker for exactly one thing: finish with a single parseable line —
`DELIVERED: <url-or-branch>` or `FAILED: <reason>` — so Bill does not have to infer an outcome
from prose. Outcome detail beyond that line Bill gets with `lb read`.

### Structural guard on "never writes code"

Bill's workdir is `~/.config/lumbergh/bill/`, not a repo. A stray edit lands in his own home, not
in the user's project. The instruction is explicit as well, but the layout enforces it.

## New `lb` surface

This is Bill's complete vocabulary.

```
lb spawn --repo <path> --branch <b> [--new] [--base <b>] --brief <file>
         --kind ship|scout [--name <n>] [--agent <provider>] [--intent "..."]
lb fleet [--wait] [--timeout <s>] [--json]
lb worktree reap <path>            # already exists, guarded
```

### `lb spawn`

One call that: validates the repo and branch, creates the worktree through
`worktrees.create()` (so links, `post_create` hooks, and the registry row all happen), creates the
tmux session with the chosen provider, and delivers the brief to the fresh agent.

- **Fails closed** at every step with an actionable message naming the fix.
- **Unwinds its own partial work.** If session creation fails after the worktree exists, the
  worktree is reaped (guarded — it is empty, so the guard passes) and the registry row removed. A
  half-created task never survives a failed spawn.
- Records `kind` and `origin="bill"` on the registry row.
- **Task identity is the session name.** There is no separate task id: the session name is already
  unique and liveness-checked, so a task's brief is `briefs/<session>.md` and its report is
  `reports/<session>.md`. When `--name` is omitted it is derived from the branch, sanitized to the
  session-name pattern and suffixed if that name is already live.
- Brief delivery reuses the existing prompt path (`POST /api/agent/sessions/{name}/prompt`),
  passing a pointer to the brief file rather than pasting its body, so long briefs do not have to
  survive a terminal paste.

### `lb fleet`

The reconciled task table — one row per worker — joining the registry, live tmux state, and
attention:

```
TASK · REPO · BRANCH · SESSION · KIND · STATE · SINCE · UNSEEN
```

`state` comes from the live monitor (`working` / `idle` / `blocked` / `error`), plus `dead` for a
registry row whose session is gone and `orphan` for a worktree with no owning session.

**Cross-repo reconciliation is new work.** `worktrees.reconcile(repo, ...)` is per-repo; a global
Bill needs the whole fleet. `lb fleet` gathers the distinct `parent_repo` values from the registry
and reconciles each, so the existing per-repo logic is reused rather than rewritten.

`--wait` **long-polls server-side** and returns as soon as any row needs Bill: `blocked`, `error`,
`dead`, or done-with-unseen-output. It costs no tokens while blocked. Bill's supervision loop is
`wait → handle → wait`. On timeout it returns the unchanged fleet so Bill can simply re-arm.

### Summon and the idle backstop

- `POST /api/bill/summon` creates the `bill` session (provider `pi`, workdir
  `~/.config/lumbergh/bill/`) if it is not live, materializing the bundle first, and returns the
  session. A dashboard button calls it; from then on Bill is an ordinary session card with a
  terminal, state badge, quick input, and mobile support. An optional setting auto-spawns him on
  Lumbergh startup, **default off**.
- **Idle-Bill nudge backstop.** If the backend observes Bill `idle` while tasks with
  `origin="bill"` are live, it injects a wake into his pane. This covers the failure firstmate
  needed an entire turn-end-guard document for: a model that ends its turn without re-arming the
  wait. Here it is a small amount of code on top of the monitor and prompt paths that already
  exist.

## The instruction bundle

Tracked under `backend/lumbergh/bill/` and **materialized** into `~/.config/lumbergh/bill/` on
summon: `AGENTS.md` is (re)rendered every time, so Bill improves when Lumbergh upgrades;
`preferences.md`, `briefs/`, and `reports/` are never touched once they exist.

Rendering substitutes the personality preamble selected by the `bill.personality` global setting
(`professional` | `lumbergh`, default `professional`). **Personality affects only what Bill says to
the user** — never briefs, commits, PR text, or anything a worker or tool reads.

The bundle is short by design. Its contents:

- Role and hard rules (below).
- The dispatch loop and the three `lb` commands, each with the shape of its output.
- The ship/scout decision, and the delivery rule.
- How to read and update `preferences.md`.
- The brief template.

### Hard rules in the bundle

1. **Never write project code.** Delegate implementation, investigation, planning, and diagnosis.
2. **Never merge or land.** Report; the user decides.
3. **Never invent an answer.** Answer a worker only from `preferences.md` or the user's own
   request. Anything else — scope, product, or design judgment — escalates to the user. This is the
   guard on "deflects": deflecting a question the worker actually needed answered produces a
   stalled worker or, worse, a confidently wrong one.
4. **Never reap unlanded work.** A `reap` refusal is a stop-and-report, never something to force.
5. **Report outcomes faithfully.** If work failed, say so with the evidence.

### Preferences

`preferences.md` is where Bill's value lives — the user's standing opinions, which no repo can
supply. When the user corrects him or states a standing preference, he appends it with the date and
the reasoning. He reads it at every session start.

The bundle accesses preferences through **one documented path**, so a later upgrade to a better
memory store does not require rewriting Bill's instructions.

## The lifecycle

1. The user tells Bill what they want, in his terminal.
2. **Resolve the repo** — from the user's words, `preferences.md`, or the repos Lumbergh already
   has sessions for. Proceed on one confident match, naming it; ask one concise question if
   several or none plausibly match. Bill never clones; he uses repos where they already are.
3. **Classify.** Sharp enough to brief → **ship**. Not sure → **scout** first: a worker whose
   deliverable is `reports/<task>.md` and no code. Bill relays the findings to the user, then
   dispatches ships from the plan. A report recommends implementation; it does not authorize it.
4. **Brief and dispatch.** Write `briefs/<task>.md`, call `lb spawn`.
5. **Supervise.** Block on `lb fleet --wait`. On a blocked worker: answer from preferences, or
   escalate. On done: read the outcome line, then report the outcome — not the mechanics.
6. **Delivery, derived not configured.** GitHub remote present → the worker runs the repo's
   validation gate, pushes, opens a PR; Bill reports the full URL and CI state. No remote → a
   validated branch off `main`, ready to fast-forward. Bill checks for the remote; he does not
   guess, and there is no per-project delivery config.
7. **The user lands it.** Bill then reaps the worktree (guarded) and reports what remains in
   flight.

**Validation-gate coupling.** The repo's validation gate is referenced by *pointer*, not by a
hardcoded command sequence, because `no-mistakes` is being rebuilt. The brief instructs the worker
to use the repo's own gate; Bill neither runs nor judges it.

## Talking to the user

Bill reports **outcomes, not mechanics**. No task ids, worktree paths, states, wake types, briefs,
or registry rows in chat unless the user needs the path to act. "The flaky login test is fixed —
PR https://... , checks green" rather than a status line. Escalations lead with the concrete
evidence, then the consequence, then a recommendation.

Away-mode digests are out of scope; Lumbergh's existing while-away notifications already cover
"something needs you."

## Failure handling

| Failure | Answer |
|---|---|
| Bill invents an answer to a worker | Hard rule 3: preferences or the user's request only, else escalate. The brief also tells workers to re-ask when an answer looks unsupported. |
| Bill's model drops the protocol | Every step is one `lb` command failing closed with a fix-it message, and there is no state for him to forget to write. |
| Bill ends his turn with workers live | The idle-Bill nudge backstop wakes him. |
| Worker dies or wedges | `lb fleet` reports `dead` from live tmux state. The worktree and any uncommitted work are preserved, never reaped. Bill reports rather than retrying blindly. |
| Bill restarts mid-flight | He re-reads `lb fleet` and continues. Registry rows are the truth; his memory is not. |
| Bill tries to write project code | His workdir is not a repo; plus hard rule 1. |
| `lb spawn` half-fails | It unwinds its own partial work — no orphan tasks. |
| Bundle refresh clobbers the user's edits | Materialization rewrites only `AGENTS.md`; `preferences.md`, `briefs/`, `reports/` are create-if-missing. Pinned by a unit test. |

## Testing

**Unit**

- Bundle materialization: fresh install; refresh updates `AGENTS.md` and preserves
  `preferences.md` / `briefs/` / `reports/`; personality renders both ways and appears only in the
  user-facing preamble.
- `lb fleet`: reconciliation across multiple repos; `state` derivation for
  active / blocked / dead / orphan; `--wait` returns on each wake condition and on timeout.
- `lb spawn`: happy path records `kind` and `origin`; each fail-closed path returns an actionable
  error; the unwind leaves no worktree and no registry row.
- Outcome-line parsing: `DELIVERED:` / `FAILED:` / absent.
- Summon: creates when absent, returns the existing session when live.

**E2E** (QEMU VM, `./test/e2e-vm.sh`)

- `lb spawn` a scout against a scratch repo → it appears in `lb fleet` → `--wait` returns on its
  state change → `lb worktree reap` roundtrip.

**Not covered by tests**

Whether a Qwen-class model actually follows the bundle is not unit-testable. It needs a manual
smoke run: summon Bill, give him one real request, watch him dispatch a scout and report. The repo
already has an eval harness under `scripts/eval/` that could grow a scripted version later; v1
states the gap rather than pretending tests cover it.

## Build order

`lb fleet --wait` and `lb spawn` are the critical path — the bundle is inert without them, and Bill
cannot supervise affordably without long-polling. Backend first, bundle second, UI last.

1. Registry extension (`kind`, `origin`) + cross-repo reconcile.
2. `lb fleet` (+ `--wait` long-poll endpoint).
3. `lb spawn` (+ unwind).
4. Bundle source, materialization, personality rendering.
5. Summon endpoint + dashboard button + idle-Bill nudge backstop.
6. Manual smoke with pi/Qwen.

## Out of scope (YAGNI)

Named explicitly so they do not creep in:

- Durable backlog, queueing, dependency ordering, re-dispatch after teardown.
- Merge automation and any autonomy flag (`yolo`).
- Secondmates / nested managers.
- Away-mode digests and escalation daemons.
- Per-project delivery modes (delivery is derived from remote presence).
- Concurrency caps and cross-repo scheduling policy.
- Project cloning or a project registry beyond what Lumbergh's sessions already imply.
- Any Bill-specific UI beyond the summon button.
- A better memory store than `preferences.md` (planned, not now).

## Smoke results (2026-07-29)

The design predicted that whether a small local model follows the bundle is not unit-testable and
needs a manual run. That run has partly happened; this records what was observed, since it is the
input to the next iteration of the bundle.

**Verified end to end**

- Full backend suite (449 tests) and `./lint.sh` clean.
- The E2E suite passes inside the QEMU VM, including the `spawn → fleet → reap` roundtrip.
  Re-run and re-confirmed at the branch head (8/8) after the final review's fix wave — an earlier
  run was invalidated when the harness check landed, which is recorded below.
- **A fresh summon works.** In a clean VM, `POST /api/bill/summon` created a live session named
  `bill` with workdir `~/.config/lumbergh/bill` and provider `pi`; a second call correctly returned
  `existing: true`.
- **The identity refusal works, against a real conflict.** On the development host a live session
  named `bill` exists that is *not* Bill (a worktree session). Summon refuses it with
  `400 stage="identity"`, names the conflict, and leaves that session untouched — confirmed by
  checking every tmux session survived.
- **The refusal reaches the user readably.** The structured `{stage, error, help}` body renders
  through the dashboard's error formatter as plain actionable text, not `[object Object]`.

**Found by the smoke run, then fixed**

Summon started Bill's session even when the `pi` binary was absent. tmux keeps a session alive after
the launch command fails, so summon returned `200`, the dashboard showed Bill as live, and Bill was
not running — the pane held only `-bash: pi: command not found` and a shell. Nothing surfaced the
failure. Summon now verifies the harness is available and refuses with an actionable error instead.

That fix then invalidated the E2E suite in the VM, where `pi` is genuinely absent: summon began
refusing with `stage="harness"`, and the test helper that learns Bill's home read a `workdir` field
the harness refusal did not carry. The final whole-branch review caught it. The refusal now carries
`workdir`, the tests accept either legitimate refusal stage, and the VM suite was re-run at the
branch head. Worth recording as a pattern: a guard added late can break the very evidence that the
work is sound, so verification has to be re-earned rather than inherited.

**Also found by the final whole-branch review**

Two defects that no single task's review could have seen, both fixed:

- `/api/bill/fleet/wait` — Bill's *primary* supervision path — called the fleet snapshot
  synchronously in its poll loop, shelling out to tmux and `git worktree list` per repo every 250ms
  for up to 300s, on the event loop that serves every terminal WebSocket. The nudge backstop had
  already been fixed for exactly this hazard, and its docstring even said the snapshot never runs on
  the loop directly — while this endpoint did.
- The bundle told Bill to spawn with a brief path relative to his home, but the CLI forwarded it
  verbatim and the server resolved it against its own working directory. The resulting error told him
  to write a brief he had already written: a stall loop on the most important command in the system,
  invisible to every test because they all passed absolute paths.

Both belong to one class — the bundle was written against the *intended* CLI rather than the shipped
one. There is now a contract test asserting every `lb` command and flag named in `AGENTS.md` exists
in the CLI's flag table, so that particular drift fails the suite instead of failing Bill.

**Still not observed**

Whether a Qwen-class model under `pi` actually follows `AGENTS.md` — resolves a repo, chooses scout
vs ship sensibly, writes a brief, calls `lb spawn` without hallucinating flags, and re-arms
`lb fleet --wait`. That requires a real conversation with a real model.

One practical obstacle: Bill's session name is `bill`, and on this machine that name is held by the
development session this work was done from. Summon therefore refuses by design. Testing Bill for
real means renaming or ending that session first.

The reviewers also noted `AGENTS.md.template` is long (~100 lines) for a model chosen partly because
it is cheap. Trimming it should wait until a real session shows which sections get ignored, rather
than being guessed at now.
