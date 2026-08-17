import { useEffect, useRef, useState } from 'react'
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
    return prev.map((item) =>
      item.type === 'tool_call' && item.tool_use_id === incoming.tool_use_id
        ? { ...item, result: { status: incoming.status, text: incoming.text } }
        : item
    )
  }
  return [...prev, incoming as RenderItem]
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
        const event: ActivityEvent = JSON.parse(e.data)
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

  return { items, isConnected, noTranscript }
}
