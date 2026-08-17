# Term / Conv — the session as two views

## Problem

The Activity feed renders what a Claude session did — messages, thinking, tool
calls, diffs — and lets you reply through `ActivityRespondBox`. It is a peer of
the terminal: the same session, rendered legibly instead of raw.

It is currently filed as a side panel. On desktop it is one of six right-panel
tabs, competing for space with the git diff; on mobile it is one of seven bottom
tabs. That framing is wrong. You do not want the conversation *beside* the
terminal, you want it *instead of* the terminal, at full size.

Two consequences follow. The view needs a home opposite the terminal rather than
next to it, and — because it becomes a primary full-height view — it needs to
render long sessions without stuttering, which it currently does not.

## Naming

The two views are **Term** and **Conv**, abbreviated everywhere they appear:
buttons, tooltips, mobile labels, settings. The full words are too long for a
mobile tab, and the pairing makes both unambiguous.

"Conversation" over "Activity" follows where the category has landed. Warp ships
this exact pair as terminal mode and agent conversation view; Pi calls its
equivalent a conversation viewer. "Activity" describes a feed you watch, which
undersells a view you can talk back through.

## Behavior

- A single icon button in the session header shows the **destination** view: in
  Term it shows a conversation icon, in Conv it shows a terminal icon. Clicking
  it swaps. `Alt+V` does the same from the keyboard.
- No segmented control. Which view you are in is obvious from looking at it.
- The choice is sticky and global — stored per browser, applied to every session,
  surviving reloads.
- Zoom is literal text scaling, and the header's zoom control targets whichever
  view is active: in Term it drives the terminal's existing font size, in Conv it
  scales the feed. Each view remembers its own size.
- Zen mode needs no changes. It collapses the right panel; whichever view is
  active fills the viewport. The slim header stays, so the toggle and zoom remain
  reachable in zen.
- Swapping views never disconnects the session. The terminal keeps its scrollback
  and its WebSocket while Conv is showing, and vice versa.

## What goes away

`'activity'` leaves the desktop right-panel tabs, the mobile bottom tabs, and the
tab-visibility gear menu. Mobile's terminal tab carries the same Term/Conv toggle,
so there is one mental model on both form factors.

A saved `rightPanel` of `'activity'` migrates to `'git'` on load, so nobody lands
on a tab that no longer exists.

The backend's `tabVisibility.activity` field stays. It becomes inert. Removing it
would require a data migration for no user-visible benefit.

## Architecture

### `hooks/useSessionView.ts` (new)

Owns the `'term' | 'conv'` state, its persistence, and its keybinding. Modeled on
`useZenMode`, which is modeled on `useSessionSwitchKeys`.

- Value persisted to `localStorage` under `lumbergh:sessionView`; anything
  unrecognized reads as `'term'`.
- A `window` keydown listener matching `Alt+V` — `e.altKey && !e.ctrlKey &&
  !e.metaKey && e.code === 'KeyV'`, then `preventDefault()`.
- Returns `{ view, setView, toggleView }`.

`e.code` rather than `e.key`, for the reason recorded in `useZenMode`: on macOS,
Option+V reports `e.key === '√'`.

### `utils/terminalChords.ts`

`Alt+V` joins `isSessionCycleChord`, so xterm declines the chord and it reaches
the window listener instead of arriving at tmux as `\x1bv`. Without this the
toggle is dead whenever the terminal has focus — which is most of the time.

### The header becomes the session header

`TerminalHeader` renders in both views rather than only above the terminal, and
gains the Term/Conv toggle button. Its existing controls keep working across both
views: Esc, Mode, `1`, and `/clear` send keys to the tmux session, which is
meaningful regardless of which rendering you are looking at.

Its zoom control becomes view-aware, driving `terminal-font-size` in Term and
`lumbergh:conversationFontSize` in Conv. The manual "fit" action is terminal-only
and is hidden in Conv.

The file keeps its name. Renaming `TerminalHeader` would touch more than it is
worth here.

### Both views stay mounted

The left pane renders `Terminal` and `ConversationView` simultaneously, hiding
the inactive one with a `hidden` class. Neither is ever unmounted by a swap.

