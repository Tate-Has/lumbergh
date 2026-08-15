import type { SessionBase } from './sessionStatus'

const BILL_NAME = 'bill'

const byName = (a: SessionBase, b: SessionBase) => a.name.localeCompare(b.name)

/** The order the session switcher presents: Bill, then starred sessions, then the
 * rest. Both the navigator dots and the Alt+Arrow bindings read from here so the
 * keys always land on the dot beside the current one. */
export function orderSessionsForNavigator(sessions: SessionBase[]): SessionBase[] {
  const active = sessions.filter((s) => s.alive && !s.paused)
  const peers = active.filter((s) => s.name !== BILL_NAME)
  return [
    ...active.filter((s) => s.name === BILL_NAME),
    ...peers.filter((s) => s.theOne).sort(byName),
    ...peers.filter((s) => !s.theOne).sort(byName),
  ]
}

/** The session one step from `current`, wrapping at both ends. Null when there is
 * nowhere to go: fewer than two sessions, or `current` is no longer among them. */
export function adjacentSessionName(
  ordered: SessionBase[],
  current: string,
  direction: 'prev' | 'next'
): string | null {
  if (ordered.length < 2) return null
  const index = ordered.findIndex((s) => s.name === current)
  if (index === -1) return null
  const step = direction === 'next' ? 1 : ordered.length - 1
  return ordered[(index + step) % ordered.length].name
}
