export interface SessionBase {
  name: string
  alive: boolean
  idleState?: 'unknown' | 'idle' | 'working' | 'blocked' | 'error' | 'stalled' | null
  unseen?: boolean
  attentionState?: 'idle' | 'blocked' | 'error' | null
  paused?: boolean
  displayName: string | null
  theOne?: boolean
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
    switch (session.idleState) {
      case 'blocked':
        return { color: 'purple', pulse: true, label: 'Blocked — while you were away' }
      case 'error':
        return { color: 'red', pulse: true, label: 'Failed — while you were away' }
      default:
        return { color: 'yellow', pulse: true, label: 'Done — while you were away' }
    }
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
  session: Pick<SessionBase, 'theOne' | 'idleState' | 'unseen'>
): number {
  if (session.theOne) return 0
  if (session.idleState === 'blocked') return 1
  if (session.unseen) return 2
  return 3
}
