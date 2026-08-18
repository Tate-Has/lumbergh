# Panel focus — any pane can fill the viewport

## Problem

Zen mode gives the terminal the whole desktop viewport, and it works. But it
hardcodes *which* pane gets the screen: `useZenMode` is a boolean, and the only
thing it can maximize is the main pane.

The Files tab is the case that exposes the limit. `FileBrowser.tsx` is already
explorer-left / preview-right with a collapsible tree — structurally the right
shape — but it is squeezed into the right panel, and a fixed 256px sidebar eats
a quarter of that. There is no way to give it the screen.

Git will want the same thing shortly. Building a second full-screen path for
each tab is how a codebase accumulates three ways to do one thing, so the
mechanism gets generalized once, and Files is its first customer.

## Behavior

- Focus has three states: nothing focused, the main pane focused, or the right
  panel focused.
- `Alt+Z` is unchanged in meaning: it always targets the **main** pane, toggling
  between focused and not. It can never land you in panel focus by surprise, and
  from panel focus it moves straight to main focus.
- The right-panel tab bar gains a maximize/restore button. That button is the
  only way into panel focus, and clicking it again leaves.
- The tab bar stays visible while the panel is focused, so you can move between
  Files, Git, Todos and the rest without dropping out of full screen — the same
  way zen keeps the slim terminal header.
- The choice is sticky per browser and survives reloads.
- Desktop only. Mobile is already one pane at a time and is untouched.

### The one asymmetry, and why

When the **right** panel is collapsed it is not rendered, exactly as today.

When the **left** pane is collapsed it stays mounted, hidden with `display:
none`.

The left pane holds the terminal: a live PTY, a WebSocket, and client-side
scrollback that cost real time and real bytes to rebuild. Unmounting it
reconnects the session and throws that away — the regression that had to be
fixed twice during zen mode and guarded again during Term/Conv. Right-panel
state is re-fetchable by comparison, so leaving that side unrendered is the
cheaper default and preserves current behavior.

## Migration

Anyone currently in zen has `lumbergh:zenMode === 'true'` in localStorage. On
first read, that migrates to `focus: 'main'` under the new key. The old key is
not written again and is left in place rather than deleted — removing it buys
nothing and a stale key is harmless.

## Architecture

### `hooks/useFocusMode.ts` (replaces `hooks/useZenMode.ts`)

Owns the focus state, its persistence, and the `Alt+Z` listener. Same shape as
the hook it replaces, which is itself modeled on `useSessionSwitchKeys`.

- `type FocusTarget = 'none' | 'main' | 'panel'`
- Persisted to `localStorage` under `lumbergh:focusMode`. An unrecognized value
  reads as `'none'`. If the key is absent, `lumbergh:zenMode === 'true'` reads as
  `'main'`.
- A `window` keydown listener matching `Alt+Z` — `e.altKey && !e.ctrlKey &&
  !e.metaKey && e.code === 'KeyZ'`, then `preventDefault()`. It sets `'main'`
  when the current value is anything other than `'main'`, and `'none'` when it is
  already `'main'`.
- Returns `{ focus, setFocus, toggleMain, togglePanel }`.
- Gated on `useIsDesktop()` the same way zen is: the stored preference survives a
  narrow viewport, but the returned value reads `'none'` below the breakpoint so
  a phone can never render a focused layout.

`e.code` rather than `e.key`, for the reason already recorded in the hook being
replaced: on macOS, Option+Z reports `e.key === 'Ω'`.

### `components/ResizablePanes.tsx`

The `collapsed?: boolean` prop becomes `collapse?: 'left' | 'right' | null`,
defaulting to `null`. The single existing call site in `SessionDetail` is
updated.

- `'right'` renders the left pane at 100% and omits the splitter and the right
  pane. This is byte-for-byte today's `collapsed` behavior.
- `'left'` renders the right pane at 100% and omits the splitter, while keeping
  the left pane mounted with `display: none` and zero width.
- `null` is the normal split, unchanged, including the persisted width and all
  drag behavior.

The stored `leftWidth` must survive a collapse round-trip in both directions
untouched.

### `components/ZenTerminal.tsx`

Already takes an `active` prop and always renders the same wrapper div, so it
needs only its prop wired to `focus === 'main'` instead of `isZen`. Its ghost
exit button and fade behavior are unchanged.

