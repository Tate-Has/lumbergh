# Manifest-Driven Detection Engine

**Date:** 2026-07-27
**Status:** Approved design
**Context:** herdr-steal bite #2 (completes item #1 of `~/.config/lumbergh/shared/herdr-steal-list.md`)

## Goal & Boundary

Replace the hardcoded regexes in `idle_detector.py` with a data-driven detection
engine that reads Lumbergh-native TOML manifests. Detection becomes a *data* concern
(editable TOML shipped with the release) instead of Python edited per Claude Code
footer change.

In scope:

- **Override-only engine.** `classify` returns `BLOCKED` / `ERROR` / `None`, a drop-in
  replacement for `classify_overrides`. The burst-fingerprint quiescence classifier in
  `idle_monitor` still owns `WORKING` / `IDLE` — that is Lumbergh's genuine edge over
  herdr and is left untouched.
- **Bundled manifests only.** Rule sets ship inside the pip package. No remote catalog.
- **Lumbergh-native lean TOML format.** Rule *content* is adapted from herdr's Claude
  and Pi manifests (factual observations of those agents' UIs); the schema is our own.
- **OSC/pane-title region**, captured cheaply (once per poll).
- **All detection data-driven**, including error and shell-prompt patterns
  (`common.toml`).

Explicitly out of scope (later bites):

- Remote catalog fetch from GitHub Pages, `min_engine_version` gating, on-disk cache.
- Positive `WORKING` / `IDLE` assertion from manifests (osc-title spinner, prompt box).
- The other 17 herdr agents beyond Claude and Pi.

## Manifest Format

One TOML file per agent under `backend/lumbergh/detect/manifests/*.toml`, plus a shared
`common.toml` for agent-agnostic rules (errors, shell prompts).

```toml
id = "claude"
aliases = ["claude-code"]

[[rules]]
id = "generic_permission_prompt"
state = "blocked"        # blocked | error | none
priority = 840           # higher wins; first match by descending priority
region = "recent"        # recent | recent_lines(N) | osc_title
not_footer = true        # fails if bottom-3 lines show live idle/working chrome
contains = ["do you want to", "esc to cancel"]   # ALL present, substring, case-insensitive
any = [                  # at least one predicate true
  { line_regex = "^\\s*❯?\\s*1\\.\\s*yes\\b" },
  { line_regex = "^\\s*2\\.\\s*no\\b" },
]
not = [ { contains = ["select model"] } ]        # none may be true
```

### States

- `blocked` — approval / question / login UI recognized; agent stopped, waiting on human.
- `error` — agent exited, crashed, rate-limited; or shell prompt on the last line.
- `none` — **veto**: force "no override, defer to quiescence." Replaces the
  `_NOT_BLOCKED_FOOTER` guard and the transient-menu exclusions as explicit,
  high-priority rules.

### Regions

- `recent` — last N non-empty lines (default 15), ANSI stripped, trailing blanks
  trimmed. Matches today's `_recent_lines`.
- `recent_lines(N)` — last N non-empty lines.
- `osc_title` — the pane's OSC-set title (empty string if unavailable).

Unknown region → the rule is skipped at load time with a log line; never a crash.

### Predicate algebra (lean subset)

- `contains` — list of substrings; **all** must be present (case-insensitive) in the
  region blob.
- `regex` — regex over the region blob.
- `line_regex` — regex applied per line; true if **any** line matches.
- `any` — list of nested predicates; true if **at least one** is true.
- `not` — list of nested predicates; true if **none** is true.
- `not_footer` (bool sugar) — convenience for the near-universal blocked-rule guard:
  fails the rule if the bottom-3 non-empty lines contain live idle/working footer chrome
  (`shift+tab to cycle`, `esc to interrupt`, `? for shortcuts`).

Unknown predicate key → the rule is skipped at load time with a log line.

### Evaluation

Rules across all applicable manifests are sorted by descending `priority`. The first
rule whose predicates all pass decides the result. A matched `state = "none"` rule
returns `None` immediately (veto short-circuit), so a high-priority veto beats a
lower-priority blocked/error rule. No match anywhere → `None`.

## Components

Each unit is independently testable with no I/O except the loader.

- **`detect/manifest.py`** — `Manifest`, `Rule`, `Predicate` dataclasses and
  `load_manifests(dir) -> list[Manifest]`. Pure parsing + validation. Malformed TOML,
  bad regex, unknown region/predicate → skip the offending rule/manifest, log, continue.
- **`detect/regions.py`** — `extract(region_spec, content, osc_title) -> list[str]`.
  Pure. Owns the `recent` / `recent_lines(N)` / `osc_title` logic and ANSI stripping.
- **`detect/engine.py`** — `classify(content, osc_title, manifests) -> SessionState | None`.
  Evaluates rules by priority; the public replacement for `classify_overrides`.
- **`detect/manifests/common.toml`** — error + shell-prompt rules (agent-agnostic).
- **`detect/manifests/claude.toml`** — Claude Code blocked rules, adapted from herdr.
- **`detect/manifests/pi.toml`** — Pi blocked rules.
- **`idle_detector.py`** — thin shim. Keeps the `SessionState` enum. `classify_overrides`
  gains an `osc_title: str = ""` parameter and delegates to `engine.classify` against
  lazily-loaded, module-cached bundled manifests. Existing import sites keep working
  (the new parameter defaults to empty).
- **`tmux_pty.capture_pane_title(session_name) -> str`** — one
  `display-message -p '#{pane_title}'`; returns `""` on any failure.
- **`idle_monitor`** — fetches the title once per `_check_session` (not per burst
  frame — titles change slowly), threads `osc_title` through `_classify_burst` into
  `classify_overrides`.

## Data Flow

```
_check_session
  ├─ _burst_capture          (BURST_CAPTURES × capture_pane_content — UNCHANGED)
  ├─ capture_pane_title      (1× per poll — NEW)
  └─ _classify_burst(captures, osc_title, now)
        └─ classify_overrides(captures[-1], osc_title)   # -> engine.classify(...)
              ├─ match blocked/error  → return that state
              ├─ match "none" veto    → return None (defer to quiescence)
              └─ no match             → return None → quiescence classifier
```

`capture_pane_content` and every input the quiescence classifier sees are **byte-identical
to today**. The only new subprocess is one `display-message` per session per poll,
marginal against the `BURST_CAPTURES` calls already made each poll. No regression risk to
terminal rendering or to `WORKING`/`IDLE` classification.

## Error Handling

- Load-time failures (bad TOML, bad regex, unknown region/predicate) are contained to the
  offending rule/manifest: log and skip. A broken manifest never takes down detection.
- `engine.classify` never raises into the monitor loop; on any internal error it returns
  `None` (defer to quiescence), matching today's fail-safe behavior.
- `capture_pane_title` failure → `""`; `osc_title` rules simply don't match, so behavior
  degrades to exactly today's (title-free) detection.
- Manifests are parsed once and cached at module level. A reload hook is deferred to the
  remote-catalog bite.

## Testing

Regression-first — the port is correct iff current behavior is preserved.

- **`backend/lumbergh/tests/test_idle_detector.py` (existing, 145 lines) must pass
  unchanged.** It is the behavioral-parity contract: every current blocked / error /
  shell-prompt / not-blocked-footer / transient-menu case must classify identically
  through the new engine.
- New unit tests:
  - `manifest.py`: valid parse; unknown-region rule skipped; bad-regex rule skipped;
    malformed manifest skipped without affecting siblings.
  - `regions.py`: `recent`, `recent_lines(N)`, `osc_title` extraction; ANSI stripping.
  - `engine.py`: priority ordering (higher wins); `none` veto short-circuits a
    lower-priority blocked rule; no-match → `None`.
  - One end-to-end case driven by `osc_title` to exercise the new signal path.
- `./lint.sh` clean before completion.

## Licensing

Rule *content* is factual observation of third-party agent UIs (e.g. Claude Code prints
`do you want to proceed?`) — thin copyright at best — and the manifest schema is
Lumbergh's own. We are not vendoring herdr's files verbatim, so no Apache-2.0 subtree is
required.

- `detect/manifests/README.md` — provenance note: rule content adapted from
  [ogulcancelik/herdr](https://github.com/ogulcancelik/herdr) at commit `dc2506e`
  (Apache-2.0), reworked into Lumbergh's own schema.
- One line in the top-level README acknowledging the same.

## Follow-up Bites (not this spec)

1. Remote catalog fetch (GitHub Pages, `min_engine_version`, cache, fallback to bundled).
2. Positive `WORKING`/`IDLE` from manifests (osc-title braille spinner, prompt box),
   which is where `osc_title` capture fully earns its keep.
3. Additional agent manifests (local models / ollama — manifests are the only option
   there since no hooks).
