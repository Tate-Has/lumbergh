import type { SessionBase } from './sessionStatus'
import { sessionUrgencyRank } from './sessionStatus'

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
 * A worker nests under a session named by its `parent` only when that parent is
 * present in this list; a worker whose parent is absent (or that has no parent —
 * an orphan worker) becomes a top-level solo so it never falls through the cracks.
 * Top-level items (overseers + solos) are ordered by urgency then recency, matching
 * the flat dashboard sort; workers within a group are ordered by urgency alone.
 */
export function groupSessions<T extends Groupable>(sessions: T[]): GroupedSessions<T> {
  const present = new Set(sessions.map((s) => s.name))
  const bill = sessions.find((s) => s.role === 'bill') ?? null

  const workersByParent = new Map<string, T[]>()
  for (const s of sessions) {
    if (s === bill) continue
    if (s.role === 'worker' && s.parent && present.has(s.parent)) {
      const list = workersByParent.get(s.parent) ?? []
      list.push(s)
      workersByParent.set(s.parent, list)
    }
  }
  for (const workers of workersByParent.values()) {
    workers.sort((a, b) => sessionUrgencyRank(a) - sessionUrgencyRank(b))
  }

  const items: SessionGroup<T>[] = []
  for (const s of sessions) {
    if (s === bill) continue
    const nestedElsewhere = s.role === 'worker' && s.parent && workersByParent.has(s.parent)
    if (nestedElsewhere) continue
    items.push({ parent: s, workers: workersByParent.get(s.name) ?? [] })
  }
  items.sort((a, b) => topLevelOrder(a.parent, b.parent))

  return { bill, items }
}