### `components/FileBrowser.tsx`

The fixed `w-64 flex-shrink-0` sidebar becomes a nested `ResizablePanes`:

- `left` is the tree, `right` is the existing content viewer.
- `storageKey="lumbergh:filesTreeWidth"`, `defaultLeftWidth={25}`,
  `minLeftWidth={10}`, `maxLeftWidth={50}`.
- The existing `sidebarCollapsed` state drives `collapse={sidebarCollapsed ?
  'left' : null}` rather than conditionally rendering the sidebar, so the
  collapse button keeps working through the same mechanism as everything else.

Nothing else in `FileBrowser` changes. The tree, the content viewer, markdown and
CSV preview, syntax highlighting, mermaid, and image rendering are all left
alone.

### `pages/SessionDetail.tsx`

Consumes `useFocusMode` in place of `useZenMode`, passes
`collapse={focus === 'main' || isTerminalOnly ? 'right' : focus === 'panel' ?
'left' : null}` to `ResizablePanes`, and renders the maximize/restore button in
the right-panel tab bar.

`ScratchPromoteBanner` continues to be hidden when the main pane is focused, and
is also hidden when the panel is focused — a focused pane means a focused pane.

### Terminal-only and panel focus cannot both win

The existing "Terminal Only" setting already collapses the right panel, and it is
expressed through the same prop. If it is on, there is no tab bar, so there is no
maximize button and panel focus is unreachable through the UI — but a stored
`focus: 'panel'` from before the setting was turned on would still be in
localStorage, producing a contradiction.

Terminal-only wins, because it is the more explicit and more durable choice: it
is a saved per-session setting, while focus is a transient view preference. The
collapse expression is therefore evaluated with `isTerminalOnly` taking
precedence, and a stored `'panel'` focus simply has no effect until the setting
is turned back off. Focus is not rewritten to `'none'` — turning Terminal Only
off should restore what you had.

## The thing most likely to break

`FileBrowser` renders its "send selection to terminal" button with `position:
fixed` and hand-computed coordinates (`buttonPos`). Panel focus changes the
layout underneath it, and a fixed-position element positioned from measured
offsets is exactly the kind of thing that looks correct in a screenshot and sits
200px wrong in use.

It must be verified by selecting text in a maximized Files panel and confirming
the button appears next to the selection, not merely that it appears.

## Testing

**Gherkin UI test** — the user story, plus the regression that matters:

```gherkin
Scenario: Maximizing the panel gives Files the whole viewport
  Given a test session exists
  And I am on the session page for "e2e-ui-session"
  When I click the "files" tab
  And I click the panel maximize button
  Then I should see the file preview
  And the terminal container is present but not visible

Scenario: The terminal survives a trip through panel focus
  Given a test session exists
  And I record terminal websocket connections
  And I am on the session page for "e2e-ui-session"
  When I click the panel maximize button
  And I click the panel maximize button
  Then exactly one terminal websocket was opened
```

The second scenario reuses the `/stream` socket-count step built for Term/Conv.
Hiding the terminal behind a collapsed pane is the same hazard in new clothes,
and a visibility assertion alone would pass through a remount.

**Unit tests** — the focus state machine as a pure function, colocated in
`frontend/src/utils/` beside `conversationFollow.ts` and the rest:

- `Alt+Z` from `'none'` gives `'main'`; from `'main'` gives `'none'`; from
  `'panel'` gives `'main'`.
- The panel toggle from `'none'` gives `'panel'`; from `'panel'` gives `'none'`;
  from `'main'` gives `'panel'`.
- A stored `lumbergh:zenMode` of `'true'` with no `lumbergh:focusMode` reads as
  `'main'`.
- An unrecognized stored value reads as `'none'`.

## Out of scope

Deferred to the Files enrichment spec that follows this one:

- Fuzzy find over the file tree.
- Surfacing which files the session actually modified. The data already exists —
  `diff_cache.py` computes it and `SessionDetail` already holds `diffData` — so
  this is wiring, not new machinery, but it is not this spec's job.
- Preview upgrades: line numbers, jump-to-line, wrap toggle, diff-against-git.

Also out of scope: any backend change, the Git tab's own redesign, and mobile,
which keeps its tab bar.
