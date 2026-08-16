# Zen Mode — full-bleed terminal on desktop

## Problem

On a desktop session page the terminal shares the viewport with a resizable right
panel (git diff, files, todos, prompts, shared files). When you just want to watch
or drive the session, that panel is noise.

A partial answer already exists: the **Terminal Only** checkbox in the tab-settings
gear. It has two flaws that keep it from being the answer:

1. It is destructive. Turning it on calls `saveSessionTabVisibility(allOff)`, which
   overwrites the session's saved tab-visibility record. Turning it off guesses at a
   restore by copying `globalTabVisibility` — your per-session panel choices are gone.
2. It is per-session and mouse-only: open the gear, find the checkbox, click it, for
   every session.

Zen mode is a non-destructive view overlay, global to the browser, on one keystroke.

## Behavior

- **Alt+Z** toggles zen mode, in both directions, from anywhere on a desktop session
  page — including while the terminal holds focus.
- In zen, the terminal fills the viewport. The right panel, the `ScratchPromoteBanner`,
  and the "Tabs" button are not rendered.
- The slim `TerminalHeader` strip stays: back, session dots, connection indicator,
  font size. Its expandable second row of send-key buttons is collapsed.
- A ghost **Exit zen** button sits top-right, transparent until the mouse moves over
  the container, fading back out after ~2s of stillness.
- Saved tab visibility is never written. Leaving zen restores the previous split
  exactly, including the `ResizablePanes` width.
- Zen is remembered globally per browser: reload, or open another session, and zen is
  still on until you turn it off.
- Desktop only. Mobile keeps its tab bar and ignores the setting entirely.

Esc is deliberately not an exit key. The terminal needs it — Esc is load-bearing in
Claude Code and vim — so the same chord toggles both ways instead.

## Approach

State lives in the frontend as view state, persisted to `localStorage` under
`lumbergh:zenMode`. This matches how `ResizablePanes` and `VerticalResizablePanes`
already persist layout via their `storageKey` props: instant toggle, no backend
round-trip, and no schema change.

Two alternatives were considered and rejected:

- **A server-side global setting** alongside `showSessionDots`. It would sync across
  devices, but adds a backend field plus a PATCH on every toggle, and pushes a
  desktop-only view preference to mobile clients that ignore it.
- **A preset over the existing tab-visibility machinery.** No new state, but it
  inherits exactly the destructive-restore flaw this feature exists to avoid.

## Components

### `hooks/useZenMode.ts` (new)

Owns the boolean and the keybinding. Modeled on `useSessionSwitchKeys`.

- Initial value read from `localStorage['lumbergh:zenMode']`; writes on change.
- Registers a `window` `keydown` listener, active only when `useIsDesktop()` is true.
- Matches `e.altKey && !e.ctrlKey && !e.metaKey && e.key === 'z'`, calls
  `preventDefault()`, and flips the boolean.
- Returns `{ isZen, toggleZen, exitZen }`.

Public surface is those three values. Nothing outside the hook touches
`localStorage` or the keybinding.

### `components/Terminal.tsx`

`isSessionCycleChord` is the existing list of chords xterm must decline so they reach
the window listeners rather than tmux. Alt+Z joins it:

```ts
if (event.altKey && event.key === 'z') return true
```

Without this, xterm consumes the chord and forwards `\x1bz` to tmux.

The component already carries an unused `hideHeader` prop. Zen does not use it — the
header stays — but `headerExpanded` is forced to `false` while zen is on, so the
send-keys row is collapsed. On leaving zen, the previous expanded state is not
restored; the row starts collapsed, matching a fresh page load.

### `pages/SessionDetail.tsx`

The desktop branch gains a third case beside `isTerminalOnly` and the split view:

```tsx
{isZen ? (
  <ZenTerminal onExit={exitZen}>{renderTerminal()}</ZenTerminal>
) : isTerminalOnly ? (
  ...existing...
) : (
  <ResizablePanes ... />
)}
```

`ScratchPromoteBanner` renders only when `!isZen`. Nothing else in the page's state
changes — `sessionTabVisibility` and `globalTabVisibility` are untouched.

### `components/ZenTerminal.tsx` (new)

A thin wrapper around the terminal that owns the fade affordance and nothing else:
full-height container, an `onMouseMove` handler that shows the exit button and arms a
~2s timer to hide it, and the button itself calling `onExit`. It does not know what
zen means or how it is stored.

## Terminal resizing

Entering and leaving zen changes the terminal's pixel box. If the fit is not
re-triggered, xterm keeps its old cols/rows and tmux renders at the wrong size —
the same class of bug the existing `handleManualFit` path addresses.

The existing resize path in `Terminal.tsx` observes its container. Verify in the
running app that the observer fires on both transitions; if it does not, drive
`handleManualFit` explicitly from the zen transition. Confirm by toggling zen with
a full-screen TUI (`htop`, or Claude Code itself) running in the session and checking
the redraw fills the new box.

## Testing

Feature-first, per the project's red-green convention.

**Gherkin UI test** (`test/e2e-ui/`) — the user story:

```gherkin
Scenario: Alt+Z gives the terminal the whole viewport
  Given a desktop session page with the git panel visible
  When I press Alt+Z
  Then the git panel is not visible
  And the terminal is visible

Scenario: Alt+Z restores the panel without losing my layout
  Given I am in zen mode on a session whose visible tabs are git and files
  When I press Alt+Z
  Then the git panel is visible
  And the session's visible tabs are still git and files
```

The second scenario is the regression guard for the destructive-restore flaw.

**Unit test** — `isSessionCycleChord` returns true for Alt+Z, so the chord never
reaches tmux.

No test for the fade timing; it is UX polish.

## Out of scope

- Mobile. The tab bar is the mobile navigation model and stays.
- The browser Fullscreen API. Zen fills the viewport, not the screen.
- Auto-hiding the header strip on mouse idle. Considered and declined — the strip
  stays put.
- Rendering the dormant `QuickInput` component. It is unused today and stays unused.
- Changing or removing the existing **Terminal Only** checkbox.
