"""Bill's control surface: the fleet view and its long poll."""

import asyncio
import logging
import re
import shlex
import shutil
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lumbergh import bill as bill_bundle
from lumbergh import fleet, session_attention, worktrees
from lumbergh.activity.resolve import resolve_adapter
from lumbergh.activity.resolve import session_meta as _session_meta
from lumbergh.idle_monitor import idle_monitor
from lumbergh.routers.sessions import SESSION_NAME_PATTERN, create_tmux_session
from lumbergh.tmux_pty import kill_tmux_session, send_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bill", tags=["bill"])

_POLL_INTERVAL = 1.5
_MAX_WAIT_TIMEOUT = 900.0
_OUTCOME_TAIL_EVENTS = 15
_DELIVERY_ATTEMPTS = 3
_DELIVERY_RETRY_DELAY = 0.05

BILL_SESSION = "bill"
BILL_PROVIDER = "pi"
BILL_ORIGIN = "bill"


def _outcome_of(session: str) -> str | None:
    """The worker's contracted final line, read from its transcript.

    ``resolve_adapter`` builds a fresh adapter each call, so ``read_new`` starts at
    offset 0 and returns full history — this never steals events from ``lb read``.

    Errors are swallowed to ``None`` (and logged) rather than raised: this feeds
    ``/fleet``, Bill's only window on every worker at once, so one corrupt transcript
    must not blind him to the rest of the fleet.
    """
    try:
        meta = _session_meta(session)
        cwd = Path(meta["workdir"]) if meta.get("workdir") else None
        adapter = resolve_adapter(session, cwd, meta.get("agent_provider"))
        if adapter is None:
            return None
        events = adapter.read_new()[-_OUTCOME_TAIL_EVENTS:]
        return fleet.parse_outcome("\n".join((e.text or "") for e in events))
    except Exception:
        logger.warning("Failed to read outcome for session %s", session, exc_info=True)
        return None


def _add_outcomes(rows: list[dict]) -> list[dict]:
    """Attach each worker's contracted final line to its row, in place."""
    for row in rows:
        row["outcome"] = _outcome_of(row["session"]) if row.get("session") else None
    return rows


def _fleet_rows(origin: str | None, with_outcome: bool = False) -> list[dict]:
    from lumbergh.routers.worktrees import _live_sessions

    rows = fleet.snapshot(
        _live_sessions(),
        state_of=lambda n: idle_monitor.get_state(n).value,
        since_of=idle_monitor.state_since_seconds,
        unseen_of=session_attention.is_unseen,
        origin=origin,
    )
    return _add_outcomes(rows) if with_outcome else rows


@router.get("/fleet")
def get_fleet(origin: str | None = None):
    rows = _fleet_rows(origin, with_outcome=True)
    return {"total": len(rows), "tasks": rows}


@router.get("/fleet/wait")
async def wait_fleet(timeout: float = 300.0, origin: str | None = None):
    """Block until any task needs Bill, so supervision costs no tokens while idle.

    The current snapshot is checked before the first sleep, so a worker that went
    blocked before the call arrived still wakes it — no lost wakeup.

    Every snapshot runs in the executor: ``_fleet_rows`` shells out to tmux and to
    ``git worktree list`` per repo, and a supervising Bill holds this loop open
    continuously, so doing it on the event loop would stall every terminal
    WebSocket at the poll rate. The poll interval is deliberately human-scale — a
    supervision wake a second late costs nothing, and sub-second polling only buys
    more subprocess churn. Outcomes are read once, on the way out, rather than on
    every poll, for the same reason.
    """
    timeout = min(max(timeout, 0.0), _MAX_WAIT_TIMEOUT)
    loop = asyncio.get_running_loop()
    deadline = time.monotonic() + timeout
    start = time.monotonic()
    while True:
        rows = await loop.run_in_executor(None, _fleet_rows, origin)
        woke = fleet.any_needs_attention(rows)
        if woke or time.monotonic() >= deadline:
            return {
                "woke": woke,
                "waited": round(time.monotonic() - start, 1),
                "total": len(rows),
                "tasks": await loop.run_in_executor(None, _add_outcomes, rows),
            }
        await asyncio.sleep(_POLL_INTERVAL)


