# SessionStart Hook for Transcript Identity

**Date:** 2026-07-27
**Status:** Approved design
**Context:** herdr-steal bite #3 (roadmap item #2 of `~/.config/lumbergh/shared/herdr-steal-list.md`)

## Goal & Boundary

Replace the fragile transcript guess in `ClaudeCodeAdapter.for_cwd` — which encodes the
cwd to `~/.claude/projects/<encoded>/` and picks the newest-mtime `.jsonl`, and so picks
the wrong session when two Claude sessions share a directory — with **authoritative
identity** from a Claude Code `SessionStart` hook. The hook hands over `session_id` and
`transcript_path` per Lumbergh session, at zero guessing cost.

In scope:

- A shipped hook script that reports identity to a file-drop store.
- Idempotent auto-install of the hook into `~/.claude/settings.json` on backend startup,
  env-gated so it is a silent no-op in every non-Lumbergh session.
- `LUMBERGH_SESSION` env injection at session creation as the correlation key.
- Adapter resolution that prefers identity and falls back to the legacy cwd guess.

Out of scope (later bites):

- `done` vs `idle` (finished-while-unseen) and push notifications.
- Pi's richer hook surface / pushing live lifecycle state from hooks.
- Any use of the hook's `additionalContext`/other stdout controls.

## Confirmed Claude Code Hook Contract

Verified against the current Claude Code docs (and to be re-checked empirically against an
installed Claude before writing the settings writer, since the exact nested shape matters):

- **SessionStart stdin JSON** includes: `session_id`, `transcript_path`, `cwd`,
  `hook_event_name` (`"SessionStart"`), `source` (one of `startup` / `resume` / `clear` /
  `compact` / `fork`), plus optional `model`, `agent_type`, `session_title`.
- **Fires on** startup, resume/continue, `/clear`, compaction, and fork — not only fresh
  launch. Identity therefore self-heals: `/clear` starts a new transcript and the hook
  re-reports it.
- **Environment inheritance**: the hook command runs with the launching shell's
  environment, so an env var injected into the tmux pane before launch is visible.
- **Exit/stdout**: exit 0 with empty stdout is a clean no-op; no exit code blocks the
  session.
- **`settings.json` hook shape** uses a nested array-of-matcher-groups under `"hooks"`
  (NOT a flat `{type, command}` object). The precise shape is verified empirically in
  Task 1 before any writer code is committed.

## Correlation & Interpreter Decisions

- **Correlation key = injected `LUMBERGH_SESSION`.** Session creation injects
  `LUMBERGH_SESSION=<session_name>` into the pane before launching the agent. The hook
  reads it, uses it as the identity filename key, and treats its absence as the env gate
  (`unset → exit 0`). The activity socket already has `session_name`, so it reads the
  identity file directly with no pane→session resolution.
- **Interpreter = the backend's own `sys.executable`.** The hook is a Python script; the
  installer registers the command as `"<sys.executable> <script_path>"`. That interpreter
  provably exists wherever Lumbergh is installed and always has stdlib `json`, with no
  dependence on `python3` being on the pane shell's `PATH`. The installer rewrites the
  managed command whenever the baked interpreter path (or hook version) drifts from the
  current values, so a moved/reinstalled Lumbergh self-heals on next backend startup.

## Components

- **`backend/lumbergh/hooks/session_start.py`** (shipped in package) — the hook body.
  Reads stdin, gates on `LUMBERGH_SESSION`, and atomically writes the identity file.
  **Self-contained (stdlib `json`/`os`/`pathlib` only)** — it does NOT import the
  `lumbergh` package, so no submodule import error or `__init__` side effect can degrade
  it. The store path and filename-key sanitization it uses are pinned to
  `session_identity`'s by a round-trip test (the hook's output must parse via
  `session_identity.read`), not by shared imports. Fully best-effort: any error → exit 0,
  no output, no file. Never blocks the agent.
- **`backend/lumbergh/hook_installer.py`** — idempotent `settings.json` surgery.
  `ensure_installed()` reads the user settings, inserts/updates a single **managed**
  SessionStart entry (tagged with a version + interpreter marker), preserves all other
  hooks, and writes back atomically. Never overwrites a settings file it cannot parse.
  Exposes `uninstall()` that removes only the managed entry.
- **`backend/lumbergh/session_identity.py`** — the file-drop store under
  `~/.config/lumbergh/session_identity/`. Owns the canonical `store_dir()` and
  `key(session_name)` (filename-safe sanitization, reused conceptually by the hook and
  verified by the round-trip test). `read(session_name) -> Identity | None`,
  `prune(live_names)`, and `write(...)` (used by the backend for prune/tests). `Identity`
  carries `session_id`, `transcript_path`, `cwd`, `source`, `written_at`.
