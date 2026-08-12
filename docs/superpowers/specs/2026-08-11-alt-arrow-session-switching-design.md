# Alt+Arrow Session Switching

## Goal

On desktop, `Alt+Left` / `Alt+Right` move to the adjacent session — from any view of a session
page, including while the terminal has keyboard focus.

## Current state

`SessionDetail.tsx` already binds `Ctrl+[` / `Ctrl+]` to `handleCycleSession`, which sorts
alive-and-unpaused sessions by name and, on `next`, jumps to the first starred *idle* session
instead of the adjacent one.

`SessionNavigatorDots` renders a different order — Bill first, then starred, then the rest, each
group name-sorted — and derives that split inline in its render.

So there are two orderings in the app, and neither is reusable.

## Behavior

`Alt+Left` / `Alt+Right` step to the adjacent session in **the order the dots are rendered**:
Bill, then starred, then the rest. Purely spatial — the key moves you to the dot beside the
current one. It wraps at both ends.

Bound on the session pages only (`/session/:name` and `/session/:name/term`); the Dashboard has no
current session to move from. Desktop only.

`Ctrl+[` / `Ctrl+]` keep their existing smart-jump behavior unchanged. This is additive.

## Components

### `frontend/src/utils/sessionOrder.ts` (new)

Pure functions, unit-tested — the navigator order becomes explicit instead of implicit in JSX.

```ts
orderSessionsForNavigator(sessions: SessionBase[]): SessionBase[]
```
Filters to `alive && !paused`, then orders: `bill` first, starred (`theOne`) name-sorted, rest
name-sorted.

```ts
adjacentSessionName(ordered: SessionBase[], current: string, dir: 'prev' | 'next'): string | null
```
Wraps around. Returns `null` when fewer than two sessions, or when `current` is absent from the
list.

### `frontend/src/components/SessionNavigatorDots.tsx` (refactor)

Builds its dots from `orderSessionsForNavigator` rather than re-deriving the Bill/starred/rest
split inline. The dots and the key bindings then read from one source and cannot drift apart. The
group separators stay driven by which groups are non-empty.

### `frontend/src/hooks/useSessionSwitchKeys.ts` (new)

Takes the current session name. A `window` `keydown` listener that, on `altKey` with `ArrowLeft` or
`ArrowRight` and `useIsDesktop()` true:

1. `preventDefault()`
2. fetches `GET /sessions`
3. `adjacentSessionName(orderSessionsForNavigator(...), name, dir)`
4. `navigate(/session/<target><routeSuffix>)`, where `routeSuffix` is `/term` when the current
   path ends in `/term`, matching what the dots already do

Fetch-on-keypress rather than polling — the same approach `handleCycleSession` takes today, so no
second 5s poller appears.

Mounted in `SessionDetail` and `TerminalWindow`.

### `frontend/src/components/Terminal.tsx` (one case)

In `attachCustomKeyEventHandler`, alongside the existing `Ctrl+[` / `Ctrl+]` pass-through:

```ts
if (event.altKey && (event.key === 'ArrowLeft' || event.key === 'ArrowRight')) return false
```

Returning `false` keeps xterm from forwarding `\e\e[D` / `\e\e[C` to tmux. Because xterm does not
call `preventDefault()` on that path, the event still bubbles to the window listener. This is what
makes the binding work while the terminal has focus.

## Tradeoff

`preventDefault()` claims `Alt+Left` / `Alt+Right` from Chrome and Firefox history Back/Forward on
Linux and Windows, on the session pages only. Accepted: the in-app back affordances (header back
button, `Esc`) are unaffected, and the Dashboard keeps browser history nav.

## Error handling

A failed `/sessions` fetch is swallowed and no navigation happens — same as `handleCycleSession`.
A `null` from `adjacentSessionName` is a no-op.

## Testing

`frontend/src/utils/sessionOrder.test.ts` (vitest, matching the `src/utils/*.test.ts` convention):

- ordering puts Bill first, then starred name-sorted, then rest name-sorted
- dead and paused sessions are excluded
- `next` from the last entry wraps to the first; `prev` from the first wraps to the last
- a single session returns `null` in both directions
- an unknown `current` returns `null`

The hook and the xterm pass-through are verified by hand in the running app: switch with the
terminal focused and confirm no stray escape characters land in the shell, and confirm the browser
does not navigate back.
