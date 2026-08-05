"""Lumbergh's agent skills — canonical content + install helpers.

Single source of truth: the strings in ``SKILLS``. Each has a committed copy at
``lumbergh/skill/<name>/SKILL.md`` that must match it (``lb skill --check`` guards
against drift). `lb skill install` writes them into every present agent skills
directory. Because both Claude Code (``~/.claude/skills``) and pi
(``~/.pi/agent/skills``) implement the same agentskills.io SKILL.md standard, one
authored skill serves a worker whichever agent it runs. Skill-based agent onboarding
is the AXI §7 pattern (see ~/.config/lumbergh/shared/herdr-steal-list.md).

Skills split by role. ``lb`` is for a *coordinator* (Bill) who drives other sessions.
``ship`` and ``scout`` are for a *worker* spawned into a worktree to execute one brief:
they carry the delivery/investigation contract that used to be restated in every brief,
so the brief can shrink to just the task and both pi and claude workers behave the same.
"""

from pathlib import Path

_LB_SKILL_MD = """\
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
- `lb fleet [--wait] [--timeout <s>] [--origin bill] [--json] [--heal]` — every task under
  way: task, repo, branch, kind, state, time in state, whether it `needs` you, its `dirty`
  and `commits` counts, its OUTCOME
  column (the worker's own final `DELIVERED:`/`FAILED:` line, once written), and the repo
  and worktree paths. Take a path from a row rather than typing one — `repo_path` is what
  `lb spawn --repo` wants, `path` is what `lb worktree reap` wants.
  `dirty` counts a worker's uncommitted files and `commits` what it has committed since it
  started. An **idle worker with `dirty` above 0 is holding work that exists nowhere else**
  — it looks finished, and tearing it down destroys that work. Ask it to commit; never reap
  it. `-` is "git could not answer", which is not `0`.
  `--wait` blocks until a task needs you (`blocked`, `error`, `undelivered`, `dead`, a
  worker gone idle holding uncommitted work, or a
  report of yours that finished a chunk — the `needs` column) or
  the timeout elapses — a timeout is a normal return (exit 0), not a failure, so re-run it
  to keep waiting.
  `undelivered` is a worker that was stood up but never took its brief: no context consumed
  and an untouched HEAD. It is not idle and not working — it is doing nothing. `--heal`
  re-sends the recorded brief to every such worker, which is the whole repair.
- `lb spawn --repo <path> --branch <b> --kind ship|scout --brief <file> [--new] [--base <b>]
  [--name <n>] [--agent <provider>] [--intent "..."]` — create an isolated worktree, start a
  worker in it, and deliver the brief. Any stage failing (bad kind/brief/repo/name, the
  worktree, the session, recording it, or delivering the brief after retries) unwinds
  everything already created, so a failed spawn never leaves a half-built task behind.
  The output names the `base` it branched from (ref + sha). `--base <b>` resolves against
  the branch's upstream when the local copy is behind it — `lb land --push` leaves local
  branches stale — and prints a `base_note` whenever local and upstream disagree.

## Worktrees

`lb worktree` manages the isolated repo copies workers run in. `lb spawn` already creates
one per task, so reach for these when adopting or cleaning up.

- `lb worktree ls --repo <path> [--json]` — every worktree of a repo, with the session (if
  any) attached to each.
- `lb worktree create --repo <path> --branch <b> [--new] [--base <b>] [--session <name>]
  [--intent "..."]` — a fresh worktree with the project's configured links applied. `--new`
  creates the branch; `--base` says off what.
- `lb worktree reap <path> [--force] [--rm-branch]` — remove a worktree once its work has
  landed. It **refuses** while the worktree has uncommitted changes (`dirty`), commits that
  are in no base branch and on no remote (`unlanded`), or no base to compare against at all
  (`unknown`); that refusal means work would be lost, so report it rather than reaching for
  `--force`. Landed-ness is patch identity against the base branch, not push state: work
  that landed by rebase or cherry-pick counts, and so does a batch the overseer landed onto
  the local base but has not pushed — which is the normal end state under `commit` delivery.
  A refusal after a green batch is therefore a real finding, not noise. On a real reap it
  also kills anything still running inside the worktree — a test server left up would
  otherwise outlive its own tree, holding a port and a database connection — and names
  every process it killed.
- `lb worktree deps <path> [--base <ref>]` — does this worktree's gate test what its code
  declares? Exits non-zero when it changed a dependency manifest while `.venv`/
  `node_modules` still points at the shared checkout, which makes lint and tests pass
  against versions the branch no longer uses.
- `lb worktree adopt <path> [--session <name>]` — start tracking a worktree that git already
  knows about but Lumbergh doesn't.
- `lb worktree link <path>` / `lb worktree unlink <path>` — re-apply or remove the project's
  configured shared files (env files, caches) in an existing worktree.

Targets `$LUMBERGH_SESSION` by default; pass `--session` for another.
"""

