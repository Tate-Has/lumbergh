/** One entry from `GET /api/bill/babysit` — a session Bill is keeping cycling. */
export interface BabysitEntry {
  session: string
  repo?: string | null
  added_at?: string
}

/** Whether a session card should offer the babysit toggle.
 *
 * Babysit targets a top-level supervised session, never a worker or Bill himself, and a
 * scratch session is too ephemeral to keep alive. The toggle shows on any live eligible
 * session; a dead one shows it only when it's *already* babysat, so an active loop stays
 * visible (and stoppable) instead of silently vanishing when its session goes offline. */
export function canBabysit(
  session: { role?: string | null; type?: string | null; alive: boolean },
  babysat: boolean
): boolean {
  if (session.role === 'worker' || session.role === 'bill') return false
  if (session.type === 'scratch') return false
  return session.alive || babysat
}
