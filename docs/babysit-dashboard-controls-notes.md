# Babysit + Bill dashboard controls — design notes

Working notes for a **future session** picking up the dashboard babysit work. Captures
what's already shipped, the pending feature, the endpoints it can build on, and the open
design questions — so the next session can start brainstorming without re-discovering it.
Not an approved spec: run the brainstorming skill before building.

_Written 2026-08-02._

> **UPDATE (2026-08-02, shipped `6e87305`):** the babysit on/off control shipped as a
> **per-card `Baby` toggle** in each live session card's footer — NOT the per-overseer
> badge / central panel this doc leans toward below. A first cut as a central "BABYSITTING"
> checklist panel was rejected by the user ("don't like the checkbox at the top… it should
> just be on the card itself"). Eligibility + component: `frontend/src/utils/babysit.ts`
> (`canBabysit`) and `frontend/src/components/BabysitToggle.tsx`. Still open: the
> **inactive-but-babysat** case (§ below, Q3-adjacent) — currently just keeps a colored
> toggle on the offline card; and the panel's refresh / stop-all verbs were dropped.
> The "where does it live" section below is superseded; the endpoint notes still hold.

## Background — the two fixes that led here

Both shipped to local `main` (unpushed at time of writing):

1. **`dd82fe2` — advance a stalled babysat overseer + `lb babysit --refresh`.**
   Overnight, `port`'s fleet batch delivered and the overseer went plain idle with no
   sentinel; `babysit.decide()` returns `NONE` for that and defers to Bill, but Bill only
   ever got the generic 15-min heartbeat and kept reporting "nothing to do." Fix: a new
   pointed level trigger `idle_monitor._maybe_advance_babysat` (below the edge nudge, above
   the heartbeat) taps Bill with an imperative naming the stuck session; plus
   `lb babysit --refresh --session X` (`POST /api/bill/babysit/refresh` →
   `babysit.refresh()`) so Bill has a one-button `/clear`+`/fleet-start`.

2. **`d400fb0` — retire Bill from the dashboard (unsummon).**
   `BillHeroCard` gained a power-icon stop control wired to the existing
   `DELETE /api/sessions/bill` (kills his session, removes his record, keeps his config dir
   so `preferences.md` survives). The confirm is **babysit-aware**: it fetches
   `GET /api/bill/babysit` and, if Bill has active babysits, names them and warns they'll run
   **unmonitored until re-summon** (babysits are server-owned and intentionally survive his
   absence). Logic is the pure util `frontend/src/utils/billStop.ts` (`buildBillStopMessage`,
   unit-tested). e2e scenario: "I can retire Bill from the dashboard and bring him back."

### Decision already made (don't relitigate)
Unsummoning Bill **keeps his babysit loops running** — they're server-owned and survive a
Bill restart by design; a re-summoned Bill picks them back up. "Stop babysitting" is NOT
part of unsummon; it belongs in the dedicated control below. (The alternative "stop them
too" and "ask me each time" were both considered and rejected.)

## The pending feature — a dashboard babysit on/off control

The user wants to **see and toggle babysits from the dashboard**, not just via the CLI.
This is the real home for "stop babysitting anything" and for starting a babysit on an
overseer without dropping to a terminal. Their words: _"a little button on the main page
where we can just turn on and off babysitting."_

Today babysits are only manageable via `lb babysit --session|--stop|--list|--refresh` (CLI)
or implicitly by Bill. Nothing in the UI shows which sessions are being babysat.

## What it can build on (likely NO new backend needed)

Existing endpoints under `/api/bill/` (router `backend/lumbergh/routers/bill.py`):
- `GET  /api/bill/babysit` → `{ babysits: [{ session, repo, added_at }] }` (list)
- `POST /api/bill/babysit` `{ session, repo? }` → start (repo auto-resolved from the
  session's workdir when omitted, so `{session}` alone works)
- `DELETE /api/bill/babysit?session=<name>` → stop → `{ session, stopped: bool }`
- `POST /api/bill/babysit/refresh` `{ session }` → run the refresh ritual now (400 if the
  session isn't babysat)

Registry module: `backend/lumbergh/babysit.py` (`babysat_sessions()`, `list_all()`,
`is_babysat()`, `read_config()`). Server-driven refresh lives in
`idle_monitor._maybe_drive_babysit` (sentinel path) + `_maybe_advance_babysat` (Bill tap).

Frontend reference: `frontend/src/utils/billStop.ts` already fetches the babysit list;
`frontend/src/components/BillHeroCard.tsx` shows the fetch+confirm pattern. Session/overseer
cards: `SessionCard.tsx`, `OverseerCard.tsx`, `WorkerRow.tsx`; the grid + handlers live in
`Dashboard.tsx` (`handleDelete`, `handleSummonBill`, `groupSessions`).

## Open design questions (for brainstorming)

1. **Where does the control live?** Candidates:
   - A **per-overseer toggle** on each overseer's card (babysit is per-session, and "keep
     this moving" reads naturally as a property of the overseer). Plus a babysat badge so
     you can see at a glance which sessions are looping. Leaning here.
   - A **dedicated babysit panel/section** on the dashboard listing all active babysits with
     stop buttons + a "stop all."
   - On **Bill's hero** (a rollup + manage affordance).
   Probably: badge + per-overseer toggle, with a "stop all" somewhere central.
2. **Starting a babysit from the UI** should be offered only for **overseer-role** sessions
   (babysit targets overseers, never workers). `POST /api/bill/babysit {session}` is enough.
3. **Show babysat state** on sessions. Note: "mark babysat rows in `lb fleet`" was a
   deferred follow-up from the original babysit work — this UI could subsume the visibility
   need (and it'd be worth adding the flag to `lb fleet`/the sessions API too so both
   surfaces agree).
4. **Confirm on stop?** Probably light or none — stopping a babysit is low-risk and
   resumable, unlike retiring Bill.
5. **Refresh button too?** A per-overseer "refresh now" (the `POST /babysit/refresh` verb)
   could sit alongside the toggle for a babysat session.

## Verify-in-app note
Frontend runs on Vite dev (`:5420`, HMR); backend on `:8420` runs uvicorn `--reload`, so
both pick up changes live. `lb` runs from the repo venv. A running Bill keeps his old
`AGENTS.md` until re-summoned (his bundle is re-materialized on summon).
