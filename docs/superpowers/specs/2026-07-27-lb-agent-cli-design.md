# `lb` — Agent-Facing Control CLI (AXI)

**Date:** 2026-07-27
**Status:** Approved design
**Context:** herdr-steal bite #6 (roadmap item #4 — the control API's `wait` primitives), authored to the AXI (Agent eXperience Interface) standard so it also seeds item #5 (a `SKILL.md` that lets an agent drive Lumbergh).

## Goal & Boundary

Ship `lb`, a small agent-ergonomic CLI installed with `pylumbergh`, that lets a coding
agent (or a person) **observe and coordinate Lumbergh sessions from the shell** — read a
session's pane, get its state, **block until a session reaches a state**, and send it a
prompt. The killer primitive is `lb wait --until blocked`: an agent can supervise a peer
session ("wait until `pi-refactor` is blocked, then intervene") instead of polling.

The north star is **driving Pi (and Claude) sessions**: an agent uses `lb` to watch and
nudge other agent sessions Lumbergh manages.

In scope (v1, lean core):

- Commands: `lb` (home/list), `lb read`, `lb state`, `lb wait`, `lb prompt`.
- **`lb read` reads the structured transcript, not the screen** — reusing Lumbergh's
  existing activity adapters (`AgentAdapter`/`ConversationEvent`). Claude via the existing
  `ClaudeCodeAdapter`; **Pi via a new `PiAdapter`** (same interface, reads
  `~/.pi/agent/sessions/`). Raw pane text drops to `--source pane`/`detection` for the
  literal screen and as the fallback when no transcript resolves. This makes `lb read`
  clean, structured, token-efficient, and **first-class for Pi (incl. local ollama models)**.
- Authored to all 10 AXI principles: TOON output, minimal schemas, truncation, aggregates,
  definitive empty states, structured errors + exit codes, content-first no-args,
  contextual disclosure, per-command `--help`.
