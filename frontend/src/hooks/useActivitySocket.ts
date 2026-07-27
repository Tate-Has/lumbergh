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

export function useActivitySocket({ sessionName }: { sessionName: string }) {
  const [items, setItems] = useState<RenderItem[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [noTranscript, setNoTranscript] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
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
  }, [sessionName])

  return { items, isConnected, noTranscript }
}
