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
