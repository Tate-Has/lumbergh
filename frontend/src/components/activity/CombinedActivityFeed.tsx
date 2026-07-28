import { useMemo, useState, useCallback } from 'react'
import { useCombinedActivitySocket } from '../../hooks/useCombinedActivitySocket'
import { ActivityCard } from './ActivityCards'
import { pairToolEvents, type PairedActivityItem } from './pairToolEvents'
import SessionTag from './SessionTag'
import ActivityRespondBox from './ActivityRespondBox'
import StatusDot from '../ui/StatusDot'

/** Connection-state → StatusDot state + label, matching the app's existing
 *  running/idle dot conventions (see components/ui/StatusDot.tsx). */
const CONNECTION_DISPLAY: Record<
  ReturnType<typeof useCombinedActivitySocket>['connectionState'],
  { state: 'connected' | 'idle' | 'disconnected'; label: string; pulse: boolean }
> = {
  open: { state: 'connected', label: 'Live', pulse: true },
  connecting: { state: 'idle', label: 'Connecting…', pulse: true },
  reconnecting: { state: 'idle', label: 'Reconnecting…', pulse: true },
  closed: { state: 'disconnected', label: 'Disconnected', pulse: false },
}

export default function CombinedActivityFeed() {
  const { items, connectionState } = useCombinedActivitySocket()
  const [hiddenSessions, setHiddenSessions] = useState<Set<string>>(new Set())
  const [expandedKey, setExpandedKey] = useState<string | null>(null)

  const toggleSession = useCallback((session: string) => {
    setHiddenSessions((prev) => {
      const next = new Set(prev)
      if (next.has(session)) next.delete(session)
      else next.add(session)
      return next
    })
  }, [])

  // Merge tool_call/tool_result pairs before anything else derives session
  // lists or ordering from the item stream — pairing is a rendering concern
  // layered on top of the hook's flat, unpaired item list (see
  // pairToolEvents.ts), so every downstream memo below works off this.
  const pairedItems = useMemo(() => pairToolEvents(items), [items])

  // All sessions seen so far, most-recently-active first (for the filter row).
  const allSessions = useMemo(() => {
    const seen = new Set<string>()
    const ordered: string[] = []
    for (let i = pairedItems.length - 1; i >= 0; i--) {
      if (!seen.has(pairedItems[i].session)) {
        seen.add(pairedItems[i].session)
        ordered.push(pairedItems[i].session)
      }
    }
    return ordered
  }, [pairedItems])

  // Thinking is ephemeral: keep it only while it's the latest event for its
  // own session (the agent is still thinking) — mirrors upstream's
  // single-session ActivityFeed, adapted per-session for the interleaved feed.
  const lastIndexBySession = useMemo(() => {
    const map: Record<string, number> = {}
    pairedItems.forEach((item, i) => {
      map[item.session] = i
    })
    return map
  }, [pairedItems])

  const visibleItems = useMemo(() => {
    const filtered = pairedItems.filter(
      (item, i) =>
        !hiddenSessions.has(item.session) &&
        (item.type !== 'thinking' || lastIndexBySession[item.session] === i)
    )
    // Newest-first for display; the hook hands us oldest-first.
    return filtered.slice().reverse()
  }, [pairedItems, hiddenSessions, lastIndexBySession])

  const conn = CONNECTION_DISPLAY[connectionState]

  return (
    <div className="flex h-full flex-col gap-3 overflow-hidden">
      <div className="flex shrink-0 items-center gap-2 px-1">
        <StatusDot state={conn.state} pulse={conn.pulse} />
        <span className="text-xs font-medium text-text-secondary">{conn.label}</span>
      </div>

      {allSessions.length > 0 && (
        <div className="flex shrink-0 gap-1.5 overflow-x-auto pb-1 [-webkit-overflow-scrolling:touch]">
          {allSessions.map((session) => (
            <SessionTag
              key={session}
              session={session}
              active={!hiddenSessions.has(session)}
              onToggle={toggleSession}
            />
          ))}
        </div>
      )}

      <div className="flex-1 space-y-2 overflow-y-auto overscroll-contain pb-4">
        {visibleItems.length === 0 && (
          <div className="flex h-full items-center justify-center p-4 text-center text-sm text-text-tertiary">
            No activity yet — activity from your running sessions will appear here.
          </div>
        )}
        {visibleItems.map((item) => (
          <FeedCard
            key={item.key}
            item={item}
            expanded={expandedKey === item.key}
            onToggleExpand={() => setExpandedKey((prev) => (prev === item.key ? null : item.key))}
            hidden={hiddenSessions.has(item.session)}
            onToggleSessionFilter={toggleSession}
          />
        ))}
      </div>
    </div>
  )
}

function FeedCard({
  item,
  expanded,
  onToggleExpand,
  hidden,
  onToggleSessionFilter,
}: {
  item: PairedActivityItem
  expanded: boolean
  onToggleExpand: () => void
  hidden: boolean
  onToggleSessionFilter: (session: string) => void
}) {
  const tag = (
    <SessionTag
      session={item.session}
      active={!hidden}
      onToggle={onToggleSessionFilter}
      className="ml-auto"
    />
  )

  return (
    <div>
      <div onClick={onToggleExpand} className="cursor-pointer">
        <ActivityCard item={item} sessionTag={tag} />
      </div>
      {expanded && (
        // Own click-stop layer: without it, clicking the textarea or Send
        // button bubbles up to the sibling's onToggleExpand above and
        // collapses (unmounts) this box in the same click that fires send().
        <div onClick={(e) => e.stopPropagation()}>
          <ActivityRespondBox sessionName={item.session} />
        </div>
      )}
    </div>
  )
}
