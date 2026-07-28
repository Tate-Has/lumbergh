export const NOTIFY_ENABLED_KEY = 'lumbergh:notifyWhileAway'

export function isNotifyEnabled(): boolean {
  try {
    return localStorage.getItem(NOTIFY_ENABLED_KEY) === '1'
  } catch {
    return false
  }
}

export function setNotifyEnabled(v: boolean): void {
  try {
    localStorage.setItem(NOTIFY_ENABLED_KEY, v ? '1' : '0')
  } catch {
    // localStorage unavailable (private mode etc.) — preference just won't persist
  }
}

export interface NotifiableSession {
  name: string
  displayName?: string | null
  unseen?: boolean
  attentionState?: 'idle' | 'blocked' | 'error' | null
}

export interface NotificationSpec {
  title: string
  body: string
  tag: string
  url: string
}

export interface NotifyContext {
  hidden: boolean
  enabled: boolean
  permissionGranted: boolean
}

const VERB: Record<string, string> = { idle: 'Done', blocked: 'Blocked', error: 'Failed' }

export function computeNotifications(
  prevUnseen: Set<string>,
  sessions: NotifiableSession[],
  ctx: NotifyContext
): { toFire: NotificationSpec[]; nextUnseen: Set<string> } {
  const nextUnseen = new Set(sessions.filter((s) => s.unseen).map((s) => s.name))

  if (!ctx.enabled || !ctx.permissionGranted || !ctx.hidden) {
    return { toFire: [], nextUnseen }
  }

  const newly = [...nextUnseen].filter((name) => !prevUnseen.has(name))
  if (newly.length === 0) {
    return { toFire: [], nextUnseen }
  }

  if (newly.length === 1) {
    const session = sessions.find((s) => s.name === newly[0])!
    const verb = VERB[session.attentionState ?? 'idle'] ?? 'Done'
    return {
      toFire: [
        {
          title: session.displayName || session.name,
          body: `${verb} — while you were away`,
          tag: session.name,
          url: `/session/${encodeURIComponent(session.name)}`,
        },
      ],
      nextUnseen,
    }
  }

  return {
    toFire: [
      {
        title: 'Lumbergh',
        body: `${newly.length} sessions need your attention`,
        tag: 'lumbergh-attention',
        url: '/',
      },
    ],
    nextUnseen,
  }
}
