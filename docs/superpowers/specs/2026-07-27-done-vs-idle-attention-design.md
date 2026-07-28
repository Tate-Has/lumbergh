# `done` vs `idle` — Seen/Unseen Attention

**Date:** 2026-07-27
**Status:** Approved design
**Context:** herdr-steal bite #4 (roadmap item #3 of `~/.config/lumbergh/shared/herdr-steal-list.md`)

## Goal & Boundary

Distinguish a session that finished or stopped **while the user wasn't looking** from one
that is merely idle, and surface a "N while you were away" count on the dashboard. This is
the foundation a future mobile-push bite sits on, and is independently useful in the open
tab.

In scope:

- Track an **unseen** overlay per session: set when the monitor observes a transition into
  `IDLE` / `BLOCKED` / `ERROR` while the session has no active viewers; cleared when a
  viewer opens the session or when it leaves the attention state (e.g. back to `WORKING`).
- "Seen" reuses the existing `active_clients` viewer presence (terminal socket / detail
  view open). Dashboard listing and CLI/REST reads never clear it.
- Expose `unseen` + `attentionState` in the existing session-list response; dashboard shows
  a count badge, per-card "while you were away" treatment, and sorts unseen up.

Out of scope (next bite):

- Web Push delivery: VAPID keys, subscription storage, push-send endpoint, service-worker
  push handler, notification-permission UX.

## Model Decisions

- **Attention set = `IDLE`, `BLOCKED`, `ERROR`.** A transition into any of these while
  unviewed marks the session unseen. `STALLED` and `WORKING` are active states and clear
  unseen (nothing finished to attend to).
- **Seen = viewer presence.** A session is seen iff it currently has ≥1 `active_clients`
  entry (the terminal websocket opened by its detail view). Opening a flagged session
  clears it; being listed on the dashboard does not; CLI/REST `GET` calls never clear it.
- **Count lives in the existing session-list response** the dashboard already polls — no
  new polling loop; the count is derived client-side from the per-session `unseen` flags.
- **BLOCKED relabels by seen/unseen:** unseen → "Blocked — while you were away"; seen (you
  are looking at it) → today's "Blocked — waiting on you". Same underlying `blocked` state.

## Components

- **`backend/lumbergh/session_attention.py`** (new) — runtime source of truth. All
  mutations happen on the asyncio event loop with no `await` between read-modify-write, so
  the in-memory maps need no locking. Best-effort persistence for restart durability.
  - `set_viewing(name: str, viewing: bool) -> None` — `True`: add to viewers **and** clear
    unseen (mark seen); `False`: drop from viewers.
  - `mark_attention(name: str, state: str) -> None` — if `name` has no viewers, record
    `unseen=True` + `attentionState=state`; else no-op.
  - `clear_unseen(name: str) -> None` — used when a session leaves the attention set.
  - `snapshot() -> dict[str, dict]` — `{name: {"unseen": bool, "attentionState": str|None}}`.
  - `unseen_count() -> int`.
  - `load() -> None` / persistence hooks against a small `attention` table.
- **`backend/lumbergh/idle_monitor.py`** — on each recorded state change (it already
  computes `old→new`), call `session_attention.mark_attention(name, new.value)` when
  `new ∈ {IDLE, BLOCKED, ERROR}`, else `session_attention.clear_unseen(name)`.
- **`backend/lumbergh/session_manager.py`** — `register_client` →
  `set_viewing(name, True)`; `unregister_client`, when the last client for the session is
  gone → `set_viewing(name, False)`.
- **`backend/lumbergh/routers/sessions.py`** — the session-list and per-session responses
  gain `unseen: bool` and `attentionState: str | None`, read from
  `session_attention.snapshot()`.
- **Frontend** — `sessionStatus.ts`: `SessionBase` gains `unseen?: boolean` and
  `attentionState?: ...`; `getSessionStatus` overlays "while you were away" labels;
  `sessionUrgencyRank` boosts unseen sessions. Dashboard renders a count badge (derived
  from the polled list) and a per-card chip.

## Data Flow

```
monitor records state change old→new (idle_monitor)
    new ∈ {IDLE,BLOCKED,ERROR}: session_attention.mark_attention(name, new.value)
        no viewers? -> unseen[name] = (True, new)   |   viewers? -> no-op (seen)
    otherwise:                 session_attention.clear_unseen(name)

user opens session detail -> terminal WS connects -> session_manager.register_client
    -> set_viewing(name, True) -> viewers.add(name); unseen.pop(name)   # seen

last viewer leaves -> unregister_client -> set_viewing(name, False) -> viewers.discard(name)

dashboard polls session list -> each session carries unseen + attentionState
    -> count badge = # unseen; per-card "while away" chip; unseen sort up
```

CLI/REST `GET` state endpoints touch none of this — only a real terminal-socket viewer
flips "seen".

## Persistence & Restart

`unseen` + `attentionState` persist to an `attention` table in each session's
`session_data` DB (best-effort, same pattern and lock as `idle_state`), loaded on startup.
`viewers` is ephemeral — rebuilt from live socket connections, never persisted. A backend
restart with a session mid-unseen keeps the flag; viewers repopulate as clients reconnect.

## Error Handling

- `session_attention` never raises into the monitor or socket paths; persistence failures
  are logged and swallowed (the in-memory truth still serves the session).
- A viewer connecting always wins (clears unseen) even against a racing transition — both
  are loop-serialized, and "seen" is the safe direction (under-notify rather than nag).

## Testing

- **`session_attention`**: transition with no viewers → unseen; with viewers → not;
  `set_viewing(True)` clears an existing unseen; leaving the attention state clears;
  `unseen_count`/`snapshot` reflect state; persist → load round-trip.
- **`idle_monitor`**: a WORKING→IDLE change with no viewers marks unseen; →WORKING clears;
  a transition while a viewer is present does not flag (monkeypatched `session_attention`).
- **`session_manager`**: `register_client` calls `set_viewing(name, True)`; the last
  `unregister_client` calls `set_viewing(name, False)`.
- **API**: the session-list response includes `unseen`/`attentionState` per session.
- **Frontend**: `sessionStatus` unseen labels ("Done/Blocked/Failed — while you were
  away") and urgency-rank ordering — mirrors the existing `sessionStatus.test.ts` style.
- `./lint.sh` clean.

## Licensing

Pattern (seen/unseen "done" distinction) adapted in spirit from herdr; no code copied. A
one-line comment in `session_attention.py` referencing the steal-list suffices.

## Follow-up Bites (not this spec)

1. **Web Push** for the unseen-attention events ("3 agents finished while you were away"):
   VAPID keypair + storage, subscription endpoint, service-worker push handler, permission
   UX, iOS-PWA caveats. This bite's `unseen` transitions are the events it will fire on.
