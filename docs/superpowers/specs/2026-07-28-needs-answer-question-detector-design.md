# Cheap-LLM "needs-answer" question detector

**Date:** 2026-07-28
**Status:** Approved design (built autonomously; open items flagged for review)
**Context:** herdr-steal follow-on — the "cheap-LLM question detector" idea captured at the
end of the v0.20.0 arc in `~/.config/lumbergh/shared/herdr-steal-list.md`. Priority item #1
of the post-release next-steps list.

## Goal & Boundary

Structural manifest detection (`SessionState.BLOCKED`) recognizes an agent parked on an
**approval or structured-question UI** — a shape to match. It structurally cannot recognize
a **free-text** question: Pi asking "Which database should I use?" renders no UI shape, the
pane is simply quiescent, and quiescence classifies it as `IDLE`. Screen-scraping patterns
will never catch this; the only tractable path is to *read* the screen with a model.

So: when a session sits sustained-`IDLE`, ask a cheap local LLM once, "has this agent
stopped and is it waiting for the human to answer something?" A positive verdict sets a
soft, advisory **`needs_answer`** flag surfaced on the dashboard.

In scope:

- A pure, testable classifier module (prompt build + verdict parse) plus a thin async
  `detect()` wrapper with a short timeout that fails safe (no verdict → not waiting).
- `idle_monitor` fires detection **once per idle episode**, after a short sustained-idle
  delay, as a fire-and-forget background task (never inline on the poll — the monitor loop
  is the event-loop-lag-sensitive path).
- Surface `needsAnswer` + `needsAnswerReason` in the session-list response; dashboard shows
  a distinct "Question — waiting on you" treatment and sorts it up.
- Opt-in setting `questionDetectionEnabled` (default **off**).

Out of scope (future bites):

- Reusing the verdict to upgrade the **attention/notification** state (a free-text question
  while-away is push-worthy). This bite only sets the live flag; attention stays as-is.
- Feeding the richer JSONL **transcript** (via the activity adapters) instead of the pane
  tail. Pane tail is what quiescence already sees and is sufficient for a yes/no.
- Positive WORKING/IDLE manifests — unrelated, already parked.

## Model decisions (review these)

- **Soft flag, not a `SessionState`.** BLOCKED is high-confidence and structural; the
  classifier (`classify_overrides`) stays pure and sync. An LLM inference is lower
  confidence and must not masquerade as BLOCKED, so `needs_answer` is a separate advisory
  overlay owned by the monitor, cleared automatically when the session leaves `IDLE`.
- **Opt-in, default off.** The detector runs a background LLM call. Even though it fires at
  most once per idle episode on a small prompt, silently generating provider traffic (or
  paid-API spend) is a surprise. Default `questionDetectionEnabled = false`; the user flips
  one toggle. *Open question for review: whether to auto-enable when the effective provider
  is local (Ollama/localhost).*
- **Reuse the main AI provider.** No second provider-config surface — `get_provider(ai)`,
  same as `session_summary`. The default provider is local Ollama (`gemma3:latest`), which
  is exactly the cheap-local-model the idea called for. Model quality only needs to answer a
  binary question about visible text.
- **Once per idle episode.** Detection is scheduled only on the first sustained-idle poll
  and is not repeated until the session leaves and re-enters `IDLE`. This bounds cost and
  avoids flapping. `BLOCKED`/`ERROR`/`WORKING`/`STALLED` never trigger it (BLOCKED already
  answers the "waiting on human" question structurally).
- **Fail safe = not waiting.** Timeout, provider error, or an unparseable verdict all yield
  "not waiting" — a supervision dashboard must not cry wolf.

## Components

- **`backend/lumbergh/question_detector.py`** (new)
  - `build_prompt(pane_text) -> str` — ANSI-stripped, trailing-blank-trimmed last
    `TAIL_LINES` of the pane, wrapped in a tight yes/no instruction.
  - `parse_verdict(raw) -> Verdict` — `Verdict(waiting: bool, reason: str)`. Model is asked
    for `YES: <short reason>` or `NO`; parsing is conservative (default `NO`, first decisive
    token wins, tolerant of markdown/rambling).
  - `async detect(pane_text, provider, timeout=DEFAULT_TIMEOUT) -> Verdict` — builds the
    prompt, `asyncio.wait_for(provider.complete(...))`, parses; any exception → `NO`.
