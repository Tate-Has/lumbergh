import { useCallback, useEffect, useRef, useState } from 'react'
import { getWsBase } from '../config'

export interface ActivityEvent {
  type:
    | 'user_message'
    | 'agent_message'
    | 'thinking'
    | 'tool_call'
    | 'tool_result'
    | 'status'
    | 'no_transcript'
  id: string
  timestamp?: number
  text?: string
  tool_name?: string
  tool_summary?: string
  tool_detail?: string
  tool_use_id?: string
  status?: string
}

// A tool_call plus its (eventual) result, rendered as one card.
export interface ToolItem extends ActivityEvent {
  type: 'tool_call'
  result?: { status?: string; text?: string }
}

export type RenderItem = ActivityEvent | ToolItem

/**
 * Fold raw events into render items: tool_results are attached to their
 * matching tool_call (by tool_use_id) rather than rendered standalone.
 */
export function mergeEvents(prev: RenderItem[], incoming: ActivityEvent): RenderItem[] {
  if (incoming.type === 'no_transcript') return prev
  if (incoming.type === 'tool_result') {
    let matched = false
    const merged = prev.map((item) => {
      if (item.type !== 'tool_call' || item.tool_use_id !== incoming.tool_use_id) return item
      matched = true
      return { ...item, result: { status: incoming.status, text: incoming.text } }
    })
    // A result whose call is not here yet belongs to an older page. Keeping it
    // (it renders as nothing) lets the call pick it up when that page loads;
    // dropping it left a finished command showing as still running.
    return matched ? merged : [...prev, incoming as RenderItem]
  }
  return [...prev, incoming as RenderItem]
}

/** Apply a page of history in one update.
 *
 * The server sends the newest page as a single frame rather than one frame per
 * event: folding it here costs one render instead of five hundred, which is the
 * difference between the view opening and the view scrolling.
 */
export function applyHistory(_prev: RenderItem[], events: ActivityEvent[]): RenderItem[] {
  return events.reduce<RenderItem[]>((items, event) => mergeEvents(items, event), [])
}

/** Prepend an older page, keeping what is already on screen.
 *
 * A result whose call lives in the older page only becomes resolvable now, so
 * the whole list is refolded rather than concatenated.
 */
export function applyOlderHistory(shown: RenderItem[], older: ActivityEvent[]): RenderItem[] {
  if (older.length === 0) return shown
  return [...older, ...shown].reduce<RenderItem[]>(
    (items, event) => mergeEvents(items, event as ActivityEvent),
    []
  )
}

/**
 * `enabled` gates the connection: while false, no WebSocket is opened (and any
 * open one is torn down). Callers that mount this eagerly alongside UI the user
 * hasn't looked at yet — e.g. a conversation pane sitting hidden next to a
 * terminal — should keep `enabled` false until the user actually shows it, then
 * leave it true forever. Toggling it back to false on every hide would force a
 * full transcript replay (the server always replays from offset 0) each time
 * the user flips back, which is worse than just staying connected.
 */
export function useConversationSocket({
  sessionName,
  enabled = true,
}: {
  sessionName: string
  enabled?: boolean
}) {
  const [items, setItems] = useState<RenderItem[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [noTranscript, setNoTranscript] = useState(false)
  // How much transcript is still behind the oldest event on screen.
  const [remaining, setRemaining] = useState(0)
  const [loadingOlder, setLoadingOlder] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!enabled) return

    let isActive = true
    let attempts = 0
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined

    const connect = () => {
      // Fresh state on every (re)connect; the server replays full history from
      // offset 0, so clearing avoids duplicating events across a reconnect.
      setItems([])
      setNoTranscript(false)
      setRemaining(0)
      setLoadingOlder(false)
      const url = `${getWsBase()}/session/${encodeURIComponent(sessionName)}/activity`
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        if (!isActive) return
        setIsConnected(true)
        attempts = 0
      }
      ws.onclose = () => {
        if (!isActive) return
        setIsConnected(false)
        // Auto-reconnect after a transient drop (backend --reload, network blip)
        // with capped exponential backoff, so the feed self-heals without a
        // manual tab switch.
        const delay = Math.min(1000 * 2 ** attempts, 5000)
        attempts += 1
        reconnectTimer = setTimeout(connect, delay)
      }
      ws.onmessage = (e) => {
        if (!isActive) return
        const frame = JSON.parse(e.data)
        if (frame.type === 'history') {
          setItems((prev) => applyHistory(prev, frame.events ?? []))
          setRemaining(frame.remaining ?? 0)
          return
        }
        if (frame.type === 'history_older') {
          setItems((prev) => applyOlderHistory(prev, frame.events ?? []))
          setRemaining(frame.remaining ?? 0)
          setLoadingOlder(false)
          return
        }
        const event: ActivityEvent = frame
        if (event.type === 'no_transcript') {
          setNoTranscript(true)
          return
        }
        setItems((prev) => mergeEvents(prev, event))
      }
    }

    connect()

    return () => {
      isActive = false
      if (reconnectTimer) clearTimeout(reconnectTimer)
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [sessionName, enabled])

  const loadOlder = useCallback(() => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    setLoadingOlder(true)
    ws.send(JSON.stringify({ type: 'more_history' }))
  }, [])

  return { items, isConnected, noTranscript, remaining, loadingOlder, loadOlder }
}
