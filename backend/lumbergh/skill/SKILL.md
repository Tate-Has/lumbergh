---
name: lb
description: >
  Observe and coordinate the other AI coding sessions Lumbergh is supervising, using the
  `lb` CLI: list sessions and their state, read a peer's transcript, wait for a session to
  reach a state, or send it a prompt. Use when you need to check on, wait for, or hand work
  to a peer Lumbergh session. Do NOT use for spawning background terminals, general shell
  tasks, or when you are not running alongside other Lumbergh sessions.
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

Targets `$LUMBERGH_SESSION` by default; pass `--session` for another.