def _settings() -> dict:
    from lumbergh.routers.settings import get_settings

    return get_settings()


def _personality() -> str:
    return _settings().get("bill", {}).get("personality") or bill_bundle.DEFAULT_PERSONALITY


def _live_bill_conflict(workdir: Path) -> str | None:
    """Describe why a live session named ``bill`` isn't actually Bill.

    ``get_live_sessions()`` only reflects tmux and knows nothing about
    ``sessions_table``, so *any* session can hold the name ``bill`` — a developer's
    own terminal, for instance. A same-named session only counts as Bill if its
    recorded home resolves to Bill's home; comparing resolved paths (not raw
    strings) means a symlinked or non-normalized path never produces a false
    mismatch.

    An unrecorded live ``bill`` (no ``sessions_table`` entry, or one with no
    ``workdir``) can't be verified as Bill either, so it is treated the same as a
    mismatch rather than trusted — trusting an unrecorded name would let any
    unrelated tmux session called ``bill`` silently pass as him.
    """
    from lumbergh.routers.sessions import get_stored_sessions

    stored = get_stored_sessions().get(BILL_SESSION)
    if stored is None or not stored.get("workdir"):
        return "a live `bill` session with no recorded working directory"

    stored_workdir = Path(stored["workdir"]).expanduser().resolve()
    if stored_workdir != workdir.resolve():
        return f"a live `bill` session whose working directory is {stored_workdir}"

    return None


def _resolve_live_bill(workdir: Path) -> dict | None:
    """If a session named ``bill`` is live, return summon's response for it.

    Returns ``None`` when no session named ``bill`` is live at all, so the caller
    knows to proceed with creating one. Raises the identity-conflict failure
    directly (rather than returning a sentinel for it) since the caller has nothing
    useful to do with a conflict except let it surface.
    """
    from lumbergh.routers.sessions import get_live_sessions

    if BILL_SESSION not in get_live_sessions():
        return None

    conflict = _live_bill_conflict(workdir)
    if conflict:
        raise _fail(
            "identity",
            f"the `bill` session name is already taken by {conflict}",
            "rename or stop that session yourself, then summon Bill again — "
            "Lumbergh will not touch a session it didn't create",
            workdir=str(workdir),
        )
    return {"session": BILL_SESSION, "workdir": str(workdir), "existing": True}


_SHELL_OPERATORS = re.compile(r"\|\||&&|;|\|")
_NOT_A_PROGRAM_NAME = re.compile(r"^[(){}<>&$`~*?]")


def _harness_binary(launch_command: str) -> str | None:
    """The program a launch command would run first, or ``None`` if that can't be
    said with confidence.

    Launch commands are shell strings, not bare paths — the provider registry has
    entries like ``"claude --continue || claude"`` — so this only looks at the
    first simple command (up to the first ``||``/``&&``/``;``/``|``) and takes its
    first token. A launch command shlex can't parse is unusual enough, and a false
    refusal of a working setup bad enough, that skipping the check (returning
    ``None``) is the safer failure mode than guessing.

    The same reasoning rules out several shapes whose first *token* is confidently
    not the program: a leading environment assignment (``ANTHROPIC_API_KEY=$KEY
    claude`` → ``ANTHROPIC_API_KEY=$KEY``), a subshell (``(pi)``), a leading
    redirect (``>log pi``), or a brace/glob. ``shutil.which`` would fail on each of
    those and summon would refuse a setup that actually works — a worse outcome than
    the silent pane failure this check exists to prevent. No provider entry looks
    like this today; an env-prefixed launch command is a realistic future one.
    """
    first_segment = _SHELL_OPERATORS.split(launch_command, maxsplit=1)[0]
    try:
        tokens = shlex.split(first_segment)
    except ValueError:
        return None
    if not tokens:
        return None
    program = tokens[0]
    if "=" in program or _NOT_A_PROGRAM_NAME.match(program):
        return None
    return program


