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
from lumbergh import bill_watch, fleet, land, session_attention, worktrees
from lumbergh.activity.resolve import resolve_adapter
from lumbergh.activity.resolve import session_meta as _session_meta
from lumbergh.briefs import enumerate_briefs
from lumbergh.idle_monitor import idle_monitor
from lumbergh.routers.sessions import SESSION_NAME_PATTERN, create_tmux_session, create_tmux_window
from lumbergh.runs import run_members
from lumbergh.spawn_delivery import DeliveryResult, deliver_when_ready
from lumbergh.targets import format_target, parse_target
from lumbergh.tmux_pty import kill_tmux_session, kill_tmux_window, list_session_windows

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bill", tags=["bill"])

_POLL_INTERVAL = 1.5
_MAX_WAIT_TIMEOUT = 900.0
_OUTCOME_TAIL_EVENTS = 15

# Worktree paths of dead tasks Bill has already been shown. A dead task has no live session
# to hold its seen/unseen flag, so its "surface once" lives here instead. In-memory only:
# after a restart re-surfacing a dead task once is harmless, and it never grows without bound
# because `_mark_seen` prunes it back to the dead tasks still in the fleet.
_dead_acked: set[str] = set()

# Overseer sessions Bill has already been shown in their current done-unseen (idle+unseen)
# episode. This is Bill's *private* seen-marker: unlike a worker, an overseer's `unseen`
# flag is the user's own dashboard "done while you were away" overlay, which Bill must not
# clear by supervising. Blocked/error overseers wake every time (not acked here); only the
# soft idle+unseen case is deduplicated. Pruned by `_mark_seen` to overseers still idle+
# unseen, so a new episode (overseer worked, then went idle again) surfaces afresh.
_overseer_acked: set[str] = set()

BILL_SESSION = "bill"
BILL_PROVIDER = "pi"
BILL_ORIGIN = "bill"


def _direct_reports(rows: list[dict], viewer: str) -> list[dict]:
    """The rows ``viewer`` is responsible for. Bill's direct reports are the overseers the
    user actually put in his hands (``row["watched"]`` — a babysit or a delegation; see
    ``bill_watch``) — plus any *orphan* worker no overseer owns (its repo has no live
    overseer), so a worker he spawns directly never falls through the cracks. An overseer's
    reports are its own workers (nested under it). Each watches only its own layer.

    Every other live session is still *listed*: Bill needs to see that a repo has an
    overseer before he can delegate to it. It just isn't his to act on."""
    if viewer == BILL_SESSION:
        return [
            r
            for r in rows
            if (r.get("role") == "overseer" and r.get("watched"))
            or (r.get("role") == "worker" and not r.get("parent"))
        ]
    return [r for r in rows if r.get("role") == "worker" and r.get("parent") == viewer]


def engage_overseer(session: str) -> None:
    """Bill has delegated to ``session``: it becomes his to watch until it reports back.

    The engagement is pre-acked, because delegation usually lands on a session that is
    *already* idle+unseen from its last chunk. Without this that stale episode would read
    as an instant answer to Bill — waking him and releasing the engagement before the
    overseer has even started. The ack is dropped the moment it goes to work (see
    ``_prune_overseer_acks``), so the chunk it actually delivers wakes him normally."""
    bill_watch.engage(session, datetime.now(UTC).isoformat())
    _overseer_acked.add(session)


def _prune_overseer_acks(rows: list[dict]) -> None:
    """Forget acks for overseers that have moved on, so a *new* done-unseen episode wakes
    Bill afresh. This runs on every evaluation, not just on a wake: an overseer that worked
    and finished again between two ``_mark_seen`` calls would otherwise stay silently acked
    from its previous episode."""
    _overseer_acked.intersection_update(
        r["task"]
        for r in rows
        if r.get("role") == "overseer" and r["state"] == "idle" and r.get("unseen")
    )