_SHIP_SKILL_MD = """\
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

**If your change touches dependencies** (`pyproject.toml`, `uv.lock`, `package.json`, a
lockfile), run `lb worktree deps .` first. Your worktree's `.venv`/`node_modules` were
copied from the main checkout, so a gate run before you fix that tests the *old* versions
and passes — the worst possible outcome, because it looks like success. If it reports
drift, install this worktree's own dependencies (the command it prints, if the repo
defines one), then gate. They're yours to reinstall: nothing you do to them touches the
main checkout.

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
"""

_SCOUT_SKILL_MD = """\
---
name: scout
description: >
  Investigate a codebase or question in an isolated worktree and report findings — read-only,
  no code changes. Use when you were spawned with a scout brief whose deliverable is a written
  report (current state, options, a recommended plan), not a diff. Ends with DELIVERED:/FAILED:.
---

# scout — investigate and report, no code

You were spawned into an isolated worktree to answer a question, not to change code. Your
deliverable is a **report**, never a diff. Do not modify, commit, or push anything.

## Investigate
1. Answer exactly what the brief asks — the state of the repo, the options, the risks, a
   recommended next step. Read widely; run read-only commands (`git log`, grep, tests in a
   read-only mode) as needed.
2. If the brief is ambiguous about what to find, ask before guessing.

## Report
Deliver a concise, decision-ready report:
- what you found (facts, not vibes),
- the options or candidate tasks, each with its trade-off,
- your recommendation — marked as a recommendation. A report recommends; it never
  authorizes. The user decides what to ship next.

## Finish
End your final message with exactly one line, nothing after it:
`DELIVERED: <one-line summary of where the report is>`   or   `FAILED: <reason>`
That line is the contract the fleet reads to know how your task ended.
"""

# The lb skill is for a coordinator; ship/scout are for workers. See the module docstring.
SKILLS: dict[str, str] = {
    "lb": _LB_SKILL_MD,
    "ship": _SHIP_SKILL_MD,
    "scout": _SCOUT_SKILL_MD,
}

# Back-compat alias: `lb skill` (no argument) prints the coordinator skill.
SKILL_MD = _LB_SKILL_MD

_AGENT_SKILL_DIRS = [
    Path.home() / ".claude" / "skills",
    Path.home() / ".pi" / "agent" / "skills",
    Path.home() / ".config" / "opencode" / "skills",
    Path.home() / ".codex" / "skills",
]


# The skill dirs Lumbergh actually launches workers under. A spawned worker reads whichever
# of these belongs to its agent, so seeding both means a worker has the skills whether it
# runs on claude or pi — even on a machine where `lb skill install` was never run by hand.
_WORKER_SKILL_DIRS = [
    Path.home() / ".claude" / "skills",
    Path.home() / ".pi" / "agent" / "skills",
]
WORKER_SKILLS = ["ship", "scout"]


def committed_path(name: str = "lb") -> Path:
    return Path(__file__).resolve().parent.parent / "skill" / name / "SKILL.md"


def ensure_worker_skills() -> list[Path]:
    """Put the worker skills where a spawned worker will find them, creating the dirs.

    Called on the spawn path so the brief can rely on `ship`/`scout` being present instead
    of restating the delivery contract every time. Idempotent; safe to call on every spawn.
    """
    return install(_WORKER_SKILL_DIRS, names=WORKER_SKILLS)


def detect_dirs() -> list[Path]:
    return [d for d in _AGENT_SKILL_DIRS if d.is_dir()]


def install(dirs: list[Path], names: list[str] | None = None) -> list[Path]:
    """Write the named skills (default: all) into each directory, idempotently."""
    names = names or list(SKILLS)
    written: list[Path] = []
    for directory in dirs:
        for name in names:
            content = SKILLS[name]
            target = directory / name / "SKILL.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or target.read_text() != content:
                target.write_text(content)
            written.append(target)
    return written


def check() -> bool:
    try:
        return all(committed_path(name).read_text() == content for name, content in SKILLS.items())
    except OSError:
        return False
