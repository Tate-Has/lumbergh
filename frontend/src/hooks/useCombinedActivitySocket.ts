import { useEffect, useRef, useState, useCallback } from 'react'
import { getWsBase } from '../config'

// Mirrors `ConversationEvent.model_dump()` from
// `backend/lumbergh/activity/events.py` — the agent-agnostic conversation
// event shape. Field names/optionality kept in lockstep with that pydantic
// model (fields the model always sets are required here; fields declared
// `X | None = None` are optional).
export type ActivityEventType =
  | 'user_message'
  | 'agent_message'
  | 'thinking'
  | 'tool_call'
  | 'tool_result'
  | 'status'

export interface ActivityEvent {
  type: ActivityEventType
  id: string
  timestamp?: number | null
  // user_message / agent_message / thinking / status
  text?: string | null
  // tool_call
  tool_name?: string | null
  tool_summary?: string | null
  tool_detail?: string | null
  // tool_call (its id) and tool_result (the call it answers), matched via
  // tool_use_id — pairing logic itself belongs to the UI layer, not this hook.
  tool_use_id?: string | null
  // tool_result: "ok" | "error"
  status?: string | null
}

// One raw `{ session, event }` message off the combined feed.
interface CombinedActivityMessage {
  session: string
  event: ActivityEvent
}

// An ActivityEvent tagged with the session it came from, plus a stable react
// key and a monotonically increasing arrival sequence used as a sort
// tiebreaker (backend timestamps are `float | None`, and two events can share
// a timestamp).
export interface ActivityItem extends ActivityEvent {
  session: string
  /** `${session}:${id}` — ids are only unique within one session's transcript. */
  key: string
  /** Local arrival order; monotonic within this hook instance. */
  seq: number
}

export type ActivityConnectionState = 'connecting' | 'open' | 'reconnecting' | 'closed'

// Hard cap on retained items so a tab left open for hours/days in the
// background doesn't grow memory without bound. Oldest items are dropped
// first once the cap is hit.
const MAX_ITEMS = 2000

export interface UseCombinedActivitySocketResult {
  /**
   * Sort order: oldest-first / newest-last (i.e. append order), like a chat
   * log. Sorted primarily by `timestamp` (nulls sort by arrival order via
   * `seq`), with `seq` as a stable tiebreaker for equal timestamps. A
   * consuming UI that wants a "newest at top" feed should reverse this list
   * itself rather than ask this hook to change order.
   */
  items: ActivityItem[]
  connectionState: ActivityConnectionState
}

/**
 * Single shared websocket to `/api/activity/stream`, aggregating activity
 * events from every currently-running session. There is no history — the
 * socket only emits events from the moment it connects onward, so a
 * reconnect (e.g. after a background-tab suspend) will show a gap, not a
 * replay.
 *
 * Reconnect behavior mirrors `useTerminalSocket.ts`: a flat retry delay after
 * an unexpected close, a StrictMode/double-effect guard (skip connecting if a
 * socket is already OPEN/CONNECTING), and visibility/pageshow/online
 * listeners that probe and reconnect immediately when a backgrounded tab
 * resumes (rather than waiting on a possibly-paused timer).
 */
export function useCombinedActivitySocket(): UseCombinedActivitySocketResult {
  const [items, setItems] = useState<ActivityItem[]>([])
  const [connectionState, setConnectionState] = useState<ActivityConnectionState>('connecting')

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)
  const connectRef = useRef<() => void>(() => {})
  const seqRef = useRef(0)
  // Distinguishes the very first connection attempt ('connecting') from
  // attempts made after a drop ('reconnecting'), for the UI's status pill.
  const hasConnectedOnceRef = useRef(false)

  const connect = useCallback(() => {
    // Guard against StrictMode/double-effect creating a second WebSocket
    // while the first is still CONNECTING (see useTerminalSocket.ts).
    const existing = wsRef.current
    if (existing?.readyState === WebSocket.OPEN || existing?.readyState === WebSocket.CONNECTING) {
      return
    }

    // No setState here: the initial 'connecting' value is already the
    // useState default, and the reconnect case is already covered by
    // ws.onclose (below) setting 'reconnecting' before it schedules the
    // retry — connect() itself must stay free of synchronous setState calls
    // since it's invoked directly from the mount effect (react-hooks/set-state-in-effect).

    const wsUrl = `${getWsBase()}/activity/stream`
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      if (wsRef.current !== ws) {
        ws.close()
        return
      }
      hasConnectedOnceRef.current = true
      setConnectionState('open')
    }

    ws.onmessage = (event) => {
      if (wsRef.current !== ws) return
      let message: CombinedActivityMessage
      try {
        message = JSON.parse(event.data)
      } catch {
        return
      }
      if (!message?.event) return

      const item: ActivityItem = {
        ...message.event,
        session: message.session,
        key: `${message.session}:${message.event.id}`,
        seq: seqRef.current++,
      }

      setItems((prev) => {
        const next = [...prev, item]
        next.sort((a, b) => {
          const ta = a.timestamp ?? null
          const tb = b.timestamp ?? null
          if (ta !== null && tb !== null && ta !== tb) return ta - tb
          if (ta !== null && tb === null) return -1
          if (ta === null && tb !== null) return 1
          return a.seq - b.seq
        })
        return next.length > MAX_ITEMS ? next.slice(next.length - MAX_ITEMS) : next
      })
    }

    ws.onclose = () => {
      if (wsRef.current !== ws) return
      wsRef.current = null
      setConnectionState('reconnecting')
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connectRef.current()
      }, 2000)
    }

    ws.onerror = () => {
      // onclose fires right after and drives reconnection; nothing extra to
      // do here beyond letting that happen.
    }

    wsRef.current = ws
  }, [])

  useEffect(() => {
    connectRef.current = connect
  }, [connect])

  useEffect(() => {
    connect()

    // Backgrounded tabs (especially iOS PWA) can have their socket killed
    // without an onclose firing, and their setTimeout paused. Probe and
    // reconnect immediately whenever the tab/page/network comes back.
    const ensureConnected = () => {
      const ws = wsRef.current
      if (!ws || ws.readyState === WebSocket.CLOSED || ws.readyState === WebSocket.CLOSING) {
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current)
          reconnectTimeoutRef.current = null
        }
        connectRef.current()
      }
    }
    const onVisibility = () => {
      if (document.visibilityState === 'visible') ensureConnected()
    }
    const onPageShow = () => ensureConnected()
    const onOnline = () => ensureConnected()
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('pageshow', onPageShow)
    window.addEventListener('online', onOnline)

    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('pageshow', onPageShow)
      window.removeEventListener('online', onOnline)
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
      if (wsRef.current) {
        const ws = wsRef.current
        wsRef.current = null
        setConnectionState('closed')
        if (ws.readyState === WebSocket.OPEN) {
          ws.close()
        } else if (ws.readyState === WebSocket.CONNECTING) {
          ws.addEventListener('open', () => ws.close(), { once: true })
        }
      }
    }
  }, [connect])

  return { items, connectionState }
}
