# Configure Bill — Design

**Date:** 2026-07-30
**Status:** Approved, ready for implementation plan

## Problem

Bill (the first-mate orchestrator) has no working configuration surface:

- His harness is **hardcoded** to `pi` (`BILL_PROVIDER = "pi"` in `routers/bill.py`). There is no way to run him on Claude Code or any other agent.
- His personality lives at `settings["bill"]["personality"]` (default `professional`, presets `professional` and `lumbergh` on disk), but `SettingsUpdate` has **no `bill` field**, so the PATCH endpoint silently drops any `bill` key. The default exists but is unreachable from the UI.

This spec adds a UI + backend plumbing so the user can set Bill's harness and personality (including a custom personality), stored in global settings.

## Decisions (from brainstorming)

- **Placement:** a dedicated **"Bill"** tab in the Settings modal.
- **Personality:** the two existing presets **plus** a custom free-text option.
- **Applying changes:** **note only** — changes take effect the next time Bill is summoned. No restart/auto-restart plumbing.
- **Harness list:** **all** providers from the registry, defaulting to Pi.

## Data model

Extends the existing `settings["bill"]` block in `~/.config/lumbergh/settings.json`:

```jsonc
"bill": {
  "harness": "pi",                 // provider key from PROVIDERS; default "pi"
  "personality": "professional",   // "professional" | "lumbergh" | "custom"
  "customPersonality": ""          // used only when personality == "custom"
}
```

Deep-merges like all other settings (`deep_merge`), so updating one field leaves the others intact. `bill` already flows out of the GET `/api/settings` response unchanged (only `password`, `cloudToken`, `backupPassphrase` are stripped), so no read-side change is needed.

## Backend

### `bill/__init__.py` — additive changes

The current `render(personality_key)` / `materialize(personality=key, ...)` API is used across the existing test suite. It is extended additively so every current call site keeps working:

- `available_personalities() -> list[str]` — scans `personality_*.md` stems (today: `["professional", "lumbergh"]`). Keeps the settings validator data-driven so a future preset file needs no validator edit.
- `_personality_body(personality, custom_text=None) -> str` — when `personality == "custom"`, returns `(custom_text or "").strip()`, falling back to the default preset body when the custom text is blank. Otherwise reads `personality_{key}.md` with the existing fallback to `DEFAULT_PERSONALITY`.
- `render(personality=DEFAULT_PERSONALITY, custom_text=None)` — passes `custom_text` through to `_personality_body`.
- `materialize(personality=DEFAULT_PERSONALITY, custom_text=None, home_dir=None)` — passes `custom_text` through to `render`.

Custom personality text is written literally into the `{{PERSONALITY}}` slot of `AGENTS.md`. It is user-facing voice only (like the `lumbergh` preset); unlike that preset it carries no self-guard against leaking into worker-facing text — that is the user's own text and their risk. The UI textarea placeholder reminds them of this.

### `routers/bill.py`

- `BILL_PROVIDER = "pi"` becomes the **default**, not the hardcode.
- `_harness() -> str` — returns `_settings().get("bill", {}).get("harness") or BILL_PROVIDER`. An unknown/removed value is tolerated because `get_launch_command` already falls back to the default provider.
- `_personality()` resolves to `(personality_key, custom_text)` read from `settings["bill"]`.
- `summon()`:
  - `materialize(personality_key, custom_text)` for the resolved personality.
  - `get_launch_command(harness, _settings().get("defaultAgent"))` using the configured harness.
  - the missing-binary `_fail("harness", ...)` message names the configured harness.
  - `_store_session(..., agent_provider=harness)` — **real fix**: the activity transcript adapter is selected by `agent_provider`, so a Claude-harness Bill will read his own transcript via the correct adapter instead of the Pi adapter.

### `routers/settings.py`

- New `BillSettings(BaseModel)`: `personality: str | None`, `customPersonality: str | None`, `harness: str | None` (all `None` default).
- Add `bill: BillSettings | None = None` to `SettingsUpdate`.
- Validation in `_validate_updates`:
  - if `personality` provided: must be in `bill.available_personalities()` ∪ `{"custom"}`, else 400.
  - if `harness` provided: must be in `PROVIDERS`, else 400 (mirrors the existing `defaultAgent` check).
  - if `customPersonality` provided: cap at ~4000 characters, else 400.
  - serialize with `model_dump(exclude_none=True)` so partial updates merge cleanly under the existing `deep_merge`.

## Frontend

- `SettingsModal.tsx`:
  - `TabId` gains `'bill'`; a **"Bill"** entry is added to the `tabs` array.
  - New state: `billHarness`, `billPersonality`, `billCustomPersonality`, loaded from `data.bill` in `fetchSettings`.
  - `handleSubmit` includes a `bill` object in the payload:
    `{ harness, personality, customPersonality }`.
- New `BillSettings.tsx` component:
  - **Harness** `<select>` reusing the `agentProviders` map (all providers), default Pi.
  - **Personality** control: the two presets with friendly labels + short descriptions, plus a **Custom** option. Selecting Custom reveals a `<textarea>` bound to `billCustomPersonality`; placeholder notes the voice is user-facing only and never seen by workers.
  - A muted note: *"Changes apply the next time Bill is summoned."*
  - Preset labels/descriptions are hardcoded in the component (they need human-friendly copy anyway); the backend remains the validation authority.

## Testing

Backend-behavioral, driven by the existing pytest suites (per the project's testing convention — the meaningful contract is that the setting actually changes what Bill runs and how he sounds, which lives in the backend). Red-green for each:

- `test_bill_bundle.py`: `render` / `materialize` with `custom_text` (custom text lands in `AGENTS.md`; blank custom falls back to the default preset); `available_personalities()` lists the on-disk presets.
- `test_settings*`: PATCH accepts a `bill` block (preset, custom, harness) and round-trips it; rejects an unknown personality, an unknown harness, and an over-long custom personality with 400.
- `test_bill_router.py`: `summon` uses the configured harness for the launch command and the stored `agent_provider`; `summon` renders a custom personality into `AGENTS.md`; the missing-binary failure names the configured harness.

No Gherkin/Playwright UI test — the behavior under test is backend, and the UI is a thin form over it.

## Out of scope (YAGNI)

- Restart / auto-restart of a live Bill on save.
- Per-project Bill configuration.
- Nudge / poll-interval tuning.
- Exposing preset personality text to the frontend (labels are hardcoded in the component).
