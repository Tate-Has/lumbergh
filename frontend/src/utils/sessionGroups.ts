import type { SessionBase } from './sessionStatus'
import { sessionUrgencyRank, resolveWorkerParent } from './sessionStatus'

interface Groupable extends SessionBase {
  lastUsedAt?: string | null
}

/** One top-level dashboard item. A group with a non-empty `workers` list is an
 * overseer (rendered with an expander); an empty `workers` list is a plain solo
 * session. Unifying the two lets the dashboard order overseers and solos together. */
export interface SessionGroup<T> {
  parent: T
  workers: T[]
}

export interface GroupedSessions<T> {
  bill: T | null
  items: SessionGroup<T>[]
}

function topLevelOrder<T extends Groupable>(a: T, b: T): number {
  const rank = sessionUrgencyRank(a) - sessionUrgencyRank(b)
  if (rank !== 0) return rank
  return (b.lastUsedAt || '').localeCompare(a.lastUsedAt || '')
}

/** Partition sessions into Bill, overseer groups, and solos.
 *
 * Parent/child grouping is resolved by `resolveWorkerParent`, the same call the
 * navigator dots make, so a sub-session nests under the same session in both views.
 * A worker with no parent on screen becomes a top-level solo so it never falls
 * through the cracks.
 * Top-level items (overseers + solos) are ordered by urgency then recency, matching
 * the flat dashboard sort; workers within a group are ordered by urgency alone.
 */
export function groupSessions<T extends Groupable>(sessions: T[]): GroupedSessions<T> {
  const present = new Set(sessions.map((s) => s.name))
  const bill = sessions.find((s) => s.role === 'bill') ?? null

  const peers = sessions.filter((s) => s !== bill)

  const workersByParent = new Map<string, T[]>()
  for (const s of peers) {
    const parent = resolveWorkerParent(s, peers, present)
    if (!parent) continue
    const list = workersByParent.get(parent) ?? []
    list.push(s)
    workersByParent.set(parent, list)
  }
  for (const workers of workersByParent.values()) {
    workers.sort((a, b) => sessionUrgencyRank(a) - sessionUrgencyRank(b))
  }

  const nested = new Set([...workersByParent.values()].flat().map((s) => s.name))
  const items: SessionGroup<T>[] = peers
    .filter((s) => !nested.has(s.name))
    .map((s) => ({ parent: s, workers: workersByParent.get(s.name) ?? [] }))
  items.sort((a, b) => topLevelOrder(a.parent, b.parent))

  return { bill, items }
}