def _needing(rows: list[dict], viewer: str) -> list[dict]:
    """``viewer``'s direct reports that have an unhandled action for it right now.

    A done-unseen overseer is de-duplicated by Bill's private ack (so it wakes once
    without clearing the user's overlay); a done worker de-dupes through its own
    ``unseen`` flag, which ``_mark_seen`` clears when its overseer views it."""
    _prune_overseer_acks(rows)
    needing = []
    for row in _direct_reports(rows, viewer):
        if not fleet.needs_attention(row):
            continue
        if (
            row["state"] == "idle"
            and row.get("role") == "overseer"
            and row.get("task") in _overseer_acked
        ):
            continue
        needing.append(row)
    return needing


def viewer_woke(rows: list[dict], viewer: str) -> bool:
    """True when one of ``viewer``'s direct reports needs action now."""
    return bool(_needing(rows, viewer))


def _stamp_attention(rows: list[dict], viewer: str) -> list[dict]:
    """Mark each row with whether it needs *this* viewer, so the table says so outright.

    Raw ``unseen`` cannot carry that: it is the user's own dashboard overlay, true for
    every session they left mid-thought. Reading it as "a report finished something for
    me" is what had Bill supervising sessions nobody handed him."""
    needing = {id(r) for r in _needing(rows, viewer)}
    for row in rows:
        row["attention"] = id(row) in needing
    return rows


def bill_woke(rows: list[dict]) -> bool:
    return viewer_woke(rows, BILL_SESSION)


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
    """Attach each worker's contracted final line to its row, in place.

    Overseers don't deliver a contracted outcome, so they're skipped — reading
    their (large, long-lived) transcripts every poll would be pure waste.
    """
    for row in rows:
        if row.get("role") == "overseer":
            row["outcome"] = None
            continue
        session = row.get("session")
        identifier = (row.get("target") or session) if session else None
        row["outcome"] = _outcome_of(identifier) if identifier else None
    return rows


def _fleet_rows(origin: str | None, with_outcome: bool = False) -> list[dict]:
    from lumbergh.routers.worktrees import _live_sessions

    rows = fleet.snapshot(
        _live_sessions(),
        state_of=lambda n: idle_monitor.get_state(n).value,
        since_of=idle_monitor.state_since_seconds,
        unseen_of=session_attention.is_unseen,
        origin=origin,
        dead_acked=_dead_acked,
        live_targets=set(idle_monitor.live_targets()),
        overseer_exclude={BILL_SESSION},
    )
    # Stamped here, inside the executor, rather than read per row on the event loop: the
    # supervise long poll asks for direct reports every 1.5s and the registries are files.
    watched = bill_watch.watched()
    for row in rows:
        if row.get("role") == "overseer":
            row["watched"] = row["task"] in watched
    return _add_outcomes(rows) if with_outcome else rows


def _mark_seen(rows: list[dict], viewer: str) -> None:
    """``viewer`` has been shown its direct reports, so a done-unseen one stops re-waking it.

    A finished report goes idle+unseen, which ``needs_attention`` reads as "surface once".
    Nothing but a human opening the session ever cleared that, so a delivered-but-unlanded
    task re-woke ``lb fleet --wait`` and the nudge on every poll, forever. Being shown the
    fleet *is* the watcher seeing it — but scoped to the watcher's own layer:

    - an **overseer** report is acked in Bill's *private* ``_overseer_acked``, never by
      clearing the user's own dashboard "unseen" overlay on that session;
    - a **worker** report is acked by clearing its ``unseen`` flag (its overseer owns it),
      or by path in ``_dead_acked`` when its session is gone (``dead``).

    The ack sets are pruned against the whole tree so a report that moved on (worked again,
    or was reaped) surfaces afresh, and they never leak.
    """
    for row in _direct_reports(rows, viewer):
        if row.get("role") == "overseer":
            if row["state"] == "idle" and row.get("unseen") and row["task"] not in _overseer_acked:
                _overseer_acked.add(row["task"])
                # A *new* done-unseen episode on a watched overseer is the chunk it owed
                # Bill. Having been shown it ends the one-shot delegation; a standing
                # babysit is untouched, so it keeps waking him until the user cancels it.
                bill_watch.release(row["task"])
        elif row.get("session"):
            session_attention.clear_unseen(row.get("target") or row["session"])
        elif row.get("state") == "dead":
            _dead_acked.add(row["path"])
    _dead_acked.intersection_update(r["path"] for r in rows if r.get("state") == "dead")
    _prune_overseer_acks(rows)
    bill_watch.prune({r["task"] for r in rows if r.get("role") == "overseer"})


