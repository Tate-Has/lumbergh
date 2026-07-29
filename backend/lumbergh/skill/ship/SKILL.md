---
name: ship
description: >
  Execute a delegated implementation task in an isolated worktree and deliver it as
  reviewed work — run the project's own validation gate, then push and open a PR (or leave a
  validated branch). Use when you were spawned into a worktree with a brief to make a code
  change and hand it back. Ends with the required DELIVERED:/FAILED: status line.
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

## Deliver
Check whether the project has a GitHub remote (`git remote -v`) — don't assume.
- **Remote present:** commit on a branch (never the default branch), push, and open a PR with
  `gh pr create`. Report the full `https://…` URL and whether checks are green.
- **No remote:** leave a validated branch off the default branch, ready to fast-forward.

## Finish
End your final message with exactly one line, nothing after it:
`DELIVERED: <pr-url-or-branch>`   or   `FAILED: <reason>`
That line is the contract the fleet reads to know how your task ended.
