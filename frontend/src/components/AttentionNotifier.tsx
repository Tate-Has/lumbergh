import { useEffect, useRef } from 'react'
import { getApiBase } from '../config'
import {
  computeNotifications,
  isNotifyEnabled,
  type NotifiableSession,
} from '../utils/attentionNotifications'

const POLL_MS = 10000

export default function AttentionNotifier() {
  const prevUnseen = useRef<Set<string>>(new Set())

  useEffect(() => {
    if (!('Notification' in window) || !('serviceWorker' in navigator)) return
    let cancelled = false

    async function poll() {
      let sessions: NotifiableSession[] = []
      try {
        const res = await fetch(`${getApiBase()}/sessions`)
        if (!res.ok) return
        sessions = (await res.json()).sessions || []
      } catch {
        return
      }
      if (cancelled) return

      const { toFire, nextUnseen } = computeNotifications(prevUnseen.current, sessions, {
        hidden: document.visibilityState === 'hidden',
        enabled: isNotifyEnabled(),
        permissionGranted: Notification.permission === 'granted',
      })
      prevUnseen.current = nextUnseen
      if (toFire.length === 0) return

      try {
        const reg = await navigator.serviceWorker.ready
        for (const spec of toFire) {
          reg.showNotification(spec.title, {
            body: spec.body,
            tag: spec.tag,
            data: { url: spec.url },
          })
        }
      } catch {
        // Service worker not ready — skip this round.
      }
    }

    poll()
    const id = setInterval(poll, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  return null
}