@router.get("/fleet")
async def get_fleet(origin: str | None = None, as_session: str | None = None):
    loop = asyncio.get_running_loop()
    rows = await loop.run_in_executor(None, _fleet_rows, origin, True)
    viewer = as_session or BILL_SESSION
    # Stamped before `_mark_seen`, or being shown the table would ack away the very thing
    # the table is meant to be telling the viewer about.
    _stamp_attention(rows, viewer)
    _mark_seen(rows, viewer)
    await session_attention.persist()
    return {"total": len(rows), "tasks": rows}


@router.get("/fleet/wait")
async def wait_fleet(
    timeout: float = 300.0, origin: str | None = None, as_session: str | None = None
):
    """Block until a direct report of the caller needs it, so supervision costs no tokens.

    ``as_session`` is who is waiting: Bill (the default) wakes on his overseers; an
    overseer passing its own name wakes on its own workers. Each watches only its layer.

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
    viewer = as_session or BILL_SESSION
    loop = asyncio.get_running_loop()
    deadline = time.monotonic() + timeout
    start = time.monotonic()
    while True:
        rows = await loop.run_in_executor(None, _fleet_rows, origin)
        woke = any(r["attention"] for r in _stamp_attention(rows, viewer))
        if woke or time.monotonic() >= deadline:
            if woke:
                # This wake has now surfaced the finished work to the watcher; without
                # marking it seen the same idle+unseen report re-wakes instantly on the
                # next `--wait`, the loop the user hit. Blocked/error keep waking on state.
                _mark_seen(rows, viewer)
                await session_attention.persist()
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


def _personality() -> tuple[str, str | None]:
    b = _settings().get("bill", {}) or {}
    return b.get("personality") or bill_bundle.DEFAULT_PERSONALITY, b.get("customPersonality")


def _harness() -> str:
    return (_settings().get("bill", {}) or {}).get("harness") or BILL_PROVIDER


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
    personality, custom_text = _personality()
    workdir = bill_bundle.materialize(personality, custom_text)

    resolved = _resolve_live_bill(workdir)
    if resolved is not None:
        return resolved

    from lumbergh.providers import get_launch_command

    harness = _harness()
    launch_command = get_launch_command(harness, _settings().get("defaultAgent"))

    binary = _harness_binary(launch_command)
    if binary and shutil.which(binary) is None:
        raise _fail(
            "harness",
            f"the `{harness}` harness binary `{binary}` is not installed",
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
            agent_provider=harness,
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


class BabysitBody(BaseModel):
    session: str
    repo: str | None = None


@router.post("/babysit")
def start_babysit(body: BabysitBody):
    """Register a keep-alive loop over an overseer. The idle monitor drives it.

    ``repo`` is only needed to read the repo's ``[babysit]`` contract; when omitted it is
    resolved from the session's own working directory, so ``lb babysit --session port``
    just works. Defaults apply when a repo has no config, so an unresolvable repo is fine.
    """
    from lumbergh import babysit

    repo = body.repo
    if repo is None:
        repo = _session_meta(body.session).get("workdir")
    return babysit.start(body.session, repo, datetime.now(UTC).isoformat())


@router.post("/babysit/refresh")
async def refresh_babysit(body: BabysitBody):
    """Run a babysat session's refresh ritual now — Bill's one-button /clear + restart, so
    he never has to cram the two into a single prompt (which the /clear would eat)."""
    from lumbergh import babysit

    status, busy = await babysit.refresh(body.session)
    if status == babysit.REFRESHED:
        return {"session": body.session, "refreshed": True}
    if status == babysit.HELD:
        raise HTTPException(
            status_code=409,
            detail={
                "error": (
                    f"{body.session} is still supervising {len(busy)} worker(s) "
                    f"({', '.join(busy)}) — refreshing would `/clear` the context "
                    "supervising them"
                ),
                "help": (
                    "it is waiting on its crew, not stalled — leave it alone until they "
                    "finish, or `lb read` a stuck one and answer it through its overseer"
                ),
            },
        )
    raise HTTPException(
        status_code=400,
        detail={
            "error": f"{body.session} is not being babysat",
            "help": "start it with `lb babysit --session <name>` first",
        },
    )


@router.delete("/babysit")
def stop_babysit(session: str):
    from lumbergh import babysit

    return {"session": session, "stopped": babysit.stop(session)}


@router.get("/babysit")
def list_babysit():
    from lumbergh import babysit

    return {"babysits": babysit.list_all()}


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
    into: str | None = None
    run: str | None = None
    delivery: str | None = None


_DEP_SYNC_HELP = (
    'add [worktree] dep_sync = "<install command>" to .lumbergh.toml so lb can give the '
    "batch its own environment, or re-run with --skip-smoke if you are gating by hand"
)


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


def _unwind(workdir: Path, *, target: str | None = None) -> None:
    """Undo partial spawn work. ``target`` is None when the tmux container never
    started, so a stage-``"session"`` failure doesn't try to kill one that
    doesn't exist; the worktree is always fresh at this point, so the reap
    guard (dirty/unpushed) never blocks it.

    A window target (``session:window``) only tears down its own window, leaving
    sibling windows in that session alive; a bare target kills the whole session.

    ``worktrees.reap`` *returns* its failures rather than raising, so its result has
    to be checked: dropping the registry row after a failed ``git worktree remove``
    would leave the directory on disk with nothing pointing at it — invisible to
    ``lb fleet`` and to reconcile — while ``_try_cleanup`` reported success and the
    "manual cleanup may be needed" help never fired. Raising here is what routes it
    into that help text.
    """
    if target is not None:
        session, window = parse_target(target)
        kill_tmux_window(target) if window else kill_tmux_session(session)
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
    target: str | None = None,
) -> HTTPException:
    """Unwind partial work and raise the stage's 400 — without letting a cleanup
    failure replace the diagnostic that got us here. If ``_unwind`` itself raises
    (e.g. a real git failure inside ``reap``), the original stage/error is still
    what the caller sees; the cleanup failure is logged and flagged in help text
    since that's exactly when a human needs to step in.
    """
    if not _try_cleanup(
        lambda: _unwind(workdir, target=target), f"unwind for stage {stage} at {workdir}"
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


# The per-mode delivery clause the worker is handed at spawn. This is where a repo's
# `[delivery] mode` (or a `--delivery` override) becomes a concrete instruction — the `ship`
# skill states all three modes and defers to whichever this names, so the skill stays global
# (see ensure_worker_skills) and there is no conflicting-instructions problem.
_DELIVERY_CLAUSE = {
    "pr": (
        "Deliver in PR mode: commit on a branch, push, and open a PR (`gh pr create`); "
        "report the URL. Final line: `DELIVERED: <pr-url>`"
    ),
    "branch": (
        "Deliver in BRANCH mode: commit on a branch and push it — do NOT open a PR. "
        "Final line: `DELIVERED: <branch>`"
    ),
    "commit": (
        "Deliver in COMMIT mode: commit on a branch and STOP — never push, never open "
        "a PR, never merge or rebase; the overseer lands your work. "
        "Final line: `DELIVERED: <sha>`"
    ),
}


def _brief_delivery(brief: Path, kind: str, name: str, mode: str = "commit") -> str:
    intro = f"Read your brief at {brief} and follow it. "
    if kind == "scout":
        report = f"Write your report to {bill_bundle.home() / 'reports' / f'{name}.md'}. "
        deliver = (
            "Finish with exactly one line: `DELIVERED: <where the report is>` "
            "or `FAILED: <reason>`."
        )
        return intro + report + deliver
    clause = _DELIVERY_CLAUSE.get(mode, _DELIVERY_CLAUSE["commit"])
    return intro + clause + ", or `FAILED: <reason>` if it did not work."


def _deliver_brief(name: str, brief: Path, kind: str, mode: str = "commit") -> DeliveryResult:
    """Hand the worker its brief once it can actually receive it.

    A fresh worker is not ready the instant its session exists: the harness boots
    for seconds and opens on Claude Code's folder-trust dialog. Typing the brief
    before its input prompt exists drops it into the void, so this waits for the
    prompt, answers the trust dialog, delivers, and confirms the worker started —
    rather than firing once and trusting that tmux accepting the keystrokes means
    the agent consumed them.
    """
    return deliver_when_ready(name, _brief_delivery(brief, kind, name, mode))


def _checked_request(body: SpawnBody) -> tuple[Path, Path, str]:
    """The brief, repo, and worker name a spawn will use — or the stage that refuses it.

    Every check here happens before anything is created, so these failures never need an
    unwind. Grouped so ``spawn`` itself reads as the create-and-unwind sequence it is.

    A window worker (``body.into`` set) picks its name from the windows already inside
    that session — the session itself being live is the point (auto-create), not a
    conflict. A bare worker keeps today's rule: its name must not collide with any live
    session.
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

    if body.into:
        taken = set(list_session_windows(body.into))
        name = body.name or _derive_name(body.branch, taken)
        if name in taken:
            raise _fail(
                "name",
                f"window `{name}` already exists in `{body.into}`",
                "pass a different --name",
            )
        return brief, repo, name

    from lumbergh.routers.sessions import get_live_sessions

    live = set(get_live_sessions().keys())
    name = body.name or _derive_name(body.branch, live)
    if name in live:
        raise _fail("name", f"session `{name}` is already live", "pass a different --name")

    return brief, repo, name


