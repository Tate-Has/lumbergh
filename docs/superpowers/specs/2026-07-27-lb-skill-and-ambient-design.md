# `lb` SKILL.md + Ambient Session Context

**Date:** 2026-07-27
**Status:** Approved design
**Context:** herdr-steal bite #7 (roadmap item #5 — ship a `SKILL.md`). Completes the `#4 → #5` loop: the `lb` control CLI is what the skill teaches an agent to drive.

## Goal & Boundary

Let an agent *drive* Lumbergh:

- **(A) Ambient context** — every Lumbergh-launched session starts already seeing a
  compact, **read-only** `lb` dashboard of its peer sessions, injected via the existing
  SessionStart hook (bite #3).
- **(B) Installable skill** — one agent-agnostic `SKILL.md` that teaches any agent to use
  `lb`, installable into every present agent skills directory.

**Capability posture (decided):** ambient context is **read-only situational awareness**
for all sessions. The full `lb` surface — including `lb prompt` (injecting input into a
peer) — is documented only in the **on-demand SKILL.md**, so *commanding* a peer is a
deliberate, task-driven act, never a default reflex. No ACLs / per-session write-tokens are
built now; a "supervisor" write-gate is a small isolated follow-up if uncontrolled
cross-session prompting ever proves a problem.

Out of scope: ambient *hooks* for agents other than Claude Code (the ambient hook stays
Claude-only; the *skill* is agent-agnostic and installs everywhere); any write-gate/ACL.

## Part A — Ambient Context (extend bite #3's hook)

`backend/lumbergh/hooks/lumbergh_session_start.py` currently writes the identity file and
exits 0 silently. Extend it:

- After the identity write, when `source ∈ {startup, resume}` (fresh orientation only — not
  `compact`/`clear`/`fork`, where re-injecting the dashboard is mid-conversation noise),
  shell out to `lb` via `[sys.executable, "-m", "lumbergh.agent_cli.main"]` with a **~2 s
  timeout**, capture stdout, and print
  `{"additionalContext": "<framing line>\n<lb home view>"}` to the hook's stdout, then
  exit 0.
- **Read-only framing.** The framing line orients observationally, e.g.
  *"Lumbergh sessions running alongside you (read-only view via `lb`):"* — it does NOT
  suggest prompting peers. (Driving is the skill's job.)
- **Best-effort, never blocks.** Any failure, non-zero exit, empty output, or the 2 s
  timeout → emit no context, exit 0. Identity is always written first and is unaffected. The
  hook stays self-contained stdlib (the subprocess is not an import).
- Still env-gated on `LUMBERGH_SESSION`; `source` comes from the SessionStart stdin JSON the
  hook already parses.

No `hook_installer` change is needed — the managed command (`<interpreter> <script>`) is
unchanged; only the script's behavior grows. Bite #3's installer/identity tests stay green.

## Part B — The Skill

- **Canonical content** lives as a `SKILL_MD` string in `backend/lumbergh/agent_cli/skill.py`
  (single source of truth). Frontmatter:
  - `name: lb`
  - `description:` trigger-shaped **with anti-trigger guidance** — e.g. *"Observe and
    coordinate other Lumbergh agent sessions from the shell with the `lb` CLI (list/read
    their state, wait for a state, send a prompt). Use when you need to check on or
    coordinate a peer session Lumbergh is running. Do NOT use for spawning background
    terminals, general shell tasks, or when not working alongside other Lumbergh sessions."*
  - Body: tells the agent to run `lb` (no args → live dashboard) and `lb <cmd> --help` — **the
    installed binary is the syntax authority** (no drifting command syntax baked into prose);
    lists the commands at a high level (incl. `lb prompt` for deliberate coordination); notes
    `lb` needs the Lumbergh server running and targets `$LUMBERGH_SESSION` by default.
- **Commands (new under `lb skill`):**
  - `lb skill` — print the canonical `SKILL.md` to stdout.
  - `lb skill install [--dir <path>]` — write `lb/SKILL.md` into agent skills dirs.
    Default: auto-detect which of `~/.claude/skills`, `~/.pi/agent/skills`,
    `~/.config/opencode/skills`, `~/.codex/skills` exist and install into each (idempotent —
    rewrite only if changed). `--dir` targets a single directory. Reports each target in TOON.
    Definitive empty state if no known dir exists (AXI §5).
  - `lb skill --check` — exit non-zero if the committed copy has drifted from `SKILL_MD`
    (CI guard against skill/CLI drift, AXI §7).
- **Committed copy** at `backend/lumbergh/skill/SKILL.md`, generated from `SKILL_MD` and kept
  in sync by `--check`. Ships in the wheel (hatchling includes it, as with the manifests/hook).

## Testing

- **Hook ambient context:** `source=startup` + stubbed `lb` subprocess → stdout is valid
  JSON carrying `additionalContext` that includes the dashboard text; `source=compact` → no
  stdout (identity only); `lb` failure/timeout → identity still written, no stdout, exit 0;
  `LUMBERGH_SESSION` unset → total no-op (unchanged from bite #3).
- **`skill.py` / `lb skill`:** `lb skill` prints the canonical content; committed
  `backend/lumbergh/skill/SKILL.md` matches `SKILL_MD` (the `--check` invariant, asserted in a
  test so CI catches drift); `install --dir tmp` writes `lb/SKILL.md` and is idempotent;
  `install` with detected dirs monkeypatched writes to each and reports them; no-known-dir →
  definitive empty message, exit 0.
- **Regression:** bite #3 hook/identity/installer tests unchanged and green; full backend
  suite; `./lint.sh` clean.

## Licensing

Ambient-hook + installable-skill is the AXI §7 pattern (followed, not vendored; axi skill at
`.claude/skills/axi`); herdr's `SKILL.md` idea adapted in spirit. A one-line provenance note
in `skill.py` referencing the steal-list suffices.

## Follow-up Bites (not this spec)

1. Multi-agent ambient hooks (Codex `~/.codex/hooks.json`, OpenCode plugin) — the skill
   already installs everywhere; only the live ambient injection is Claude-only for now.
2. Supervisor write-gate for `lb prompt` (per-session role or write-token) — only if
   uncontrolled cross-session prompting becomes a real problem.
3. Positive `WORKING`/`IDLE` manifest detection + osc-title (correct Pi *state*).
