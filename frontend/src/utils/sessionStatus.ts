export interface SessionBase {
  name: string
  alive: boolean
  idleState?: 'unknown' | 'idle' | 'working' | 'blocked' | 'error' | 'stalled' | null
  unseen?: boolean
  attentionState?: 'idle' | 'blocked' | 'error' | null
  needsAnswer?: boolean
  paused?: boolean
  displayName: string | null
  theOne?: boolean
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
    case 'stalled':
      return { color: 'red', pulse: true, label: 'Stalled' }
    default:
      return { color: 'green', pulse: false, label: 'Active' }
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

export function sessionUrgencyRank(
  session: Pick<SessionBase, 'theOne' | 'idleState' | 'unseen' | 'needsAnswer'>
): number {
  if (session.theOne) return 0
  if (session.idleState === 'blocked') return 1
  if (session.needsAnswer) return 1
  if (session.unseen) return 2
  return 3
}
