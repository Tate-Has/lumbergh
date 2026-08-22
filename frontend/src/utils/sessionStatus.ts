export interface SessionBase {
  name: string
  alive: boolean
  idleState?: 'unknown' | 'idle' | 'working' | 'blocked' | 'error' | null
  unseen?: boolean
  attentionState?: 'idle' | 'blocked' | 'error' | null
  needsAnswer?: boolean
  paused?: boolean
  displayName: string | null
  theOne?: boolean
  role?: 'bill' | 'worker' | 'session'
  parent?: string | null
  workdir?: string | null
  worktreeParentRepo?: string | null
}

/** The name of the running session a worker belongs to, or null if none is on
 * screen. The single source of truth for parent/child grouping — the dashboard
 * cards and the navigator dots both resolve through here, so a sub-session nests
 * under the same session in both views.
 *
 * The recorded `parent` is the session that spawned the worker, which may since
 * have died while the worker lives on; its bubble would then drift off among the
 * top-level sessions. Fall back to the repo the worktree was cut from: whichever
 * live session is checked out there is the one the user means by "the parent". */
export function resolveWorkerParent<T extends SessionBase>(
  worker: T,
  peers: T[],
  present: Set<string>
): string | null {
  if (worker.role !== 'worker') return null
  if (worker.parent && present.has(worker.parent)) return worker.parent
  const repo = worker.worktreeParentRepo
  if (!repo) return null
  return peers.find((s) => s.role !== 'worker' && s.workdir === repo)?.name ?? null
}

/** Whether a session has an unhandled action for the user: it is stuck
 * (blocked/error), has a pending question, or finished a chunk unseen
 * (idle + "while you were away"). Mirrors the backend's `fleet.needs_attention`
 * so the dashboard rollups match Bill's own supervision cues. */
export function sessionNeedsAttention(
  session: Pick<SessionBase, 'idleState' | 'unseen' | 'needsAnswer'>
): boolean {
  return (
    session.idleState === 'blocked' ||
    session.idleState === 'error' ||
    (session.idleState === 'idle' && !!session.unseen) ||
    !!session.needsAnswer
  )
}

/** Normalize the `/sessions` payload into a session array.
 *
 * The endpoint returns `{ sessions: [...] }`; older call sites assumed a bare
 * array and silently dropped every session. Accept both so the overlay is robust.
 */
export function parseSessionsPayload(data: unknown): SessionBase[] {
  if (Array.isArray(data)) return data as SessionBase[]
  const wrapped = (data as { sessions?: unknown })?.sessions
  return Array.isArray(wrapped) ? (wrapped as SessionBase[]) : []
}

export function getSessionStatus(session: SessionBase): {
  color: string
  pulse: boolean
  label: string
} {
  if (!session.alive) {
    return { color: 'gray', pulse: false, label: 'Offline' }
  }
  if (session.unseen) {
    if (session.idleState === 'blocked') {
      return { color: 'purple', pulse: true, label: 'Blocked — while you were away' }
    }
    if (session.idleState === 'error') {
      return { color: 'red', pulse: true, label: 'Failed — while you were away' }
    }
    if (session.needsAnswer) {
      return { color: 'purple', pulse: true, label: 'Question — while you were away' }
    }
    return { color: 'yellow', pulse: true, label: 'Done — while you were away' }
  }
  if (session.needsAnswer && session.idleState === 'idle') {
    return { color: 'purple', pulse: true, label: 'Question — waiting on you' }
  }
  switch (session.idleState) {
    case 'idle':
      return { color: 'yellow', pulse: true, label: 'Waiting for input' }
    case 'working':
      return { color: 'green', pulse: false, label: 'Working' }
    case 'blocked':
      return { color: 'purple', pulse: true, label: 'Blocked — waiting on you' }
    case 'error':
      return { color: 'red', pulse: true, label: 'Error' }
    default:
      // No state, not "fine": the monitor writes nothing until it has classified a
      // session, and a missing row must never read as a healthy green one.
      return { color: 'gray', pulse: false, label: 'Unknown' }
  }
}

export const statusColorClasses: Record<string, { dot: string; text: string }> = {
  gray: { dot: 'bg-text-tertiary', text: 'text-text-tertiary' },
  yellow: { dot: 'bg-warning shadow-[0_0_6px_rgba(255,159,10,0.4)]', text: 'text-warning' },
  green: { dot: 'bg-success shadow-[0_0_6px_rgba(48,209,88,0.4)]', text: 'text-success' },
  red: { dot: 'bg-danger shadow-[0_0_6px_rgba(255,69,58,0.4)]', text: 'text-danger' },
  purple: {
    dot: 'bg-purple shadow-[0_0_6px_rgba(191,90,242,0.4)]',
    text: 'text-purple',
  },
}

/** Sort key for the dashboard: lower floats higher.
 *
 * Only two things outrank recency — the session you pinned, and one that has
 * actually stopped and is waiting on a human. "Done while you were away" used to
 * sit in between, which pushed whatever you had just been working on to the
 * bottom of the list; it keeps its badge and its colour, but not a place above
 * the session in front of you.
 */
export function sessionUrgencyRank(
  session: Pick<SessionBase, 'theOne' | 'idleState' | 'unseen' | 'needsAnswer'>
): number {
  if (session.theOne) return 0
  if (session.idleState === 'blocked') return 1
  if (session.needsAnswer) return 1
  return 2
}