This is a hard requirement, not an optimization. Unmounting `Terminal` tears down
xterm and the WebSocket, losing client-side scrollback and reconnecting the
session — the regression that had to be fixed twice during zen mode.

`Terminal` already handles being re-shown: its `isVisible` prop clears
`lastSentSizeRef` and refits through a double `requestAnimationFrame`, which is
how mobile tab switching works today. Pass `isVisible={view === 'term'}`.

### `components/conversation/` (renamed from `activity/`)

- `ConversationView.tsx` — the shell: scroll container, follow behavior, the
  virtualizer, the respond box.
- `ConversationItem.tsx` — the card components (`BashCard`, `EditCard`,
  `GenericToolCard`, `ThinkingBlock`, `AgentMarkdown`, `Item`), lifted out of
  today's single file.
- `ConversationRespondBox.tsx` — renamed from `ActivityRespondBox.tsx`,
  otherwise unchanged.
- `hooks/useConversationSocket.ts` — renamed from `useActivitySocket.ts`.

Frontend renames only. The WebSocket endpoint, its payloads, and every line of
backend code stay exactly as they are.

The split exists because virtualization will push the current 267-line file well
past a size worth holding in one piece, and the shell and the cards have
genuinely different jobs.

### Virtualization

`ConversationView` renders through `useVirtualizer` from `@tanstack/react-virtual`
— already a dependency — with `measureElement` for dynamic row heights. Rows vary
from a one-line status to a long expanded diff, so fixed estimates will not do.

Three things invalidate a measured height and must trigger re-measure:

1. A card expanding or collapsing.
2. A zoom change.
3. Markdown, fonts, or images settling after first paint.

### Follow behavior

Today's auto-follow observes the content element with a `ResizeObserver` and
pins `scrollTop` to `scrollHeight`. Virtualized content has no stable content
element to observe, so follow is rebuilt:

- While following, new items call `virtualizer.scrollToIndex(count - 1)`.
- The existing scroll handler that decides whether the user has scrolled away
  (`scrollHeight - scrollTop - clientHeight < 40`) is preserved, as is the
  "Jump to latest ↓" button and the `programmaticRef` guard that keeps
  self-inflicted scrolls from being read as the user scrolling away.

This interaction between virtualization and follow-to-bottom is where the bugs
will be. It gets the most test attention.

## Testing

**Gherkin UI tests** — the user-facing story:

```gherkin
Scenario: The toggle swaps between terminal and conversation
  Given I am on a desktop session page in Term view
  When I click the view toggle
  Then I should see the conversation feed
  And I should not see the terminal

Scenario: The view choice sticks across a reload
  Given I am on a session page in Conv view
  When I reload the page
  Then I should see the conversation feed

Scenario: Swapping views keeps the session connected
  Given I am on a session page in Term view
  When I click the view toggle
  And I click the view toggle again
  Then the terminal is still connected
```

**Unit tests:**

- A jsdom mount-count test with a negative control, asserting `Terminal` mounts
  exactly once across `term → conv → term`. The negative control matters: during
  zen mode an implementer reported this fixed on faulty evidence, and only a
  mechanism-level repro caught it.
- A virtualization test: a feed of many items puts only a windowed subset in the
  DOM.
- `isSessionCycleChord` claims `Alt+V`, including the macOS shape where
  `e.key === '√'` and `e.code === 'KeyV'`.

## Out of scope

Five ideas worth stealing from Warp's block model and 1DevTool's reader mode are
deliberately deferred to their own spec, so this one stays shippable:

- Liveness-aware collapse — expand a tool card while it runs, collapse it on
  completion. Today everything starts collapsed, so a running Bash hides its own
  output at exactly the moment you want to watch it.
- Grouping consecutive file edits under one "Edited 3 files" header.
- Expand-all / collapse-all on a key.
- Block-level navigation — jump turn to turn instead of scrolling.
- Search within the conversation.

Also out of scope: the Git and Files tabs, which are their own sub-projects; any
backend change; and the generative-UI widget approach, which solves a different
problem.
