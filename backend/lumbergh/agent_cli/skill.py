"""The `lb` agent skill — canonical content + install helpers.

Single source of truth: SKILL_MD. The committed copy at ``lumbergh/skill/SKILL.md``
must match it (``lb skill --check`` guards against drift). `lb skill install`
writes it into every present agent skills directory. Skill-based agent onboarding
is the AXI §7 pattern (see ~/.config/lumbergh/shared/herdr-steal-list.md).
"""

from pathlib import Path

SKILL_MD = """\
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

`lb` lets you see and coordinate the other agent sessions Lumbergh is running. Run it with
no arguments for a live dashboard. The installed binary is the source of truth for exact
syntax — run `lb <command> --help` rather than guessing.

## Orient first

```
lb
```

Lists every live session with its state (`working` / `idle` / `blocked` / `error`) and
whether it finished while unseen. Start here.

## Commands

- `lb` — live dashboard of all sessions.
- `lb read --session <name> [--last N] [--source transcript|pane|detection] [--full]` — see
  what a session is doing. Default is its recent transcript (messages + tool calls);
  `pane` shows the raw terminal (e.g. a permission prompt); `detection` shows what the
  state classifier sees.
- `lb state --session <name>` — a session's current state, whether it's unseen, and how
  long it's been in that state.
- `lb wait --session <name> --until idle|working|blocked|error|rest [--timeout <s>]` —
  block until a session reaches a state. Use this to supervise: wait `--until blocked`,
  then step in.
- `lb prompt --session <name> "<text>" [--wait]` — send a line of input to a peer session.
  This drives another agent, so use it deliberately; `--wait` blocks until its state changes.

## Notes

- Defaults to the session you're in (`$LUMBERGH_SESSION`); pass `--session` to target another.
- Requires the Lumbergh server to be running; if it's off, `lb` says so.
- Output is compact TOON — a header line `name[count]{fields}:` then one row per line.
"""

_AGENT_SKILL_DIRS = [
    Path.home() / ".claude" / "skills",
    Path.home() / ".pi" / "agent" / "skills",
    Path.home() / ".config" / "opencode" / "skills",
    Path.home() / ".codex" / "skills",
]


def committed_path() -> Path:
    return Path(__file__).resolve().parent.parent / "skill" / "SKILL.md"


def detect_dirs() -> list[Path]:
    return [d for d in _AGENT_SKILL_DIRS if d.is_dir()]


def install(dirs: list[Path]) -> list[Path]:
    written: list[Path] = []
    for directory in dirs:
        target = directory / "lb" / "SKILL.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_text() != SKILL_MD:
            target.write_text(SKILL_MD)
        written.append(target)
    return written


def check() -> bool:
    try:
        return committed_path().read_text() == SKILL_MD
    except OSError:
        return False
