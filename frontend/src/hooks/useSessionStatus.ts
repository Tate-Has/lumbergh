import { useState, useEffect, useRef, useCallback } from 'react'
import { getApiBase } from '../config'
import { getSessionStatus, type SessionBase } from '../utils/sessionStatus'

export interface SessionStatusInfo {
  color: string
  pulse: boolean
  label: string
}

export function useSessionStatus(sessionNames: string[]): Record<string, SessionStatusInfo> {
  const [statusMap, setStatusMap] = useState<Record<string, SessionStatusInfo>>({})
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const sessionNamesRef = useRef(sessionNames)
  sessionNamesRef.current = sessionNames

  const fetchStatuses = useCallback(async () => {
    const names = sessionNamesRef.current
    if (names.length === 0) {
      setStatusMap({})
      return
    }

    try {
      const res = await fetch(`${getApiBase()}/sessions`)
      if (!res.ok) throw new Error('Failed to fetch sessions')
      const data = await res.json()
      const sessions: SessionBase[] = data.sessions || data || []

      const newMap: Record<string, SessionStatusInfo> = {}
      for (const name of names) {
        const session = sessions.find((s: SessionBase) => s.name === name)
        if (session) {
          newMap[name] = getSessionStatus(session)
        } else {
          // Session not found in Lumbergh — treat as offline
          newMap[name] = { color: 'gray', pulse: false, label: 'Offline' }
        }
      }
      setStatusMap(newMap)
    } catch {
      // Lumbergh offline — mark all as offline silently
      const offlineMap: Record<string, SessionStatusInfo> = {}
      for (const name of sessionNamesRef.current) {
        offlineMap[name] = { color: 'gray', pulse: false, label: 'Offline' }
      }
      setStatusMap(offlineMap)
    }
  }, [])

  const hasSessionNames = sessionNames.length > 0

  useEffect(() => {
    if (!hasSessionNames) {
      setStatusMap({})
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
      return
    }

    // Fetch immediately
    fetchStatuses()

    // Then poll every 5s
    intervalRef.current = setInterval(fetchStatuses, 5000)

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [hasSessionNames, fetchStatuses])

  return statusMap
}