@router.post("/summon")
def summon():
    """Materialize Bill's home and start his session, or hand back the live one.

    The bundle is (re)materialized before the liveness check so an already-running
    Bill still gets a refreshed ``AGENTS.md`` when Lumbergh upgrades. Materializing
    only ever touches Bill's own home directory, never the contested session, so
    doing it before we even know whether the name is safe to use is harmless — and
    it means an upgrade lands even when a name conflict blocks the summon itself.
    """
    workdir = bill_bundle.materialize(_personality())

    resolved = _resolve_live_bill(workdir)
    if resolved is not None:
        return resolved

    from lumbergh.providers import get_launch_command

    launch_command = get_launch_command(BILL_PROVIDER, _settings().get("defaultAgent"))

    binary = _harness_binary(launch_command)
    if binary and shutil.which(binary) is None:
        raise _fail(
            "harness",
            f"the `{BILL_PROVIDER}` harness binary `{binary}` is not installed",
            f"install `{binary}`, then summon Bill again",
            # Bill's home is already materialized by this point, and a caller that
            # only wanted to find it (the e2e suite, a UI showing his briefs) must not
            # be denied the path just because the session can't start.
            workdir=str(workdir),
        )

    try:
        create_tmux_session(BILL_SESSION, workdir, launch_command=launch_command)
    except (RuntimeError, OSError) as e:
        # A losing double-click races the winning request's create_tmux_session call
        # here. tmux reports that as a generic RuntimeError, so the only reliable way
        # to tell "someone else just won" from "tmux is actually broken" is to ask
        # tmux itself who is live now, rather than parse the error string. The same
        # identity check applies here too: the name that just appeared might not be
        # the race winner's Bill at all.
        resolved = _resolve_live_bill(workdir)
        if resolved is not None:
            return resolved
        # Not a race, so tmux really is broken. Reported with a stage, like every other
        # summon failure and like spawn's identical case: the dashboard renders
        # {stage, error, help} into something actionable, and a bare 500 becomes a
        # generic alert for one of summon's two likeliest real failures.
        raise _fail(
            "session",
            f"could not start Bill's session: {e}",
            "check tmux, then summon Bill again",
            workdir=str(workdir),
        ) from e

    try:
        _store_session(
            name=BILL_SESSION,
            workdir=str(workdir),
            description="Your engineering manager",
            type="direct",
            agent_provider=BILL_PROVIDER,
        )
    except Exception as e:
        # get_live_sessions() only reflects tmux, never sessions_table, so a session
        # that exists but never got recorded would look live forever and permanently
        # win the idempotency check above. Killing it here leaves a clean slate. The
        # kill itself is best-effort: if it also fails, the store failure above must
        # still be what surfaces, not a new exception from the cleanup.
        cleaned = _try_cleanup(
            lambda: kill_tmux_session(BILL_SESSION), f"kill {BILL_SESSION} after a failed store"
        )
        help_text = "check the session store, then summon Bill again"
        if not cleaned:
            help_text += (
                f" — the `{BILL_SESSION}` tmux session could not be cleaned up "
                "and may need stopping by hand first"
            )
        raise _fail(
            "record",
            f"could not record Bill's session: {e}",
            help_text,
            workdir=str(workdir),
        ) from e

    return {"session": BILL_SESSION, "workdir": str(workdir), "existing": False}


class SpawnBody(BaseModel):
    repo: str
    branch: str
    kind: str
    brief_path: str
    name: str | None = None
    create_branch: bool = False
    base_branch: str | None = None
    agent_provider: str | None = None
    task_intent: str | None = None


def _fail(stage: str, error: str, help_text: str, **extra: str) -> HTTPException:
    """Build the 400 every failure stage raises.

    ``extra`` lets a specific stage attach fields a client might need to recover —
    e.g. the identity stage includes ``workdir`` so a caller can still find Bill's
    home when the name is refused, without a separate lookup endpoint.
    """
    return HTTPException(
        status_code=400, detail={"stage": stage, "error": error, "help": help_text, **extra}
    )


def _derive_name(branch: str, live: set[str]) -> str:
    base = re.sub(r"[^a-zA-Z0-9_-]", "-", branch).strip("-") or "task"
    if base not in live:
        return base
    n = 2
    while f"{base}-{n}" in live:
        n += 1
    return f"{base}-{n}"


def _store_session(**fields) -> None:
    from tinydb import Query

    from lumbergh.routers.sessions import sessions_table

    sessions_table.upsert(fields, Query().name == fields["name"])