@router.post("/spawn")
def spawn(body: SpawnBody):
    """Create worktree + tmux container + deliver the brief, unwinding any partial work.

    ``body.into`` places the worker in a window of that session (auto-created if not
    already live) instead of a session of its own; ``target`` is what addresses it
    either way — the bare name, or ``session:window``. Window workers are intentionally
    left out of the session store (Task 4's registry resolves their cwd instead), so
    they show up via discovery and the fleet board, not the sessions list.
    """
    brief, repo, name = _checked_request(body)
    target = format_target(body.into, name) if body.into else name

    from lumbergh.routers.settings import get_settings

    created = worktrees.create(
        repo,
        body.branch,
        created_at=datetime.now(UTC).isoformat(),
        create_branch=body.create_branch,
        base_branch=body.base_branch,
        session=None if body.into else name,
        target=target,
        run=body.run,
        task_intent=body.task_intent,
        kind=body.kind,
        origin=BILL_ORIGIN,
        global_base_dir=get_settings().get("worktree", {}).get("base_dir") or None,
    )
    if created.get("error"):
        raise _fail("worktree", created["error"], "fix the branch or repo and retry")

    workdir = Path(created["path"])
    from lumbergh.agent_cli import skill
    from lumbergh.providers import get_launch_command

    # Best-effort, before the agent boots and reads its skills: a worker should always have
    # the ship/scout contract available, so the brief needn't restate it. Never fail a spawn
    # over this — a missing skill only costs the worker a little context, not the task.
    try:
        skill.ensure_worker_skills()
    except Exception:
        logger.warning("could not install worker skills for %s", target, exc_info=True)

    launch = get_launch_command(body.agent_provider, get_settings().get("defaultAgent"))
    try:
        if body.into:
            create_tmux_window(body.into, name, workdir, launch_command=launch)
        else:
            create_tmux_session(name, workdir, launch_command=launch)
    except (RuntimeError, OSError) as e:
        raise _unwind_and_fail(
            "session", f"could not start the worker: {e}", "check tmux, then retry", workdir
        )

    if not body.into:
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
                target=target,
            )

    try:
        mode = body.delivery or worktrees.read_delivery_mode(repo)
        delivery = _deliver_brief(target, brief, body.kind, mode)
    except Exception as e:
        raise _unwind_and_fail(
            "delivery",
            f"could not deliver the brief: {e}",
            "check tmux, then retry",
            workdir,
            target=target,
        )

    if not delivery.delivered:
        raise _unwind_and_fail(
            "delivery",
            delivery.reason,
            "inspect the worker's terminal with `lb read --source pane`, then retry",
            workdir,
            target=target,
        )

    return {
        "session": target,
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


class InitBody(BaseModel):
    repo: str
    delivery: str | None = None
    smoke: str | None = None
    dep_sync: str | None = None


_INIT_HEADER = (
    "# Lumbergh project config. Declares how `lb` treats this repo so the tool imposes\n"
    "# no pattern — see `lb init --help`.\n"
)


@router.post("/init")
def init(body: InitBody):
    """Scaffold or extend a repo's .lumbergh.toml — declare its delivery policy once.

    Never clobbers: an existing table is reported and left as-is; only missing tables
    are appended. So it's safe for an agent to run on any repo.
    """
    import tomllib

    repo = Path(body.repo).expanduser()
    if not (repo / ".git").exists():
        raise _fail("repo", f"{repo} is not a git repository", "pass the repo's root path")
    mode = body.delivery or "commit"
    if mode not in worktrees.DELIVERY_MODES:
        raise _fail("delivery", f"unknown delivery mode `{mode}`", "use pr | branch | commit")

    dotfile = repo / ".lumbergh.toml"
    existing = tomllib.loads(dotfile.read_text()) if dotfile.is_file() else {}

    blocks, added, present = [], [], []
    if "delivery" in existing:
        present.append(f"[delivery] mode = {existing['delivery'].get('mode')!r}")
    else:
        blocks.append(
            f'[delivery]\nmode = "{mode}"  # pr (push + gh pr create) | branch (push, no PR) | commit (commit + stop)\n'
        )
        added.append("delivery")
    if body.smoke:
        if "land" in existing:
            present.append(f"[land] smoke = {existing['land'].get('smoke')!r}")
        else:
            blocks.append(f'[land]\nsmoke = "{body.smoke}"\n')
            added.append("land")
    if body.dep_sync:
        if "worktree" in existing:
            present.append(f"[worktree] dep_sync = {existing['worktree'].get('dep_sync')!r}")
        else:
            blocks.append(
                f"[worktree]\n# Install a worktree's own dependencies once its link to the\n"
                f"# shared checkout is broken, so a dependency change gates honestly.\n"
                f'dep_sync = "{body.dep_sync}"\n'
            )
            added.append("worktree")

    if blocks:
        if dotfile.is_file():
            body_text = dotfile.read_text().rstrip("\n") + "\n\n" + "\n".join(blocks)
        else:
            body_text = _INIT_HEADER + "\n" + "\n".join(blocks)
        dotfile.write_text(body_text)

    return {
        "path": str(dotfile),
        "created": not existing and bool(blocks),
        "added": added,
        "unchanged": present,
    }


class BatchBody(BaseModel):
    repo: str
    run: str
    briefs: list[str]
    kind: str
    base: str | None = None
    session: str | None = None
    delivery: str | None = None


@router.post("/batch")
def batch(body: BatchBody):
    """Stand up one window worker per brief, all in one session, grouped by run."""
    session = body.session or body.run
    try:
        pairs = enumerate_briefs(body.briefs)
    except ValueError as e:
        raise _fail("briefs", str(e), "check --briefs paths and filenames")
    if not pairs:
        raise _fail("briefs", "no briefs found", "pass a directory of .md files or a file list")

    workers, failed = [], []
    for brief_path, stem in pairs:
        try:
            workers.append(
                spawn(
                    SpawnBody(
                        repo=body.repo,
                        branch=stem,
                        kind=body.kind,
                        brief_path=str(brief_path),
                        name=stem,
                        create_branch=True,
                        base_branch=body.base,
                        into=session,
                        run=body.run,
                        delivery=body.delivery,
                    )
                )
            )
        except HTTPException as e:
            failed.append({"brief": stem, "error": e.detail})
    return {"run": body.run, "session": session, "workers": workers, "failed": failed}


class LandBody(BaseModel):
    run: str
    onto: str | None = None
    push: bool = False
    smoke: str | None = None
    skip_smoke: bool = False


def _land_existing_batch(body: LandBody, repo: Path, base: str, batch_branch: str, member_branches):
    """Land the batch branch a prior no-push `land` left in place — push *that*
    ref, never a fresh re-assembly. Rebuilding here would discard any commit the
    overseer added to the inspected branch and could push a tree that smoke never
    saw. Refuse instead if a worker moved since assembly, so the batch's newer
    work isn't silently dropped either."""
    stale = land.stale_members(repo, base, batch_branch, member_branches)
    if stale:
        raise _fail(
            "stale",
            f"workers moved since `{batch_branch}` was assembled: {', '.join(stale)}",
            f"re-assemble with `lb land --run {body.run}` (no --push), then --push",
        )

    smoke_state = "skipped"
    if not body.skip_smoke:
        cmd = body.smoke or worktrees.read_land_smoke(repo)
        if not cmd:
            raise _fail(
                "smoke",
                "no smoke command configured",
                "add [land].smoke to .lumbergh.toml, or pass --smoke/--skip-smoke",
            )
        worktree = land.checkout_batch(repo, batch_branch)
        deps = land.prepare_deps(repo, worktree, base)
        if not deps["ok"]:
            land.remove_worktree(repo, worktree)
            raise _fail("deps", deps["error"], _DEP_SYNC_HELP)
        smoke = land.run_smoke(worktree, cmd)
        land.remove_worktree(repo, worktree)
        if not smoke["ok"]:
            raise _fail(
                "smoke",
                f"smoke failed (exit {smoke['returncode']})",
                f"batch branch {batch_branch} left in place; fix and re-push",
            )
        smoke_state = "passed"

    picked = land.commits_by_branch(repo, base, member_branches)
    sha = land.head_sha(repo, batch_branch)
    push = land.push_batch(repo, batch_branch, base)
    if not push["ok"]:
        raise _fail("push", push.get("error", "push failed"), "check the remote and retry")
    land.delete_batch(repo, batch_branch)
    return {
        "run": body.run,
        "batch": batch_branch,
        "base": base,
        "pushed": True,
        "sha": sha,
        "picked": picked,
        "smoke": smoke_state,
    }


@router.post("/land")
def land_run(body: LandBody):
    """Assemble a run's branches, smoke-test, and (only on explicit go) single-push."""
    members = run_members(body.run)
    if not members:
        raise _fail("run", f"no workers in run `{body.run}`", "check the --run id")
    repos = {m.get("parent_repo") for m in members}
    repo_path = next(iter(repos)) if len(repos) == 1 else None
    if repo_path is None:
        raise _fail("run", "run spans multiple repos (or a member has no repo)", "land per repo")
    repo = Path(repo_path)
    base = body.onto or "main"
    member_branches = [m["branch"] for m in members]
    batch_branch = f"batch-{body.run}"

    # Membership, not name matching, decides who is in a batch — so a member whose
    # branch can't be resolved is a hard error naming the worker, never a silent
    # omission that produces output indistinguishable from a complete land.
    missing = [m for m in members if not land.branch_exists(repo, m["branch"])]
    if missing:
        named = ", ".join(f"{m.get('target') or '?'} (branch `{m['branch']}`)" for m in missing)
        raise _fail(
            "members",
            f"run members whose branch does not exist: {named}",
            "the worker's branch was renamed or never created — fix the registry entry "
            "(`lb worktree ls`) or drop the member, then re-run",
        )

    # `--push` against a batch a prior `land` already assembled lands that exact
    # branch — the one the overseer was told to inspect — rather than rebuilding.
    if body.push and land.batch_exists(repo, batch_branch):
        return _land_existing_batch(body, repo, base, batch_branch, member_branches)
    return _assemble_and_land(body, repo, base, member_branches)


def _assemble_and_land(body: LandBody, repo: Path, base: str, member_branches: list[str]) -> dict:
    result = land.assemble(repo, body.run, base, member_branches)
    if not result["ok"]:
        raise _fail(
            result["stage"],
            result.get("error", "assembly failed"),
            "resolve the conflict/ordering and re-run",
            **{k: str(v) for k, v in result.items() if k in ("branch", "commit") and v is not None},
        )

    worktree = Path(result["worktree"])
    batch_branch = result["batch"]

    smoke_state = "skipped"
    resynced: list[str] = []
    if not body.skip_smoke:
        cmd = body.smoke or worktrees.read_land_smoke(repo)
        if not cmd:
            land.cleanup_assembly(repo, worktree, batch_branch)
            raise _fail(
                "smoke",
                "no smoke command configured",
                "add [land].smoke to .lumbergh.toml, or pass --smoke/--skip-smoke",
            )
        deps = land.prepare_deps(repo, worktree, base)
        if not deps["ok"]:
            land.cleanup_assembly(repo, worktree, batch_branch)
            raise _fail("deps", deps["error"], _DEP_SYNC_HELP)
        resynced = deps["resynced"]
        smoke = land.run_smoke(worktree, cmd)
        if not smoke["ok"]:
            raise _fail(
                "smoke",
                f"smoke failed (exit {smoke['returncode']})",
                f"batch branch {batch_branch} left for inspection at {worktree}",
            )
        smoke_state = "passed"

    if not body.push:
        # Keep the batch branch (drop only the throwaway worktree): the response
        # advertises it, so it must be a real ref the overseer can inspect. A later
        # `land --push` lands this exact branch (not a re-assembly); `lb teardown`
        # drops it.
        land.remove_worktree(repo, worktree)
        return {
            "run": body.run,
            "batch": batch_branch,
            "base": base,
            "pushed": False,
            "picked": result["picked"],
            "deps": resynced,
            "smoke": smoke_state,
            "next": (
                f"batch branch `{batch_branch}` is assembled and left in place — inspect it, "
                f"then re-run with --push to land it, or `lb teardown --run {body.run}` to drop it"
            ),
        }

    sha = land.head_sha(worktree, "HEAD")
    push = land.push_batch(worktree, batch_branch, base)
    land.cleanup_assembly(repo, worktree, batch_branch)
    if not push["ok"]:
        raise _fail("push", push.get("error", "push failed"), "check the remote and retry")
    return {
        "run": body.run,
        "batch": batch_branch,
        "base": base,
        "pushed": True,
        "sha": sha,
        "picked": result["picked"],
        "deps": resynced,
        "smoke": smoke_state,
    }


class TeardownBody(BaseModel):
    run: str
    force: bool = False


@router.post("/teardown")
def teardown(body: TeardownBody):
    """Kill each run member's window and reap its worktree; refuse dirty work."""
    members = run_members(body.run)
    results, refused = [], []
    for m in members:
        target = m.get("target")
        killed = False
        if target:
            session, window = parse_target(target)
            # A batch worker is one window of a shared session — kill just its
            # window. A standalone worker owns its whole session (a bare target),
            # so kill the session; otherwise it lingers in the list pointing at a
            # worktree that no longer exists.
            killed = kill_tmux_window(target) if window is not None else kill_tmux_session(session)
        reap = worktrees.reap(Path(m["path"]), force=body.force, rm_branch=True)
        if reap.get("status") != "removed":
            # Two refusals with one message is how `--force` became reflex: say which.
            refused.append({"target": target, "reason": reap.get("reason", "error")})
        results.append(
            {
                "target": target,
                "killed": killed,
                "reaped": reap.get("status"),
                # Whether this worker's work reached a remote. Torn down with
                # `landed: false` is the signal a repo needs to put the worker's
                # tracking issue back on its board — lb knows nothing about boards.
                "landed": reap.get("landed"),
            }
        )
    # Drop the batch branch a prior no-push `land` left behind (a no-op if there
    # was none, or if a member's repo has no such branch).
    for repo_path in {m.get("parent_repo") for m in members}:
        if repo_path:
            land.delete_batch(Path(repo_path), f"batch-{body.run}")
    return {"run": body.run, "results": results, "refused": refused}
