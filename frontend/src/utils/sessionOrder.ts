import type { SessionBase } from './sessionStatus'
import { resolveWorkerParent } from './sessionStatus'

const BILL_NAME = 'bill'

const byName = (a: SessionBase, b: SessionBase) => a.name.localeCompare(b.name)

export interface NavigatorGroups<T extends SessionBase = SessionBase> {
  bill: T | null
  starred: T[]
  rest: T[]
}

/** The switcher's three runs of bubbles: Bill, starred sessions, then the rest.
 * A worker trails immediately behind its parent inside whichever run the parent
 * landed in, so a sub-session never drifts away from the session that spawned it.
 * A worker with no parent on screen stands on its own as a top-level session. */
export function navigatorGroups<T extends SessionBase>(sessions: T[]): NavigatorGroups<T> {
  const active = sessions.filter((s) => s.alive && !s.paused)
  const peers = active.filter((s) => s.name !== BILL_NAME)
  const present = new Set(peers.map((s) => s.name))

  const workersByParent = new Map<string, T[]>()
  for (const s of peers) {
    const parent = resolveWorkerParent(s, peers, present)
    if (!parent) continue
    const list = workersByParent.get(parent) ?? []
    list.push(s)
    workersByParent.set(parent, list)
  }
  for (const workers of workersByParent.values()) workers.sort(byName)

  const nested = new Set([...workersByParent.values()].flat().map((s) => s.name))
  const tops = peers.filter((s) => !nested.has(s.name))
  const withWorkers = (s: T) => [s, ...(workersByParent.get(s.name) ?? [])]

  return {
    bill: active.find((s) => s.name === BILL_NAME) ?? null,
    starred: tops
      .filter((s) => s.theOne)
      .sort(byName)
      .flatMap(withWorkers),
    rest: tops
      .filter((s) => !s.theOne)
      .sort(byName)
      .flatMap(withWorkers),
  }
}

/** The order the session switcher presents, flattened. Both the navigator dots and
 * the Alt+Arrow bindings read from here so the keys always land on the dot beside
 * the current one. */
export function orderSessionsForNavigator<T extends SessionBase>(sessions: T[]): T[] {
  const { bill, starred, rest } = navigatorGroups(sessions)
  return [...(bill ? [bill] : []), ...starred, ...rest]
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