def _try_cleanup(cleanup: Callable[[], None], description: str) -> bool:
    """Run a best-effort cleanup step, returning whether it succeeded.

    A failure here is logged, never raised: cleanup always runs alongside a real
    error already in flight, and that original error must be what the caller sees,
    not whatever the cleanup attempt blew up with.
    """
    try:
        cleanup()
        return True
    except Exception:
        logger.warning("Cleanup failed: %s", description, exc_info=True)
        return False


def _unwind(workdir: Path, *, session: str | None = None) -> None:
    """Undo partial spawn work. ``session`` is None when the tmux session never
    started, so a stage-``"session"`` failure doesn't try to kill one that
    doesn't exist; the worktree is always fresh at this point, so the reap
    guard (dirty/unpushed) never blocks it.

    ``worktrees.reap`` *returns* its failures rather than raising, so its result has
    to be checked: dropping the registry row after a failed ``git worktree remove``
    would leave the directory on disk with nothing pointing at it — invisible to
    ``lb fleet`` and to reconcile — while ``_try_cleanup`` reported success and the
    "manual cleanup may be needed" help never fired. Raising here is what routes it
    into that help text.
    """
    if session is not None:
        kill_tmux_session(session)
    reaped = worktrees.reap(workdir, force=True)
    if reaped.get("error"):
        raise RuntimeError(f"could not remove the worktree at {workdir}: {reaped['error']}")
    worktrees.remove_entry(workdir)


def _unwind_and_fail(
    stage: str,
    error: str,
    help_text: str,
    workdir: Path,
    *,
    session: str | None = None,
) -> HTTPException:
    """Unwind partial work and raise the stage's 400 — without letting a cleanup
    failure replace the diagnostic that got us here. If ``_unwind`` itself raises
    (e.g. a real git failure inside ``reap``), the original stage/error is still
    what the caller sees; the cleanup failure is logged and flagged in help text
    since that's exactly when a human needs to step in.
    """
    if not _try_cleanup(
        lambda: _unwind(workdir, session=session), f"unwind for stage {stage} at {workdir}"
    ):
        help_text += (
            " Cleanup of the partially-created task also failed; manual cleanup may be needed."
        )
    return _fail(stage, error, help_text)


def _resolve_brief(brief_path: str) -> Path:
    """Where a spawn request's ``brief_path`` actually lives on this server.

    A relative path resolves against Bill's home, not the server process's cwd:
    ``AGENTS.md`` tells Bill to write ``briefs/<slug>.md`` and then spawn with
    ``--brief briefs/<slug>.md``, and his cwd *is* his home, so his own relative
    path is the one that must work. Resolving it against the server's cwd instead
    made the documented invocation fail with "write the brief before spawning" —
    telling a weak model to redo what it had just done.
    """
    brief = Path(brief_path).expanduser()
    return brief if brief.is_absolute() else bill_bundle.home() / brief


def _brief_delivery(brief: Path, kind: str, name: str) -> str:
    report = f"Write your report to {bill_bundle.home() / 'reports' / f'{name}.md'}. "
    return (
        f"Read your brief at {brief} and follow it. "
        + (report if kind == "scout" else "")
        + "Finish your final message with exactly one line: "
        "`DELIVERED: <pr-url-or-branch>` or `FAILED: <reason>`."
    )


def _deliver_brief(name: str, brief: Path, kind: str) -> bool:
    """Send the brief pointer, retrying a bounded number of times.

    A transient tmux hiccup right after session creation is plausible and much
    cheaper to retry than to tear the task down over.
    """
    text = _brief_delivery(brief, kind, name)
    for attempt in range(_DELIVERY_ATTEMPTS):
        if send_text(name, text):
            return True
        if attempt < _DELIVERY_ATTEMPTS - 1:
            time.sleep(_DELIVERY_RETRY_DELAY)
    return False


