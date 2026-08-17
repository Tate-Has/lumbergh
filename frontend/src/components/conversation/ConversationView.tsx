import { useCallback, useEffect, useRef, useState } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useConversationSocket } from '../../hooks/useConversationSocket'
import ConversationRespondBox from './ConversationRespondBox'
import { Item } from './ConversationItem'

export default function ConversationView({
  sessionName,
  enabled = true,
  scale = 1,
}: {
  sessionName: string
  enabled?: boolean
  scale?: number
}) {
  const { items, noTranscript } = useConversationSocket({ sessionName, enabled })
  const scrollRef = useRef<HTMLDivElement>(null)
  const [following, setFollowing] = useState(true)
  const followingRef = useRef(true)
  // A scroll event only means "the user scrolled away" when a real gesture
  // caused it AND it moved the feed upward. Virtualized rows re-measure
  // constantly, and both our own stick-to-bottom and the virtualizer's scroll
  // adjustments fire scroll events whose position momentarily sits short of the
  // bottom — reading those as user intent detaches follow permanently and
  // strands the feed at the top. A gesture near one of those (a click on a tool
  // card's expand toggle, whose scroll-anchoring shift arrives inside the
  // gesture window) is exactly the same misread, which is why direction, not
  // the gesture alone, decides.
  const gestureAtRef = useRef(0)
  const draggingRef = useRef(false)
  const lastScrollTopRef = useRef(0)

  useEffect(() => {
    followingRef.current = following
  }, [following])

  // Thinking is ephemeral: keep it only while it's the latest event (the agent is
  // still thinking). Once any real output follows, it drops out of the history.
  const visibleItems = items.filter((item, i) => item.type !== 'thinking' || i === items.length - 1)

  // TanStack Virtual returns functions React Compiler can't memoize; skipping
  // memoization here is safe (and the compiler's own advice).
  // eslint-disable-next-line react-hooks/incompatible-library
  const virtualizer = useVirtualizer({
    count: visibleItems.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => 80,
    overscan: 8,
    // Key sizes by item, not index: the trailing `thinking` item drops out of
    // visibleItems, and an index-keyed cache would hand its height to whatever
    // row slides into its place.
    getItemKey: (index) => visibleItems[index].id,
  })

  // The spacer height and every row's `start` come out of the same measurements
  // array, so the scroller's own bottom is exactly the last row's rendered
  // bottom — internally consistent, whatever the unmeasured rows above are
  // currently estimated at. scrollToIndex instead aims at the estimated size of
  // a row it has not rendered yet, and lands short.
  const scrollToLatest = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
    lastScrollTopRef.current = el.scrollTop
  }, [])

  // Stay pinned to the bottom while following. A single scroll-to-bottom fires
  // before rows have measured and before late layout (markdown, fonts, images)
  // finishes growing them, stranding the view mid-feed; re-running whenever the
  // measured total height changes keeps it at the latest through settle, zoom
  // changes, card expansion and new events alike.
  const totalSize = virtualizer.getTotalSize()
  useEffect(() => {
    if (!followingRef.current) return
    scrollToLatest()
  }, [totalSize, scrollToLatest])

  // The viewport itself can shrink without the feed growing — a zoom step
  // resizes the respond box and header around it — which pushes the last row
  // out of sight while firing neither a scroll event nor a total-size change.
  // This observes the scroll container only; rows are TanStack's to observe.
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const observer = new ResizeObserver(() => {
      if (followingRef.current) scrollToLatest()
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [scrollToLatest])

  const markGesture = () => {
    gestureAtRef.current = Date.now()
  }

  // A touch pan that takes scrolling over from the drag fires pointercancel,
  // never pointerup, so every end-of-drag event has to clear the latch — one
  // missed release would leave every later scroll looking user-driven forever.
  const onPointerDown = () => {
    draggingRef.current = true
    markGesture()
    const release = () => {
      draggingRef.current = false
      markGesture()
      for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) {
        window.removeEventListener(event, release)
      }
    }
    for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) {
      window.addEventListener(event, release)
    }
  }

  const onScroll = () => {
    const el = scrollRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    const atBottom = distanceFromBottom < 40
    const userDriven = draggingRef.current || Date.now() - gestureAtRef.current < 400
    const movedUp = el.scrollTop < lastScrollTopRef.current
    lastScrollTopRef.current = el.scrollTop
    if (userDriven) {
      // Never fight an upward scroll — and never mistake anything else for one.
      // Only an upward move ends follow; landing at the bottom restores it.
      // Expanding a card adds height above the viewport, and scroll anchoring
      // pushes scrollTop *down* to compensate: a downward (or zero-delta) scroll
      // inside the gesture window is layout, not intent, and leaves follow alone
      // until the totalSize effect re-pins.
      if (atBottom || movedUp) {
        followingRef.current = atBottom
        setFollowing(atBottom)
      }
      return
    }
    // Backstop for every way of scrolling we cannot detect — keyboard aimed at
    // the document, a Firefox scrollbar drag, find-in-page. Half a viewport, not
    // a whole one: PageUp deliberately keeps a strip of overlap for context and
    // moves only ~0.9 of the viewport, so a full-viewport threshold would miss
    // the very case this exists for. Settle corrections all fire at a distance
    // near zero, well clear of half a viewport.
    if (followingRef.current && distanceFromBottom >= Math.max(150, el.clientHeight / 2)) {
      followingRef.current = false
      setFollowing(false)
      return
    }
    // Otherwise this is layout settling under us. Re-stick unless the feed is
    // drifting upward on its own (touch momentum after a flick), which would
    // fight the user.
    if (followingRef.current && !atBottom && !movedUp) scrollToLatest()
  }

  if (noTranscript) {
    return (
      <div
        data-testid="conversation-view"
        className="flex h-full items-center justify-center p-4 text-center text-sm text-text-tertiary"
        style={{ zoom: scale }}
      >
        No transcript found for this session yet. Start interacting in the terminal.
      </div>
    )
  }

  return (
    <div
      data-testid="conversation-view"
      className="relative flex h-full flex-col"
      style={{ zoom: scale }}
    >
      <div
        ref={scrollRef}
        onScroll={onScroll}
        onWheel={markGesture}
        onTouchMove={markGesture}
        onKeyDown={markGesture}
        onPointerDown={onPointerDown}
        className="flex-1 overflow-y-auto overscroll-contain"
      >
        <div style={{ height: totalSize, position: 'relative' }}>
          {virtualizer.getVirtualItems().map((row) => (
            <div
              key={visibleItems[row.index].id}
              data-index={row.index}
              ref={virtualizer.measureElement}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                transform: `translateY(${row.start}px)`,
              }}
              className="px-3 py-1.5"
            >
              <Item item={visibleItems[row.index]} />
            </div>
          ))}
        </div>
      </div>
      {!following && (
        <button
          onClick={() => {
            followingRef.current = true
            setFollowing(true)
            scrollToLatest()
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