- **`backend/lumbergh/idle_monitor.py`**
  - New per-session maps: `_needs_answer: dict[str,str]` (name → reason),
    `_question_checked: set[str]` (this idle episode already scheduled),
    `_question_inflight: set[str]`. All mutated on the loop; no locks.
  - Constant `QUESTION_CHECK_DELAY_SECONDS` — how long a session must remain continuously
    `IDLE` (via `state_since_seconds`) before we bother the model.
  - In `_check_session`: when `state == IDLE`, not yet checked/inflight, sustained past the
    delay, and enabled → `create_task(self._run_question_detection(name))`. When
    `state != IDLE` → drop the session from all three maps (question is stale).
  - `_run_question_detection(name)` — mark checked+inflight; read settings, gate on
    `questionDetectionEnabled` and a configured AI provider; capture plain pane text
    (`capture_pane_text`, offloaded); re-verify still `IDLE`; `detect()`; if `waiting` and
    still `IDLE`, set `_needs_answer[name]`. Always clear inflight.
  - `needs_answer_reason(name) -> str | None`. Dead-session cleanup pops all three maps.
- **`backend/lumbergh/routers/sessions.py`** — `get_session_status` adds `needsAnswer`
  (bool) + `needsAnswerReason` from `idle_monitor`; both session-list dict builders forward
  them.
- **`backend/lumbergh/routers/settings.py`** — flat `questionDetectionEnabled: bool`
  (default `False`) in defaults, `SettingsUpdate`, and `_OPTIONAL_FIELDS`.
- **Frontend** — `sessionStatus.ts` gains `needsAnswer?: boolean`; a live idle session with
  `needsAnswer` renders purple-pulse "Question — waiting on you" (unseen → "Question — while
  you were away"), and ranks just below structural `blocked` in `sessionUrgencyRank`.
  `GeneralSettings` gets a toggle mirroring `showSessionDots`.

## Test plan

- `question_detector`: `parse_verdict` table (YES/NO/markdown/ambiguous/empty → conservative
  NO), `build_prompt` (ANSI stripped, tail bounded), `detect` fail-safe on a raising/slow
  provider stub.
- `idle_monitor`: fires once after the delay and not before; not fired for
  WORKING/BLOCKED; flag cleared on leaving IDLE; `needs_answer_reason` set from a stubbed
  detector; not re-fired within the same episode; dead-session cleanup.
- `sessions`/`settings`: `needsAnswer` present in the list payload; setting round-trips and
  defaults off.
- Frontend `sessionStatus.test.ts`: label + urgency for needs-answer, seen and unseen.

## Live verification (2026-07-28)

Ran `detect()` against the two local Ollama models on hand (`gemma3:latest` — the
settings default — and `llama3.2:latest`) over a 7-case realistic set: free-text
questions, plan/clarify requests, a still-working frame, and finished-and-idle Claude
panes (box + `? for shortcuts` footer).

**Key finding — strip terminal chrome or the feature is unusable.** With the raw pane,
*both* models read the live `? for shortcuts` footer and the empty `│ > │` input box as
a question and false-positived on finished-idle panes — i.e. on nearly every done Claude
session. Filtering UI chrome in `_clean_tail` (footer markers reused from
`detect.engine._FOOTER_MARKERS`, plus box-drawing-only / lone-`>` lines) fixed it: both
models then scored **7/7**, correctly separating "asked the human something" from "done
and idle". This is why the chrome filter is load-bearing, not cosmetic.

Model sensitivity is real (before the fix, gemma3 was materially more trigger-happy than
llama3.2), which reinforces the opt-in default. If false positives reappear on a user's
model, the cheapest next lever is a stricter prompt or a 2-of-3 vote before setting the
flag — deferred until observed.