def _checked_request(body: SpawnBody) -> tuple[Path, Path, str]:
    """The brief, repo, and session name a spawn will use — or the stage that refuses it.

    Every check here happens before anything is created, so these failures never need an
    unwind. Grouped so ``spawn`` itself reads as the create-and-unwind sequence it is.
    """
    if body.kind not in bill_bundle.TASK_KINDS:
        raise _fail("kind", f"unknown kind `{body.kind}`", "kind must be ship or scout")

    brief = _resolve_brief(body.brief_path)
    if not brief.is_file():
        if Path(body.brief_path).expanduser().is_absolute():
            brief_help = "check the path, then write the brief before spawning"
        else:
            brief_help = (
                "check the path, then write the brief before spawning — a relative "
                f"--brief is resolved against {bill_bundle.home()}"
            )
        raise _fail("brief", f"no brief file at {brief}", brief_help)

    repo = Path(body.repo).expanduser()
    if not (repo / ".git").exists():
        raise _fail("repo", f"{repo} is not a git repository", "pass the repo's root path")

    if body.name and not SESSION_NAME_PATTERN.match(body.name):
        raise _fail(
            "name",
            f"invalid session name `{body.name}`",
            "--name may only use letters, numbers, underscores, and hyphens",
        )

    from lumbergh.routers.sessions import get_live_sessions

    live = set(get_live_sessions().keys())
    name = body.name or _derive_name(body.branch, live)
    if name in live:
        raise _fail("name", f"session `{name}` is already live", "pass a different --name")

    return brief, repo, name


@router.post("/spawn")
def spawn(body: SpawnBody):
    """Create worktree + session + deliver the brief, unwinding any partial work."""
    brief, repo, name = _checked_request(body)

    from lumbergh.routers.settings import get_settings

    created = worktrees.create(
        repo,
        body.branch,
        created_at=datetime.now(UTC).isoformat(),
        create_branch=body.create_branch,
        base_branch=body.base_branch,
        session=name,
        task_intent=body.task_intent,
        kind=body.kind,
        origin=BILL_ORIGIN,
        global_base_dir=get_settings().get("worktree", {}).get("base_dir") or None,
    )
    if created.get("error"):
        raise _fail("worktree", created["error"], "fix the branch or repo and retry")

    workdir = Path(created["path"])
    from lumbergh.providers import get_launch_command

    launch = get_launch_command(body.agent_provider, get_settings().get("defaultAgent"))
    try:
        create_tmux_session(name, workdir, launch_command=launch)
    except (RuntimeError, OSError) as e:
        raise _unwind_and_fail(
            "session", f"could not start the worker: {e}", "check tmux, then retry", workdir
        )

    try:
        _store_session(
            name=name,
            workdir=str(workdir),
            description=body.task_intent or "",
            type="worktree",
            agent_provider=body.agent_provider,
            worktree_parent_repo=str(repo.resolve()),
            worktree_branch=body.branch,
        )
    except Exception as e:
        # Its own stage: failing to record the task is a store problem, not a delivery
        # one, and "check tmux" is the wrong thing to tell a caller whose disk is full.
        raise _unwind_and_fail(
            "record",
            f"could not record the task: {e}",
            "check the session store, then retry",
            workdir,
            session=name,
        )

    try:
        delivered = _deliver_brief(name, brief, body.kind)
    except Exception as e:
        raise _unwind_and_fail(
            "delivery",
            f"could not deliver the brief: {e}",
            "check tmux, then retry",
            workdir,
            session=name,
        )

    if not delivered:
        raise _unwind_and_fail(
            "delivery",
            f"worker did not accept the brief after {_DELIVERY_ATTEMPTS} attempts",
            "check tmux, then retry",
            workdir,
            session=name,
        )

    return {
        "session": name,
        "path": str(workdir),
        "branch": body.branch,
        "kind": body.kind,
        "brief_path": str(brief),
    }


class BriefBody(BaseModel):
    path: str
    body: str


@router.post("/brief")
def write_brief(body: BriefBody):
    """Write a brief, refusing any path outside Bill's ``briefs/`` directory.

    Bill writes his own briefs with his own file tools; this exists for callers that
    can't reach his home directly — a future UI showing a brief before spawn, or an
    E2E client that only ever sends path strings across a possible host/VM split.
    """
    target = Path(body.path).expanduser().resolve()
    home_dir = bill_bundle.home().resolve()
    if not target.is_relative_to(home_dir / "briefs"):
        raise _fail("path", f"{target} is outside {home_dir / 'briefs'}", "write under briefs/")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body.body)
    return {"path": str(target)}
