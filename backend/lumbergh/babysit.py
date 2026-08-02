"""Server-owned keep-alive loops: cycle an overseer through its refresh ritual.

Bill starts a babysit; the idle monitor drives it. When a babysat session goes idle
having printed the refresh sentinel, the loop sends the two commands the session cannot
run for itself — the ``/clear`` and the restart on the far side of a context wipe, which
destroy the very context that would remember to run them — so the session keeps moving
through its backlog without waking Bill.

The session owns *when* (it watches its own context bar and prints the sentinel); the loop
owns only what survives the clear. Genuine exceptions (blocked, error, backlog-empty) are
not handled here — they fall through to Bill's normal overseer supervision, which already
wakes him on exactly those. The one thing this module must own is the mechanical refresh,
because nothing else can do it and a small model hand-driving it is what this replaces.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from lumbergh.constants import CONFIG_DIR

BABYSITS_PATH = CONFIG_DIR / "babysits.json"

# Gap between the refresh commands. `/clear` is near-instant but the input box needs a beat
# to settle before the restart is typed, or the two race into one garbled line.
REFRESH_GAP_SECONDS = 1.2

# How many trailing transcript events to scan for the sentinel. The session prints it as the
# last line of its handoff command, so the freshest events are all that matter.
_TAIL_EVENTS = 12

DEFAULTS: dict = {
    "refresh_ready": "⟳ REFRESH-READY",
    "backlog_empty": "⟳ BACKLOG-EMPTY",
    "on_refresh": ["/clear", "/fleet-start"],
}

REFRESH = "refresh"
EMPTY = "empty"
NONE = "none"


def read_config(repo: Path | None) -> dict:
    """The babysit contract for ``repo`` — sentinels and refresh commands.

    Defaults match the ``port`` convention, so a repo that adopts it needs no config.
    ``[babysit]`` in ``.lumbergh.toml`` overrides any of the three keys.
    """
    cfg = dict(DEFAULTS)
    if repo is None:
        return cfg
    dotfile = repo / ".lumbergh.toml"
    if not dotfile.is_file():
        return cfg
    section = tomllib.loads(dotfile.read_text()).get("babysit", {})
    for key in ("refresh_ready", "backlog_empty"):
        value = section.get(key)
        if isinstance(value, str) and value:
            cfg[key] = value
    on_refresh = section.get("on_refresh")
    if isinstance(on_refresh, list) and on_refresh:
        cfg["on_refresh"] = [str(c) for c in on_refresh]
    return cfg


def _load() -> dict[str, dict]:
    try:
        data = json.loads(BABYSITS_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(registry: dict[str, dict]) -> None:
    BABYSITS_PATH.parent.mkdir(parents=True, exist_ok=True)
    BABYSITS_PATH.write_text(json.dumps(registry, indent=2))


def start(session: str, repo: str | None, added_at: str) -> dict:
    registry = _load()
    registry[session] = {"repo": repo, "added_at": added_at}
    _save(registry)
    return {"session": session, **registry[session]}


def stop(session: str) -> bool:
    registry = _load()
    existed = registry.pop(session, None) is not None
    if existed:
        _save(registry)
    return existed


def is_babysat(session: str) -> bool:
    return session in _load()


def babysat_sessions() -> set[str]:
    return set(_load().keys())


def list_all() -> list[dict]:
    return [{"session": name, **entry} for name, entry in _load().items()]


def repo_of(session: str) -> Path | None:
    entry = _load().get(session)
    if entry and entry.get("repo"):
        return Path(entry["repo"])
    return None


def decide(last_text: str, config: dict) -> str:
    """What the idle session is asking for, read from its latest transcript text.

    ``empty`` is checked before ``refresh`` so a run that both refreshed and then found
    nothing still stops rather than looping. Absent either sentinel it is a plain idle the
    loop leaves alone — Bill's supervision handles a genuinely-done or blocked overseer.
    """
    text = last_text or ""
    if config["backlog_empty"] in text:
        return EMPTY
    if config["refresh_ready"] in text:
        return REFRESH
    return NONE


def last_agent_text(session: str) -> str:
    """The tail of a session's transcript as plain text, for sentinel matching.

    Mirrors ``routers.bill._outcome_of``: a fresh adapter reads from offset 0 and returns
    full history, so this never steals events from ``lb read``. Any failure collapses to
    empty text — a babysit must never crash the idle monitor over one unreadable transcript.
    """
    from lumbergh.activity.resolve import resolve_adapter, session_meta

    try:
        meta = session_meta(session)
        cwd = Path(meta["workdir"]) if meta.get("workdir") else None
        adapter = resolve_adapter(session, cwd, meta.get("agent_provider"))
        if adapter is None:
            return ""
        events = adapter.read_new()[-_TAIL_EVENTS:]
        return "\n".join((event.text or "") for event in events)
    except Exception:
        return ""


async def on_idle(session: str) -> str:
    """Drive one babysat session that just went idle. Returns the action taken.

    Called by the idle monitor on the transition into idle. All blocking work (transcript
    read, tmux sends) goes to the executor so the monitor's poll loop is never stalled.
    """
    import asyncio

    if session not in babysat_sessions():
        return NONE

    from lumbergh import session_attention
    from lumbergh.tmux_pty import send_text

    loop = asyncio.get_event_loop()
    config = read_config(repo_of(session))
    text = await loop.run_in_executor(None, last_agent_text, session)
    action = decide(text, config)

    if action == REFRESH:
        for i, command in enumerate(config["on_refresh"]):
            if i:
                await asyncio.sleep(REFRESH_GAP_SECONDS)
            await loop.run_in_executor(None, send_text, session, command)
        # The loop just handled this idle; clear the attention overlay so the same idle
        # doesn't also nudge Bill in the window before the session goes back to working.
        session_attention.clear_unseen(session)
        await session_attention.persist()
    elif action == EMPTY:
        # Nothing left to do — release the loop and let the session's idle+unseen surface
        # to Bill through normal supervision, so he reports "backlog clear" to the user.
        stop(session)

    return action