- **`backend/lumbergh/routers/sessions.py`** — inject `LUMBERGH_SESSION=<name>` into the
  pane (via `send-keys "export LUMBERGH_SESSION=<name>"` before the launch send-keys, for
  portability across tmux/psmux versions) at session creation.
- **`backend/lumbergh/activity/claude_code.py`** — a constructor path taking an explicit
  `transcript_path` (already present as `__init__`); no guessing when identity is known.
- **`backend/lumbergh/main.py`** — the activity socket resolves the adapter identity-first
  with cwd fallback (see Data Flow).
- **Backend startup** (`main.py` lifespan/startup) — calls
  `hook_installer.ensure_installed()` once, best-effort.

## Data Flow

```
backend startup
  hook_installer.ensure_installed()
    → managed SessionStart hook in ~/.claude/settings.json
      command = "<sys.executable> .../hooks/session_start.py"

create session
  tmux new-session -d -s <name> -c <workdir>
  send-keys "export LUMBERGH_SESSION=<name>"   Enter
  send-keys <launch agent command>             Enter
    claude starts → SessionStart hook fires (env gate passes)
      → atomically writes session_identity/<key(name)>.json
        { session_id, transcript_path, cwd, source, written_at }

open activity socket(session_name)
  ident = session_identity.read(session_name)
  if ident and Path(ident.transcript_path).exists():
      adapter = ClaudeCodeAdapter(ident.transcript_path, root=ident.cwd)   # authoritative
  else:
      adapter = ClaudeCodeAdapter.for_cwd(cwd)                              # legacy guess
```

Re-fires (resume/clear/compact/fork) overwrite the identity file (last-writer-wins),
keeping `transcript_path` current.

## Safe-Install Specifics

The installer must never damage the user's config:

- Read → parse → merge → write atomically (temp file + `os.replace`).
- If `settings.json` exists but is not valid JSON, **do not** write — log and skip.
- The managed entry is identifiable (a stable marker embedded in the entry, e.g. a
  `# lumbergh-managed vN` sentinel in the command string or a sibling key), so a re-run
  updates it in place rather than appending a duplicate.
- Rewrite the managed entry when the hook version or the baked interpreter path differs
  from current; otherwise leave the file byte-unchanged (idempotent).
- `uninstall()` removes only the managed entry, leaving sibling SessionStart hooks intact.
- No `settings.json` present → create a minimal one containing only the managed hook.

## Error Handling

- **Hook script**: missing/empty `LUMBERGH_SESSION`, unparseable stdin, unwritable store
  dir → exit 0, no output, no file. The agent is never degraded.
- **Installer**: missing/malformed/unwritable `settings.json` → log and skip; backend
  startup continues. Identity detection simply stays on the cwd fallback.
- **Identity read**: file missing or malformed, or `transcript_path` no longer on disk →
  return None / fall back to `for_cwd`.

## Testing

- **`session_identity.py`**: write→read round-trip; missing file → None; malformed file →
  None; `prune(live)` deletes files for dead sessions only.
- **`hook_installer.py`** (against a `tmp_path` fake home): fresh install produces a valid
  managed entry; idempotent re-run leaves the file byte-identical and adds no duplicate;
  an unrelated pre-existing user SessionStart hook is preserved; a stale managed
  version/interpreter marker is rewritten; a malformed settings.json is left untouched and
  the call reports failure without raising.
- **Adapter resolution** (unit around the resolver): identity present + transcript file
  exists → uses identity path; identity present but transcript missing → falls back to
  `for_cwd`; no identity → `for_cwd`.
- **Hook script** (invoked as a subprocess with piped stdin): with `LUMBERGH_SESSION` set,
  a sample SessionStart payload writes the expected JSON to the store; with the env unset,
  no file is written and exit code is 0.
- `./lint.sh` clean.

## Licensing

The pattern (env-gated silent no-op, versioned managed block, identity-from-hooks) is
adapted in spirit from herdr; no code is copied. A one-line comment in
`hook_installer.py` referencing the steal-list suffices — no new attribution file.

## Follow-up Bites (not this spec)

1. `done` vs `idle` seen/unseen state + mobile push ("finished while you were away").
2. Pi adapter using its richer plugin hook surface.
3. Pushing live lifecycle state (working/blocked/idle) from hooks where the API is
   expressive enough, per the herdr "identity from hooks, state from screen" rule.
