# A backlog loop that works in any repo

**Date:** 2026-08-09
**Status:** approved, ready to implement

## The problem

Bill's babysit loop refreshes an idle overseer by sending `/clear` followed by a restart
command. The default restart command is `/fleet-start`, which exists only as a skill in the
`propane_port` repo. In every other repo the session clears its context and then sits there,
having been handed a command that does not resolve — a worse outcome than doing nothing.

The escape hatch (`[babysit] on_refresh` in `.lumbergh.toml`) exists but is documented only
inside a design spec, so a user hits the broken behaviour with no visible way to learn the fix.

Bill itself is fine. Every `/fleet-*` mention in `bill/AGENTS.md.template` is a *prohibition*
("you do not relay these yourself"); Bill never invokes them. The coupling is one line of
`babysit.py`.

## The diagnosis

`/fleet-start` conflates two things:

- **The ritual** — load state, pick the next thing, start it without asking, emit a sentinel
  when there is nothing left. This is entirely generic.
- **The backlog** — `HANDOFF.md`, `gh issue list`, file-disjoint lanes, worktree spawning.
  This is entirely port-specific.

Lumbergh ships the second half by accident and none of the first.

## The insight

Lumbergh already owns a repo-scoped backlog. Todos are keyed by project
(`get_project_db(workdir)`, "shared across sessions with the same repo"), they live in TinyDB
rather than in a context window so they survive `/clear` by construction, and users already
curate them in the dashboard. No new file, no new discipline, no `gh` dependency, works
offline.

The missing piece is that **no CLI can reach them**, so an agent cannot read the backlog or
tick anything off.

## Design

### 1. `lb todo` — the missing primitive

```
lb todo                    # list, with indices and done state
lb todo next               # first undone item; empty output and exit 1 if none
lb todo done <n>           # tick it off
lb todo add <text>         # append
```

`--repo` defaults to cwd, matching `lb init`. Output is toon, matching every other `lb`
command. `lb todo next` is load-bearing: it is the entire "what's next" query, and its empty
case is what drives `⟳ BACKLOG-EMPTY`.

The existing todo endpoints are session-scoped (`/{name}/todos`) and resolve the project
*through* a session. The CLI needs repo-scoped access, so this adds `/api/bill/todos` taking a
repo path directly — consistent with how `lb init` posts to `/api/bill/init`. Storage does not
change; both views hit the same project DB.

### 2. A shipped `next` skill

Added to the `SKILLS` table in `agent_cli/skill.py` beside `lb`/`ship`/`scout`, with its
committed copy at `lumbergh/skill/next/SKILL.md` so `lb skill --check` guards drift. It rides
the existing `ensure_worker_skills()` auto-install, so it is present before the agent boots.
That is what makes this work out of the box rather than being one more thing to set up.

The skill body:

1. `lb todo next` — nothing? Print `⟳ BACKLOG-EMPTY` on its own line and stop.
2. Otherwise work it, following the repo's own `CLAUDE.md` / `AGENTS.md` conventions.
3. Commit locally when done. Never push, never open a PR, never touch a remote.
4. `lb todo done <n>`. If the task ended mid-flight, append one line to the project scratchpad.
5. Print `⟳ REFRESH-READY` on its own line.

The todo list *is* the handoff. Ticking items off as they complete is the state that survives
`/clear`; the scratchpad line covers work interrupted partway.

### 3. The default changes

```python
"on_refresh": ["/clear", "/next"]   # was ["/clear", "/fleet-start"]
```

Port keeps its richer behaviour with one `.lumbergh.toml` stanza pinning
`on_refresh = ["/clear", "/fleet-start"]`. That is the right trade: today the default is broken
for every repo except one, and that one repo is the best equipped to configure itself.

Sentinels (`⟳ REFRESH-READY`, `⟳ BACKLOG-EMPTY`) are unchanged — already generic, already
configurable.

### 4. Supporting changes

- `bill/AGENTS.md.template` gains a short paragraph saying the generic path exists. Today every
  `/fleet-*` mention there is a prohibition, so nothing tells Bill that a repo with todos can
  simply be babysat.
- User-facing docs gain a `[babysit]` configuration section.

## Guardrails

The loop may **work and commit locally; it may not push**. Progress stays durable and
reviewable, and nothing leaves the machine unattended. This matches how the `ship` skill
already gates delivery.

This is skill *instruction*, not a mechanical gate — the same soft guarantee `ship` relies on.
Making it mechanical is a separate change with real teeth and real annoyance; it is not in
scope here, and the limitation should be stated plainly rather than implied away.

## Failure modes

| Situation | Behaviour |
|---|---|
| Empty todo list | `⟳ BACKLOG-EMPTY` on the first cycle; babysit stops cleanly. A repo that never adopted todos costs one cycle, not a spin. |
| Vague todo | The agent does something imperfect, commits locally, the user reviews. Nothing leaves the machine. |
| Server unreachable | `lb todo` fails; the skill stops rather than inventing work. |

## Out of scope

- **Spawning parallel workers.** The loop is sequential: one session, one task at a time. That
  is the loop being asked for, and it needs no worktrees, briefs, or dependency setup. Repos
  wanting the fleet model already have `on_refresh` to point at their own skill.
- **Porting port's fleet skills into Lumbergh.** They encode one repo's backlog workflow;
  shipping them would bless it as the product's.
- **A mechanical push gate.** See Guardrails.

## Testing

- `lb todo` CLI: list, next, done, add; repo scoping; exit code on an empty backlog.
- The repo-scoped `/api/bill/todos` endpoint.
- The changed `babysit.py` default.
- Skill drift via the existing `lb skill --check`.
