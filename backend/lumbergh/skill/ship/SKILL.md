---
name: ship
description: >
  Execute a delegated implementation task in an isolated worktree and deliver it as
  reviewed work — run the project's own validation gate, then deliver in the mode the task
  message names (open a PR, push a branch, or commit and stop). Use when you were spawned
  into a worktree with a brief to make a code change and hand it back. Ends with the required
  DELIVERED:/FAILED: status line.
---

# ship — implement a delegated task and deliver it

You were spawned into an **isolated git worktree** to carry out the one task in your brief.
This is not the user's main checkout — never touch that, and never merge or land the work
yourself. The user decides what lands.

## Do the work
1. Implement exactly what the brief asks. Keep it scoped — don't gold-plate, don't widen the
   change beyond the brief.
2. If an instruction looks wrong, unsupported, or ambiguous, **stop and ask** rather than
   guessing. A confident wrong guess is the most expensive outcome.

## Validate — the project's own gate, not one you invent
Find and run this project's validation gate, and fix everything it flags before delivering.
Look, in order, for what the project already defines:
- a `CLAUDE.md` / `AGENTS.md` that names the lint / test / build commands,
- a `justfile`, `Makefile`, `package.json` scripts, a `lint.sh` / `test.sh`, or CI config.
Run the lint/format and the test suite it specifies. Don't invent commands the project
already documents, and don't skip the gate because the change "looks small."

## Deliver — in the mode your task message names
The message that handed you this task names your delivery MODE. Repos differ — some use
PRs, some never do — so do **exactly** the mode you were given and nothing more. Always
commit on a branch, never the default branch, and never merge or land yourself.
- **pr** — push your branch and open a PR (`gh pr create`); report the full `https://…` URL
  and whether checks are green. Deliver `DELIVERED: <pr-url>`.
- **branch** — push your branch; do **not** open a PR. Deliver `DELIVERED: <branch>`.
- **commit** — commit locally and **STOP**: never push, never open a PR, never merge/rebase.
  The overseer assembles and lands your work. Deliver `DELIVERED: <sha>`.

If — and only if — no mode was named, default to **commit** (commit and stop; never push
or open a PR on your own).

## Finish
End your final message with exactly one line, nothing after it — the shape your mode calls for:
`DELIVERED: <pr-url | branch | sha>`   or   `FAILED: <reason>`
That line is the contract the fleet reads to know how your task ended.
