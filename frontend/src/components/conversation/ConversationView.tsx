import { useEffect, useRef, useState } from 'react'
import { useConversationSocket } from '../../hooks/useConversationSocket'
import ConversationRespondBox from './ConversationRespondBox'
import { Item } from './ConversationItem'

export default function ConversationView({
  sessionName,
  enabled = true,
}: {
  sessionName: string
  enabled?: boolean
}) {
  const { items, noTranscript } = useConversationSocket({ sessionName, enabled })
  const scrollRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const [following, setFollowing] = useState(true)
  const followingRef = useRef(true)
  // True while we are programmatically scrolling, so the scroll event our own
  // stick() fires doesn't get mistaken for the user scrolling away.
  const programmaticRef = useRef(false)

  useEffect(() => {
    followingRef.current = following
  }, [following])

  // Thinking is ephemeral: keep it only while it's the latest event (the agent is
  // still thinking). Once any real output follows, it drops out of the history.
  const visibleItems = items.filter((item, i) => item.type !== 'thinking' || i === items.length - 1)

  // Stay pinned to the bottom while following. A single scroll-to-bottom fires
  // before late layout (markdown, fonts, images, flex sizing) finishes growing
  // the content, stranding the view mid-feed; re-sticking on every content
  // resize keeps it at the latest through settle and new events alike.
  useEffect(() => {
    const scroller = scrollRef.current
    const content = contentRef.current
    if (!scroller || !content) return
    const stick = () => {
      if (!followingRef.current) return
      programmaticRef.current = true
      scroller.scrollTop = scroller.scrollHeight
      requestAnimationFrame(() => {
        programmaticRef.current = false
      })
    }
    stick()
    const observer = new ResizeObserver(stick)
    observer.observe(content)
    return () => observer.disconnect()
  }, [])

  const onScroll = () => {
    if (programmaticRef.current) return
    const el = scrollRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
    followingRef.current = atBottom
    setFollowing(atBottom)
  }

  if (noTranscript) {
    return (
      <div
        data-testid="conversation-view"
        className="flex h-full items-center justify-center p-4 text-center text-sm text-text-tertiary"
      >
        No transcript found for this session yet. Start interacting in the terminal.
      </div>
    )
  }

  return (
    <div data-testid="conversation-view" className="relative flex h-full flex-col">
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="flex-1 overflow-y-auto overscroll-contain"
      >
        <div ref={contentRef} className="space-y-3 p-3">
          {visibleItems.map((item) => (
            <Item key={item.id} item={item} />
          ))}
        </div>
      </div>
      {!following && (
        <button
          onClick={() => {
            followingRef.current = true
            setFollowing(true)
            const el = scrollRef.current
            if (el) el.scrollTop = el.scrollHeight
          }}
          className="absolute bottom-16 left-1/2 -translate-x-1/2 rounded-full bg-action px-3 py-1 text-xs text-white shadow"
        >
          Jump to latest ↓
        </button>
      )}
      <ConversationRespondBox sessionName={sessionName} />
    </div>
  )
}