- Targets "the session I'm in" by default via `$LUMBERGH_SESSION` (from bite #3).

Out of scope (v2+):

- `wait-output --match/--regex`, prompt-effect-stall timeout, `recent-unwrapped` source,
  named-agent addressing, alt-screen fallback.
- Item #5 itself (the SessionStart ambient-context hook + generated `SKILL.md`) — this spec
  describes the hand-off but implements only the CLI it depends on.

## Architecture

`lb` is a **thin HTTP client** to a new localhost-only `/api/agent/*` surface on the
existing FastAPI backend. The CLI's only job is argument parsing, calling the backend, and
formatting **TOON**; all tmux/state logic stays in the backend (single source of truth).

Rationale for HTTP-to-backend over the CLI reading tmux/DB directly:

- The backend already holds **live state in memory** (`idle_monitor._states`,
  `session_attention`), so `state`/`wait` are served instantly with **no `session_data`
  TinyDB read racing the monitor's writes**.
- `wait` is a backend async loop watching in-memory state — lost-wakeup-safe (it checks the
  current state first) and correct, which is the property herdr stresses most.
- The CLI reuses `tmux_pty` (via the backend) for `read`/`prompt`; no logic duplication.

### Auth: a local token file (not a loopback-IP check)

`/api/agent/*` is exempted from the password `AuthMiddleware` **only when the request
carries a valid agent token**. On startup the server writes a random token to
`~/.config/lumbergh/agent-token` (mode `0600`); `lb` reads it and sends
`X-Lumbergh-Agent-Token`. A loopback-IP check is **insufficient** — the cloud tunnel can
proxy to the backend over localhost, so a tunneled remote request could appear as
`127.0.0.1`. The token file is readable only by the local user, so only local processes can
authenticate, and tunneled/remote callers (lacking the token) get `403`.

### "Only works when the server is on"

Because `lb` reaches the backend over HTTP, a stopped server = connection refused. `lb`
catches that and prints the AXI "server not running" error (exit 1). No separate health
ping is needed; the connection *is* the gate.

## Command Surface (v1)

Global flags (always allowed on every command, per AXI §6): `--session <name>` (defaults to
`$LUMBERGH_SESSION`; required for session-scoped commands when the env var is unset),
`--help`. Unknown flags are rejected by name with the command's valid flags inlined
(exit 2).

Output is TOON on stdout; diagnostics/progress go to stderr; exit codes are 0 (success incl.
no-ops), 1 (operational error), 2 (usage error).

### `lb` (home view — AXI §8, §10)

No arguments → identify the tool, then show live sessions and next-step hints. No usage text.

```
bin: ~/.local/bin/lb
description: Observe and coordinate Lumbergh agent sessions from the shell
count: 3 of 3 total
sessions[3]{name,state,unseen}:
  api,working,false
  pi-refactor,blocked,true
  docs,idle,false
help[2]:
  Run `lb read --session <name>` to see a session's pane
  Run `lb wait --session <name> --until idle` to block until it finishes
```

- `state` is the monitor's live classification (`working|idle|blocked|error|stalled|unknown`).
- `unseen` is the bite-#4 attention flag.
- Empty case (AXI §5): `sessions: 0 live sessions` (exit 0).
- Backend: `GET /api/agent/sessions` → `{sessions:[{name,state,unseen}], total}`.

### `lb read [--source transcript|pane|detection] [--last N] [--full]` (AXI §3)

Default `--source transcript`: the recent **structured conversation** (agent-agnostic
`ConversationEvent`s) from the session's transcript — resolved via `ClaudeCodeAdapter`
(Claude) or `PiAdapter` (Pi), selected by the session's `agent_provider`. This is the rich,
token-efficient view of *what the agent has been doing* — messages, thinking, tool calls —
far better than scraping the terminal. Default `--last 10` events; text fields truncated
(~500 chars) with `--full` to expand.

```
session: pi-refactor
source: transcript
count: 10 of 214 events
events[10]{type,tool,text}:
  agent_message,,"I'll add the counter module and its test."
  tool_call,bash,"uv add pytest"
  tool_result,bash,"ok"
  tool_call,write,wordfreq/counter.py
  agent_message,,"Now wiring the CLI entry point…"
help[1]: Run `lb read --session pi-refactor --full --last 40` for more
```

`--source pane` = the literal visible terminal (clean text) — the right lens for a
permission prompt UI or spinner. `--source detection` = the exact recent-lines region the
state classifier keys on (a near-free debugging affordance — you never guess at a
misclassification). Both truncate at ~1500 chars with `--full`.

- If no transcript resolves (unknown agent / no transcript yet), `transcript` falls back to
  `pane` and says so in a `note:` line (AXI §5 — definitive, not silent).
- Backend: `GET /api/agent/sessions/{name}/read?source=&last=&full=` — for `transcript`,
  resolves the adapter and returns recent `ConversationEvent`s (JSON); for `pane`/`detection`,
  captures clean pane text via `tmux_pty`.

### `lb state` (AXI §4)

The live classification for one session, with the attention overlay. Self-contained → no
hints.

```
session: pi-refactor
state: blocked
unseen: true
since: 41s
```

- `since` = seconds in the current state (from the monitor), cheaply derived.
- Backend: `GET /api/agent/sessions/{name}/state`.

### `lb wait --until <state> [--timeout <secs>]` (the core primitive)

Block until the session reaches `--until` (one of `idle|working|blocked|error|stalled`, or
`rest` = any of idle/blocked/error). Returns immediately if already there (lost-wakeup
safety). Default `--timeout 300`.

```
$ lb wait --session pi-refactor --until blocked
session: pi-refactor
state: blocked
waited: 12s
```

On timeout (AXI §6, actionable error, exit 1):

```
error: timed out after 300s waiting for pi-refactor to reach `blocked` (still `working`)
help: raise the limit with `--timeout <secs>` or check `lb read --session pi-refactor`
```

- Backend: `GET /api/agent/sessions/{name}/wait?until=&timeout=` — an async loop over the
  in-memory monitor state (poll interval ~250 ms), returning on match or timeout. No DB
  reads; no busy-wait on the CLI side.

### `lb prompt "<text>" [--wait]`

Send a line of input to the session (types `<text>` then Enter into the pane). Without
`--wait`, confirm and return. With `--wait`, additionally block until the session's state
changes from what it was at send time (a lean take on herdr's prompt-effect check), so the
agent knows the prompt landed.

```
$ lb prompt --session pi-refactor "continue with the plan" --wait
session: pi-refactor
sent: "continue with the plan"
state: working
```

- Missing text (AXI §6): `error: prompt text is required` / `help: lb prompt "<text>"
  [--wait] [--session <name>]` (exit 2).
- Backend: `POST /api/agent/sessions/{name}/prompt` → `tmux send-keys`, then (if `wait`)
  the same state-change loop as `wait`.

## Backend surface

- **`backend/lumbergh/activity/pi.py`** — new `PiAdapter(AgentAdapter)`: reads
  `~/.pi/agent/sessions/<enc-cwd>/<newest>.jsonl` (encoding: `"-" + cwd.replace("/","-") +
  "--"`; the transcript's first `session` line carries `cwd` for verification). Parses Pi's
  `message` events → `ConversationEvent`s: user/assistant `text` → user_message/agent_message,
  `thinking` → thinking, `toolCall{name,arguments,id}` → tool_call (lowercase-tool
  summarizer), `toolResult` messages → tool_result. Mirrors `ClaudeCodeAdapter`'s structure
  and its `read_new()`/`_source_signature()` contract.
- **`backend/lumbergh/activity/resolve.py`** — `resolve_adapter(session_name, cwd,
  provider) -> AgentAdapter | None`: picks `ClaudeCodeAdapter` / `PiAdapter` by
  `agent_provider` (falling back to trying each). One place both the activity websocket and
  the agent router use, so adapter selection never drifts.
- **`backend/lumbergh/routers/agent.py`** — the `/api/agent/*` router: `sessions`,
  `sessions/{name}/read`, `sessions/{name}/state`, `sessions/{name}/wait`,
  `sessions/{name}/prompt`. `read` uses `resolve_adapter` for the transcript source and
  `tmux_pty` for pane/detection; `state`/`wait` read live state from `idle_monitor` +
  `session_attention`; `prompt` sends via `tmux_pty`. Returns plain JSON (the CLI renders TOON).
- **`backend/lumbergh/agent_token.py`** — `ensure_token()` (create `~/.config/lumbergh/
  agent-token` `0600` if absent, return it) called on startup; `verify(token)`.
- **`backend/lumbergh/auth.py`** — exempt `/api/agent/*` when `X-Lumbergh-Agent-Token`
  matches; otherwise it falls through to normal auth (so a tunneled caller without the
  token gets `401/403`, never the agent API).
- **`backend/lumbergh/agent_cli.py`** + `[project.scripts] lb = "lumbergh.agent_cli:main"`
  — the `lb` entry point: arg parsing (per-command known-flag validation, AXI §6), the HTTP
  calls, TOON rendering, and the connection-refused → "server not running" mapping.

## TOON rendering

A tiny internal renderer (`to_toon`) at the CLI's output boundary — collections as
`name[count]{fields}:` + comma-delimited rows (values quoted only when they contain spaces,
commas, or colons); single objects as `key: value`; multi-line text via a `pane: |` block.
Internal logic stays on JSON from the backend; TOON is applied only when printing.

## Error & exit-code contract (AXI §6)

- Unknown flag / missing required arg / bad `--until` value → structured error + the
  command's valid options inlined, exit **2**.
- Server down (connection refused) → "server not running, start with `lumbergh`", exit **1**.
- Unknown session → `error: no session named "<x>"` + a `sessions[..]{name}:` list +
  `help: run \`lb\``, exit **1**.
- `wait` timeout → actionable error, exit **1**.
- Success and no-ops → exit **0**. All errors print to **stdout** in TOON; only diagnostics
  go to stderr.

## How #4 drives #5 (hand-off, not built here)

AXI §7 prescribes exactly the item-#5 shape, and bite #3 already built the installer:

- **Ambient context**: extend the managed `SessionStart` hook to emit `additionalContext`
  containing `lb`'s compact home view (the `sessions[..]{name,state,unseen}` TOON), so every
  agent session starts already seeing the supervision dashboard — ruthlessly minimized per
  AXI §7. The hook is env-gated and idempotent (bite #3's guarantees carry over).
- **Installable skill**: generate `SKILL.md` from the *same* text as `lb`'s no-args home
  guidance (single source of truth; a `--check` CI step fails if it drifts), with
  trigger-shaped frontmatter and non-interactive (`npx`/absolute-path) command examples.

Both are their own follow-up bite; this spec only commits to the `lb` CLI + `/api/agent`
surface they consume.

## Testing

- **TOON renderer** (`to_toon`): collections, single objects, quoting (spaces/commas/
  colons), empty collection, the `pane: |` block — pure unit tests.
- **Arg parsing / flag validation**: unknown flag → exit 2 with inlined valid flags; missing
  prompt text → exit 2; bad `--until` value → exit 2; `--session` defaulting from
  `$LUMBERGH_SESSION`.
- **CLI ↔ backend** (mocked HTTP): home list renders sessions + total + hints; empty list is
  definitive; unknown session error shape; connection-refused → "server not running" exit 1.
- **`agent_token`**: create-if-absent with `0600`, stable across calls, `verify` accepts the
  written token and rejects others.
- **`PiAdapter`**: resolves the newest `.jsonl` for an encoded cwd; parses a real captured
  Pi transcript fixture into the expected `ConversationEvent` sequence (user_message /
  thinking / agent_message / tool_call with lowercase tool + summary / tool_result); returns
  `[]` when the sessions dir is absent. `resolve_adapter` picks Pi vs Claude by provider.
- **`/api/agent` router**: `read` returns transcript events for a Claude and a Pi session
  (adapter monkeypatched), and falls back to pane with a `note` when no transcript resolves;
  `state` reflects `idle_monitor` + `session_attention`; `wait` returns immediately when
  already in the target state and times out otherwise (injected fast clock / short timeout);
  `prompt` calls `tmux send-keys`; missing/invalid token → 401.
- **AXI conformance smoke**: `lb` with no args exits 0 and prints data (not help); every
  subcommand supports `--help`.
- `./lint.sh` clean.

## Licensing

The control-API surface is adapted in spirit from herdr; no code copied. AXI is an external
design standard (its skill is installed under `.claude/skills/axi`), followed, not vendored.
A one-line provenance note in `agent_cli.py` referencing the steal-list suffices.

## Follow-up Bites (not this spec)

1. **#5**: SessionStart ambient-context hook (extend bite #3) + generated `SKILL.md`.
2. **v2 control API**: `wait-output --match/--regex`, prompt-effect-stall timeout,
   `recent-unwrapped` source, named-agent addressing, alt-screen fallback.
3. **Positive `WORKING`/`IDLE` manifest detection + OSC-title** — the prerequisite for
   correct Pi/local-model *state* (Pi's static "Working…" defeats quiescence). `lb read` now
   gives Pi correct *content* via `PiAdapter`; this remaining piece gives Pi correct *state*,
   and `read --source detection` makes tuning those rules observable. Strong pairing with the
   live Pi session available here.
