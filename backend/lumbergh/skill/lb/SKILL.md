---
name: lb
description: >
  Observe and coordinate the other AI coding sessions Lumbergh is supervising, using the
  `lb` CLI: list sessions and their state, read a peer's transcript, wait for a session to
  reach a state, send it a prompt, spawn a new worker in its own worktree, or supervise the
  whole fleet at once. Use when you need to check on, wait for, hand work to, or create a
  peer Lumbergh session. Do NOT use for spawning background terminals, general shell tasks,
  or when you are not running alongside other Lumbergh sessions.
---

# lb — drive Lumbergh sessions

Run `lb` (no args) for a live dashboard of every session and its state
(`working`/`idle`/`blocked`/`error`, and whether it finished unseen). The binary is the
authority on syntax — run `lb <command> --help` when unsure.

## Commands

- `lb read --session <name> [--last N] [--source transcript|pane|detection] [--full]` —
  what a session is doing. Default `transcript` (messages + tool calls); `pane` = raw
  terminal (e.g. a permission prompt); `detection` = what the state classifier sees.
- `lb state --session <name>` — current state, unseen flag, time in state.
- `lb wait --session <name> --until idle|working|blocked|error|rest [--timeout <s>]` —
  block until a session reaches a state (e.g. `--until blocked`, then step in).
- `lb wait-output --session <name> --match "<text>" [--regex <re>] [--timeout <s>]` —
  block until the terminal shows text / matches a regex; the current screen is checked
  first, so output that already appeared still matches.
- `lb prompt --session <name> "<text>" [--wait]` — send input to a peer; this drives
  another agent, so use it deliberately. `--wait` blocks until its state changes.
- `lb fleet [--wait] [--timeout <s>] [--origin bill] [--json]` — every task under way: task,
  repo, branch, kind, state, time in state, whether it finished unseen, its OUTCOME column
  (the worker's own final `DELIVERED:`/`FAILED:` line, once it's written one), and the repo
  and worktree paths. Take a path from a row rather than typing one — `repo_path` is what
  `lb spawn --repo` wants, `path` is what `lb worktree reap` wants.
  `--wait` blocks until a task needs you (`blocked`, `error`, `dead`, or finished unseen) or
  the timeout elapses — a timeout is a normal return (exit 0), not a failure, so re-run it
  to keep waiting.
- `lb spawn --repo <path> --branch <b> --kind ship|scout --brief <file> [--new] [--base <b>]
  [--name <n>] [--agent <provider>] [--intent "..."]` — create an isolated worktree, start a
  worker in it, and deliver the brief. Any stage failing (bad kind/brief/repo/name, the
  worktree, the session, recording it, or delivering the brief after retries) unwinds
  everything already created, so a failed spawn never leaves a half-built task behind.

## Worktrees

`lb worktree` manages the isolated repo copies workers run in. `lb spawn` already creates
one per task, so reach for these when adopting or cleaning up.

- `lb worktree ls --repo <path> [--json]` — every worktree of a repo, with the session (if
  any) attached to each.
- `lb worktree create --repo <path> --branch <b> [--new] [--base <b>] [--session <name>]
  [--intent "..."]` — a fresh worktree with the project's configured links applied. `--new`
  creates the branch; `--base` says off what.
- `lb worktree reap <path> [--force] [--rm-branch]` — remove a worktree once its work has
  landed. It **refuses** while the worktree has uncommitted changes or unpushed commits;
  that refusal means work would be lost, so report it rather than reaching for `--force`.
- `lb worktree adopt <path> [--session <name>]` — start tracking a worktree that git already
  knows about but Lumbergh doesn't.
- `lb worktree link <path>` / `lb worktree unlink <path>` — re-apply or remove the project's
  configured shared files (env files, caches) in an existing worktree.

Targets `$LUMBERGH_SESSION` by default; pass `--session` for another.
