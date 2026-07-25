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
    // Reset state when session changes; synchronous setState here avoids stale data
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItems([])
    setNoTranscript(false)
    let isActive = true
    const url = `${getWsBase()}/session/${encodeURIComponent(sessionName)}/activity`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      if (!isActive) return
      setIsConnected(true)
    }
    ws.onclose = () => {
      if (!isActive) return
      setIsConnected(false)
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

    return () => {
      isActive = false
      wsRef.current = null
      ws.close()
    }
  }, [sessionName])

  return { items, isConnected, noTranscript }
}
